import os
import re
import time
from urllib.parse import urlencode

import requests
from flask import Flask, request, jsonify, redirect, session, send_from_directory
from flask_cors import CORS

# ----------------------------
# 基本設定
# ----------------------------
SITE_URL = os.getenv("SITE_URL", "https://socialavatar.onrender.com").rstrip("/")
SESSION_SECRET = os.getenv("SESSION_SECRET", "secret").strip()
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "").rstrip("/")

# Instagram Basic Display
IG_BASIC_APP_ID = os.getenv("IG_BASIC_APP_ID", "").strip()
IG_BASIC_APP_SECRET = os.getenv("IG_BASIC_APP_SECRET", "").strip()
BD_REDIRECT_URI = f"{SITE_URL}/bd/callback"  # ✅ 目前設定使用此路徑

IG_OAUTH_AUTHORIZE = "https://api.instagram.com/oauth/authorize"
IG_OAUTH_TOKEN = "https://api.instagram.com/oauth/access_token"
IG_GRAPH_ME = "https://graph.instagram.com/me"
IG_GRAPH_MEDIA = "https://graph.instagram.com/me/media"

# Optional: OpenAI API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
try:
    from openai import OpenAI
    _oai = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
except Exception:
    _oai = None


# ----------------------------
# Flask 初始化
# ----------------------------
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = SESSION_SECRET

# 支援跨網域
app.config.update(
    SESSION_COOKIE_SAMESITE="None",
    SESSION_COOKIE_SECURE=True
)
allowed_origins = [FRONTEND_ORIGIN or SITE_URL]
CORS(app, resources={r"/*": {"origins": allowed_origins}}, supports_credentials=True)


# ----------------------------
# HTTP 輔助
# ----------------------------
def _http_post(url, data, timeout=20):
    r = requests.post(url, data=data, timeout=timeout)
    try:
        return r.ok, r.json(), r.status_code
    except Exception:
        return r.ok, {"raw": r.text}, r.status_code


def _http_get(url, params, timeout=20):
    r = requests.get(url, params=params, timeout=timeout)
    try:
        return r.ok, r.json(), r.status_code
    except Exception:
        return r.ok, {"raw": r.text}, r.status_code


# ----------------------------
# MBTI 分析邏輯
# ----------------------------
def mbti_heuristic(profile: dict, media_list: list):
    bio = (profile.get("biography") or "").lower()
    followers = int(profile.get("followers_count") or 0)
    imgs = sum(1 for m in media_list if m.get("media_type") == "IMAGE")
    vids = sum(1 for m in media_list if m.get("media_type") in ("VIDEO", "REEL"))

    E = "E" if followers > 5000 or "travel" in bio else "I"
    N = "N" if "design" in bio or "art" in bio else "S"
    T = "T" if "engineer" in bio or "分析" in bio else "F"
    P = "P" if vids > imgs else "J"

    reason = f"粉絲量與內容顯示偏{('外向' if E=='E' else '內向')}、思維偏{('直覺' if N=='N' else '感覺')}、傾向{('理性分析' if T=='T' else '情感表達')}，貼文風格偏{('感知' if P=='P' else '判斷')}型。"
    return f"{E}{N}{T}{P}", reason[:100]


def summarize_with_openai(profile: dict, media_list: list, mbti: str):
    """可選：使用 OpenAI 生成自然中文摘要（100 字）"""
    if not _oai:
        raise RuntimeError("OPENAI_API_KEY not set")

    texts = []
    for m in (media_list or [])[:10]:
        cap = (m.get("caption") or "").strip()
        if cap:
            texts.append(cap[:80])
    joined = "\n- " + "\n- ".join(texts) if texts else "（無貼文）"

    prompt = f"""
請用自然中文簡短描述此 IG 使用者的性格特質（100字內），MBTI 為 {mbti}。
帳號：@{profile.get('username')}
粉絲：{profile.get('followers_count')}、追蹤：{profile.get('follows_count')}、貼文：{profile.get('media_count')}
Bio：{profile.get('biography') or '（無）'}
貼文文字：{joined}
    """

    resp = _oai.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.7,
        max_tokens=220,
        messages=[
            {"role": "system", "content": "你是社群人格分析專家，用口語、簡潔、正向中文回答。"},
            {"role": "user", "content": prompt}
        ]
    )
    return resp.choices[0].message.content.strip()[:100]


# ----------------------------
# Routes
# ----------------------------
@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/health")
def health():
    return jsonify({"ok": True, "redirect_uri": BD_REDIRECT_URI})


# --- 登入流程 ---
@app.get("/bd/login")
def bd_login():
    params = {
        "client_id": IG_BASIC_APP_ID,
        "redirect_uri": BD_REDIRECT_URI,
        "scope": "user_profile,user_media",
        "response_type": "code",
    }
    return redirect(f"{IG_OAUTH_AUTHORIZE}?{urlencode(params)}")


@app.get("/bd/callback")
def bd_callback():
    code = request.args.get("code")
    if not code:
        return "Missing code", 400

    ok, data, _ = _http_post(IG_OAUTH_TOKEN, {
        "client_id": IG_BASIC_APP_ID,
        "client_secret": IG_BASIC_APP_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": BD_REDIRECT_URI,
        "code": code,
    })
    if not ok:
        return jsonify({"error": data}), 400

    token = data.get("access_token")
    if not token:
        return jsonify({"error": "no token"}), 400

    ok, me, _ = _http_get(IG_GRAPH_ME, {
        "fields": "id,username,account_type",
        "access_token": token,
    })
    if not ok:
        return jsonify({"error": me}), 400

    session["bd"] = {
        "token": token,
        "id": me.get("id"),
        "username": me.get("username"),
        "account_type": me.get("account_type"),
        "at": int(time.time())
    }
    return redirect("/")


@app.get("/bd/status")
def bd_status():
    bd = session.get("bd")
    if not bd:
        return jsonify({"status": "not_bound"})
    return jsonify({"status": "bound", "username": bd.get("username"), "has_token": True})


@app.post("/bd/verify")
def bd_verify():
    """上傳截圖OCR資料，比對帳號一致性"""
    bd = session.get("bd")
    if not bd:
        return jsonify({"ok": False, "error": "not logged in"})

    body = request.get_json(silent=True) or {}
    ocr_user = re.sub(r"[^A-Za-z0-9._]", "", (body.get("ocr_username") or "").lower())
    real_user = (bd.get("username") or "").lower()

    if not ocr_user:
        return jsonify({"ok": False, "error": "missing_username"})
    if ocr_user != real_user:
        return jsonify({"ok": False, "error": f"username mismatch ({ocr_user} vs {real_user})"})

    session["verified"] = {
        "followers": body.get("followers"),
        "following": body.get("following"),
        "posts": body.get("posts"),
        "at": int(time.time())
    }
    return jsonify({"ok": True, "username": real_user})


@app.post("/bd/analyze")
def bd_analyze():
    """生成 MBTI 分析結果"""
    bd = session.get("bd")
    if not bd:
        return jsonify({"ok": False, "error": "not logged in"})
    token = bd.get("token")

    ok, media, _ = _http_get(IG_GRAPH_MEDIA, {
        "fields": "id,caption,media_type,media_url,timestamp",
        "limit": 30,
        "access_token": token
    })
    media_list = media.get("data", []) if ok else []

    verified = session.get("verified", {})
    profile = {
        "username": bd.get("username"),
        "followers_count": verified.get("followers") or 0,
        "follows_count": verified.get("following") or 0,
        "media_count": verified.get("posts") or len(media_list),
        "biography": None
    }

    mbti, reason = mbti_heuristic(profile, media_list)
    if _oai:
        try:
            reason = summarize_with_openai(profile, media_list, mbti)
        except Exception as e:
            print("OpenAI fail:", e)

    return jsonify({
        "ok": True,
        "username": profile["username"],
        "mbti": mbti,
        "reason": reason
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
