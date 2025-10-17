import os
import re
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v24.0")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "").strip()
IG_USER_ID = os.getenv("IG_USER_ID", "").strip()   # 你的 IG Business/Creator 帳號 user_id
# 前端網域（強烈建議設定）。例如：https://socialavatar.vercel.app
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "https://socialavatar.vercel.app").rstrip("/")

# 逾時（秒）
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "20"))

# -----------------------------------------------------------------------------
# Flask + CORS
# -----------------------------------------------------------------------------
app = Flask(__name__)

# 嚴格 CORS：只允許你的前端網域（若你想先放寬測試，可改 origins="*"）
CORS(app, resources={r"/*": {"origins": [FRONTEND_ORIGIN]}})

# -----------------------------------------------------------------------------
# Utils
# -----------------------------------------------------------------------------
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

def _ensure_tokens():
    if not PAGE_ACCESS_TOKEN or not IG_USER_ID:
        raise RuntimeError("Missing PAGE_ACCESS_TOKEN or IG_USER_ID in environment.")

def _cleanup_username(username: str) -> str:
    """
    移除 @、空白、換行，只保留英數與底線與點。
    """
    if not isinstance(username, str):
        return ""
    u = username.strip().lstrip("@")
    u = re.sub(r"[^A-Za-z0-9._]", "", u)
    return u

def _get_business_discovery(username: str, fields: str):
    """
    Graph API Business Discovery call:
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

def fetch_profile(username: str):
    """
    取得基本檔案資訊
    """
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
    # 回傳乾淨 JSON
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

def fetch_recent_media(username: str, limit: int = 30):
    """
    取得最近貼文（圖片/影片/短片）
    """
    fields = f"media.limit({limit}){{id,caption,media_type,media_url,thumbnail_url,permalink,timestamp}}"
    bd = _get_business_discovery(username, fields)
    media = bd.get("media", {}).get("data", []) or []
    # 只抽出需要的欄位
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

def simple_mbti_inference(profile, media_list):
    """
    非正式/示範用：非常簡單的 Heuristic，
    依簡歷與貼文主題給一個 MBTI + 理由（僅 Demo）。
    """
    bio = (profile.get("biography") or "").lower()
    name = (profile.get("name") or "")
    mc = profile.get("media_count") or 0
    followers = profile.get("followers_count") or 0

    # 圖像/文字簡單特徵
    imgs = sum(1 for m in media_list if (m.get("media_type") == "IMAGE"))
    vids = sum(1 for m in media_list if (m.get("media_type") in ("VIDEO", "REEL", "CLIP")))

    # 很粗略的關鍵字判斷
    score_E = 1 if followers > 5000 else 0
    if "travel" in bio or "football" in bio or "🏀" in name:
        score_E += 1
    score_N = 1 if "research" in bio or "design" in bio or "創作" in bio else 0
    score_T = 1 if "engineer" in bio or "分析" in bio or "data" in bio else 0
    score_P = 1 if vids > imgs else 0

    # 粗暴湊型
    E_or_I = "E" if score_E >= 1 else "I"
    N_or_S = "N" if score_N >= 1 else "S"
    T_or_F = "T" if score_T >= 1 else "F"
    J_or_P = "P" if score_P >= 1 else "J"

    mbti = f"{E_or_I}{N_or_S}{T_or_F}{J_or_P}"
    reason = (
        f"根據公開資訊與貼文特徵估計：\n"
        f"• 粉絲數/社交指標 → {'外向(E)' if E_or_I=='E' else '內向(I)'}\n"
        f"• 簡介/語意字詞 → {'直覺(N)' if N_or_S=='N' else '感覺(S)'}\n"
        f"• 自述/專業關鍵詞 → {'思考(T)' if T_or_F=='T' else '情感(F)'}\n"
        f"• 圖片 vs 影片比例 → {'感知(P)' if J_or_P=='P' else '判斷(J)'}\n"
        f"（*僅示範用途，不代表嚴謹心理測評*）"
    )
    return mbti, reason

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/health")
def health():
    return jsonify({"status": "ok", "frontend_allowed": FRONTEND_ORIGIN}), 200

# ✅ 改成支援 GET + POST（並處理 OPTIONS）
@app.route("/api/analyze", methods=["GET", "POST", "OPTIONS"])
def analyze():
    try:
        _ensure_tokens()

        # Preflight
        if request.method == "OPTIONS":
            return ("", 204)

        # 取 username：POST 從 JSON，GET 從 query string
        if request.method == "POST":
            body = request.get_json(silent=True) or {}
            username = _cleanup_username(body.get("username", ""))
        else:  # GET
            username = _cleanup_username(request.args.get("username", ""))

        if not username:
            return jsonify({"error": "username is required"}), 400

        # 取得檔案與貼文
        profile = fetch_profile(username)
        media = fetch_recent_media(username, limit=30)

        # Demo：簡單的人格推估
        mbti, reason = simple_mbti_inference(profile, media)

        return jsonify({
            "ok": True,
            "username": username,
            "profile": profile,
            "media": media,               # 前端若只要部分欄位，可自行過濾
            "mbti": mbti,
            "explanation": reason,
        }), 200

    except requests.Timeout:
        return jsonify({"error": "Upstream timeout"}), 504
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        # 保險：避免把內部錯誤細節曝露給前端
        return jsonify({"error": "Server error", "detail": str(e)}), 500


@app.get("/")
def index_root():
    return jsonify({"message": "SocialAvatar API is running.", "version": GRAPH_VERSION}), 200

# -----------------------------------------------------------------------------
# Entrypoint (for local dev)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # 本地開發才會使用；Render 會用 gunicorn 之類的啟動方式
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
