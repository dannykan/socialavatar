import os
import re
import json
import time
import logging
import requests
from urllib.parse import urlencode
from flask import Flask, request, jsonify, redirect, session, send_from_directory
from flask_cors import CORS

# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v24.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"

FB_APP_ID = os.getenv("FB_APP_ID")
FB_APP_SECRET = os.getenv("FB_APP_SECRET")
SITE_URL = os.getenv("SITE_URL", "https://socialavatar.onrender.com").rstrip("/")
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "https://socialavatar.vercel.app").rstrip("/")

REDIRECT_URI = f"{SITE_URL}/auth/callback"
OAUTH_SCOPES = ["pages_show_list", "instagram_basic"]
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "20"))

# -----------------------------------------------------------------------------
# APP INIT
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = SESSION_SECRET
CORS(app, supports_credentials=True, origins=[FRONTEND_ORIGIN])
app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True,
)
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def graph_get(path, params, timeout=HTTP_TIMEOUT):
    r = requests.get(f"{GRAPH}/{path.lstrip('/')}", params=params, timeout=timeout)
    ok = r.ok
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}
    return ok, data, r.status_code

def mbti_heuristic(profile, media_list):
    bio = (profile.get("biography") or "").lower()
    name = (profile.get("name") or "")
    followers = int(profile.get("followers_count") or 0)
    imgs = sum(1 for m in media_list if (m.get("media_type") == "IMAGE"))
    vids = sum(1 for m in media_list if (m.get("media_type") in ("VIDEO", "REEL", "CLIP")))

    score_E = 1 if followers > 5000 else 0
    if any(k in bio for k in ["travel", "music", "basketball"]) or "🏀" in name:
        score_E += 1
    score_N = 1 if any(k in bio for k in ["research", "design", "創作"]) else 0
    score_T = 1 if any(k in bio for k in ["engineer", "分析", "data"]) else 0
    score_P = 1 if vids > imgs else 0

    E_or_I = "E" if score_E >= 1 else "I"
    N_or_S = "N" if score_N >= 1 else "S"
    T_or_F = "T" if score_T >= 1 else "F"
    J_or_P = "P" if score_P >= 1 else "J"

    mbti = f"{E_or_I}{N_or_S}{T_or_F}{J_or_P}"
    reason = f"粉絲量與內容顯示偏向{'外向' if E_or_I=='E' else '內向'}、思維偏{'感覺' if N_or_S=='S' else '直覺'}、" \
             f"傾向{'情感交流' if T_or_F=='F' else '理性分析'}，貼文風格偏{'感知' if J_or_P=='P' else '判斷'}型。"
    return mbti, reason[:100]

def require_bind():
    bind = session.get("bind")
    if not bind:
        raise RuntimeError("not bound")
    return bind

# -----------------------------------------------------------------------------
# ROUTES
# -----------------------------------------------------------------------------
@app.get("/auth/login")
def auth_login():
    params = {
        "client_id": FB_APP_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": ",".join(OAUTH_SCOPES),
    }
    return redirect(f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth?{urlencode(params)}")

@app.get("/auth/callback")
def auth_callback():
    try:
        code = request.args.get("code")
        if not code:
            return "Missing code", 400

        ok, data, _ = graph_get("oauth/access_token", {
            "client_id": FB_APP_ID,
            "client_secret": FB_APP_SECRET,
            "redirect_uri": REDIRECT_URI,
            "code": code,
        })
        if not ok:
            return jsonify({"step": "code_to_token", "error": data}), 400
        short_token = data["access_token"]

        ok, data, _ = graph_get("oauth/access_token", {
            "grant_type": "fb_exchange_token",
            "client_id": FB_APP_ID,
            "client_secret": FB_APP_SECRET,
            "fb_exchange_token": short_token,
        })
        if not ok:
            return jsonify({"step": "exchange_long", "error": data}), 400

        long_user_token = data["access_token"]
        expires_in = int(data.get("expires_in") or 0)

        ok, pages, _ = graph_get("me/accounts", {"access_token": long_user_token})
        if not ok:
            return jsonify({"step": "me_accounts", "error": pages}), 400

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
                    "page_name": p.get("name"),
                    "page_token": ptoken,
                    "ig_user_id": ig["id"],
                    "ig_username": ig.get("username"),
                    "long_user_expires_at": int(time.time()) + expires_in
                }
                break

        if not chosen:
            return "No connected IG account found", 400

        session["bind"] = chosen
        app.logger.info("✅ Session bound for user %s", chosen.get("ig_username"))
        return redirect(f"{FRONTEND_ORIGIN}/result")

    except Exception as e:
        app.logger.exception("[auth_callback] Error")
        return jsonify({"error": str(e)}), 500

@app.get("/auth/status")
def auth_status():
    b = session.get("bind")
    if not b:
        return jsonify({"status": "not bound"})
    return jsonify({
        "status": "bound",
        "page_id": b["page_id"],
        "ig_user_id": b["ig_user_id"],
        "ig_username": b.get("ig_username"),
        "long_user_expires_at": b.get("long_user_expires_at")
    })

@app.post("/me/ig/analyze")
def me_ig_analyze():
    try:
        b = require_bind()
        ok, prof, _ = graph_get(
            b["ig_user_id"],
            {"fields": "id,username,name,biography,followers_count,media_count,follows_count", "access_token": b["page_token"]}
        )
        ok, media, _ = graph_get(
            f"{b['ig_user_id']}/media",
            {"fields": "id,media_type,caption", "limit": 30, "access_token": b["page_token"]}
        )
        mbti, reason = mbti_heuristic(prof, media.get("data", []))
        return jsonify({"ok": True, "ig_account": prof["username"], "profile_name": prof["name"], "mbti": mbti, "reason": reason})
    except RuntimeError:
        return jsonify({"ok": False, "error": "not bound"}), 401
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/debug/session")
def debug_session():
    b = session.get("bind")
    if not b:
        return jsonify({"ok": False, "detail": "not bound"})
    masked = {k: v for k, v in b.items() if k != "page_token"}
    masked["has_page_token"] = bool(b.get("page_token"))
    return jsonify({"ok": True, "bind": masked})

@app.get("/health")
def health():
    return jsonify({"status": "ok", "redirect_uri": REDIRECT_URI})

# Serve index.html from /static
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
