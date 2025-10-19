import os
import io
import re
import json
import base64
import traceback
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from PIL import Image

# ============ Config ============
AI_ON         = os.getenv("AI_ON", "true").lower() in ("1", "true", "yes")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MAX_SIDE      = int(os.getenv("MAX_SIDE", "1280"))
JPEG_Q        = int(os.getenv("JPEG_Q", "72"))

# 建議的 Gunicorn 環境值（在 Render 的 Environment 設定）
# WEB_CONCURRENCY=1
# THREADS=1
# TIMEOUT=120

# ============ Flask ============
app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app, resources={r"/*": {"origins": "*"}})

# 供 /debug/last_ai
_LAST_AI_RAW = ""     # 原始 AI 回覆（字串）
_LAST_AI_OBJ = None   # 解析後 JSON（dict）


# ============ Utilities ============
def _pil_downscale_to_jpeg(file_storage, max_side=MAX_SIDE, jpeg_q=JPEG_Q) -> bytes:
    """
    將上傳圖縮到長邊 <= max_side，轉 JPEG，回傳 bytes。
    """
    im = Image.open(file_storage.stream).convert("RGB")
    w, h = im.size
    scale = min(1.0, float(max_side) / max(w, h))
    if scale < 1.0:
        im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=jpeg_q, optimize=True)
    buf.seek(0)
    return buf.read()


def _b64_image_uri(jpeg_bytes: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode("utf-8")


def _parse_ai_json(text: str) -> dict:
    """
    從 AI 的文字中找第一個 {...} 區塊並做 json.loads。
    允許 AI 回覆中含有 ```json ...``` 的情況。
    """
    if not text:
        return {}
    m = re.search(r'\{[\s\S]*\}', text)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def _fallback_result() -> dict:
    """
    AI 失敗或關閉時的保底輸出。
    """
    return {
        "display_name": "使用者",
        "username": "",
        "followers": 0,
        "following": 0,
        "posts": 0,
        "mbti": "ESFJ",
        "summary": "依上傳截圖初步推斷，僅供娛樂參考。",
        "vehicle": "步行",
    }


def _call_openai_vision(profile_b64: str, post_b64_list: list) -> str:
    """
    使用 OpenAI（Vision / Multimodal）做一次總結。
    回傳為純文字（我們再去剝 JSON）。
    """
    # 若沒 key 直接 raise 讓外層 fallback
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing")

    import requests

    system_prompt = (
        "你是一位社群人格分析助手。"
        "請閱讀一張 Instagram 個人頁截圖（可能另外附上 1-4 張近期貼文首圖），"
        "根據名稱、帳號、粉絲、追蹤、貼文數與版面風格，生成 JSON 物件，"
        "欄位如下：\n"
        "display_name（字串）、username（字串）、followers（整數）、"
        "following（整數）、posts（整數）、mbti（四碼大寫）、"
        "summary（80-100 字繁體中文摘要）、vehicle（步行/單車/汽車/飛行）。\n"
        "請只輸出 JSON，不要加其他說明。"
    )

    # Vision 模型（例如 gpt-4o-mini），使用 OpenAI responses API
    url = "https://api.openai.com/v1/responses"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    contents = [
        {"type": "input_text", "text": "以下是使用者的 IG 個人頁截圖。"},
        {"type": "input_image", "image_url": {"url": profile_b64}},
    ]
    if post_b64_list:
        contents.append({"type": "input_text", "text": "以下可能是 1-4 張最新貼文首圖："})
        for b in post_b64_list:
            contents.append({"type": "input_image", "image_url": {"url": b}})

    body = {
        "model": "gpt-4o-mini",
        "input": [{
            "role": "system",
            "content": [{"type": "text", "text": system_prompt}]
        }, {
            "role": "user",
            "content": contents
        }],
        # 僅需文字輸出
        "max_output_tokens": 800,
    }

    resp = requests.post(url, headers=headers, data=json.dumps(body), timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenAI HTTP {resp.status_code}: {resp.text}")

    data = resp.json()
    # OpenAI responses API 結構：data["output_text"] 或從 output[0].content 取出
    # 新版 SDK/HTTP 回傳中，有便捷的 "output_text"
    text = data.get("output_text")
    if not text:
        # 後備：嘗試從第一段內容取文字
        try:
            chunks = data["output"][0]["content"]
            text = "".join([c.get("text", "") for c in chunks if c.get("type") == "output_text"])
        except Exception:
            text = ""

    return text or ""


# ============ Routes ============
@app.get("/")
def index():
    # /static/index.html
    return send_from_directory(app.static_folder, "index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok", "max_side": MAX_SIDE, "jpeg_q": JPEG_Q})


@app.get("/debug/config")
def debug_config():
    return jsonify({"ai_on": AI_ON, "max_side": MAX_SIDE, "jpeg_q": JPEG_Q})


@app.get("/debug/last_ai")
def debug_last_ai():
    return jsonify({
        "raw": _LAST_AI_RAW,
        "ai": _LAST_AI_OBJ,
    })


@app.post("/bd/analyze")
def bd_analyze():
    global _LAST_AI_RAW, _LAST_AI_OBJ

    try:
        if "profile" not in request.files:
            return jsonify({"ok": False, "error": "profile image required"}), 400

        # 讀圖 + 壓縮
        profile_jpeg = _pil_downscale_to_jpeg(request.files["profile"])
        post_b64_list = []
        for f in request.files.getlist("posts"):
            if not f or f.filename == "":
                continue
            post_b64_list.append(_b64_image_uri(_pil_downscale_to_jpeg(f)))

        profile_b64 = _b64_image_uri(profile_jpeg)

        used_fallback = False
        ai_obj = None
        raw_text = ""

        if AI_ON and OPENAI_API_KEY:
            try:
                raw_text = _call_openai_vision(profile_b64, post_b64_list)
                ai_obj = _parse_ai_json(raw_text)
            except Exception as e:
                used_fallback = True
                raw_text = f"[OpenAI failed] {e}\n{traceback.format_exc()}"
                ai_obj = _fallback_result()
        else:
            used_fallback = True
            ai_obj = _fallback_result()
            raw_text = "[AI disabled] fallback used."

        # 存最後一次
        _LAST_AI_RAW = raw_text
        _LAST_AI_OBJ = ai_obj

        return jsonify({"ok": True, "ai": ai_obj, "used_fallback": used_fallback}), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()}), 500


# 讓 /static/* 能服務
@app.get("/<path:path>")
def static_passthrough(path):
    return send_from_directory(app.static_folder, path)


if __name__ == "__main__":
    # 本地測試
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
