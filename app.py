# app.py
import os
import io
import json
import base64
from datetime import datetime

from flask import Flask, request, jsonify, redirect, send_from_directory

# =========================
# Globals & Config
# =========================
app = Flask(__name__)

# 給前端讀的最新 AI 輸出（/debug/last_ai）
LAST_AI_TEXT = {"raw": "", "text": "", "ai": None}

OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
AI_ON = os.getenv("AI_ON", "1").lower() in ("1", "true", "yes")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")

# 圖片壓縮參數
MAX_SIDE = int(os.getenv("MAX_SIDE", "1280"))
JPEG_Q = int(os.getenv("JPEG_Q", "72"))

# =========================
# Utilities
# =========================
def _pil_compress_to_b64(file_storage, max_side=MAX_SIDE, jpeg_q=JPEG_Q) -> str:
    """
    讀取上傳檔案 → 壓縮縮邊 → 轉 JPEG → 回傳 base64 字串（不含 data: 前綴）
    """
    from PIL import Image, ImageOps

    im = Image.open(file_storage.stream).convert("RGB")
    w, h = im.size
    scale = min(1.0, float(max_side) / float(max(w, h)))
    if scale < 1.0:
        new_w, new_h = int(w * scale), int(h * scale)
        im = im.resize((new_w, new_h), Image.LANCZOS)

    # 去除奇怪的 EXIF 方向
    im = ImageOps.exif_transpose(im)

    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=jpeg_q, optimize=True)
    b = buf.getvalue()
    return base64.b64encode(b).decode("utf-8")


def _fallback_summary() -> dict:
    """
    OpenAI 失敗時的保底輸出。
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


def _parse_model_text_to_ai(text: str) -> dict:
    """
    嘗試把模型輸出的文字解析成我們需要的欄位。
    期待是 JSON，若不是就盡力抽取。
    """
    ai = _fallback_summary()
    if not text:
        return ai
    # 試著找出最像 JSON 的片段
    raw = text.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(raw[start : end + 1])
            # 合併
            for k in ("display_name", "username", "mbti", "summary", "vehicle"):
                if k in data and isinstance(data[k], str):
                    ai[k] = data[k]
            for k in ("followers", "following", "posts"):
                if k in data:
                    try:
                        ai[k] = int(data[k])
                    except Exception:
                        pass
            # 正規化 MBTI
            if isinstance(ai["mbti"], str):
                ai["mbti"] = ai["mbti"].strip().upper()
        except Exception:
            # 不是 JSON 就當純文字塞進 summary
            ai["summary"] = raw[:400]
    else:
        ai["summary"] = raw[:400]

    # vehicle 安全值
    if not ai.get("vehicle"):
        ai["vehicle"] = "步行"
    return ai


def _call_openai_vision(profile_b64: str, posts_b64: list[str]) -> str:
    """
    呼叫 OpenAI Responses API（Vision），傳入：1 張個人頁 + 最多 4 張首圖。
    回傳模型輸出的「純文字」。
    """
    import requests

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing")

    prompt = (
        "你是一位社群人格分析師。請用『第一次打開 IG 個人頁』的直覺來判讀此帳號："
        "只根據個人頁可見的資料（粉絲/追蹤/貼文數、名稱、自我介紹、首屏縮圖），"
        "判斷對方的社群 MBTI 類型（如：INTP/ESFJ 等），並用自然、有個性的口吻，"
        "給一段約 200 字的分析說明（為什麼會這樣覺得）。不要用制式報表語氣。"
        "若無法判斷，請誠實說明不確定並給出可能的類型與理由。"
        "請以 JSON 回覆："
        "{\"display_name\":\"...\",\"username\":\"...\",\"followers\":數字,"
        "\"following\":數字,\"posts\":數字,\"mbti\":\"...\",\"summary\":\"...\",\"vehicle\":\"...\"}"
    )

    content = [
        {"type": "input_text", "text": prompt},
        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{profile_b64}"},
    ]
    for b in (posts_b64 or [])[:4]:
        content.append({"type": "input_image", "image_url": f"data:image/jpeg;base64,{b}"})

    body = {
        "model": OPENAI_VISION_MODEL,
        "input": [{"role": "user", "content": content}],
        "max_output_tokens": 700,
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(
        "https://api.openai.com/v1/responses",
        headers=headers,
        data=json.dumps(body),
        timeout=60,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"OpenAI HTTP {resp.status_code}: {resp.text}")

    data = resp.json()

    # 優先解析 Responses API 的 output 陣列
    out_text = ""
    if isinstance(data.get("output"), list):
        for item in data["output"]:
            if isinstance(item, dict) and item.get("type") == "output_text":
                out_text += item.get("content", "")

    # 備援
    if not out_text:
        out_text = data.get("output_text", "") or \
                   (data.get("choices", [{}])[0].get("message", {}).get("content", ""))

    return out_text.strip()


# =========================
# Routes
# =========================
@app.get("/")
def root():
    # 首頁導向到 landing
    return redirect("/static/landing.html", code=302)


@app.get("/health")
def health():
    return jsonify({"status": "ok", "max_side": MAX_SIDE, "jpeg_q": JPEG_Q})


@app.get("/debug/config")
def debug_config():
    return jsonify({"ai_on": AI_ON, "max_side": MAX_SIDE, "jpeg_q": JPEG_Q})


@app.get("/debug/last_ai")
def debug_last_ai():
    # 提供最後一次 AI 原始文字 + 解析後 ai
    return jsonify({
        "raw": LAST_AI_TEXT.get("raw", ""),
        "text": LAST_AI_TEXT.get("text", ""),
        "ai": LAST_AI_TEXT.get("ai", None),
        "ts": datetime.utcnow().isoformat() + "Z",
    })


@app.post("/bd/analyze")
def bd_analyze():
    """
    表單欄位：
    - profile: 必填，單檔（個人頁截圖）
    - posts:   選填，多檔（最多 4 張首圖）
    """
    try:
        if "profile" not in request.files:
            return jsonify({"ok": False, "error": "missing profile"}), 400

        profile_file = request.files["profile"]
        posts_files = request.files.getlist("posts")[:4] if "posts" in request.files else []

        # 先壓縮成 base64
        try:
            profile_b64 = _pil_compress_to_b64(profile_file)
        except Exception as e:
            return jsonify({"ok": False, "error": f"profile compress failed: {e}"}), 400

        posts_b64 = []
        for pf in posts_files:
            try:
                posts_b64.append(_pil_compress_to_b64(pf))
            except Exception:
                # 單張失敗就略過
                pass

        # 是否啟用 OpenAI
        diagnose = []
        if not AI_ON:
            diagnose.append("AI_ON disabled")
        if not OPENAI_API_KEY:
            diagnose.append("OPENAI_API_KEY missing")
        use_openai = AI_ON and bool(OPENAI_API_KEY)

        raw_text = ""
        used_fallback = False

        if use_openai:
            try:
                raw_text = _call_openai_vision(profile_b64, posts_b64)
            except Exception as e:
                raw_text = f"[OpenAI failed] {e}"
                used_fallback = True
        else:
            raw_text = "[OpenAI skipped] " + ("; ".join(diagnose) or "unknown reason")
            used_fallback = True

        # 解析成 ai 物件
        ai_obj = _parse_model_text_to_ai(raw_text)
        LAST_AI_TEXT["raw"] = (raw_text or "")[:4000]
        LAST_AI_TEXT["text"] = LAST_AI_TEXT["raw"]  # 目前 text 與 raw 同步
        LAST_AI_TEXT["ai"] = ai_obj

        return jsonify({
            "ok": True,
            "used_fallback": used_fallback,
            "ai": ai_obj,
            "diagnose": {
                "ai_on": AI_ON,
                "has_api_key": bool(OPENAI_API_KEY),
                "model": OPENAI_VISION_MODEL,
                "posts_sent": len(posts_b64),
            }
        })

    except Exception as e:
        # 保險：任何例外都回傳安全訊息
        LAST_AI_TEXT["raw"] = f"(server error) {e}"
        LAST_AI_TEXT["text"] = ""
        LAST_AI_TEXT["ai"] = None
        return jsonify({"ok": False, "error": "server error"}), 500


# 讓你可以直接以 /static/... 讀取靜態頁（Render 也會自己處理）
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


if __name__ == "__main__":
    # 本地測試
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")), debug=True)
