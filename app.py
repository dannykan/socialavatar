# app.py — Fixed version with gender support
import os, io, base64, json
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from PIL import Image
import requests

# -----------------------------------------------------------------------------
# App & Config
# -----------------------------------------------------------------------------
app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_SIDE = int(os.getenv("MAX_SIDE", "1280"))
JPEG_Q = int(os.getenv("JPEG_QUALITY", "72"))

# -----------------------------------------------------------------------------
# Last AI buffer
# -----------------------------------------------------------------------------
LAST_AI_TEXT = { "raw": "", "text": "", "ts": None }

def _set_last_ai(text: str = "", raw: str = ""):
    LAST_AI_TEXT["text"] = text or ""
    LAST_AI_TEXT["raw"]  = raw or ""
    LAST_AI_TEXT["ts"]   = datetime.now(timezone.utc).isoformat()

def save_last_ai(ai_dict=None, raw="", text=""):
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

def _extract_json_block(s: str):
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
# OpenAI
# -----------------------------------------------------------------------------
def call_openai_vision(profile_b64: str, posts_b64_list: list[str], gender: str = ""):
    if not OPENAI_API_KEY:
        raise RuntimeError("No OPENAI_API_KEY configured")

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    # 根據性別調整 prompt
    gender_context = ""
    if gender == "male":
        gender_context = "此帳號使用者為男性。"
    elif gender == "female":
        gender_context = "此帳號使用者為女性。"

    sys_prompt = (
        f"你是一位社群人格分析師。{gender_context}"
        "透過第一次打開 IG 個人頁，根據可見的資料（粉絲/追蹤/貼文數、名稱、自我介紹、提供截圖中的各個首圖縮圖），"
        "判斷對方的社群 MBTI 類型（如：INTP/ESFJ 等），並用自然、有個性的口吻，"
        "給一段約 200 字的分析說明（為什麼會這樣覺得）。不要用制式報表語氣。\n"
        "請務必只輸出 JSON，不要加任何註解或 Markdown 區塊。\n"
        "欄位固定為：display_name, username, followers, following, posts, mbti, summary。"
    )

    user_content = [
        {"type": "text", "text": "以下是 IG 個人頁截圖（含數字/名稱/bio/首屏格）："},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{profile_b64}"}}
    ]
    
    for i, b64 in enumerate(posts_b64_list[:3], start=1):
        user_content.append({"type": "text", "text": f"貼文首圖 #{i}："})
        user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content}
        ],
        "max_tokens": 700
    }

    # Try with retry mechanism
    for attempt in range(2):  # Try twice
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=90)
            if resp.ok:
                break
            if attempt == 0:  # First attempt failed
                print(f"OpenAI attempt {attempt + 1} failed: {resp.status_code}")
                continue
            else:  # Second attempt also failed
                error_detail = resp.text[:500] if resp.text else "No error details"
                raise RuntimeError(f"OpenAI HTTP {resp.status_code}: {error_detail}")
        except requests.exceptions.Timeout:
            if attempt == 0:
                print("OpenAI timeout, retrying...")
                continue
            else:
                raise RuntimeError("OpenAI request timeout after retry")
        except requests.exceptions.RequestException as e:
            if attempt == 0:
                print(f"OpenAI request error, retrying: {e}")
                continue
            else:
                raise RuntimeError(f"OpenAI request failed: {e}")

    data = resp.json()
    out_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    
    if not out_text:
        out_text = json.dumps(data, ensure_ascii=False)

    return out_text.strip(), resp.text

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/")
def serve_landing():
    return send_from_directory(app.static_folder, "landing.html")

@app.route("/health")
def health():
    return jsonify({"status": "ok", "max_side": MAX_SIDE, "jpeg_q": JPEG_Q})

@app.route("/debug/config")
def debug_config():
    return jsonify({
        "ai_on": bool(OPENAI_API_KEY),
        "has_api_key": bool(OPENAI_API_KEY),
        "model": OPENAI_MODEL,
        "max_side": MAX_SIDE,
        "jpeg_q": JPEG_Q
    })

@app.route("/debug/last_ai")
def debug_last_ai():
    return jsonify(LAST_AI_TEXT)

@app.route("/bd/analyze", methods=["POST"])
def bd_analyze():
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    diagnose = {
        "ai_on": bool(OPENAI_API_KEY),
        "model": OPENAI_MODEL,
        "used_fallback": False,
        "fail_reason": "",
        "posts_sent": 0,
    }

    # 讀取性別資料
    gender = request.form.get("gender", "").strip()
    if not gender:
        return jsonify({"ok": False, "error": "missing_gender"}), 400
    
    # 驗證性別值
    valid_genders = ["male", "female"]
    if gender not in valid_genders:
        return jsonify({"ok": False, "error": "invalid_gender"}), 400

    # Read profile image
    f_profile = request.files.get("profile")
    if not f_profile:
        return jsonify({"ok": False, "error": "missing_profile_image"}), 400

    try:
        img_profile = Image.open(f_profile.stream)
        profile_b64 = _pil_compress_to_b64(img_profile)
    except Exception as e:
        return jsonify({"ok": False, "error": "bad_profile_image", "detail": str(e)}), 400

    # Read posts (multiple files with same field name)
    posts_b64 = []
    for f in request.files.getlist("posts")[:6]:
        try:
            img = Image.open(f.stream)
            posts_b64.append(_pil_compress_to_b64(img))
        except Exception:
            continue
    
    diagnose["posts_sent"] = len(posts_b64)

    # Call OpenAI with gender
    parsed, ai_text, raw = None, "", ""
    try:
        if OPENAI_API_KEY:
            ai_text, raw = call_openai_vision(profile_b64, posts_b64, gender)
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

    # Build result
    if not parsed:
        result = {
            "display_name": "使用者",
            "username": "",
            "followers": 0,
            "following": 0,
            "posts": 0,
            "mbti": "ESFJ",
            "summary": "依上傳截圖初步推斷，僅供娛樂參考。",
            "gender": gender,
        }
    else:
        def _to_int(x):
            try: return int(x)
            except Exception: return 0
        result = {
            "display_name": str(parsed.get("display_name") or "").strip()[:100],
            "username": str(parsed.get("username") or "").strip()[:100],
            "followers": _to_int(parsed.get("followers")),
            "following": _to_int(parsed.get("following")),
            "posts": _to_int(parsed.get("posts")),
            "mbti": str(parsed.get("mbti") or "").strip()[:10].upper(),
            "summary": str(parsed.get("summary") or "").strip()[:600],
            "gender": gender,
        }

    result["vehicle"] = pick_vehicle(result.get("followers", 0))
    save_last_ai(ai_dict=result, raw=raw, text=ai_text)

    return jsonify({"ok": True, **result, "diagnose": diagnose})

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
