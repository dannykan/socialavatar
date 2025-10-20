# app.py — clean single-route version
import os, io, base64, json
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS  # ← Add this import
from PIL import Image
import requests

# -----------------------------------------------------------------------------
# App & Config
# -----------------------------------------------------------------------------
app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)  # Enable CORS for all routes

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_SIDE = int(os.getenv("AX_IMG_SIDE", "1280"))
JPEG_Q = int(os.getenv("JPEG_QUALITY", "72"))

# -----------------------------------------------------------------------------
# Last AI buffer (for /debug/last_ai)
# -----------------------------------------------------------------------------
LAST_AI_TEXT = { "raw": "", "text": "", "ts": None }

def _set_last_ai(text: str = "", raw: str = ""):
    LAST_AI_TEXT["text"] = text or ""
    LAST_AI_TEXT["raw"]  = raw or ""
    LAST_AI_TEXT["ts"]   = datetime.now(timezone.utc).isoformat()

def save_last_ai(ai_dict=None, raw="", text=""):
    """把 AI 結果/原始回應暫存到記憶體，/debug/last_ai 會讀到"""
    s_text = text or ""
    if not s_text and ai_dict is not None:
        try:
            s_text = json.dumps(ai_dict, ensure_ascii=False)
        except Exception:
            s_text = ""
    _set_last_ai(text=s_text, raw=raw or "")

# -----------------------------------------------------------------------------
# Utils
# -----------------------------------------------------------------------------
def _pil_compress_to_b64(img: Image.Image) -> str:
    """壓縮長邊至 MAX_SIDE、存 JPEG(JPEG_Q) 為 base64"""
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > MAX_SIDE and min(w, h) > 0:
        if w >= h:
            nh = int(h * (MAX_SIDE / float(w)))
            nw = MAX_SIDE
        else:
            nw = int(w * (MAX_SIDE / float(h)))
            nh = MAX_SIDE
        img = img.resize((nw, nh), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_Q, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")

def _extract_images_from_form(form_field: str, max_files: int = 6):
    """從 multipart/form-data 取多張圖，回傳 base64 陣列"""
    out = []
    for f in request.files.getlist(form_field)[:max_files]:
        try:
            img = Image.open(f.stream)
            out.append(_pil_compress_to_b64(img))
        except Exception:
            continue
    return out

def _extract_json_block(s: str):
    """把 ```json ... ``` 或混雜文字裡第一對 { } 的 JSON 抽出來"""
    if not s: return None
    txt = s.strip()
    if txt.startswith("```"):
        nl = txt.find("\n")
        if nl > -1: txt = txt[nl+1:]
        if txt.endswith("```"): txt = txt[:-3]
    l, r = txt.find("{"), txt.rfind("}")
    if l != -1 and r != -1 and r > l:
        try: return json.loads(txt[l:r+1])
        except Exception: return None
    return None

def pick_vehicle(followers: int) -> str:
    if followers >= 1_000_000: return "太空船"
    if followers >=   100_000: return "火箭"
    if followers >=    50_000: return "飛機"
    if followers >=    10_000: return "汽車"
    if followers >=     5_000: return "機車"
    if followers >=     1_000: return "滑板車"
    if followers >=       500: return "三輪車"
    return "步行"

# -----------------------------------------------------------------------------
# OpenAI (Responses API)
# -----------------------------------------------------------------------------
def call_openai_vision(profile_b64: str, posts_b64_list: list[str]):
    """回傳：(模型輸出純文字, 完整原始回應字串)。失敗 raise RuntimeError。"""
    if not OPENAI_API_KEY:
        raise RuntimeError("No OPENAI_API_KEY configured")

    url = "https://api.openai.com/v1/responses"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    sys_prompt = (
        "你是一位社群人格分析師。請用『第一次打開 IG 個人頁』的直覺來判讀此帳號："
        "只根據個人頁可見的資料（粉絲/追蹤/貼文數、名稱、自我介紹、首屏縮圖），"
        "判斷對方的社群 MBTI 類型（如：INTP/ESFJ 等），並用自然、有個性的口吻，"
        "給一段約 200 字的分析說明（為什麼會這樣覺得）。不要用制式報表語氣。\n"
        "請務必只輸出 JSON，不要加任何註解或 Markdown 區塊。\n"
        "欄位固定為：display_name, username, followers, following, posts, mbti, summary, vehicle。"
    )

    contents = [
        {"type": "input_text",  "text": sys_prompt},
        {"type": "input_text",  "text": "以下是 IG 個人頁截圖（含數字/名稱/bio/首屏格）：" },
        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{profile_b64}"},
    ]
    for i, b64 in enumerate(posts_b64_list[:3], start=1):
        contents.append({"type": "input_text",  "text": f"貼文首圖 #{i}：" })
        contents.append({"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}"})

    payload = {
        "model": OPENAI_MODEL,
        "input": [ { "role": "user", "content": contents } ],
        "max_output_tokens": 700
    }

    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=90)
    if not resp.ok:
        raise RuntimeError(f"OpenAI HTTP {resp.status_code}: {resp.text}")

    data = resp.json()

    # 擷取 output_text
    out_text = ""
    if isinstance(data.get("output"), list):
        for msg in data["output"]:
            for c in msg.get("content", []):
                if c.get("type") in ("output_text", "text") and c.get("text"):
                    out_text += c["text"]

    if not out_text:
        # 取不到純文字時，回傳整包 JSON 讓上層寫入 /debug/last_ai 排錯
        out_text = json.dumps(data, ensure_ascii=False)

    return out_text.strip(), resp.text

# -----------------------------------------------------------------------------
# Routes （⚠️ 只宣告一次，不要重複）
# -----------------------------------------------------------------------------
@app.get("/", endpoint="home")
def serve_landing():
    return send_from_directory(app.static_folder, "landing.html")

@app.get("/health")
def health():
    return jsonify({"status": "ok", "max_side": MAX_SIDE, "jpeg_q": JPEG_Q})

@app.get("/debug/config")
def debug_config():
    return jsonify({
        "ai_on": bool(OPENAI_API_KEY),
        "has_api_key": bool(OPENAI_API_KEY),
        "model": OPENAI_MODEL,
        "max_side": MAX_SIDE,
        "jpeg_q": JPEG_Q
    })

@app.get("/debug/last_ai")
def debug_last_ai():
    return jsonify(LAST_AI_TEXT)

@app.post("/bd/analyze")
def bd_analyze():
    """
    表單欄位：
      - profile: 必填（單檔）IG 個人頁截圖
      - posts  : 可選（多檔）首屏貼文縮圖
    回傳：
      { ok, mbti, summary, username, display_name, followers, following, posts, vehicle, diagnose }
    """
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    diagnose = {
        "ai_on": bool(OPENAI_API_KEY),
        "model": OPENAI_MODEL,
        "used_fallback": False,
        "fail_reason": "",
        "posts_sent": 0,
    }

    # 1) 讀檔與驗證
    f_profile = request.files.get("profile")
    if not f_profile:
        return jsonify({"ok": False, "error": "missing_profile_image"}), 400
    
    # 檔案大小驗證
    if f_profile.content_length and f_profile.content_length > MAX_FILE_SIZE:
        return jsonify({"ok": False, "error": "file_too_large"}), 413

    try:
        img_profile = Image.open(f_profile.stream)
        profile_b64 = _pil_compress_to_b64(img_profile)
    except Exception as e:
        return jsonify({"ok": False, "error": "bad_profile_image", "detail": str(e)}), 400

    posts_b64 = _extract_images_from_form("posts", max_files=6)
    diagnose["posts_sent"] = len(posts_b64)

    # 2) OpenAI
    parsed, ai_text, raw = None, "", ""
    try:
        if OPENAI_API_KEY:
            ai_text, raw = call_openai_vision(profile_b64, posts_b64)
            parsed = _extract_json_block(ai_text)
            if not parsed:
                diagnose["fail_reason"] = "json_parse"
                diagnose["used_fallback"] = True
        else:
            raw = "[OpenAI disabled] Missing OPENAI_API_KEY"
            diagnose["fail_reason"] = "no_api_key"
            diagnose["used_fallback"] = True
    except Exception as e:
        raw = f"[OpenAI failed] {e}"
        diagnose["fail_reason"] = "openai_http"
        diagnose["used_fallback"] = True

    # 3) 組合輸出
    if not parsed:
        result = {
            "display_name": "使用者",
            "username": "",
            "followers": 0,
            "following": 0,
            "posts": 0,
            "mbti": "ESFJ",
            "summary": "依上傳截圖初步推斷，僅供娛樂參考。",
        }
    else:
        def _to_int(x):
            try: return int(x)
            except Exception: return 0
        result = {
            "display_name": str(parsed.get("display_name") or "").strip()[:100],
            "username":     str(parsed.get("username") or "").strip()[:100],
            "followers":    _to_int(parsed.get("followers")),
            "following":    _to_int(parsed.get("following")),
            "posts":        _to_int(parsed.get("posts")),
            "mbti":         str(parsed.get("mbti") or "").strip()[:10].upper(),
            "summary":      str(parsed.get("summary") or "").strip()[:600],
        }

    result["vehicle"] = pick_vehicle(result.get("followers", 0))

    # 4) 存 /debug/last_ai
    save_last_ai(ai_dict=result, raw=raw, text=ai_text)

    # 5) 回傳
    return jsonify({"ok": True, **result, "diagnose": diagnose})

# -----------------------------------------------------------------------------
# Local dev
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
