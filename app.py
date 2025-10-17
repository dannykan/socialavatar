import os
import time
import re
import json
import requests
from urllib.parse import urlencode
from flask import Flask, request, jsonify, redirect, session
from flask_cors import CORS

# -----------------------------------------------------------------------------
# Environment / Config
# -----------------------------------------------------------------------------
GRAPH_VERSION   = os.getenv("GRAPH_VERSION", "v24.0")
GRAPH           = f"https://graph.facebook.com/{GRAPH_VERSION}"

FB_APP_ID       = os.getenv("FB_APP_ID")        # 必填
FB_APP_SECRET   = os.getenv("FB_APP_SECRET")    # 必填
SITE_URL        = os.getenv("SITE_URL", "").rstrip("/")  # 你的後端完整網址（例：https://socialavatar.onrender.com）
SESSION_SECRET  = os.getenv("SESSION_SECRET", "change-me")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "https://socialavatar.vercel.app").rstrip("/")

REDIRECT_URI    = f"{SITE_URL}/auth/callback"
HTTP_TIMEOUT    = int(os.getenv("HTTP_TIMEOUT", "20"))

OAUTH_SCOPES = [
    "pages_show_list",
    "instagram_basic",
    # 視需求再加：
    # "pages_read_engagement",
    # "instagram_manage_insights",
    # "business_management",
]

# -----------------------------------------------------------------------------
# Flask
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = SESSION_SECRET

# 跨站需要
app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True  # Render 是 HTTPS，務必 True
)

CORS(
    app,
    resources={r"/*": {"origins": [FRONTEND_ORIGIN]}},
    supports_credentials=True,
)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def graph_get(path, params, timeout=HTTP_TIMEOUT):
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

def mbti_heuristic(profile, media_list):
    """
    極簡 Demo：根據followers / bio關鍵字 / 圖片vs影片比，推一個 MBTI + 50字內說明
    """
    bio = (profile.get("biography") or "").lower()
    name = (profile.get("name") or "")
    followers = int(profile.get("followers_count") or 0)

    imgs = sum(1 for m in media_list if (m.get("media_type") == "IMAGE"))
    vids = sum(1 for m in media_list if (m.get("media_type") in ("VIDEO", "REEL", "CLIP")))

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
    if len(short) > 50:
        short = short[:50] + "…"
    return mbti, short

def require_bind():
    bind = session.get("bind")
    if not bind:
        raise RuntimeError("not bound")
    return bind

# -----------------------------------------------------------------------------
# Health / Debug
# -----------------------------------------------------------------------------
@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "frontend_allowed": FRONTEND_ORIGIN,
        "redirect_uri": REDIRECT_URI
    })

# -----------------------------------------------------------------------------
# OAuth Flow
# -----------------------------------------------------------------------------
@app.get("/auth/login")
def auth_login():
    if not FB_APP_ID or not FB_APP_SECRET or not SITE_URL:
        return jsonify({"error": "FB_APP_ID / FB_APP_SECRET / SITE_URL not set"}), 500

    params = {
        "client_id": FB_APP_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": ",".join(OAUTH_SCOPES),
        # "state": "csrf-token"
    }
    return redirect(f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth?{urlencode(params)}")

@app.get("/auth/callback")
def auth_callback():
    code = request.args.get("code")
    if not code:
        return "Missing code", 400

    # 1) code → 短期 user token
    ok, data, _ = graph_get(
        "oauth/access_token",
        {
            "client_id": FB_APP_ID,
            "client_secret": FB_APP_SECRET,
            "redirect_uri": REDIRECT_URI,
            "code": code,
        },
    )
    if not ok:
        return jsonify({"step": "code_to_short_token", "error": data}), 400
    short_user_token = data["access_token"]

    # 2) 短期 → 長期 user token
    ok, data, _ = graph_get(
        "oauth/access_token",
        {
            "grant_type": "fb_exchange_token",
            "client_id": FB_APP_ID,
            "client_secret": FB_APP_SECRET,
            "fb_exchange_token": short_user_token,
        },
    )
    if not ok:
        return jsonify({"step": "short_to_long_user_token", "error": data}), 400
    long_user_token = data["access_token"]
    expires_in = int(data.get("expires_in") or 0)

    # 3) 找 Pages
    ok, pages, _ = graph_get("me/accounts", {"access_token": long_user_token})
    if not ok:
        return jsonify({"step": "me_accounts", "error": pages}), 400

    chosen = None
    for p in pages.get("data", []):
        page_id = p["id"]
        page_token = p["access_token"]
        # 查頁面是否連 IG
        ok, info, _ = graph_get(
            page_id,
            {"fields": "connected_instagram_account{id,username}", "access_token": page_token},
        )
        if ok and info.get("connected_instagram_account", {}).get("id"):
            ig = info["connected_instagram_account"]
            chosen = {
                "page_id": page_id,
                "page_name": p.get("name"),
                "page_token": page_token,       # 後續 IG Graph 用此 Token
                "ig_user_id": ig["id"],
                "ig_username": ig.get("username"),
            }
            break

    if not chosen:
        return "No connected Instagram account on any managed Page.", 400

    session["bind"] = {
        "long_user_token": long_user_token,
        "long_user_expires_at": int(time.time()) + expires_in,
        **chosen,
    }

    # 綁定完成 → 回前端
    return redirect(f"{FRONTEND_ORIGIN}/?bind=success")

@app.get("/auth/status")
def auth_status():
    b = session.get("bind")
    if not b:
        return jsonify({"status": "not bound"})
    # 不回傳 token 給前端，只回可視資訊
    return jsonify({
        "status": "bound",
        "page_id": b["page_id"],
        "page_name": b.get("page_name"),
        "ig_user_id": b["ig_user_id"],
        "ig_username": b.get("ig_username"),
        "long_user_expires_at": b.get("long_user_expires_at"),
    })

@app.post("/auth/logout")
def auth_logout():
    session.pop("bind", None)
    return jsonify({"ok": True})

# -----------------------------------------------------------------------------
# IG Graph endpoints (需要綁定)
# -----------------------------------------------------------------------------
@app.get("/me/ig/basic")
def me_ig_basic():
    try:
        b = require_bind()
        ok, data, status = graph_get(
            b["ig_user_id"],
            {
                "fields": "id,username,media_count,followers_count,follows_count,profile_picture_url,biography,name",
                "access_token": b["page_token"],
            },
        )
        return (jsonify(data), status)
    except RuntimeError:
        return jsonify({"error": "not bound"}), 401

@app.get("/me/ig/media")
def me_ig_media():
    try:
        b = require_bind()
        ok, data, status = graph_get(
            f"{b['ig_user_id']}/media",
            {
                "fields": "id,media_type,caption,permalink,media_url,thumbnail_url,timestamp",
                "limit": 30,
                "access_token": b["page_token"],
            },
        )
        return (jsonify(data), status)
    except RuntimeError:
        return jsonify({"error": "not bound"}), 401

@app.post("/me/ig/analyze")
def me_ig_analyze():
    """
    回應前端需要的四個欄位：
    1. ig_account
    2. profile_name
    3. mbti
    4. reason (<= 50字)
    """
    try:
        b = require_bind()

        # 取基本資料
        ok, prof, _ = graph_get(
            b["ig_user_id"],
            {
                "fields": "id,username,name,biography,followers_count,media_count,follows_count,profile_picture_url",
                "access_token": b["page_token"],
            },
        )
        if not ok:
            return jsonify({"error": "profile_fetch_failed", "detail": prof}), 400

        # 取最近貼文
        ok, media, _ = graph_get(
            f"{b['ig_user_id']}/media",
            {
                "fields": "id,media_type,caption,media_url,thumbnail_url,permalink,timestamp",
                "limit": 30,
                "access_token": b["page_token"],
            },
        )
        if not ok:
            return jsonify({"error": "media_fetch_failed", "detail": media}), 400

        media_list = media.get("data", []) or []
        mbti, reason = mbti_heuristic(prof, media_list)

        out = {
            "ig_account": prof.get("username") or b.get("ig_username") or "",
            "profile_name": prof.get("name") or prof.get("username") or "",  # 加這個 fallback
            "mbti": mbti,
            "reason": reason,  # <= 50字
        }
        return jsonify(out)
    except RuntimeError:
        return jsonify({"error": "not bound"}), 401
    except Exception as e:
        return jsonify({"error": "server_error", "detail": str(e)}), 500

# -----------------------------------------------------------------------------
# Root
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    return jsonify({"message": "SocialAvatar API", "frontend": FRONTEND_ORIGIN})

# -----------------------------------------------------------------------------
# Local dev
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)

