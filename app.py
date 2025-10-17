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

# ================================
# Debug helpers for Page Token
# ================================
APP_ID = os.getenv("APP_ID", "").strip()
APP_SECRET = os.getenv("APP_SECRET", "").strip()

def _app_access_token() -> str:
    """
    產生 App Access Token: {app_id}|{app_secret}
    用於 /debug_token 檢查任意 token
    """
    if not APP_ID or not APP_SECRET:
        raise RuntimeError("Missing APP_ID / APP_SECRET in environment for debug.")
    return f"{APP_ID}|{APP_SECRET}"

def _graph_get(path, params=None):
    url = f"{GRAPH_BASE}/{path.lstrip('/')}"
    r = requests.get(url, params=params or {}, timeout=HTTP_TIMEOUT)
    try:
        data = r.json()
    except Exception:
        data = {"error": {"message": r.text}}
    return r.status_code, data

@app.get("/debug/token_tail")
def debug_token_tail():
    """
    用來確認 Render 環境變數是否真的換成「新 Token」。
    只顯示尾碼與字元數，避免 token 外洩。
    """
    tail = PAGE_ACCESS_TOKEN[-10:] if PAGE_ACCESS_TOKEN else ""
    return jsonify({
        "read_from_env": bool(PAGE_ACCESS_TOKEN),
        "token_len": len(PAGE_ACCESS_TOKEN),
        "token_tail": tail
    })

@app.get("/debug/debug_token")
def debug_debug_token():
    """
    用 Graph 的 /debug_token 解析目前 PAGE_ACCESS_TOKEN。
    需要 APP_ID / APP_SECRET，請在 Render 設定環境變數。
    """
    try:
        app_token = _app_access_token()
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400

    params = {
        "input_token": PAGE_ACCESS_TOKEN,
        "access_token": app_token
    }
    status, data = _graph_get("/debug_token", params)
    return jsonify({
        "status": status,
        "raw": data
    }), status

@app.get("/debug/check_token")
def debug_check_token():
    """
    高度摘要：透過 /debug_token 判斷是否有效、token 類型、到期時間、scopes。
    並額外取 /me 與 /{page_id} 基本資料。
    """
    try:
        app_token = _app_access_token()
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400

    # 1) 解析 token
    st, info = _graph_get("/debug_token", {
        "input_token": PAGE_ACCESS_TOKEN,
        "access_token": app_token
    })
    if st != 200 or not info.get("data"):
        return jsonify({"ok": False, "debug_token": info}), 400

    data = info["data"]
    is_valid = data.get("is_valid")
    token_type = data.get("type")      # 期望為 "PAGE"
    scopes = data.get("scopes", [])
    user_id = data.get("user_id")      # 對 Page Token 而言，這其實就是 page_id
    expires_at = data.get("expires_at")
    issued_at = data.get("issued_at")

    summary = {
        "ok": bool(is_valid),
        "token_type": token_type,
        "page_id_from_token": user_id,
        "expires_at": expires_at,
        "issued_at": issued_at,
        "scopes": scopes,
    }

    # 2) 讀 /me (用 page token 會得到 Page)
    st2, me = _graph_get("/me", params={"access_token": PAGE_ACCESS_TOKEN, "fields": "id,name"})
    summary["me_status"] = st2
    summary["me"] = me

    # 3) 讀 page 綁定的 IG（如果 user_id 有值）
    page_check = {}
    if user_id:
        st3, page_info = _graph_get(f"/{user_id}", params={
            "access_token": PAGE_ACCESS_TOKEN,
            "fields": "name,connected_instagram_account,instagram_business_account"
        })
        page_check = {
            "status": st3,
            "page_info": page_info
        }

    return jsonify({
        "summary": summary,
        "debug_token_raw": info,
        "page_binding": page_check
    }), 200

@app.get("/debug/whoami")
def debug_whoami():
    """
    用目前 PAGE_ACCESS_TOKEN 呼叫 /me?fields=id,name
    快速確認 Token 實際代表的主體（Page / User）
    """
    st, data = _graph_get("/me", {"access_token": PAGE_ACCESS_TOKEN, "fields": "id,name"})
    return jsonify({"status": st, "data": data}), st

@app.get("/debug/page_binding")
def debug_page_binding():
    """
    當你已經知道 page_id（可從 /debug/check_token 看到），
    也可以帶 ?page_id= 直接檢查此 Page 是否綁定 IG。
    """
    page_id = request.args.get("page_id", "").strip()
    if not page_id:
        # 如果沒帶，就嘗試從 debug_token 找
        try:
            app_token = _app_access_token()
            st, info = _graph_get("/debug_token", {
                "input_token": PAGE_ACCESS_TOKEN,
                "access_token": app_token
            })
            page_id = info.get("data", {}).get("user_id", "")
        except Exception:
            pass

    if not page_id:
        return jsonify({"error": "page_id missing and cannot be derived from token"}), 400

    st2, page_info = _graph_get(f"/{page_id}", {
        "access_token": PAGE_ACCESS_TOKEN,
        "fields": "id,name,connected_instagram_account,instagram_business_account"
    })
    return jsonify({"status": st2, "page_info": page_info}), st2

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


@app.get("/debug/token")
def debug_token():
    try:
        token = PAGE_ACCESS_TOKEN.strip()
        url = f"https://graph.facebook.com/{GRAPH_VERSION}/debug_token"
        params = {"input_token": token, "access_token": token}
        r = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500
