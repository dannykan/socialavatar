import os
import time
import re
import json
import requests
from urllib.parse import urlencode
from flask import Flask, request, jsonify, redirect, session
from flask_cors import CORS
from openai import OpenAI

# -----------------------------------------------------------------------------
# Environment / Config
# -----------------------------------------------------------------------------
GRAPH_VERSION   = os.getenv("GRAPH_VERSION", "v24.0")
GRAPH           = f"https://graph.facebook.com/{GRAPH_VERSION}"

FB_APP_ID       = os.getenv("FB_APP_ID")
FB_APP_SECRET   = os.getenv("FB_APP_SECRET")
SITE_URL        = os.getenv("SITE_URL", "").rstrip("/")
SESSION_SECRET  = os.getenv("SESSION_SECRET", "change-me")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "https://socialavatar.vercel.app").rstrip("/")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")

REDIRECT_URI    = f"{SITE_URL}/auth/callback"
HTTP_TIMEOUT    = int(os.getenv("HTTP_TIMEOUT", "20"))

OAUTH_SCOPES = ["pages_show_list", "instagram_basic"]

# -----------------------------------------------------------------------------
# Flask
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = SESSION_SECRET
app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True
)
CORS(app, resources={r"/*": {"origins": [FRONTEND_ORIGIN]}}, supports_credentials=True)

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

def mbti_heuristic(profile, media_list):
    bio = (profile.get("biography") or "").lower()
    name = (profile.get("name") or "")
    followers = int(profile.get("followers_count") or 0)
    imgs = sum(1 for m in media_list if m.get("media_type") == "IMAGE")
    vids = sum(1 for m in media_list if m.get("media_type") in ("VIDEO", "REEL", "CLIP"))
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
    reason = f"粉絲量顯示{'外向' if E_or_I=='E' else '內向'}；" \
             f"簡介字詞偏{'直覺' if N_or_S=='N' else '感覺'}；" \
             f"專業傾向{'思考' if T_or_F=='T' else '情感'}；" \
             f"貼文型態偏{'感知' if J_or_P=='P' else '判斷'}。"
    return mbti, reason

def require_bind():
    bind = session.get("bind")
    if not bind:
        raise RuntimeError("not bound")
    return bind

# -----------------------------------------------------------------------------
# OAuth Flow
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
        return jsonify(data), 400
    short_token = data["access_token"]

    ok, data, _ = graph_get("oauth/access_token", {
        "grant_type": "fb_exchange_token",
        "client_id": FB_APP_ID,
        "client_secret": FB_APP_SECRET,
        "fb_exchange_token": short_token,
    })
    long_token = data["access_token"]
    ok, pages, _ = graph_get("me/accounts", {"access_token": long_token})
    chosen = None
    for p in pages.get("data", []):
        pid, ptoken = p["id"], p["access_token"]
        ok, info, _ = graph_get(pid, {
            "fields": "connected_instagram_account{id,username}",
            "access_token": ptoken,
        })
        if ok and info.get("connected_instagram_account", {}).get("id"):
            ig = info["connected_instagram_account"]
            chosen = {"page_id": pid, "page_token": ptoken, "ig_user_id": ig["id"], "ig_username": ig["username"]}
            break
    if not chosen:
        return "No connected Instagram account.", 400
    session["bind"] = chosen
    return redirect(f"{FRONTEND_ORIGIN}/?bind=success")

# -----------------------------------------------------------------------------
# IG Graph endpoints (主要分析)
# -----------------------------------------------------------------------------
@app.post("/me/ig/analyze")
def me_ig_analyze():
    try:
        b = require_bind()
        client = OpenAI(api_key=OPENAI_API_KEY)

        # 1️⃣ 抓 IG 基本資料
        ok, prof, _ = graph_get(b["ig_user_id"], {
            "fields": "id,username,name,biography,followers_count,media_count,follows_count,profile_picture_url",
            "access_token": b["page_token"],
        })
        if not ok:
            return jsonify(prof), 400

        # 2️⃣ 抓貼文縮圖
        ok, media, _ = graph_get(f"{b['ig_user_id']}/media", {
            "fields": "id,media_type,caption,media_url,thumbnail_url,timestamp",
            "limit": 30,
            "access_token": b["page_token"],
        })
        if not ok:
            return jsonify(media), 400
        media_list = media.get("data", []) or []

        username = prof.get("username")
        profile_name = prof.get("name")
        bio = prof.get("biography", "")
        followers = prof.get("followers_count", 0)
        follows = prof.get("follows_count", 0)
        media_count = prof.get("media_count", 0)
        mbti_guess, short_reason = mbti_heuristic(prof, media_list)

        # 取前 12 張縮圖（避免 token 超標）
        thumbs = []
        for m in media_list:
            url = m.get("thumbnail_url") or (m.get("media_url") if m.get("media_type") == "IMAGE" else None)
            if url:
                thumbs.append(url)
            if len(thumbs) >= 12:
                break

        # 3️⃣ 給 GPT 看整體印象
        system_prompt = (
            "你是一位 IG 人格分析師。"
            "請模擬第一次打開此帳號時的直覺，從頭像、貼文縮圖、自我介紹、粉絲/追蹤數的比例、"
            "整體氛圍判斷這個人屬於哪種 MBTI 類型，並以約 100 字自然、有畫面感的語氣說明原因。"
            "不要重複帳號資料。"
        )

        text_block = (
            f"帳號：@{username}\n"
            f"名稱：{profile_name}\n"
            f"粉絲：{followers}；追蹤：{follows}；貼文：{media_count}\n"
            f"自介：{bio or '（無）'}\n"
            f"起始推測 MBTI（可參考，不需採用）：{mbti_guess}（{short_reason}）"
        )

        messages = [{"role": "system", "content": system_prompt}]
        content = [{"type": "text", "text": text_block}]
        for url in thumbs:
            content.append({"type": "image_url", "image_url": {"url": url}})
        messages.append({"role": "user", "content": content})

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.9,
            max_tokens=220,
        )
        ai_text = resp.choices[0].message.content.strip()

        # 簡易解析：抓 MBTI & 說明
        mbti_final = mbti_guess
        reason_final = ai_text
        m = re.search(r"\b([IE][NS][TF][JP])\b", ai_text)
        if m:
            mbti_final = m.group(1).upper()
        if len(reason_final) > 140:
            reason_final = reason_final[:140] + "…"

        return jsonify({
            "ig_account": username,
            "profile_name": profile_name,
            "mbti": mbti_final,
            "reason": reason_final,
            "thumbnails": thumbs,
            "stats": {"followers": followers, "follows": follows, "media_count": media_count},
        })

    except RuntimeError:
        return jsonify({"error": "not bound"}), 401
    except Exception as e:
        return jsonify({"error": "server_error", "detail": str(e)}), 500

# -----------------------------------------------------------------------------
# Health Check
# -----------------------------------------------------------------------------
@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "redirect_uri": REDIRECT_URI,
        "frontend": FRONTEND_ORIGIN
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)


from flask import send_from_directory

@app.route("/")
def serve_index():
    return send_from_directory("static", "index.html")

@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)
