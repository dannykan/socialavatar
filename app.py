# app.py — IG Personality Type Analysis (v2)
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
# 12種IG人格類型定義
# -----------------------------------------------------------------------------
PERSONALITY_TYPES = {
    "type_1": {"name_zh": "夢幻柔焦系", "name_en": "Dreamy Aesthetic", "emoji": "🌸"},
    "type_2": {"name_zh": "藝術實驗者", "name_en": "Artistic Experimenter", "emoji": "🎨"},
    "type_3": {"name_zh": "戶外探險家", "name_en": "Outdoor Adventurer", "emoji": "🏔️"},
    "type_4": {"name_zh": "知識策展人", "name_en": "Knowledge Curator", "emoji": "📚"},
    "type_5": {"name_zh": "生活記錄者", "name_en": "Everyday Chronicler", "emoji": "🍜"},
    "type_6": {"name_zh": "質感品味家", "name_en": "Refined Aesthete", "emoji": "✨"},
    "type_7": {"name_zh": "幽默創作者", "name_en": "Humor Creator", "emoji": "🎭"},
    "type_8": {"name_zh": "專業形象派", "name_en": "Professional Persona", "emoji": "💼"},
    "type_9": {"name_zh": "永續生活者", "name_en": "Sustainable Liver", "emoji": "🌿"},
    "type_10": {"name_zh": "次文化愛好者", "name_en": "Subculture Enthusiast", "emoji": "🎮"},
    "type_11": {"name_zh": "健康積極派", "name_en": "Fitness Motivator", "emoji": "💪"},
    "type_12": {"name_zh": "靈性探索者", "name_en": "Spiritual Seeker", "emoji": "🔮"}
}

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

# -----------------------------------------------------------------------------
# OpenAI Vision API Call with New Prompt
# -----------------------------------------------------------------------------
def call_openai_vision(profile_b64: str, posts_b64_list: list[str]):
    if not OPENAI_API_KEY:
        raise RuntimeError("No OPENAI_API_KEY configured")

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    sys_prompt = """你是專業的 Instagram 社群風格分析師。

根據用戶提供的 IG 個人頁截圖和貼文縮圖，判斷該帳號屬於以下 12 種人格類型中的哪一種（或雙重類型）：

**12種類型定義：**

1. 🌸 type_1: 夢幻柔焦系 - 粉色系/柔焦/浪漫/溫柔emoji多
2. 🎨 type_2: 藝術實驗者 - 高對比/黑白/概念照/極簡bio
3. 🏔️ type_3: 戶外探險家 - 自然景觀/旅行/運動/定位多
4. 📚 type_4: 知識策展人 - 書籍/infographic/專業標籤/外連
5. 🍜 type_5: 生活記錄者 - 無濾鏡/日常/真實/口語bio
6. ✨ type_6: 質感品味家 - 莫蘭迪色/極簡/設計物/精品
7. 🎭 type_7: 幽默創作者 - meme風/明亮多彩/搞笑/梗多
8. 💼 type_8: 專業形象派 - 商務正式/演講/作品集/職稱
9. 🌿 type_9: 永續生活者 - 大地色/環保/手作/理念
10. 🎮 type_10: 次文化愛好者 - 霓虹色/動漫遊戲/cosplay/黑話
11. 💪 type_11: 健康積極派 - 運動場景/健身/激勵/數據
12. 🔮 type_12: 靈性探索者 - 神秘紫/占星/冥想/哲學

**分析維度（權重）：**
1. 視覺風格 (40%): 色調、濾鏡、構圖、元素
2. Bio語氣 (25%): 語言風格、emoji使用、符號特徵
3. 內容主題 (25%): 主要發布內容類型
4. 整體氛圍 (10%): 專業vs隨性、內向vs外向

**輸出規則：**
- 信心度 ≥ 75%: 單一類型
- 65% ≤ 信心度 < 75% 且次要 > 55%: 雙重類型
- 信心度 < 65%: 使用 "mixed" 類型

請只輸出 JSON（不要任何註解或 Markdown）：
{
  "primary_type": {
    "id": "type_X",
    "confidence": 0.85
  },
  "secondary_type": {
    "id": "type_Y",
    "confidence": 0.62
  },
  "analysis": {
    "color_palette": ["#FFB6C1", "#F5F5DC", "#FFC0CB"],
    "visual_style": "柔焦、高曝光、留白多",
    "bio_tone": "溫柔詩意,使用大量emoji",
    "content_theme": "以自拍和咖啡廳場景為主",
    "unique_traits": ["復古膠片感濾鏡", "常出現花朵元素", "粉紫色系"]
  },
  "personality_statement": "用足跡串聯世界的角落,在旅程與日常間記錄值得珍藏的時刻",
  "display_name": "使用者名稱",
  "username": "帳號名",
  "followers": 10100,
  "following": 909,
  "posts": 181
}
"""

    user_content = [
        {"type": "text", "text": "以下是 IG 個人頁截圖（含bio/粉絲數/首頁格）："},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{profile_b64}"}}
    ]
    
    for i, b64 in enumerate(posts_b64_list[:6], start=1):
        user_content.append({"type": "text", "text": f"貼文首圖 #{i}："})
        user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content}
        ],
        "max_tokens": 1000
    }

    # Try with retry mechanism
    for attempt in range(2):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=90)
            if resp.ok:
                break
            if attempt == 0:
                print(f"OpenAI attempt {attempt + 1} failed: {resp.status_code}")
                continue
            else:
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

    # Read profile image
    f_profile = request.files.get("profile")
    if not f_profile:
        return jsonify({"ok": False, "error": "missing_profile_image"}), 400

    try:
        img_profile = Image.open(f_profile.stream)
        profile_b64 = _pil_compress_to_b64(img_profile)
    except Exception as e:
        return jsonify({"ok": False, "error": "bad_profile_image", "detail": str(e)}), 400

    # Read posts
    posts_b64 = []
    for f in request.files.getlist("posts")[:6]:
        try:
            img = Image.open(f.stream)
            posts_b64.append(_pil_compress_to_b64(img))
        except Exception:
            continue
    
    diagnose["posts_sent"] = len(posts_b64)

    # Call OpenAI
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

    # Build result
    if not parsed:
        result = {
            "primary_type": {
                "id": "type_5",
                "name_zh": "生活記錄者",
                "name_en": "Everyday Chronicler",
                "emoji": "🍜",
                "confidence": 0.50
            },
            "secondary_type": None,
            "analysis": {
                "color_palette": ["#E67E22", "#F39C12", "#D35400"],
                "visual_style": "自然隨性",
                "bio_tone": "口語親切",
                "content_theme": "日常記錄",
                "unique_traits": ["真實", "生活感"]
            },
            "personality_statement": "依上傳截圖初步推斷，僅供娛樂參考。",
            "display_name": "使用者",
            "username": "",
            "followers": 0,
            "following": 0,
            "posts": 0
        }
    else:
        def _safe_get_type_info(type_id):
            if type_id in PERSONALITY_TYPES:
                return PERSONALITY_TYPES[type_id]
            return {"name_zh": "混合型", "name_en": "Mixed Type", "emoji": "🦄"}
        
        primary_id = parsed.get("primary_type", {}).get("id", "type_5")
        primary_info = _safe_get_type_info(primary_id)
        
        secondary_id = parsed.get("secondary_type", {}).get("id") if parsed.get("secondary_type") else None
        secondary_info = _safe_get_type_info(secondary_id) if secondary_id else None
        
        def _to_int(x):
            try: return int(x)
            except Exception: return 0
        
        result = {
            "primary_type": {
                "id": primary_id,
                "name_zh": primary_info["name_zh"],
                "name_en": primary_info["name_en"],
                "emoji": primary_info["emoji"],
                "confidence": float(parsed.get("primary_type", {}).get("confidence", 0.5))
            },
            "secondary_type": {
                "id": secondary_id,
                "name_zh": secondary_info["name_zh"] if secondary_info else None,
                "name_en": secondary_info["name_en"] if secondary_info else None,
                "emoji": secondary_info["emoji"] if secondary_info else None,
                "confidence": float(parsed.get("secondary_type", {}).get("confidence", 0))
            } if secondary_id else None,
            "analysis": {
                "color_palette": parsed.get("analysis", {}).get("color_palette", []),
                "visual_style": parsed.get("analysis", {}).get("visual_style", ""),
                "bio_tone": parsed.get("analysis", {}).get("bio_tone", ""),
                "content_theme": parsed.get("analysis", {}).get("content_theme", ""),
                "unique_traits": parsed.get("analysis", {}).get("unique_traits", [])
            },
            "personality_statement": str(parsed.get("personality_statement", "")).strip()[:300],
            "display_name": str(parsed.get("display_name") or "").strip()[:100],
            "username": str(parsed.get("username") or "").strip()[:100],
            "followers": _to_int(parsed.get("followers")),
            "following": _to_int(parsed.get("following")),
            "posts": _to_int(parsed.get("posts"))
        }

    save_last_ai(ai_dict=result, raw=raw, text=ai_text)

    return jsonify({"ok": True, **result, "diagnose": diagnose})

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
