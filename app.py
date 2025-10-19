# app.py
import os, io, re, json, base64
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from PIL import Image

# ---------- 基本設定 ----------
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_SIDE = int(os.getenv("MAX_IMG_SIDE", "1280"))      # 後端縮圖最長邊
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "72"))    # 後端 JPEG 轉檔畫質
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Flask
app = Flask(__name__, static_folder="static", static_url_path="/")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB 上限
CORS(app, resources={r"/*": {"origins": "*"}})

# 最近一次 AI 文字（debug 用）
_last_ai = {"text": ""}

# ---------- 工具：dataURL -> Pillow Image、縮圖、存檔 ----------
_dataurl_re = re.compile(r"^data:(?P<mime>[^;]+);base64,(?P<b64>.+)$", re.I)

def decode_data_url_to_image(data_url: str) -> Image.Image:
    m = _dataurl_re.match(data_url or "")
    if not m:
        raise ValueError("Invalid data URL")
    raw = base64.b64decode(m.group("b64"))
    im = Image.open(io.BytesIO(raw))
    return im

def save_file_from_data_url(data_url: str, filename_prefix: str) -> str:
    im = decode_data_url_to_image(data_url)
    im = im.convert("RGB")
    w, h = im.size
    scale = min(1.0, MAX_SIDE / max(w, h))
    if scale < 1:
        im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    fname = f"{filename_prefix}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.jpg"
    fpath = os.path.join(UPLOAD_DIR, fname)
    im.save(fpath, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return fpath

def to_raw_b64_from_dataurl(data_url: str) -> str:
    m = _dataurl_re.match(data_url or "")
    if not m:
        return ""
    return m.group("b64")

# ---------- Heuristic MBTI（保底） ----------
def heuristic_mbti(summary_hint: str = ""):
    """
    非嚴謹：根據簡單字詞/提示給一個 MBTI、和 100 字內說明。
    """
    text = (summary_hint or "").lower()
    score_e = 1 if any(k in text for k in ["旅", "展演", "派對", "event", "travel"]) else 0
    score_n = 1 if any(k in text for k in ["概念", "創作", "design", "vision"]) else 0
    score_t = 1 if any(k in text for k in ["分析", "研究", "engineer", "數據"]) else 0
    score_p = 1 if any(k in text for k in ["隨性", "vlog", "日常", "動態"]) else 0

    E = "E" if score_e else "I"
    N = "N" if score_n else "S"
    T = "T" if score_t else "F"
    P = "P" if score_p else "J"
    mbti = f"{E}{N}{T}{P}"

    reason = (
        "根據截圖中呈現的關鍵元素與風格，推斷此帳號偏向 "
        f"{mbti}。內容呈現與互動線索顯示其社交取向、思維傾向與表達方式；"
        "此結果僅供娛樂參考。"
    )
    return mbti, reason[:100]

# ---------- OpenAI（可選） ----------
def call_openai_summary(profile_b64: str, posts_b64: list, mbti_hint: str = "") -> str:
    """
    使用多圖 + 系統提示請模型輸出 80~100 字中文摘要。
    需要環境變數 OPENAI_API_KEY；失敗就拋出例外，外層會 fallback。
    """
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    content = [
        {"type": "text", "text":
            "你是一位社群觀察員。根據以下 Instagram 個人頁截圖與數張貼文首圖，"
            "輸出 80~100 字中文摘要，描述此帳號的社群個性與風格；"
            "語氣自然、正向、中立，不要帶貶義、不評判；不要加標題或列表。"}
    ]
    # 個人頁
    content.append({"type":"input_image","image_url":{"url":"data:image/jpeg;base64,"+profile_b64}})
    # 貼文最多 3~4 張即可
    for b64 in (posts_b64 or [])[:4]:
        content.append({"type":"input_image","image_url":{"url":"data:image/jpeg;base64,"+b64}})

    # 可加 MBTI 提示，但不要讓模型只回 MBTI
    if mbti_hint:
        content.append({"type":"text","text":f"可參考 MBTI 提示：{mbti_hint}，但仍以圖片為主輸出摘要。"})

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":content}],
        temperature=0.6,
        max_tokens=220
    )
    text = (resp.choices[0].message.content or "").strip()
    return text[:120]

# ---------- API ----------
@app.post("/api/analyze")
def api_analyze():
    try:
        body = request.get_json(silent=True) or {}
        profile = body.get("profile_screenshot")
        posts = (body.get("post_images") or [])[:4]
        username_input = (body.get("username_input") or "").strip()

        if not profile:
            return jsonify({"ok": False, "error": "profile screenshot missing"}), 400

        # 先存成壓縮後 JPEG（可用於除錯、日後溯源）
        profile_path = save_file_from_data_url(profile, "profile")
        post_paths = []
        for i, p in enumerate(posts):
            try:
                post_paths.append(save_file_from_data_url(p, f"post{i+1}"))
            except Exception:
                pass

        # Heuristic 先給一個 MBTI 與 100字內說明（AI 失敗時會用）
        mbti_guess, reason = heuristic_mbti(username_input)

        # 有 OpenAI 就嘗試多圖分析 → 覆蓋 reason
        if OPENAI_API_KEY:
            try:
                prof_b64 = to_raw_b64_from_dataurl(profile)
                posts_b64 = [to_raw_b64_from_dataurl(p) for p in posts if p]
                ai_text = call_openai_summary(prof_b64, posts_b64, mbti_guess)
                if ai_text:
                    reason = ai_text[:120]
                    _last_ai["text"] = reason
            except Exception as e:
                # 不中斷，回 fallback
                _last_ai["text"] = f"(AI失敗，fallback) {e}"

        data = {
            "display_name": (username_input or "用戶"),
            "username": "",  # 若未做 OCR/解析，可留空
            "followers": None,
            "following": None,
            "posts": None,
            "mbti": mbti_guess,
            "reason": reason,
            "vehicle": "步行"  # 你的載具分級邏輯可自行放入
        }
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/debug/last_ai")
def debug_last_ai():
    return jsonify(_last_ai)

# 靜態頁（首頁就是 index.html）
@app.get("/")
def root():
    return app.send_static_file("index.html")

# Render 健康檢查
@app.get("/health")
def health():
    return jsonify({"status":"ok","max_side":MAX_SIDE,"jpeg_q":JPEG_QUALITY})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","10000")), debug=True)
