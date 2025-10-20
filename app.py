# app.py
import os
import io
import json
import base64
from typing import List, Tuple

from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS

from PIL import Image

import requests

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
AI_ON = os.getenv("AI_ON", "1") == "1" and bool(OPENAI_API_KEY)

MAX_SIDE = int(os.getenv("MAX_SIDE", "1280"))
JPEG_Q = int(os.getenv("JPEG_Q", "72"))

# 全域緩存最後一次 AI 原始/結構化結果（給 /debug/last_ai）
_last_ai_raw = ""
_last_ai_obj = None

# -----------------------------------------------------------------------------
# Flask
# -----------------------------------------------------------------------------
app = Flask(__name__)
# 前端與後端同網域，或你也可加 origins=["https://socialavatar.vercel.app"]
CORS(app)

# -----------------------------------------------------------------------------
# Utils: image compress -> base64 data url
# -----------------------------------------------------------------------------
def compress_to_jpeg_b64(file_storage, max_side: int = MAX_SIDE, jpeg_q: int = JPEG_Q) -> str:
    """
    將前端上傳圖片縮放到最長邊不超過 max_side，轉 JPEG（品質 jpeg_q），輸出 base64（不含 data: 前綴）
    """
    if not file_storage:
        return ""
    file_storage.stream.seek(0)
    im = Image.open(file_storage.stream).convert("RGB")
    w, h = im.size
    ratio = max(w, h) / float(max_side)
    if ratio > 1.0:
        w2 = int(round(w / ratio))
        h2 = int(round(h / ratio))
        im = im.resize((w2, h2), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=jpeg_q, optimize=True)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    # 去除換行（保險）
    return "".join(b64.split())


def _data_url_from_b64(b64: str) -> str:
    """
    Responses API 對圖像輸入要 'image_url' 並且是字串 URL。
    我們用 data URL 形式：data:image/jpeg;base64,<base64...>
    """
    b64 = "".join((b64 or "").split())
    return f"data:image/jpeg;base64,{b64}" if b64 else ""


# -----------------------------------------------------------------------------
# OpenAI Vision (Responses API)
# -----------------------------------------------------------------------------
PROMPT_SYS = (
    "你是一位社群人格分析師。請用『第一次打開 IG 個人頁』的直覺來判讀此帳號："
    "只根據個人頁可見的資料（粉絲/追蹤/貼文數、名稱、自我介紹、首屏縮圖），"
    "判斷對方的社群 MBTI 類型（如：INTP/ESFJ 等），並用自然、有個性的口吻，"
    "給一段約 200 字的分析說明（為什麼會這樣覺得）。不要用制式報表語氣。"
    "請輸出 JSON，鍵為：display_name, username, followers, following, posts, mbti, summary, vehicle。"
)

def call_openai_vision(profile_b64: str, posts_b64: List[str]) -> str:
    """
    回傳 OpenAI Responses API 的 output_text（字串）。
    失敗 raise RuntimeError，呼叫端自行捕捉並 fallback。
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    # 建 content：文字 + 圖像（圖像都要用 'image_url': <string>）
    content = [
        {"type": "input_text", "text": PROMPT_SYS},
        {"type": "input_image", "image_url": _data_url_from_b64(profile_b64)},
    ]
    for b in (posts_b64 or [])[:4]:
        url = _data_url_from_b64(b)
        if url:
            content.append({"type": "input_image", "image_url": url})

    payload = {
        "model": "gpt-4.1-mini",  # 可換成你帳戶可用的 vision 模型
        "input": [
            {
                "role": "user",
                "content": content
            }
        ],
        # 強制 JSON schema，降低解析錯誤機率
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "ig_mbti_card",
                "schema": {
                    "type": "object",
                    "properties": {
                        "display_name": {"type": "string"},
                        "username": {"type": "string"},
                        "followers": {"type": "number"},
                        "following": {"type": "number"},
                        "posts": {"type": "number"},
                        "mbti": {"type": "string"},
                        "summary": {"type": "string"},
                        "vehicle": {"type": "string"}
                    },
                    "required": ["display_name", "mbti", "summary"],
                    "additionalProperties": True
                }
            }
        }
    }

    r = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload),
        timeout=120,
    )

    if r.status_code >= 400:
        raise RuntimeError(f"OpenAI HTTP {r.status_code}: {r.text}")

    data = r.json()
    # Responses API：常見位置是 output_text
    if "output_text" in data and isinstance(data["output_text"], str):
        return data["output_text"]

    # 有些情況會在 choices[0].message.content
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        return json.dumps(data, ensure_ascii=False)


# -----------------------------------------------------------------------------
# Heuristic fallback（當 AI 失敗時也能出結果）
# -----------------------------------------------------------------------------
def simple_vehicle_by_followers(followers: int) -> str:
    """
    與你先前規則接近的簡版載具級距（可再調整）
    """
    f = followers or 0
    if f < 1000: return "步行"
    if f < 5000: return "三輪車"
    if f < 10000: return "滑板車"
    if f < 50000: return "機車"
    if f < 100000: return "汽車"
    if f < 500000: return "飛機"
    if f < 1000000: return "火箭"
    if f < 10000000: return "飛船"
    return "星艦"

def fallback_from_profile_img() -> dict:
    """
    在不能解析圖片時，給出保底結果。
    """
    return {
        "display_name": "使用者",
        "username": "",
        "followers": 0,
        "following": 0,
        "posts": 0,
        "mbti": "ESFJ",
        "summary": "依上傳截圖初步推斷，僅供娛樂參考。",
        "vehicle": "步行"
    }

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    # 直接導向前端 landing
    return redirect("/static/landing.html")

@app.get("/health")
def health():
    return jsonify({"status": "ok", "max_side": MAX_SIDE, "jpeg_q": JPEG_Q})

@app.get("/debug/config")
def debug_config():
    return jsonify({"ai_on": AI_ON, "max_side": MAX_SIDE, "jpeg_q": JPEG_Q})

@app.get("/debug/last_ai")
def debug_last_ai():
    return jsonify({
        "ai": _last_ai_obj,
        "raw": _last_ai_raw
    })

# 主要分析端點：接收 multipart/form-data
# - profile: 必填 1 張
# - posts: 選填多張（建議 ≤4）
@app.post("/bd/analyze")
def bd_analyze():
    global _last_ai_raw, _last_ai_obj

    try:
        # 1) 讀檔
        profile = request.files.get("profile")
        posts = request.files.getlist("posts")

        # 紀錄一下收到了幾張
        print("[/bd/analyze] incoming files:", {
            "profile": getattr(profile, "filename", None),
            "posts_count": len(posts or [])
        })

        if not profile:
            return jsonify({"ok": False, "where": "upload", "detail": "profile image is required"}), 200

        # 2) 後端保險壓縮 -> base64
        profile_b64 = compress_to_jpeg_b64(profile, MAX_SIDE, JPEG_Q)
        posts_b64 = []
        for p in (posts or [])[:4]:
            try:
                posts_b64.append(compress_to_jpeg_b64(p, MAX_SIDE, JPEG_Q))
            except Exception:
                # 單張失敗忽略，不影響整體
                pass

        # 3) 呼叫 OpenAI（可關閉）
        used_fallback = False
        ai_json_obj = None
        raw_text = ""

        if AI_ON and profile_b64:
            try:
                raw_text = call_openai_vision(profile_b64, posts_b64)
                # 預期 raw_text 是 JSON 字串（因我們用了 json_schema）
                # 但保險起見，先嘗試剝除反引號等包裝
                s = (raw_text or "").strip()
                if s.startswith("```"):
                    # 可能像 ```json ... ```
                    s = s.strip("`")
                    # 去掉可能的語言標籤行
                    if "\n" in s:
                        s = "\n".join(s.split("\n")[1:])
                ai_json_obj = json.loads(s)
            except Exception as e:
                used_fallback = True
                _last_ai_raw = f"[OpenAI failed] {e}"
                ai_json_obj = fallback_from_profile_img()
        else:
            # 沒開 AI 或沒金鑰 → fallback
            used_fallback = True
            ai_json_obj = fallback_from_profile_img()

        # 4) 最終補齊欄位與載具
        # 若缺 followers/… 等數值時，保持預設 0
        followers = int(ai_json_obj.get("followers") or 0)
        vehicle = ai_json_obj.get("vehicle") or simple_vehicle_by_followers(followers)
        ai_json_obj["vehicle"] = vehicle

        # 5) 記錄最後一次結果（除錯頁用）
        _last_ai_obj = ai_json_obj
        if not _last_ai_raw:
            _last_ai_raw = raw_text or "(empty)"

        print("[/bd/analyze] done. used_fallback:", used_fallback)

        # 6) 回傳前端
        return jsonify({"ok": True, "data": ai_json_obj}), 200

    except Exception as e:
        # 兜底錯誤
        _last_ai_raw = f"[Server error] {e}"
        _last_ai_obj = None
        return jsonify({"ok": False, "where": "server", "detail": str(e)}), 200


# 可選：讓 Flask 也能回傳 /static/* 檔案（Render 也會處理靜態檔）
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # 本地開發：python app.py
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
