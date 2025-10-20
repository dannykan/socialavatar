import os
import io
import json
import base64
import logging
import tempfile
from flask import Flask, request, jsonify, send_from_directory, render_template
from PIL import Image
import requests

app = Flask(__name__, static_folder="static", template_folder="static")

# ---- 設定 ----
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
JPEG_Q = int(os.getenv("JPEG_Q", 72))
MAX_SIDE = int(os.getenv("MAX_SIDE", 1280))

# ---- 紀錄器 ----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("socialavatar")

last_ai = {"ai": None, "raw": ""}


def compress_image(file) -> str:
    """壓縮上傳圖片並轉為 base64 data URI"""
    img = Image.open(file)
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=JPEG_Q)
    data = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{data}"


def _call_openai_vision(profile_b64: str, post_b64_list: list) -> str:
    """使用 OpenAI Responses API 分析 IG 個人頁與貼文圖"""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing")

    system_prompt = (
        "你是一位社群人格分析師。請用『第一次打開 IG 個人頁』的直覺來判讀此帳號："
        "只根據個人頁可見的資料（粉絲/追蹤/貼文數、名稱、自我介紹、首屏縮圖），"
        "判斷對方的社群 MBTI 類型（四碼大寫，如 INTP、ESFJ 等；即使不確定也請選出最相近的一種），"
        "並用自然、有個性的口吻，給一段約 200 字的分析說明（為什麼會這樣覺得），"
        "不要用制式報表語氣。"
        "最終只輸出下列欄位的 JSON（不得遺漏任何欄位）："
        "{display_name, username, followers, following, posts, mbti, summary, vehicle}。"
        "其中："
        "• mbti 必須為四碼大寫（例如 ENTP、ISFJ）。"
        "• summary 介於 180–220 個中文字，口語、順暢、具畫面感。"
        "• vehicle 僅能為：步行 / 單車 / 汽車 / 飛行（依你對此人的社群節奏與調性直覺判定）。"
        "請嚴格只輸出 JSON，不要出現解說、標記、程式碼框或多餘文字。"
    )

    url = "https://api.openai.com/v1/responses"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

    contents = [
        {"type": "input_text", "text": "這是使用者的 IG 個人頁截圖。"},
        {"type": "input_image", "image_url": profile_b64},
    ]
    if post_b64_list:
        contents.append({"type": "input_text", "text": "以下是使用者的幾張貼文首圖："})
        for b in post_b64_list:
            contents.append({"type": "input_image", "image_url": b})

    body = {
        "model": "gpt-4o-mini",
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
            {"role": "user", "content": contents},
        ],
        "max_output_tokens": 800,
    }

    resp = requests.post(url, headers=headers, data=json.dumps(body), timeout=90)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenAI HTTP {resp.status_code}: {resp.text}")

    data = resp.json()
    text = data.get("output_text")
    if not text:
        try:
            chunks = data["output"][0]["content"]
            text = "".join([c.get("text", "") for c in chunks if c.get("type") == "output_text"])
        except Exception:
            text = ""
    return text or ""


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/bd/analyze", methods=["POST"])
def bd_analyze():
    logger.info("[/bd/analyze] incoming files: %s", {k: f.filename for k, f in request.files.items()})

    try:
        profile_b64 = compress_image(request.files["profile"])
        posts = [compress_image(request.files[k]) for k in request.files if k.startswith("post")]
    except Exception as e:
        return jsonify({"error": f"image processing failed: {e}"}), 500

    used_fallback = False
    try:
        raw_text = _call_openai_vision(profile_b64, posts)
        parsed = json.loads(raw_text)
    except Exception as e:
        used_fallback = True
        logger.error("[OpenAI failed] %s", e)
        parsed = {
            "display_name": "使用者",
            "username": "",
            "followers": 0,
            "following": 0,
            "posts": 0,
            "mbti": "ESFJ",
            "summary": "依上傳截圖初步推斷，僅供娛樂參考。",
            "vehicle": "步行",
        }
        raw_text = f"[OpenAI failed] {e}\n"

    last_ai.update({"ai": parsed, "raw": raw_text})
    logger.info("[/bd/analyze] done. used_fallback: %s", used_fallback)

    return jsonify({"result": parsed, "used_fallback": used_fallback})


@app.route("/debug/last_ai")
def debug_last_ai():
    return jsonify(last_ai)


@app.route("/debug/config")
def debug_config():
    return jsonify({"ai_on": bool(OPENAI_API_KEY), "jpeg_q": JPEG_Q, "max_side": MAX_SIDE})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "jpeg_q": JPEG_Q, "max_side": MAX_SIDE})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
