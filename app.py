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

# 所有回應都禁快取，避免 /auth/status 被舊值蓋住
@app.after_request
def add_no_cache_headers(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

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
        "redirect_uri": REDIRECT_URI,   # 記得與 FB 後台一致
        "code": code,
    })
    if not ok:
        return jsonify({"step": "code_to_short", "error": data}), 400
    short_user_token = data["access_token"]

    # 2) 短期 -> 長期 user token（可拿來查 pages）
    ok, data, _ = graph_get("oauth/access_token", {
        "grant_type": "fb_exchange_token",
        "client_id": FB_APP_ID,
        "client_secret": FB_APP_SECRET,
        "fb_exchange_token": short_user_token,
    })
    if not ok:
        return jsonify({"step": "short_to_long", "error": data}), 400
    long_user_token = data["access_token"]
    expires_in = int(data.get("expires_in") or 0)

    # 3) 找有連 IG 的 Page，取 page_token + ig_user_id
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
                "page_token": ptoken,
                "ig_user_id": ig["id"],
                "ig_username": ig.get("username"),
            }
            break

    if not chosen:
        return "No connected Instagram account found", 400

    # 4) 寫入 session（頁面分析會使用）
    session["bind"] = {
        **chosen,
        "long_user_expires_at": int(time.time()) + expires_in
    }

    # 5) 用回應物件來做 redirect + 設定 cookie + 防快取
    # 如果前端頁也放在後端同一網域，就導向 /result；如果是獨立網域，換成 FRONTEND_ORIGIN + '/result'
    # resp = redirect(f"{FRONTEND_ORIGIN}/result")
    resp = redirect("/result")

    # 額外種一顆測試 cookie（不是必要，只是方便你在 DevTools 看到瀏覽器確實收到了 cookie）
    resp.set_cookie("sa_bound", "1", max_age=86400, secure=True, samesite="None")

    # 再保險一次：別被快取
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

# -----------------------------------------------------------------------------
# 分析 API（前端 /result 會呼叫）
# -----------------------------------------------------------------------------
@app.route("/me/ig/analyze", methods=["GET", "POST"])
def me_ig_analyze():
    """
    回應：
      ok: true/false
      ig_account, profile_name, mbti, reason
      如果失敗 -> ok:false, where:'哪步', detail:{...}
    """
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

    # 3) 先做 Heuristic（一定要有），OpenAI 只是加值（失敗也不該讓整個流程中止）
    try:
        mbti, reason = mbti_heuristic(prof, media_list)
    except Exception as e:
        return jsonify({"ok": False, "where": "heuristic", "detail": str(e)}), 200

    # 4) 如果有 OPENAI_API_KEY，使用 AI 生成更完整描述（可選）
    use_openai = bool(os.getenv("OPENAI_API_KEY"))
    if use_openai:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            prompt = f"""
            這是一個 Instagram 使用者的公開資料：
            名稱：{prof.get('name')}
            簡介：{prof.get('biography')}
            貼文數：{prof.get('media_count')}
            粉絲數：{prof.get('followers_count')}
            追蹤數：{prof.get('follows_count')}
            MBTI 初步推論：{mbti}

            請以心理學角度，用輕鬆口吻（100字內），生成一段分析說明，描述這個人的社群個性、風格與氛圍。
            """
            resp = client.responses.create(
                model="gpt-4.1-mini",
                input=prompt,
                max_output_tokens=150
            )
            text = resp.output_text.strip()
            if text:
                reason = text[:100]
        except Exception as e:
            print("[OpenAI failed]", e)

    # --------------------------
    # ✅ 最後保底輸出邏輯
    # --------------------------
    if not prof or not isinstance(prof, dict):
        prof = {"username": b.get("ig_username", ""), "name": ""}

    if 'mbti' not in locals():
        try:
            mbti, reason = mbti_heuristic(prof, [])
        except:
            mbti, reason = "ISFJ", "保底輸出：資料不足，以保守穩健型給出暫時結果。"

    return jsonify({
        "ok": True,
        "ig_account": prof.get("username") or b.get("ig_username") or "",
        "profile_name": prof.get("name") or "",
        "mbti": mbti,
        "reason": reason
    }), 200

@app.get("/me/ig/check")
def me_ig_check():
    """一次把 profile 與 media 的 raw 給你看（masked）"""
    try:
        b = require_bind()
    except RuntimeError:
        return jsonify({"ok": False, "where":"session", "detail":"not bound"})
    out = {"ok": True, "page_id": b["page_id"], "ig_user_id": b["ig_user_id"]}

    ok, prof, _ = graph_get(
        b["ig_user_id"],
        {"fields":"id,username,name,followers_count,media_count","access_token": b["page_token"]}
    )
    out["profile_ok"] = ok
    out["profile"] = prof

    ok, media, _ = graph_get(
        f"{b['ig_user_id']}/media",
        {"fields":"id,media_type,timestamp","limit": 5, "access_token": b["page_token"]}
    )
    out["media_ok"] = ok
    out["media_count"] = len(media.get("data",[])) if isinstance(media,dict) else None
    if not ok:
        out["media_error"] = media
    return jsonify(out)

@app.get("/debug/session")
def debug_session():
    """檢視 session（不含敏感 token）"""
    b = session.get("bind")
    if not b:
        return jsonify({"ok": False, "detail": "not bound"})
    masked = {k: v for k, v in b.items() if k != "page_token"}
    masked["has_page_token"] = bool(b.get("page_token"))
    return jsonify({"ok": True, "bind": masked})

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
