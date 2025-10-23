# app_v5.py — IG Value Estimation System (v5) with Open-Ended Analysis
import os, io, base64, json, re
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
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")  # 建議用 gpt-4o 獲得更好分析
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
# 工具函數
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
        return 1.5
    elif ratio >= 1.5:
        return 1.2
    elif ratio >= 1.0:
        return 1.0
    elif ratio >= 0.5:
        return 0.8
    else:
        return 0.6

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
# JSON Parsing（新增：從自然語言中提取 JSON）
# -----------------------------------------------------------------------------
def extract_json_from_text(text: str):
    """從包含自然語言的文本中提取 JSON"""
    # 先嘗試找 ```json ``` 包裹的內容
    json_pattern = r'```json\s*(\{.*?\})\s*```'
    match = re.search(json_pattern, text, re.DOTALL)
    
    if match:
        json_str = match.group(1)
        try:
            return json.loads(json_str)
        except:
            pass
    
    # 再嘗試找任何 {...} 的內容
    json_pattern2 = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(json_pattern2, text, re.DOTALL)
    
    # 從最長的開始嘗試解析
    for json_str in sorted(matches, key=len, reverse=True):
        try:
            data = json.loads(json_str)
            # 驗證是否包含我們需要的關鍵字段
            if 'account_value' in data or 'visual_quality' in data:
                return data
        except:
            continue
    
    return None

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
        "max_tokens": 3000,
        "temperature": 0.7
    }
    
    resp = requests.post(url, headers=headers, json=payload, timeout=90)
    resp.raise_for_status()
    
    data = resp.json()
    raw_text = data["choices"][0]["message"]["content"]
    return raw_text

# -----------------------------------------------------------------------------
# System Prompt for Value Estimation (V5 - 開放式分析)
# -----------------------------------------------------------------------------
SYSTEM_PROMPT = """你是一個專業的 Instagram 帳號估值專家，擅長評估帳號的市場價值和商業潛力。

你的任務是深入分析這個 IG 帳號，回答以下問題：

**核心問題：這個 IG 帳號如果要賣掉，市場價格是多少？為什麼？**

請從以下角度分析：
1. 粉絲質量與互動潛力
2. 內容風格與主題定位
3. 視覺品質與專業度
4. 品牌合作潛力
5. 特殊加分項（藍勾、海外背景、專業身份等）
6. 可改進之處

請用自然、專業的口吻分析，就像你是一個經驗豐富的 KOL 經紀人在評估帳號。

**分析完後，在最後提供結構化的 JSON 數據。**"""

# -----------------------------------------------------------------------------
# User Prompt Generator (V5 - 開放式分析)
# -----------------------------------------------------------------------------
def build_user_prompt(followers, following, posts):
    return f"""請分析這個 Instagram 帳號的商業價值。

**基本數據：**
- 粉絲數：{followers:,}
- 追蹤數：{following:,}
- 貼文數：{posts:,}

**請完成以下任務：**

1. **寫一段專業的估值分析**（2-3段），回答：
   - 這個帳號如果要賣掉，市場價格大概多少？為什麼？
   - 粉絲質量如何？內容風格如何？
   - 適合什麼品牌合作？
   - 有什麼特別的加分項？

2. **在分析文字後面，提供以下 JSON 數據：**

```json
{{
  "account_value": {{
    "min": 50000,
    "max": 80000,
    "reasoning": "簡短說明估值邏輯（1-2句話）"
  }},
  "pricing": {{
    "post": 8000,
    "story": 3200,
    "reels": 12000
  }},
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
  "engagement_potential": {{
    "has_cta_in_bio": true,
    "emoji_density": 7.0,
    "selfie_ratio": 0.6,
    "content_discussability": 8.0
  }},
  "niche_focus": {{
    "theme_consistency": 8.5,
    "has_professional_keyword": true,
    "vertical_depth": 8.0
  }},
  "audience_value": {{
    "audience_tier": "美食料理",
    "engagement_quality": 7.5,
    "target_precision": 8.0
  }},
  "cross_platform": {{
    "has_youtube": false,
    "has_tiktok": false,
    "has_blog": true,
    "has_other_social": false,
    "content_reusability": 7.0
  }},
  "personality_type": {{
    "primary_type": "type_5",
    "confidence": 0.75,
    "reasoning": "以日常美食記錄為主，風格自然親切"
  }},
  "improvement_tips": [
    "增加與粉絲互動的 Story 內容",
    "建立固定發文時段提升粉絲黏性",
    "嘗試加入簡短的美食小知識"
  ]
}}
```

可用人格類型：
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

**記得：先寫分析文字，再附上 JSON。**"""

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
        "version": "v5",
        "model": OPENAI_MODEL,
        "ai_enabled": bool(OPENAI_API_KEY),
        "max_side": MAX_SIDE,
        "jpeg_quality": JPEG_Q,
        "new_features": [
            "open_ended_analysis",
            "natural_language_valuation",
            "contextual_reasoning"
        ]
    })

@app.route("/debug/config")
def debug_config():
    return jsonify({
        "ai_on": bool(OPENAI_API_KEY),
        "model": OPENAI_MODEL,
        "max_side": MAX_SIDE,
        "jpeg_q": JPEG_Q,
        "version": "v5"
    })

@app.route("/debug/last_ai")
def debug_last_ai():
    return jsonify(LAST_AI_TEXT)

@app.route("/bd/analyze", methods=["POST"])
def analyze():
    """主分析端點（V5 - 開放式分析）"""
    
    # 1. 檢查 OpenAI API Key
    if not OPENAI_API_KEY:
        return jsonify({"ok": False, "error": "OpenAI API key not configured"}), 500
    
    # 2. 獲取上傳的圖片
    profile_file = request.files.get("profile")
    if not profile_file:
        return jsonify({"ok": False, "error": "請上傳 IG 個人頁截圖。請確保截圖包含用戶名、粉絲數、追蹤數、貼文數等完整資訊。"}), 400
    
    try:
        profile_img = Image.open(profile_file.stream)
    except Exception as e:
        return jsonify({"ok": False, "error": "圖片格式不支援，請上傳 JPG 或 PNG 格式的截圖。"}), 400
    
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
        ocr_data = extract_json_from_text(ocr_result)
        
        if not ocr_data:
            return jsonify({"ok": False, "error": "無法從截圖中讀取 IG 資訊。請確保截圖清晰且包含完整的個人頁面資訊（用戶名、粉絲數、追蹤數、貼文數）。"}), 400
        
        username = ocr_data.get("username", "")
        display_name = ocr_data.get("display_name", "")
        followers = int(ocr_data.get("followers", 0))
        following = int(ocr_data.get("following", 0))
        posts = int(ocr_data.get("posts", 0))
        
    except Exception as e:
        return jsonify({"ok": False, "error": "截圖解析失敗。請確保上傳的是清晰的 IG 個人頁截圖，包含完整的用戶資訊。"}), 400
    
    # 7. 進行完整的開放式價值分析（V5 - 新方法）
    try:
        user_prompt = build_user_prompt(followers, following, posts)
        ai_response = call_openai_vision(all_images, user_prompt, SYSTEM_PROMPT)
        
        save_last_ai(raw=ai_response)
        
        # 從自然語言回答中提取 JSON 數據
        ai_data = extract_json_from_text(ai_response)
        
        if not ai_data:
            return jsonify({"ok": False, "error": "AI 分析結果格式錯誤。請重新上傳截圖並重試。"}), 500
        
        # 提取分析文字（JSON 之前的部分）
        json_start = ai_response.find('{')
        analysis_text = ai_response[:json_start].strip() if json_start > 0 else ""
        
        # 清理可能的程式碼殘留
        if analysis_text:
            # 移除可能的 markdown 程式碼標記
            analysis_text = analysis_text.replace('```json', '').replace('```', '')
            # 移除多餘的空白行
            analysis_text = '\n\n'.join([p.strip() for p in analysis_text.split('\n\n') if p.strip()])
        
    except Exception as e:
        return jsonify({"ok": False, "error": "AI 分析服務暫時無法使用。請稍後再試，或檢查截圖是否清晰完整。"}), 500
    
    # 8. 計算係數（用於前端顯示）
    def calc_multiplier(data, key, default=1.0):
        """從 AI 數據計算係數"""
        section = ai_data.get(key, {})
        if not section:
            return default
        
        # 根據不同維度計算
        if key == "visual_quality":
            return section.get("overall", 5.0) / 5.0
        elif key == "content_type":
            content_map = {
                "美妝時尚": 2.5, "旅遊探店": 2.0, "美食料理": 1.8,
                "健身運動": 1.8, "科技3C": 1.6, "親子家庭": 1.7,
                "攝影藝術": 1.5, "寵物萌寵": 1.5, "知識教育": 1.4,
                "生活風格": 1.2, "生活日常": 1.0, "個人隨拍": 0.8
            }
            return content_map.get(section.get("primary", "生活日常"), 1.0)
        elif key == "professionalism":
            score = (
                (1 if section.get("has_business_tag") else 0) * 0.2 +
                (1 if section.get("has_contact") else 0) * 0.15 +
                (1 if section.get("has_link") else 0) * 0.15 +
                section.get("consistency_score", 5) / 10 * 0.25 +
                section.get("brand_identity", 5) / 10 * 0.25
            )
            return 0.9 + score
        elif key == "uniqueness":
            creativity = section.get("creativity_score", 5.0)
            diff = section.get("differentiation", 5.0)
            avg = (creativity + diff) / 2
            if avg >= 8.5: return 1.6
            elif avg >= 7.0: return 1.3
            else: return 1.0
        elif key in ["engagement_potential", "niche_focus", "audience_value"]:
            # 簡化計算
            scores = [v for v in section.values() if isinstance(v, (int, float))]
            if not scores: return 1.0
            avg = sum(scores) / len(scores)
            return 0.8 + (avg / 10) * 0.8
        elif key == "cross_platform":
            count = sum(1 for v in section.values() if isinstance(v, bool) and v)
            return 1.0 + count * 0.1
        
        return default
    
    multipliers = {
        "visual": calc_multiplier(ai_data, "visual_quality"),
        "content": calc_multiplier(ai_data, "content_type"),
        "professional": calc_multiplier(ai_data, "professionalism"),
        "follower": calculate_follower_quality_multiplier(followers, following),
        "unique": calc_multiplier(ai_data, "uniqueness"),
        "engagement": calc_multiplier(ai_data, "engagement_potential"),
        "niche": calc_multiplier(ai_data, "niche_focus"),
        "audience": calc_multiplier(ai_data, "audience_value"),
        "cross_platform": calc_multiplier(ai_data, "cross_platform")
    }
    
    # 9. 組裝回傳資料
    personality = ai_data.get("personality_type", {})
    primary_type_id = personality.get("primary_type", "type_5")
    primary_type_info = PERSONALITY_TYPES.get(primary_type_id, PERSONALITY_TYPES["type_5"])
    
    account_value_data = ai_data.get("account_value", {})
    pricing_data = ai_data.get("pricing", {})
    
    result = {
        "ok": True,
        "version": "v5",
        
        # 基本資訊
        "username": username,
        "display_name": display_name,
        "followers": followers,
        "following": following,
        "posts": posts,
        
        # AI 分析文字（新增）
        "analysis_text": analysis_text,
        
        # 人格類型
        "primary_type": {
            "id": primary_type_id,
            "name_zh": primary_type_info["name_zh"],
            "name_en": primary_type_info["name_en"],
            "emoji": primary_type_info["emoji"],
            "confidence": personality.get("confidence", 0.5),
            "reasoning": personality.get("reasoning", "")
        },
        
        # 身價評估（使用 AI 估算的價格）
        "value_estimation": {
            "base_price": calculate_base_price(followers),
            "follower_tier": get_follower_tier(followers),
            "follower_quality": get_follower_quality_label(followers, following),
            "account_value_min": account_value_data.get("min", 0),
            "account_value_max": account_value_data.get("max", 0),
            "account_value_reasoning": account_value_data.get("reasoning", ""),
            "multipliers": {k: round(v, 2) for k, v in multipliers.items()},
            "post_value": pricing_data.get("post", 0),
            "story_value": pricing_data.get("story", 0),
            "reels_value": pricing_data.get("reels", 0)
        },
        
        # 分析詳情
        "analysis": {
            "visual_quality": ai_data.get("visual_quality", {}),
            "content_type": ai_data.get("content_type", {}),
            "professionalism": ai_data.get("professionalism", {}),
            "uniqueness": ai_data.get("uniqueness", {}),
            "engagement_potential": ai_data.get("engagement_potential", {}),
            "niche_focus": ai_data.get("niche_focus", {}),
            "audience_value": ai_data.get("audience_value", {}),
            "cross_platform": ai_data.get("cross_platform", {})
        },
        
        # 描述
        "improvement_tips": ai_data.get("improvement_tips", []),
        
        # 診斷資訊
        "diagnose": {
            "ai_on": True,
            "model": OPENAI_MODEL,
            "version": "v5",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }
    
    save_last_ai(ai_dict=result)
    
    return jsonify(result)

# -----------------------------------------------------------------------------
# Leaderboard API
# -----------------------------------------------------------------------------
@app.route("/api/leaderboard", methods=["GET"])
def get_leaderboard():
    """獲取排行榜數據"""
    try:
        # 這裡應該從數據庫獲取真實數據
        # 目前返回模擬數據
        mock_data = [
            {
                "rank": 1,
                "username": "taylorswift",
                "displayName": "Taylor Swift",
                "followers": "282M",
                "accountValue": 9850000,
                "avatar": "TS"
            },
            {
                "rank": 2,
                "username": "cristiano",
                "displayName": "Cristiano Ronaldo", 
                "followers": "631M",
                "accountValue": 9200000,
                "avatar": "CR"
            },
            {
                "rank": 3,
                "username": "therock",
                "displayName": "Dwayne Johnson",
                "followers": "395M", 
                "accountValue": 8750000,
                "avatar": "DJ"
            }
        ]
        
        return jsonify({
            "ok": True,
            "data": mock_data,
            "total": len(mock_data)
        })
        
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"獲取排行榜數據失敗: {str(e)}"
        }), 500

# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)