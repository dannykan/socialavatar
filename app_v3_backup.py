# app.py — IG Value Estimation System (v3)
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
# 12種IG人格類型定義（保留）
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
# 內容類型商業係數
# -----------------------------------------------------------------------------
CONTENT_TYPE_MULTIPLIERS = {
    "美妝時尚": 2.5,
    "旅遊探店": 2.0,
    "美食料理": 1.8,
    "健身運動": 1.8,
    "科技3C": 1.6,
    "親子家庭": 1.7,
    "攝影藝術": 1.5,
    "寵物萌寵": 1.5,
    "知識教育": 1.4,
    "生活風格": 1.2,
    "生活日常": 1.0,
    "個人隨拍": 0.8
}

# -----------------------------------------------------------------------------
# 身價計算工具函數
# -----------------------------------------------------------------------------
def calculate_base_price(followers):
    """根據粉絲數計算基礎身價"""
    if followers >= 100000:
        return 80000
    elif followers >= 50000:
        return 35000
    elif followers >= 10000:
        return 12000
    elif followers >= 5000:
        return 3500
    elif followers >= 1000:
        return 1200
    elif followers >= 500:
        return 600
    else:
        return 200

def get_follower_tier(followers):
    """獲取粉絲級別名稱"""
    if followers >= 100000:
        return "名人級"
    elif followers >= 50000:
        return "網紅級"
    elif followers >= 10000:
        return "意見領袖"
    elif followers >= 5000:
        return "微網紅"
    elif followers >= 1000:
        return "潛力股"
    elif followers >= 500:
        return "新星"
    else:
        return "素人"

def calculate_follower_quality_multiplier(followers, following):
    """計算粉絲品質係數"""
    if following == 0:
        return 1.0
    
    ratio = followers / following
    
    if ratio >= 3.0:
        return 1.5  # 高影響力
    elif ratio >= 1.5:
        return 1.2  # 有吸引力
    elif ratio >= 1.0:
        return 1.0  # 標準
    elif ratio >= 0.5:
        return 0.8  # 需成長
    else:
        return 0.6  # 待建立

def get_follower_quality_label(followers, following):
    """獲取粉絲品質標籤"""
    if following == 0:
        return "標準"
    
    ratio = followers / following
    
    if ratio >= 3.0:
        return "高影響力"
    elif ratio >= 1.5:
        return "有吸引力"
    elif ratio >= 1.0:
        return "標準"
    elif ratio >= 0.5:
        return "需成長"
    else:
        return "待建立"

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
            s_text = json.dumps(ai_dict, ensure_ascii=False, indent=2)
        except:
            s_text = str(ai_dict)
    _set_last_ai(text=s_text, raw=raw)

# -----------------------------------------------------------------------------
# Image Processing
# -----------------------------------------------------------------------------
def resize_and_encode_b64(pil_img: Image.Image, max_side=MAX_SIDE, quality=JPEG_Q):
    w, h = pil_img.size
    if max(w, h) > max_side:
        ratio = max_side / max(w, h)
        nw, nh = int(w * ratio), int(h * ratio)
        pil_img = pil_img.resize((nw, nh), Image.Resampling.LANCZOS)
    
    if pil_img.mode in ('RGBA', 'LA', 'P'):
        bg = Image.new('RGB', pil_img.size, (255, 255, 255))
        if pil_img.mode == 'P':
            pil_img = pil_img.convert('RGBA')
        bg.paste(pil_img, mask=pil_img.split()[-1] if pil_img.mode in ('RGBA', 'LA') else None)
        pil_img = bg
    
    buf = io.BytesIO()
    pil_img.save(buf, format='JPEG', quality=quality)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')

# -----------------------------------------------------------------------------
# OpenAI Vision API
# -----------------------------------------------------------------------------
def call_openai_vision(base64_imgs: list, user_prompt: str, system_prompt: str = ""):
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set")
    
    content_parts = []
    if user_prompt:
        content_parts.append({"type": "text", "text": user_prompt})
    
    for b64 in base64_imgs:
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
        })
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": content_parts})
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "max_tokens": 2000,
        "temperature": 0.7
    }
    
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    
    data = resp.json()
    raw_text = data["choices"][0]["message"]["content"]
    return raw_text

# -----------------------------------------------------------------------------
# System Prompt for Value Estimation
# -----------------------------------------------------------------------------
SYSTEM_PROMPT = """你是一個專業的社群媒體價值評估顧問，專門分析 Instagram 帳號的商業價值。

你的任務是：
1. 分析 IG 個人頁截圖與貼文內容
2. 評估帳號的視覺品質、內容類型、專業度等維度
3. 計算該帳號的商業價值（發文報價、Story 報價等）

請以專業、客觀的角度進行分析，同時保持友善和鼓勵的語氣。

**必須以純 JSON 格式回應，不要有任何其他文字。**"""

# -----------------------------------------------------------------------------
# User Prompt Generator
# -----------------------------------------------------------------------------
def build_user_prompt(followers, following, posts):
    return f"""請分析這個 Instagram 帳號的商業價值。

**基本數據：**
- 粉絲數：{followers:,}
- 追蹤數：{following:,}
- 貼文數：{posts:,}

**請評估以下維度（各項評分 1-10）：**

1. **視覺品質** (visual_quality)
   - color_harmony: 色彩和諧度
   - composition: 構圖專業度
   - editing: 後製品質
   - overall: 整體美感

2. **內容類型識別** (content_type)
   - primary: 主要類別（從以下選擇）
     * 美妝時尚, 旅遊探店, 美食料理, 健身運動, 科技3C
     * 親子家庭, 攝影藝術, 寵物萌寵, 知識教育, 生活風格
     * 生活日常, 個人隨拍
   - focus_score: 垂直度（1-10，專注單一領域程度）
   - commercial_potential: 商業潛力（low/medium/high/very_high）

3. **專業程度** (professionalism)
   - has_business_tag: Bio 有職業標籤（true/false）
   - has_contact: Bio 有聯絡方式（true/false）
   - has_link: 有外連（true/false）
   - consistency_score: 發文規律性（1-10）
   - brand_identity: 品牌識別度（1-10）

4. **風格獨特性** (uniqueness)
   - style_signature: 風格簽名（簡短描述，如 "極簡美食"）
   - creativity_score: 創意度（1-10）
   - differentiation: 差異化程度（1-10）

5. **12 種人格類型判定** (personality_type)
   - primary_type: 主要類型 ID（type_1 到 type_12）
   - confidence: 信心度（0.0-1.0）
   - reasoning: 判定理由（簡短說明）

可用類型：
- type_1: 夢幻柔焦系 🌸
- type_2: 藝術實驗者 🎨
- type_3: 戶外探險家 🏔️
- type_4: 知識策展人 📚
- type_5: 生活記錄者 🍜
- type_6: 質感品味家 ✨
- type_7: 幽默創作者 🎭
- type_8: 專業形象派 💼
- type_9: 永續生活者 🌿
- type_10: 次文化愛好者 🎮
- type_11: 健康積極派 💪
- type_12: 靈性探索者 🔮

6. **個性化描述** (descriptions)
   - value_statement: 價值陳述（一句話形容此帳號的商業價值，20-30字）
   - improvement_tips: 價值提升建議（陣列，3-5 個具體建議）

**必須回傳純 JSON，格式如下：**

```json
{{
  "visual_quality": {{
    "color_harmony": 8.5,
    "composition": 7.8,
    "editing": 8.2,
    "overall": 8.1
  }},
  "content_type": {{
    "primary": "美食料理",
    "focus_score": 8,
    "commercial_potential": "high"
  }},
  "professionalism": {{
    "has_business_tag": true,
    "has_contact": false,
    "has_link": true,
    "consistency_score": 7.5,
    "brand_identity": 8.0
  }},
  "uniqueness": {{
    "style_signature": "極簡美食攝影",
    "creativity_score": 7.8,
    "differentiation": 7.5
  }},
  "personality_type": {{
    "primary_type": "type_5",
    "confidence": 0.75,
    "reasoning": "以日常美食記錄為主，風格自然親切"
  }},
  "descriptions": {{
    "value_statement": "用鏡頭記錄城市角落的美味故事，溫暖親切的美食引路人",
    "improvement_tips": [
      "在 Bio 加入合作聯絡方式可提升 15% 價值",
      "增加 Reels 內容以把握當前流量紅利",
      "建立固定發文時間提高粉絲黏性",
      "嘗試與在地餐廳建立長期合作關係"
    ]
  }}
}}
```

**重要：只回傳 JSON，不要有任何其他文字或說明。**"""

# -----------------------------------------------------------------------------
# JSON Parser with Fallback
# -----------------------------------------------------------------------------
def safe_parse_json(text):
    """嘗試多種方式解析 JSON"""
    text = text.strip()
    
    # 方法 1: 直接解析
    try:
        return json.loads(text)
    except:
        pass
    
    # 方法 2: 移除 markdown code fence
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except:
            pass
    
    # 方法 3: 尋找第一個 { 到最後一個 }
    first = text.find("{")
    last = text.rfind("}")
    if first >= 0 and last > first:
        try:
            return json.loads(text[first:last+1])
        except:
            pass
    
    return None

# -----------------------------------------------------------------------------
# Calculate Final Value
# -----------------------------------------------------------------------------
def calculate_value(followers, following, ai_analysis):
    """計算最終身價"""
    
    # 1. 基礎價
    base_price = calculate_base_price(followers)
    
    # 2. 視覺品質係數
    visual = ai_analysis.get("visual_quality", {})
    visual_overall = visual.get("overall", 5.0)
    
    if visual_overall >= 9.0:
        visual_mult = 2.0
    elif visual_overall >= 7.5:
        visual_mult = 1.5
    elif visual_overall >= 6.0:
        visual_mult = 1.2
    elif visual_overall >= 4.0:
        visual_mult = 1.0
    else:
        visual_mult = 0.7
    
    # 3. 內容類型係數
    content = ai_analysis.get("content_type", {})
    primary_type = content.get("primary", "生活日常")
    content_mult = CONTENT_TYPE_MULTIPLIERS.get(primary_type, 1.0)
    
    # 4. 專業度係數
    prof = ai_analysis.get("professionalism", {})
    prof_score = (
        (1 if prof.get("has_business_tag") else 0) * 0.2 +
        (1 if prof.get("has_contact") else 0) * 0.15 +
        (1 if prof.get("has_link") else 0) * 0.15 +
        prof.get("consistency_score", 5) / 10 * 0.25 +
        prof.get("brand_identity", 5) / 10 * 0.25
    )
    prof_mult = 0.9 + prof_score  # 0.9 ~ 1.9
    
    # 5. 粉絲品質係數
    follower_mult = calculate_follower_quality_multiplier(followers, following)
    
    # 6. 風格獨特性係數
    unique = ai_analysis.get("uniqueness", {})
    creativity = unique.get("creativity_score", 5.0)
    differentiation = unique.get("differentiation", 5.0)
    unique_avg = (creativity + differentiation) / 2
    
    if unique_avg >= 8.5:
        unique_mult = 1.6
    elif unique_avg >= 7.0:
        unique_mult = 1.3
    else:
        unique_mult = 1.0
    
    # 計算最終價值
    post_value = int(base_price * visual_mult * content_mult * prof_mult * follower_mult * unique_mult)
    story_value = int(post_value * 0.4)
    reels_value = int(post_value * 1.3)
    monthly_package = int(post_value * 4)
    
    return {
        "base_price": base_price,
        "multipliers": {
            "visual": round(visual_mult, 2),
            "content": round(content_mult, 2),
            "professional": round(prof_mult, 2),
            "follower": round(follower_mult, 2),
            "unique": round(unique_mult, 2)
        },
        "post_value": post_value,
        "story_value": story_value,
        "reels_value": reels_value,
        "monthly_package": monthly_package
    }

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "landing.html")

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "model": OPENAI_MODEL,
        "ai_enabled": bool(OPENAI_API_KEY),
        "max_side": MAX_SIDE,
        "jpeg_quality": JPEG_Q
    })

@app.route("/debug/config")
def debug_config():
    return jsonify({
        "ai_on": bool(OPENAI_API_KEY),
        "model": OPENAI_MODEL,
        "max_side": MAX_SIDE,
        "jpeg_q": JPEG_Q
    })

@app.route("/debug/last_ai")
def debug_last_ai():
    return jsonify(LAST_AI_TEXT)

@app.route("/bd/analyze", methods=["POST"])
def analyze():
    """主分析端點"""
    
    # 1. 檢查 OpenAI API Key
    if not OPENAI_API_KEY:
        return jsonify({"ok": False, "error": "OpenAI API key not configured"}), 500
    
    # 2. 獲取上傳的圖片
    profile_file = request.files.get("profile")
    if not profile_file:
        return jsonify({"ok": False, "error": "未上傳 profile 截圖"}), 400
    
    try:
        profile_img = Image.open(profile_file.stream)
    except Exception as e:
        return jsonify({"ok": False, "error": f"無法讀取 profile 圖片: {str(e)}"}), 400
    
    # 3. 處理 profile 圖片
    profile_b64 = resize_and_encode_b64(profile_img, MAX_SIDE, JPEG_Q)
    
    # 4. 處理其他貼文圖片（最多 6 張）
    post_files = request.files.getlist("posts")
    post_b64_list = []
    
    for pf in post_files[:6]:
        try:
            post_img = Image.open(pf.stream)
            post_b64_list.append(resize_and_encode_b64(post_img, MAX_SIDE, JPEG_Q))
        except:
            continue
    
    # 5. 準備所有圖片
    all_images = [profile_b64] + post_b64_list
    
    # 6. 先進行基礎 OCR 分析（提取粉絲數等）
    ocr_prompt = """請從這個 Instagram 個人頁截圖中提取以下資訊：

1. 用戶名（username，不含 @）
2. 顯示名稱（display name）
3. 粉絲數（followers）
4. 追蹤數（following）
5. 貼文數（posts）

以 JSON 格式回傳：
```json
{
  "username": "user123",
  "display_name": "User Name",
  "followers": 7200,
  "following": 850,
  "posts": 342
}
```

只回傳 JSON，不要其他文字。"""
    
    try:
        ocr_result = call_openai_vision([profile_b64], ocr_prompt, "")
        ocr_data = safe_parse_json(ocr_result)
        
        if not ocr_data:
            return jsonify({"ok": False, "error": "無法解析基本資訊"}), 500
        
        username = ocr_data.get("username", "")
        display_name = ocr_data.get("display_name", "")
        followers = int(ocr_data.get("followers", 0))
        following = int(ocr_data.get("following", 0))
        posts = int(ocr_data.get("posts", 0))
        
    except Exception as e:
        return jsonify({"ok": False, "error": f"基本資訊提取失敗: {str(e)}"}), 500
    
    # 7. 進行完整的價值分析
    try:
        user_prompt = build_user_prompt(followers, following, posts)
        ai_response = call_openai_vision(all_images, user_prompt, SYSTEM_PROMPT)
        
        save_last_ai(raw=ai_response)
        
        ai_data = safe_parse_json(ai_response)
        
        if not ai_data:
            return jsonify({"ok": False, "error": "AI 回應格式錯誤"}), 500
        
    except Exception as e:
        return jsonify({"ok": False, "error": f"AI 分析失敗: {str(e)}"}), 500
    
    # 8. 計算身價
    value_result = calculate_value(followers, following, ai_data)
    
    # 9. 組裝回傳資料
    personality = ai_data.get("personality_type", {})
    primary_type_id = personality.get("primary_type", "type_5")
    primary_type_info = PERSONALITY_TYPES.get(primary_type_id, PERSONALITY_TYPES["type_5"])
    
    result = {
        "ok": True,
        
        # 基本資訊
        "username": username,
        "display_name": display_name,
        "followers": followers,
        "following": following,
        "posts": posts,
        
        # 人格類型
        "primary_type": {
            "id": primary_type_id,
            "name_zh": primary_type_info["name_zh"],
            "name_en": primary_type_info["name_en"],
            "emoji": primary_type_info["emoji"],
            "confidence": personality.get("confidence", 0.5),
            "reasoning": personality.get("reasoning", "")
        },
        
        # 身價評估
        "value_estimation": {
            "base_price": value_result["base_price"],
            "follower_tier": get_follower_tier(followers),
            "follower_quality": get_follower_quality_label(followers, following),
            "multipliers": value_result["multipliers"],
            "post_value": value_result["post_value"],
            "story_value": value_result["story_value"],
            "reels_value": value_result["reels_value"],
            "monthly_package": value_result["monthly_package"]
        },
        
        # 分析詳情
        "analysis": {
            "visual_quality": ai_data.get("visual_quality", {}),
            "content_type": ai_data.get("content_type", {}),
            "professionalism": ai_data.get("professionalism", {}),
            "uniqueness": ai_data.get("uniqueness", {})
        },
        
        # 描述
        "value_statement": ai_data.get("descriptions", {}).get("value_statement", ""),
        "improvement_tips": ai_data.get("descriptions", {}).get("improvement_tips", []),
        
        # 診斷資訊
        "diagnose": {
            "ai_on": True,
            "model": OPENAI_MODEL,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }
    
    save_last_ai(ai_dict=result)
    
    return jsonify(result)

# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)
