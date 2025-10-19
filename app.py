# app.py — Instagram Basic Display ONLY
import os
import re
import time
from urllib.parse import urlencode

import requests
from flask import Flask, request, jsonify, redirect, session, send_from_directory
from flask_cors import CORS

# -----------------------------------
# Config
# -----------------------------------
SITE_URL = os.getenv("SITE_URL", "").rstrip("/")
if not SITE_URL:
    raise RuntimeError("SITE_URL is required (e.g. https://socialavatar.onrender.com)")

SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me").strip()
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "").rstrip("/")
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "20"))

# Instagram Basic Display
IG_BASIC_APP_ID = os.getenv("IG_BASIC_APP_ID", "").strip()
IG_BASIC_APP_SECRET = os.getenv("IG_BASIC_APP_SECRET", "").strip()
BD_REDIRECT_URI = f"{SITE_URL}/bd/callback"

IG_OAUTH_AUTHORIZE = "https://api.instagram.com/oauth/authorize"
IG_OAUTH_TOKEN     = "https://api.instagram.com/oauth/access_token"
IG_GRAPH_ME        = "https://graph.instagram.com/me"
IG_GRAPH_MEDIA     = "https://graph.instagram.com/me/media"

# OpenAI（可選）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
try:
    from openai import OpenAI
    _oai = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
except Exception:
    _oai = None

# -----------------------------------
# Flask
# -----------------------------------
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = SESSION_SECRET

# 跨站 Cookie（若前後端不同網域）
app.config.update(SESSION_COOKIE_SAMESITE="None", SESSION_COOKIE_SECURE=True)
allowed_origins = [FRONTEND_ORIGIN or SITE_URL]
CORS(app, resources={r"/*": {"origins": allowed_origins}}, supports_credentials=True)

# -----------------------------------
# HTTP helpers
# -----------------------------------
def _http_post(url, data, timeout=HTTP_TIMEOUT):
    r = requests.post(url, data=data, timeout=timeout)
    try:
        j = r.json()
    except Exception:
        j = {"raw": r.text}
    return r.ok, j, r.status_code

def _http_get(url, params, timeout=HTTP_TIMEOUT):
    r = requests.get(url, params=params, timeout=timeout)
    try:
        j = r.json()
    except Exception:
        j = {"raw": r.text}
    return r.ok, j, r.status_code

def _clip(s: str, n: int = 100) -> str:
    return (s or "")[:n]

# -----------------------------------
# 極簡 MBTI Heuristic（內容＋粗特徵）
# -----------------------------------
def mbti_heuristic(profile: dict, media_list: list):
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

    E = "E" if score_E >= 1 else "I"
    N = "N" if score_N >= 1 else "S"
    T = "T" if score_T >= 1 else "F"
    P = "P" if score_P >= 1 else "J"

    reason = "；".join([
        "粉絲量顯示" + ("外向" if E == "E" else "內向"),
        "簡介字詞偏" + ("直覺" if N == "N" else "感覺"),
        "專業傾向" + ("思考" if T == "T" else "情感"),
        "貼文型態偏" + ("感知" if P == "P" else "判斷"),
    ])
    return f"{E}{N}{T}{P}", _clip(reason, 100)

def summarize_with_openai(profile: dict, media_list: list, mbti: str) -> str:
    if not _oai:
        raise RuntimeError("OPENAI_API_KEY not set")
    caps = []
    for m in (media_list or [])[:10]:
        cap = (m.get("caption") or "").strip()
        if cap: caps.append(_clip(cap, 80))
    caps_txt = "\n- " + "\n- ".join(caps) if caps else "（無最近貼文文字）"

    prompt = f"""
你是社群觀察員。用自然、口語、正向中文解釋為何此帳號傾向 MBTI「{mbti}」；限制最長100字，不用條列。
【帳號】@{profile.get('username') or ''}
【追蹤者】{profile.get('followers_count') or 0}
【追蹤中】{profile.get('follows_count') or 0}
【貼文數】{profile.get('media_count') or 0}
【BIO】{profile.get('biography') or '（無）'}
【最近貼文】{caps_txt}
""".strip()

    resp = _oai.chat.completions.create(
        model="gpt-4o-mini", temperature=0.7, max_tokens=220,
        messages=[
            {"role": "system", "content": "你是擅長社群洞察的中文寫手，語氣自然友善、簡潔。"},
            {"role": "user", "content": prompt}
        ]
    )
    return _clip((resp.choices[0].message.content or "").strip(), 100)

# -----------------------------------
# Static & Root
# -----------------------------------
@app.get("/")
def root():
    return send_from_directory(app.static_folder, "index.html")

@app.get("/health")
def health():
    return jsonify({"status": "ok", "site_url": SITE_URL, "bd_redirect": BD_REDIRECT_URI})

# -----------------------------------
# Instagram Basic Display OAuth
# -----------------------------------
@app.get("/bd/login")
def bd_login():
    if not IG_BASIC_APP_ID or not IG_BASIC_APP_SECRET:
        return jsonify({"error": "IG_BASIC_APP_ID / IG_BASIC_APP_SECRET not set"}), 500
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

    # code -> user access token
    ok, tok, _ = _http_post(IG_OAUTH_TOKEN, data={
        "client_id": IG_BASIC_APP_ID,
        "client_secret": IG_BASIC_APP_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": BD_REDIRECT_URI,
        "code": code,
    })
    if not ok:
        return jsonify({"error": tok}), 400

    user_access_token = tok.get("access_token")
    if not user_access_token:
        return jsonify({"error": "no access_token"}), 400

    # 取得 id/username（Basic Display 可用）
    ok, who, _ = _http_get(IG_GRAPH_ME, params={
        "fields": "id,username,account_type",
        "access_token": user_access_token,
    })
    if not ok:
        return jsonify({"error": who}), 400

    session["bd"] = {
        "user_access_token": user_access_token,
        "user_id": who.get("id"),
        "username": who.get("username"),
        "account_type": who.get("account_type"),
        "bound_at": int(time.time()),
    }
    return redirect("/")

@app.get("/bd/status")
def bd_status():
    bd = session.get("bd")
    if not bd:
        return jsonify({"status": "not_bound"})
    masked = {k: v for k, v in bd.items() if k != "user_access_token"}
    masked["has_token"] = bool(bd.get("user_access_token"))
    return jsonify({"status": "bound", **masked})

# -----------------------------------
# Basic Display Media
# -----------------------------------
@app.get("/bd/media")
def bd_media():
    bd = session.get("bd")
    if not bd:
        return jsonify({"error": "not bound"}), 401
    ok, media, status = _http_get(IG_GRAPH_MEDIA, params={
        "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp",
        "limit": 30,
        "access_token": bd["user_access_token"],
    })
    return (jsonify(media), status)

# -----------------------------------
# OCR 提交與一致性驗證
# -----------------------------------
def _norm_user(u: str) -> str:
    return re.sub(r"[^A-Za-z0-9._]", "", (u or "").strip().lstrip("@")).lower()

def _parse_num(s):
    if s is None: return None
    s = str(s).strip().lower().replace(",", "")
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([km])?$", s)
    if not m:
        return int(s) if s.isdigit() else None
    val = float(m.group(1))
    suf = m.group(2)
    if suf == "k": val *= 1_000
    elif suf == "m": val *= 1_000_000
    return int(round(val))

@app.post("/bd/verify_submit")
def bd_verify_submit():
    bd = session.get("bd")
    if not bd:
        return jsonify({"ok": False, "where": "session", "detail": "not bound"}), 200

    body = request.get_json(silent=True) or {}
    ocr_user  = _norm_user(body.get("ocr_username"))
    real_user = _norm_user(bd.get("username"))

    if not ocr_user:
        return jsonify({"ok": False, "where": "ocr", "detail": "username_missing"}), 200
    if ocr_user != real_user:
        return jsonify({"ok": False, "where": "username_mismatch", "expected": real_user, "got": ocr_user}), 200

    followers = _parse_num(body.get("followers"))
    following = _parse_num(body.get("following"))
    posts     = _parse_num(body.get("posts"))

    session["bd_verified"] = {
        "username": real_user,
        "followers": followers,
        "following": following,
        "posts": posts,
        "source": "screenshot_ocr",
        "verified_at": int(time.time())
    }
    return jsonify({"ok": True, "username": real_user, "followers": followers, "following": following, "posts": posts})

@app.get("/bd/verify_status")
def bd_verify_status():
    bd = session.get("bd")
    if not bd:
        return jsonify({"status": "not_bound"})
    v = session.get("bd_verified")
    return jsonify({"status": "verified" if v else "pending", "username": bd.get("username"), "verified": v or None})

# -----------------------------------
# 內容版分析（Lite）
# -----------------------------------
@app.post("/bd/analyze")
def bd_analyze():
    bd = session.get("bd")
    if not bd:
        return jsonify({"ok": False, "where": "session", "detail": "not bound"}), 200

    ok, media, _ = _http_get(IG_GRAPH_MEDIA, params={
        "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp",
        "limit": 30,
        "access_token": bd["user_access_token"],
    })
    media_list = media.get("data", []) if ok and isinstance(media, dict) else []

    v = session.get("bd_verified") or {}
    profile = {
        "username": bd.get("username"),
        "name": None,
        "biography": None,
        "followers_count": v.get("followers") or 0,
        "follows_count": v.get("following") or 0,
        "media_count": v.get("posts") if v.get("posts") is not None else len(media_list),
        "profile_picture_url": None,
    }

    mbti, reason = mbti_heuristic(profile, media_list)
    if _oai:
        try:
            ai_reason = summarize_with_openai(profile, media_list, mbti)
            if ai_reason: reason = ai_reason
        except Exception as e:
            print("[OpenAI failed]", e)

    return jsonify({
        "ok": True,
        "ig_account": profile["username"],
        "mbti": mbti,
        "reason": _clip(reason, 100),
        "verified_numbers": bool(v),
        "numbers_source": v.get("source") if v else None
    })

# -----------------------------------
# Entrypoint
# -----------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
