# app.py — V5 Final Optimized: Tiered Valuation & Dynamic Pricing
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
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o") 
MAX_SIDE = int(os.getenv("MAX_SIDE", "1280"))
JPEG_Q = int(os.getenv("JPEG_QUALITY", "72"))

# 12種IG人格類型定義 (保持不變)
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
# 核心算法 1：級距式基礎價值 (Tiered Base Value)
# -----------------------------------------------------------------------------
def calculate_tiered_base_value(followers):
    """
    使用累進費率計算基礎價值，避免大帳號價值虛高，保障小帳號價值。
    回傳：基礎單篇貼文價值 (NTD)
    """
    # 定義級距：(上限粉絲數, 每粉單價)
    tiers = [
        (5000, 0.60),    # 0-5k粉：每粉 0.6 元 (CPM 600)
        (15000, 0.45),   # 5k-20k粉：每粉 0.45 元
        (80000, 0.35),   # 20k-100k粉：每粉 0.35 元
        (400000, 0.25),  # 100k-500k粉：每粉 0.25 元
        (float('inf'), 0.15) # 500k以上：每粉 0.15 元
    ]
    
    remaining = followers
    total_value = 0
    
    for limit, price in tiers:
        if remaining <= 0:
            break
        count = min(remaining, limit)
        total_value += count * price
        remaining -= count
        
    # 最低保底價 150 元
    return max(int(total_value), 150)

# -----------------------------------------------------------------------------
# 核心算法 2：動態估價模型 (Dynamic Valuation Model)
# -----------------------------------------------------------------------------
def calculate_account_valuation(followers, following, ai_data):
    """
    綜合估價邏輯：
    1. 算出級距 Base
    2. 乘上 AI 分析的四大係數 (Ratio, Visual, Niche, Commercial)
    3. 根據內容偏好 (Content Format) 動態推算 Reels/Story 價格
    4. 最後推算帳號總身價
    """
    
    # 1. 基礎貼文價值 (Tiered)
    base_post_value = calculate_tiered_base_value(followers)

    # 2. 邏輯係數 (Hard Logic)
    ratio = followers / (following if following > 0 else 1)
    ratio_mult = 1.0
    if ratio > 50: ratio_mult = 1.4     # 巨星
    elif ratio > 10: ratio_mult = 1.2   # 優質創作者
    elif ratio < 0.8: ratio_mult = 0.6  # 互粉帳號
    elif ratio < 0.3: ratio_mult = 0.3  # 垃圾帳號

    # 3. AI 美感係數 (Visual) - 這是讓貼文報價上升的關鍵
    visual_score = ai_data.get("visual_quality", {}).get("overall", 5.0)
    # 映射：1分=0.7x, 10分=1.8x (美感有溢價)
    visual_mult = 0.7 + (visual_score / 10.0) * 1.1

    # 4. AI 利基係數 (Niche) - 決定商業含金量
    niche_tier = ai_data.get("content_type", {}).get("category_tier", "mid")
    niche_map = {
        "high": 2.2,      # 金融/醫美
        "mid_high": 1.6,  # 時尚/3C/汽車
        "mid": 1.2,       # 美食/旅遊
        "low": 0.8        # 語錄/迷因/日記
    }
    niche_mult = niche_map.get(niche_tier, 1.0)

    # 5. 商業訊號 (Signal)
    comm_mult = 1.2 if ai_data.get("professionalism", {}).get("has_contact") else 1.0

    # --- 綜合算出：單篇貼文報價 (Post Price) ---
    # 注意：這裡已經包含了所有維度的加成
    final_post_mult = ratio_mult * visual_mult * niche_mult * comm_mult
    estimated_post_price = int(base_post_value * final_post_mult)

    # --- 動態計算 Story & Reels ---
    # 從 AI 獲取內容偏好 (1-10分)
    content_format = ai_data.get("content_format", {})
    video_score = content_format.get("video_focus", 3)       # 預設 3 (偏圖文)
    personal_score = content_format.get("personal_connection", 5) # 預設 5
    
    # Reels 倍率：基礎 1.1x，視訊分數每高 1 分 +0.12x (最高可達 ~2.3x)
    # 邏輯：如果你是影片創作者，你的 Reels 會比 Post 貴很多
    reels_mult = 1.1 + (max(0, video_score - 2) * 0.12)
    
    # Story 倍率：基礎 0.25x，個人連結每高 1 分 +0.04x (最高可達 ~0.6x)
    # 邏輯：如果你很親民(personal connection高)，限動黏著度高，價格才高
    story_mult = 0.25 + (max(0, personal_score - 3) * 0.04)

    estimated_reels_price = int(estimated_post_price * reels_mult)
    estimated_story_price = int(estimated_post_price * story_mult)

    # --- 帳號總身價 (Account Asset Value) ---
    # 定義：這個帳號作為一個「資產」的估值
    # 邏輯：(預估月營收 x 18個月 P/E Ratio) + (粉絲基礎資產)
    # 假設：活躍創作者平均一個月接 4 篇 Post + 4 篇 Story
    monthly_revenue = (estimated_post_price * 4) + (estimated_story_price * 4)
    asset_value = int(monthly_revenue * 18)
    
    # 修正極端值 (針對超小或超大帳號的校正)
    if asset_value < 3000: asset_value = 3000

    return {
        "account_asset_value": asset_value,
        "post_value": estimated_post_price,
        "story_value": estimated_story_price,
        "reels_value": estimated_reels_price,
        "multipliers": {
            "ratio": round(ratio_mult, 2),
            "visual": round(visual_mult, 2),
            "niche": round(niche_mult, 2),
            "commercial": round(comm_mult, 2),
            "total": round(final_post_mult, 2)
        }
    }

# -----------------------------------------------------------------------------
# Helpers
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

def extract_json_from_text(text: str):
    json_pattern = r'```json\s*(\{.*?\})\s*```'
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        try: return json.loads(match.group(1))
        except: pass
    json_pattern2 = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(json_pattern2, text, re.DOTALL)
    for json_str in sorted(matches, key=len, reverse=True):
        try: return json.loads(json_str)
        except: continue
    return None

def call_openai_vision(base64_imgs: list, user_prompt: str, system_prompt: str = ""):
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set")
    
    content_parts = [{"type": "text", "text": user_prompt}]
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
        "max_tokens": 2500,
        "temperature": 0.7
    }
    
    resp = requests.post(url, headers=headers, json=payload, timeout=90)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

# -----------------------------------------------------------------------------
# System & User Prompt (Updated)
# -----------------------------------------------------------------------------
SYSTEM_PROMPT = """你是一位嚴格的 Instagram 帳號鑑價師。
請透過視覺細節進行商業價值評估，並專注於分析：
1. 視覺美感 (Visual): 1-10分
2. 利基含金量 (Niche): 判斷領域 (High/Mid/Low)
3. 內容格式 (Format): 是影片為主還是圖文為主？
4. 親密度 (Connection): 是高冷型還是親民型？"""

def build_user_prompt(followers, following, posts):
    return f"""分析這個 IG 帳號截圖。數據：粉絲 {followers}, 追蹤 {following}, 貼文 {posts}。

請完成兩個任務：

1. **專業短評 (Analysis Text)**：
用 200 字以內，針對其「商業變現潛力」給出評價。指出優點與缺點。

2. **數據提取 (JSON)**：
請嚴格回傳以下 JSON：

```json
{{
  "visual_quality": {{ 
    "overall": 7.5,  // 1.0-10.0，10分是頂級雜誌感
    "consistency": 8.0 
  }},
  "content_type": {{
    "primary": "美食",
    "category_tier": "mid" // high(金融/醫美/精品), mid_high(時尚/3C), mid(美食/旅遊), low(日記/迷因)
  }},
  "content_format": {{
    "video_focus": 3, // 1-10: 1=純圖文, 8-10=Reels創作者(影響Reels報價)
    "personal_connection": 6 // 1-10: 1=官方冷淡, 8-10=像朋友一樣(影響Story報價)
  }},
  "professionalism": {{ 
    "has_contact": true,
    "is_business_account": false
  }},
  "personality_type": {{ 
    "primary_type": "type_5", // 對應12型人格
    "reasoning": "簡短理由" 
  }},
  "improvement_tips": [
    "建議...",
    "建議..."
  ]
}}
