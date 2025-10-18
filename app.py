import os
import re
import requests
from urllib.parse import urlencode
from flask import (
    Flask, request, jsonify, redirect, session, send_from_directory
)

# -----------------------------------------------------------------------------
# Environment / Config
# -----------------------------------------------------------------------------
GRAPH_VERSION   = os.getenv("GRAPH_VERSION", "v24.0")
GRAPH           = f"https://graph.facebook.com/{GRAPH_VERSION}"

FB_APP_ID       = os.getenv("FB_APP_ID")
FB_APP_SECRET   = os.getenv("FB_APP_SECRET")
SITE_URL        = os.getenv("SITE_URL", "").rstrip("/")   # e.g. https://socialavatar.onrender.com
SESSION_SECRET  = os.getenv("SESSION_SECRET", "change-me")

REDIRECT_URI    = f"{SITE_URL}/auth/callback"
HTTP_TIMEOUT    = int(os.getenv("HTTP_TIMEOUT", "20"))

# 僅用到基礎查詢 IG 檔案/媒體
OAUTH_SCOPES = ["pages_show_list", "instagram_basic"]

# -----------------------------------------------------------------------------
# Flask setup（同域靜態前端）
# -----------------------------------------------------------------------------
app = Flask(__name__, static_folder="static", static_url_path="/")
app.secret_key = SESSION_SECRET
app.config.update(
    SESSION_COOKIE_SAMESITE="None",   # 跨站安全 cookie（雖然我們同域，但保險）
    SESSION_COOKIE_SECURE=True        # Render 走 HTTPS → True
)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def graph_get(path, params, timeout=HTTP_TIMEOUT):
    """簡化 GET 呼叫 Graph API。"""
    r = requests.get(f"{GRAPH}/{path.lstrip('/')}", params=params, timeout=timeout)
    ok = r.ok
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}
    return ok, data, r.status_code

def mbti_heuristic(profile, media_list):
    """極簡 Heuristic：用粉絲量、bio 關鍵字、圖片/影片比例，估一個 MBTI 與說明。"""
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
    reason = (
        f"粉絲量與內容表現顯示偏向{('外向' if E_or_I=='E' else '內向')}、"
        f"思維偏{('直覺' if N_or_S=='N' else '感覺')}、"
        f"傾向{('理性思考' if T_or_F=='T' else '情感交流')}，"
        f"貼文風格較{('感知' if J_or_P=='P' else '判斷')}型。"
    )
    return mbti, reason

def require_bind():
    """確保使用者已完成綁定流程（session 內要有 page_token / ig_user_id）。"""
    bind = session.get("bind")
    if not bind:
        raise RuntimeError("not bound")
    return bind

# -----------------------------------------------------------------------------
# Root（強制重新登入）
# -----------------------------------------------------------------------------
@app.get("/")
def home():
    session.pop("bind", None)          # 清掉任何舊 session
    return redirect("/auth/login")     # 直接走登入

# 提供結果頁（卡片 UI）
@app.get("/result")
def serve_result():
    return send_from_directory("static", "index.html")

# -----------------------------------------------------------------------------
# OAuth Flow
# -----------------------------------------------------------------------------
@app.get("/auth/login")
def auth_login():
    if not FB_APP_ID or not FB_APP_SECRET or not SITE_URL:
        return jsonify({"error": "missing env vars FB_APP_ID/FB_APP_SECRET/SITE_URL"}), 500
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

    # 3) 找有連 IG 的 Page，取 page_token + ig_user_id
    ok, pages, _ = graph_get("me/accounts", {"access_token": long_user_token})
    if not ok:
        return jsonify({"error": pages}), 400

    chosen = None
    for p in pages.get("data", []):
        pid, ptoken = p["id"], p["access_token"]
        ok, info, _ = graph_get(pid, {
            "fields": "connected_instagram_account{id,username}",
            "access_token": ptoken,
        })
        if ok and info.get("connected_instagram_account"):
            ig = info["connected_instagram_account"]
            chosen = {
                "page_id": pid,
                "page_token": ptoken,
                "ig_user_id": ig["id"],
                "ig_username": ig.get("username"),
            }
            break

    if not chosen:
        return "No connected Instagram account found", 400

    session["bind"] = chosen
    return redirect("/result")  # 登入完成 → 前端卡片頁

# -----------------------------------------------------------------------------
# 分析 API（前端 /result 會呼叫）
# -----------------------------------------------------------------------------
@app.get("/analyze")
def analyze():
    try:
        b = require_bind()

        # 基本檔案
        ok, prof, _ = graph_get(b["ig_user_id"], {
            "fields": "id,username,name,biography,followers_count,media_count,follows_count,profile_picture_url",
            "access_token": b["page_token"],
        })
        if not ok:
            return jsonify({"error": "profile_fetch_failed", "detail": prof}), 400

        # 最近 30 則貼文（含縮圖）
        ok, media, _ = graph_get(f"{b['ig_user_id']}/media", {
            "fields": "id,media_type,caption,media_url,thumbnail_url,permalink,timestamp",
            "limit": 30, "access_token": b["page_token"],
        })
        if not ok:
            return jsonify({"error": "media_fetch_failed", "detail": media}), 400

        media_list = media.get("data", []) or []

        # 取前 12 張可用縮圖（IMAGE 用 media_url，其它用 thumbnail_url）
        thumbs = []
        for m in media_list:
            url = m.get("thumbnail_url") or (m.get("media_url") if m.get("media_type") == "IMAGE" else None)
            if url:
                thumbs.append(url)
            if len(thumbs) >= 12:
                break

        # Heuristic 推估 MBTI + 說明（之後你可換成 OpenAI 版本）
        mbti, reason = mbti_heuristic(prof, media_list)

        out = {
            "ig_account": prof.get("username") or b.get("ig_username"),
            "profile_name": prof.get("name") or (prof.get("username") or ""),
            "mbti": mbti,
            "reason": reason,
            "thumbnails": thumbs,
            "stats": {
                "followers": int(prof.get("followers_count") or 0),
                "follows": int(prof.get("follows_count") or 0),
                "media_count": int(prof.get("media_count") or 0),
            },
        }
        return jsonify(out)
    except RuntimeError:
        return jsonify({"error": "not bound"}), 401
    except Exception as e:
        return jsonify({"error": "server_error", "detail": str(e)}), 500

# -----------------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------------
@app.get("/health")
def health():
    return jsonify({"status": "ok", "redirect_uri": REDIRECT_URI})

# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
