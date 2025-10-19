import os
import io
import base64
import re
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ========== 基本設定 ==========
app = Flask(__name__, static_url_path="/static", static_folder="static")
CORS(app, supports_credentials=True)

# 檔案儲存路徑
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# AI 可用與否（僅在 key 存在時才載入 OpenAI client）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
AI_ENABLED = bool(OPENAI_API_KEY)

client = None
if AI_ENABLED:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        # 若 openai 套件或初始化失敗，仍保證系統能運行
        print("[WARN] OpenAI client init failed:", e)
        AI_ENABLED = False
        client = None

# 方便 /debug/last_ai 檢查的暫存
_last_ai_text = ""


def save_file_from_data_url(data_url: str, filename_prefix: str) -> str:
    """
    data_url: 'data:image/png;base64,xxxx'
    return: filepath
    """
    m = re.match(r"^data:(?P<mime>[^;]+);base64,(?P<b64>.+)$", data_url)
    if not m:
        raise ValueError("Invalid data URL")
    mime = m.group("mime")
    b64 = m.group("b64")
    ext = "jpg"
    if "png" in mime:
        ext = "png"
    elif "jpeg" in mime or "jpg" in mime:
        ext = "jpg"
    elif "webp" in mime:
        ext = "webp"

    raw = base64.b64decode(b64)
    fname = f"{filename_prefix}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{ext}"
    fpath = os.path.join(UPLOAD_DIR, fname)
    with open(fpath, "wb") as f:
        f.write(raw)
    return fpath


def call_openai_summary(images_b64: list, fallback_mbti: str = "ISFJ") -> dict:
    """
    回傳:
      {
        "username": "...",
        "name": "...",
        "bio": "...",
        "followers": 123,
        "following": 99,
        "posts": 45,
        "mbti": "ESFJ",
        "reason100": "..."
      }
    若 AI_DISABLED 或失敗 -> 以簡單 Heuristic / 預設值回傳
    """
    global _last_ai_text

    # 預設（AI 失敗時）
    default = {
        "username": "",
        "name": "",
        "bio": "",
        "followers": 0,
        "following": 0,
        "posts": 0,
        "mbti": fallback_mbti,
        "reason100": "依上傳截圖初步推斷，僅供娛樂參考。"
    }

    if not AI_ENABLED or client is None:
        _last_ai_text = "(AI disabled) fallback used"
        return default

    try:
        # OpenAI Multi-modal 推理（多圖）
        content = [
            {"type": "text",
             "text": (
                 "你是社群人格觀察員。請從 IG 個人頁截圖與首圖中，"
                 "判讀：username、顯示名稱、bio、followers、following、posts，"
                 "並根據整體風格推一個 MBTI（四個字母），並寫 100 字以內的中文敘述。"
                 "用 JSON 回覆，不要其他字元。格式："
                 '{"username":"","name":"","bio":"","followers":0,"following":0,"posts":0,"mbti":"ESFJ","reason100":""}'
             )}
        ]
        # 依序加入圖片
        for b64 in images_b64:
            content.append({
                "type": "input_image",
                "image_data": b64  # 你前端已提供純 base64（不含 data: 前綴）
            })

        resp = client.responses.create(
            model="gpt-4o",   # 模型建議用 gpt-4o，較穩定
            input=[{"role": "user", "content": content}]
        )

        text = getattr(resp, "output_text", "") or ""
        _last_ai_text = text or "(empty)"

        # 嘗試把結果 parse 成 dict
        import json
        parsed = json.loads(text)
        # 基本容錯
        for k in default.keys():
            if k not in parsed:
                parsed[k] = default[k]
        # 型別校正
        for nkey in ["followers", "following", "posts"]:
            try:
                parsed[nkey] = int(parsed[nkey])
            except Exception:
                parsed[nkey] = 0
        parsed["mbti"] = (parsed.get("mbti") or fallback_mbti).upper()[:4]
        parsed["reason100"] = (parsed.get("reason100") or default["reason100"])[:120]
        return parsed

    except Exception as e:
        print("[OpenAI failed]", e)
        _last_ai_text = f"(exception) {e}"
        return default


# ========== API ==========

@app.get("/")
def root():
    # 直接把使用者導向結果頁（單頁 App）
    return send_from_directory("static", "index.html")


@app.post("/api/analyze")
def api_analyze():
    """
    接收：
      {
        "username_input": "danny",
        "profile_screenshot": "data:image/png;base64,....",   # 必填
        "post_images": ["data:image/png;base64,...", ...]     # 可選 0~9 張
      }
    回傳：
      {
        "ok": true,
        "data": {
          "displayName": "...",
          "username": "...",
          "followers": 123, "following": 45, "posts": 87,
          "mbti": "ESFJ",
          "reason": "100 字",
          "vehicle": "步行/腳踏車/汽車/火箭"
        }
      }
    """
    body = request.get_json(silent=True) or {}
    profile_shot = body.get("profile_screenshot", "")
    post_images = body.get("post_images", []) or []
    username_input = (body.get("username_input") or "").strip()

    if not profile_shot:
        return jsonify({"ok": False, "error": "profile_screenshot required"}), 400

    # 存檔（可省略）
    try:
        save_file_from_data_url(profile_shot, "profile")
        for i, p in enumerate(post_images[:9]):
            save_file_from_data_url(p, f"post{i+1}")
    except Exception as e:
        print("[save failed]", e)

    # 轉成純 base64，給 OpenAI
    def to_raw_b64(data_url: str) -> str:
        if data_url.startswith("data:"):
            return data_url.split(",", 1)[1]
        return data_url

    imgs_b64 = [to_raw_b64(profile_shot)] + [to_raw_b64(p) for p in post_images[:9]]

    # 呼叫 AI（或 fallback）
    parsed = call_openai_summary(imgs_b64)

    # 統一顯示名稱
    display_name = parsed.get("name") or username_input or "匿名使用者"
    uname = parsed.get("username") or username_input

    # 載具分級（示意）
    followers = int(parsed.get("followers") or 0)
    if followers >= 100000:
        vehicle = "火箭"
    elif followers >= 20000:
        vehicle = "超跑"
    elif followers >= 5000:
        vehicle = "汽車"
    elif followers >= 1000:
        vehicle = "腳踏車"
    else:
        vehicle = "步行"

    out = {
        "displayName": display_name,
        "username": uname,
        "followers": followers,
        "following": int(parsed.get("following") or 0),
        "posts": int(parsed.get("posts") or 0),
        "mbti": parsed.get("mbti") or "ISFJ",
        "reason": parsed.get("reason100") or "依上傳截圖初步推斷，僅供娛樂參考。",
        "vehicle": vehicle
    }
    return jsonify({"ok": True, "data": out})


# ======== Debug routes ========

@app.get("/debug/config")
def debug_config():
    """檢查伺服器上的 AI 狀態與 Key 有無"""
    return jsonify({
        "ai_enabled": AI_ENABLED,
        "has_key": bool(OPENAI_API_KEY),
        "client_ready": bool(client) if AI_ENABLED else False
    })


@app.get("/debug/last_ai")
def debug_last_ai():
    """看 AI 最後回傳的原始字串（便於定位解析問題）"""
    return jsonify({"text": _last_ai_text})


# ========== 靜態檔 ==========

@app.get("/result")
def result():
    return send_from_directory("static", "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
