# app.py
import os
import re
import time
from urllib.parse import urlencode

import requests
from flask import (
    Flask,
    request,
    jsonify,
    redirect,
    session,
    send_from_directory,
)

from flask_cors import CORS

# ------------------------------
# Config & constants
# ------------------------------
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v24.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"

FB_APP_ID = os.getenv("FB_APP_ID", "").strip()
FB_APP_SECRET = os.getenv("FB_APP_SECRET", "").strip()

SITE_URL = os.getenv("SITE_URL", "").rstrip("/")            # 例: https://socialavatar.onrender.com
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "").rstrip("/")  # 例: https://socialavatar.vercel.app
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me").strip()

if not SITE_URL:
    raise RuntimeError("SITE_URL is required (e.g. https://socialavatar.onrender.com)")

REDIRECT_URI = f"{SITE_URL}/auth/callback"
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "20"))

OAUTH_SCOPES = [
    "pages_show_list",
    "instagram_basic",
    # 視需求再加:
    # "pages_read_engagement",
    # "instagram_manage_insights",
    # "business_management",
]

# OpenAI (optional, for 100字摘要)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
try:
    from openai import OpenAI
    _oai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
except Exception:
    _oai_client = None


# ------------------------------
# Flask
# ------------------------------
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = SESSION_SECRET

# 跨站 cookie 設定，供前端跨網域呼叫時保留 session
app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True,  # Render 是 HTTPS，務必 True 才能跨站送 cookie
)

# 嚴格 CORS：只允許你的前端網域（或同網域）
allowed_origins = [FRONTEND_ORIGIN] if FRONTEND_ORIGIN else [SITE_URL]
CORS(
    app,
    resources={r"/*": {"origins": allowed_origins}},
    supports_credentials=True,
)


# ------------------------------
# Helpers
# ------------------------------
def graph_get(path, params, timeout=HTTP_TIMEOUT):
    """GET Graph API，回 (ok, json, status_code)"""
    r = requests.get(f"{GRAPH}/{path.lstrip('/')}", params=params, timeout=timeout)
    ok = r.ok
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}
    return ok, data, r.status_code


def sanitize_username(u: str) -> str:
    if not isinstance(u, str):
        return ""
    u = u.strip().lstrip("@")
    return re.sub(r"[^A-Za-z0-9._]", "", u)


def _clip_chars(s: str, limit: int = 100) -> str:
    """安全以字元數截斷，避免超過限制。"""
    if not isinstance(s, str):
        return ""
    return s[:limit]


def mbti_heuristic(profile: dict, media_list: list) -> tuple[str, str]:
    """
    非正式/示範用：非常簡單的 Heuristic，
    依簡歷與貼文主題給一個 MBTI + 理由（短版）。
    """
    bio = (profile.get("biography") or "").lower()
    name = (profile.get("name") or "")
    followers = int(profile.get("followers_count") or 0)

    imgs = sum(1 for m in (media_list or []) if (m.get("media_type") == "IMAGE"))
    vids = sum(1 for m in (media_list or []) if (m.get("media_type") in ("VIDEO", "REEL", "CLIP")))

    score_E = 1 if followers > 5000 else 0
    if any(k in bio for k in ["travel", "music", "football", "basketball"]) or "🏀" in name:
        score_E += 1
    score_N = 1 if any(k in bio for k in ["research", "design", "創作"]) else 0
    score_T = 1 if any(k in bio for k in ["engineer", "分析", "data"]) else 0
    score_P = 1 if vids > imgs else 0

    E_or_I = "E" if score_E >= 1 else "I"
    N_or_S = "N" if score_N >= 1 else "S"
    T_or_F = "T" if score_T >= 1 else "F"
    J_or_P = "P" if score_P >= 1 else "J"

    mbti = f"{E_or_I}{N_or_S}{T_or_F}{J_or_P}"
    reason = []
    reason.append("粉絲量顯示" + ("外向" if E_or_I == "E" else "內向"))
    reason.append("簡介字詞偏" + ("直覺" if N_or_S == "N" else "感覺"))
    reason.append("專業傾向" + ("思考" if T_or_F == "T" else "情感"))
    reason.append("貼文型態偏" + ("感知" if J_or_P == "P" else "判斷"))
    short = "；".join(reason)
    return mbti, _clip_chars(short, 100)


def summarize_with_openai(profile: dict, media_list: list, mbti: str) -> str:
    """
    用 OpenAI 產生 100 字以內的中文摘要；若失敗拋出例外，呼叫端會 fallback。
    """
    if not _oai_client:
        raise RuntimeError("OPENAI_API_KEY not set")

    caps = []
    for m in (media_list or [])[:10]:
        cap = (m.get("caption") or "").strip()
        if cap:
            caps.append(_clip_chars(cap, 80))
    caps_txt = "\n- " + "\n- ".join(caps) if caps else "（無最近貼文文字）"

    prompt = f"""
你是一位社群觀察員。請用自然、口語、正向、輕鬆的中文，
根據使用者的 IG 基本資料與貼文線索，解釋為何他/她傾向 MBTI 類型「{mbti}」。
限制：最長 100 字、不要使用條列、不要出現「因為/所以/因此」等生硬辭。
避免空泛形容，盡量結合粉絲數、貼文型態、BIO 關鍵字、整體調性。

【基本資料】
- 帳號：@{profile.get('username') or ''}
- 名稱：{profile.get('name') or ''}
- 粉絲：{profile.get('followers_count') or 0}
- 追蹤：{profile.get('follows_count') or 0}
- 貼文：{profile.get('media_count') or 0}
- BIO：{profile.get('biography') or '（無）'}

【最近貼文文字線索】
{caps_txt}
""".strip()

    resp = _oai_client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.7,
        max_tokens=220,
        messages=[
            {"role": "system", "content": "你是擅長社群洞察與風格判讀的中文寫手，語氣自然友善、簡潔。"},
            {"role": "user", "content": prompt},
        ],
    )
    text = (resp.choices[0].message.content or "").strip()
    return _clip_chars(text, 100)


def require_bind():
    b = session.get("bind")
    if not b:
        raise RuntimeError("not bound")
    return b


# ------------------------------
# Static pages
# ------------------------------
@app.get("/")
def root():
    # 讓 / 直接導向 /result (單頁前端)，也可改成 send_from_directory 你的首頁
    return redirect("/result", code=302)


@app.get("/result")
def result_page():
    # 提供前端結果頁（就在 /static/index.html）
    return send_from_directory(app.static_folder, "index.html")


# ------------------------------
# OAuth flow
# ------------------------------
@app.get("/auth/login")
def auth_login():
    if not FB_APP_ID or not FB_APP_SECRET:
        return jsonify({"error": "FB_APP_ID / FB_APP_SECRET not set"}), 500

    params = {
        "client_id": FB_APP_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": ",".join(OAUTH_SCOPES),
    }
    return redirect(f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth?{urlencode(params)}")


@app.get("/auth/callback")
def auth_callback():
    code = request.args.get("code")
    if not code:
        return "Missing code", 400

    # 1) code -> 短期 user token
    ok, data, _ = graph_get("oauth/access_token", {
        "client_id": FB_APP_ID,
        "client_secret": FB_APP_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    })
    if not ok:
        return jsonify({"error": data}), 400
    short_user_token = data["access_token"]

    # 2) 短期 -> 長期 user token
    ok, data, _ = graph_get("oauth/access_token", {
        "grant_type": "fb_exchange_token",
        "client_id": FB_APP_ID,
        "client_secret": FB_APP_SECRET,
        "fb_exchange_token": short_user_token,
    })
    if not ok:
        return jsonify({"error": data}), 400
    long_user_token = data["access_token"]
    expires_in = int(data.get("expires_in") or 0)

    # 3) 找有連 IG 的 Page，取 page_token + ig_user_id
    ok, pages, _ = graph_get("me/accounts", {"access_token": long_user_token})
    if not ok:
        return jsonify({"error": pages}), 400

    chosen = None
    for p in pages.get("data", []):
        pid, ptoken = p["id"], p["access_token"]
        ok, info, _ = graph_get(pid, {
            "fields": "connected_instagram_account{id,username},name",
            "access_token": ptoken,
        })
        if ok and info.get("connected_instagram_account"):
            ig = info["connected_instagram_account"]
            chosen = {
                "page_id": pid,
                "page_name": info.get("name"),
                "page_token": ptoken,
                "ig_user_id": ig["id"],
                "ig_username": ig.get("username"),
            }
            break

    if not chosen:
        return "No connected Instagram account found", 400

    session["bind"] = {
        **chosen,
        "long_user_expires_at": (int(time.time()) + expires_in) if expires_in else None,
    }

    # 登入完成 → 前端結果頁
    return redirect("/result")


@app.get("/auth/status")
def auth_status():
    b = session.get("bind")
    if not b:
        return jsonify({"status": "not bound"}), 200
    masked = {k: v for k, v in b.items() if k != "page_token"}
    masked["has_page_token"] = bool(b.get("page_token"))
    return jsonify({"status": "bound", **masked}), 200


@app.post("/auth/logout")
def auth_logout():
    session.pop("bind", None)
    return jsonify({"ok": True})


# ------------------------------
# IG Graph endpoints (需要綁定)
# ------------------------------
@app.get("/me/ig/basic")
def me_ig_basic():
    try:
        b = require_bind()
    except RuntimeError:
        return jsonify({"error": "not bound"}), 401

    ok, data, status = graph_get(
        b["ig_user_id"],
        {
            "fields": "id,username,media_count,followers_count,follows_count,profile_picture_url,biography,name",
            "access_token": b["page_token"],
        },
    )
    return (jsonify(data), status)


@app.get("/me/ig/media")
def me_ig_media():
    try:
        b = require_bind()
    except RuntimeError:
        return jsonify({"error": "not bound"}), 401

    ok, data, status = graph_get(
        f"{b['ig_user_id']}/media",
        {
            "fields": "id,media_type,caption,permalink,media_url,thumbnail_url,timestamp",
            "limit": 30,
            "access_token": b["page_token"],
        },
    )
    return (jsonify(data), status)


@app.post("/me/ig/analyze")
def me_ig_analyze():
    """
    回應：
      ok: true/false
      ig_account, profile_name, mbti, reason
      如果失敗 -> ok:false, where:'哪步', detail:{...}
    """
    # 0) 必須先綁定
    try:
        b = require_bind()
    except RuntimeError:
        return jsonify({"ok": False, "where": "session", "detail": "not bound"}), 200

    # 1) 取基本資料
    ok, prof, _ = graph_get(
        b["ig_user_id"],
        {
            "fields": "id,username,name,biography,followers_count,media_count,follows_count,profile_picture_url",
            "access_token": b["page_token"],
        },
    )
    if not ok:
        return jsonify({"ok": False, "where": "profile_fetch", "detail": prof}), 200

    # 2) 取最近貼文
    ok, media, _ = graph_get(
        f"{b['ig_user_id']}/media",
        {
            "fields": "id,media_type,caption,media_url,thumbnail_url,permalink,timestamp",
            "limit": 30,
            "access_token": b["page_token"],
        },
    )
    if not ok:
        return jsonify({"ok": False, "where": "media_fetch", "detail": media}), 200

    media_list = media.get("data", []) or []

    # 3) Heuristic
    try:
        mbti, reason = mbti_heuristic(prof, media_list)
    except Exception as e:
        return jsonify({"ok": False, "where": "heuristic", "detail": str(e)}), 200

    # 4) OpenAI 100字摘要（有 key 才使用，失敗就 fallback 不中斷）
    if _oai_client:
        try:
            ai_reason = summarize_with_openai(prof, media_list, mbti)
            if ai_reason:
                reason = ai_reason
        except Exception as e:
            print("[OpenAI failed]", e)

    out = {
        "ok": True,
        "ig_account": prof.get("username") or b.get("ig_username") or "",
        "profile_name": prof.get("name") or "",
        "mbti": mbti,
        "reason": _clip_chars(reason, 100),
    }
    return jsonify(out), 200


# ------------------------------
# Debug endpoints
# ------------------------------
@app.get("/me/ig/check")
def me_ig_check():
    """一次把 profile 與 media 的 raw 狀態回傳（方便偵錯）"""
    try:
        b = require_bind()
    except RuntimeError:
        return jsonify({"ok": False, "where": "session", "detail": "not bound"})
    out = {"ok": True, "page_id": b["page_id"], "ig_user_id": b["ig_user_id"]}

    ok, prof, _ = graph_get(
        b["ig_user_id"],
        {"fields": "id,username,name,followers_count,media_count", "access_token": b["page_token"]},
    )
    out["profile_ok"] = ok
    out["profile"] = prof

    ok, media, _ = graph_get(
        f"{b['ig_user_id']}/media",
        {"fields": "id,media_type,timestamp", "limit": 5, "access_token": b["page_token"]},
    )
    out["media_ok"] = ok
    out["media_count"] = len(media.get("data", [])) if isinstance(media, dict) else None
    if not ok:
        out["media_error"] = media
    return jsonify(out)


@app.get("/debug/session")
def debug_session():
    """檢視 session（遮蔽 page_token）"""
    b = session.get("bind")
    if not b:
        return jsonify({"ok": False, "detail": "not bound"})
    masked = {k: v for k, v in b.items() if k != "page_token"}
    masked["has_page_token"] = bool(b.get("page_token"))
    return jsonify({"ok": True, "bind": masked})


# ------------------------------
# Health
# ------------------------------
@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "redirect_uri": REDIRECT_URI,
        "frontend_allowed": allowed_origins,
        "site_url": SITE_URL
    })


# ------------------------------
# Entrypoint
# ------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
