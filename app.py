import os
import re
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v24.0").strip()
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "").strip()  # 必須是「Page 長效 Token」
IG_USER_ID = os.getenv("IG_USER_ID", "").strip()                # 連到該 Page 的 IG Business/Creator user_id

# 前端網域（強烈建議設定成你的 Vercel 網域）
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "https://socialavatar.vercel.app").rstrip("/")

# App for debug_token 用
APP_ID = os.getenv("APP_ID", "").strip()
APP_SECRET = os.getenv("APP_SECRET", "").strip()

# 逾時（秒）
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "20"))

# -----------------------------------------------------------------------------
# Flask + CORS
# -----------------------------------------------------------------------------
app = Flask(__name__)
# 嚴格 CORS：只允許你的前端網域
CORS(app, resources={r"/*": {"origins": [FRONTEND_ORIGIN]}})

GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


# -----------------------------------------------------------------------------
# Utils
# -----------------------------------------------------------------------------
def _ensure_tokens():
    if not PAGE_ACCESS_TOKEN or not IG_USER_ID:
        raise RuntimeError("Missing PAGE_ACCESS_TOKEN or IG_USER_ID in environment.")


def _cleanup_username(username: str) -> str:
    """移除 @、空白、換行，只保留英數/底線/點號。"""
    if not isinstance(username, str):
        return ""
    u = username.strip().lstrip("@")
    u = re.sub(r"[^A-Za-z0-9._]", "", u)
    return u


def _get_business_discovery(username: str, fields: str):
    """
    Graph API Business Discovery：
    GET /{ig_user_id}?fields=business_discovery.username(USER){FIELDS}&access_token=...
    """
    url = f"{GRAPH_BASE}/{IG_USER_ID}"
    params = {
        "fields": f"business_discovery.username({username}){{{fields}}}",
        "access_token": PAGE_ACCESS_TOKEN,
    }
    r = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"Graph error ({r.status_code}): {r.text}")
    data = r.json()
    bd = data.get("business_discovery")
    if not bd:
        raise RuntimeError("No business_discovery returned. The username may be invalid or not public.")
    return bd


def fetch_profile(username: str) -> dict:
    """取得基本檔案資訊（僅用於內部分析，不直接回給前端）。"""
    fields = ",".join([
        "id",
        "username",
        "media_count",
        "followers_count",
        "follows_count",
        "profile_picture_url",
        "name",
        "biography",
    ])
    bd = _get_business_discovery(username, fields)
    return {
        "id": bd.get("id"),
        "username": bd.get("username"),
        "media_count": bd.get("media_count"),
        "followers_count": bd.get("followers_count"),
        "follows_count": bd.get("follows_count"),
        "profile_picture_url": bd.get("profile_picture_url"),
        "name": bd.get("name"),
        "biography": bd.get("biography"),
    }


def fetch_recent_media(username: str, limit: int = 30) -> list:
    """取得最近貼文（圖片/影片/短片）供簡單特徵分析。"""
    fields = f"media.limit({limit}){{id,caption,media_type,media_url,thumbnail_url,permalink,timestamp}}"
    bd = _get_business_discovery(username, fields)
    media = bd.get("media", {}).get("data", []) or []
    cleaned = []
    for m in media:
        cleaned.append({
            "id": m.get("id"),
            "caption": m.get("caption"),
            "media_type": m.get("media_type"),
            "media_url": m.get("media_url"),
            "thumbnail_url": m.get("thumbnail_url"),
            "permalink": m.get("permalink"),
            "timestamp": m.get("timestamp"),
        })
    return cleaned


def simple_mbti_inference(profile: dict, media_list: list) -> tuple[str, str]:
    """
    非正式/示範用的簡單 Heuristic：依資料給出一個 MBTI 與短原因（50 字內）。
    """
    bio = (profile.get("biography") or "").lower()
    name = (profile.get("name") or "")
    followers = profile.get("followers_count") or 0

    imgs = sum(1 for m in media_list if (m.get("media_type") == "IMAGE"))
    vids = sum(1 for m in media_list if (m.get("media_type") in ("VIDEO", "REEL", "CLIP")))

    score_E = 1 if followers > 5000 else 0
    if "travel" in bio or "football" in bio or "🏀" in name:
        score_E += 1
    score_N = 1 if ("research" in bio or "design" in bio or "創作" in bio) else 0
    score_T = 1 if ("engineer" in bio or "分析" in bio or "data" in bio) else 0
    score_P = 1 if vids > imgs else 0

    E_or_I = "E" if score_E >= 1 else "I"
    N_or_S = "N" if score_N >= 1 else "S"
    T_or_F = "T" if score_T >= 1 else "F"
    J_or_P = "P" if score_P >= 1 else "J"

    mbti = f"{E_or_I}{N_or_S}{T_or_F}{J_or_P}"

    # 50 字內的極短理由（中文長度用 len 簡化估算）
    reason = (
        f"粉絲與簡介顯示{('外向' if E_or_I=='E' else '內向')}、"
        f"{('直覺' if N_or_S=='N' else '感覺')}與"
        f"{('思考' if T_or_F=='T' else '情感')}傾向；"
        f"{'影片多於圖片' if J_or_P=='P' else '圖片多於影片'}，判為{('感知' if J_or_P=='P' else '判斷')}型。"
    )
    # 硬切 50 字
    if len(reason) > 50:
        reason = reason[:50]
    return mbti, reason


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/health")
def health():
    return jsonify({"status": "ok", "frontend_allowed": FRONTEND_ORIGIN}), 200


@app.get("/")
def index_root():
    return jsonify({"message": "SocialAvatar API is running.", "version": GRAPH_VERSION}), 200


@app.post("/api/analyze")
def analyze():
    """
    前端只需要四個欄位：
      - ig_username
      - profile_name
      - mbti
      - reason (<= 50 字)
    """
    try:
        _ensure_tokens()

        body = request.get_json(silent=True) or {}
        username = _cleanup_username(body.get("username", ""))
        if not username:
            return jsonify({"error": "username is required"}), 400

        # 取得檔案與貼文（僅用於內部推估）
        profile = fetch_profile(username)
        media = fetch_recent_media(username, limit=30)

        mbti, reason = simple_mbti_inference(profile, media)

        return jsonify({
            "ok": True,
            "ig_username": profile.get("username") or username,
            "profile_name": profile.get("name") or "",
            "mbti": mbti,
            "reason": reason,  # 已限制 50 字內
        }), 200

    except requests.Timeout:
        return jsonify({"error": "Upstream timeout"}), 504
    except RuntimeError as e:
        # Graph 相關錯誤、權限/Token 錯誤會在這裡
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        # 保險：避免把內部錯誤細節曝露給前端
        return jsonify({"error": "Server error"}), 500


# -----------------------------------------------------------------------------
# DEBUG endpoints（部署後測完請移除）
# -----------------------------------------------------------------------------
@app.get("/debug/token_tail")
def token_tail():
    tail = PAGE_ACCESS_TOKEN[-8:] if PAGE_ACCESS_TOKEN else None
    return jsonify({
        "token_tail": tail,
        "ig_user_id": IG_USER_ID
    }), 200


@app.get("/debug/check_token")
def check_token():
    if not PAGE_ACCESS_TOKEN or not APP_ID or not APP_SECRET:
        return jsonify({"error": "missing PAGE_ACCESS_TOKEN / APP_ID / APP_SECRET"}), 400
    app_access = f"{APP_ID}|{APP_SECRET}"
    url = f"{GRAPH_BASE}/debug_token"
    try:
        resp = requests.get(url, params={
            "input_token": PAGE_ACCESS_TOKEN,
            "access_token": app_access
        }, timeout=HTTP_TIMEOUT)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": f"debug_token failed: {str(e)}"}), 500


# -----------------------------------------------------------------------------
# Entrypoint (for local dev)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # 本地開發才會用；Render 會用 gunicorn/uvicorn 啟動
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
