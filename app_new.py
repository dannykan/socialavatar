#!/usr/bin/env python3
"""
Instagram 帳號估值系統 - 新版本
使用開放式 AI 回答 + 數據提取策略
"""

import os
import json
import re
import io
import base64
import requests
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore

# 環境變數
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
MAX_SIDE = int(os.getenv("MAX_SIDE", "1280"))
JPEG_Q = int(os.getenv("JPEG_QUALITY", "72"))

# Flask 應用
app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

# Firebase 初始化
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("firebase-config.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()
except:
    db = None

# 全局變數
LAST_AI_TEXT = {"text": "", "raw": ""}

def extract_data_from_ai_response(ai_response: str) -> dict:
    """
    從 AI 的開放式回答中提取關鍵數據
    """
    
    # 提取帳號價值
    account_value = extract_account_value(ai_response)
    
    # 提取報價信息
    pricing = extract_pricing(ai_response)
    
    # 提取其他分析數據
    analysis_data = extract_analysis_data(ai_response)
    
    return {
        "account_value": account_value,
        "pricing": pricing,
        "analysis": analysis_data
    }

def extract_account_value(text: str) -> dict:
    """提取帳號價值信息"""
    
    # 尋找價格範圍
    price_patterns = [
        r'NT\$?[\s]*([0-9,]+)[\s]*[-~至到]\s*NT\$?[\s]*([0-9,]+)',
        r'([0-9,]+)[\s]*[-~至到]\s*([0-9,]+)[\s]*元',
        r'價值[約為]*[\s]*NT\$?[\s]*([0-9,]+)[\s]*[-~至到]\s*NT\$?[\s]*([0-9,]+)',
        r'估值[約為]*[\s]*([0-9,]+)[\s]*[-~至到]\s*([0-9,]+)[\s]*元'
    ]
    
    min_value = None
    max_value = None
    reasoning = ""
    
    for pattern in price_patterns:
        match = re.search(pattern, text)
        if match:
            min_value = int(match.group(1).replace(',', ''))
            max_value = int(match.group(2).replace(',', ''))
            break
    
    # 如果沒找到範圍，尋找單一價格
    if not min_value:
        single_price_patterns = [
            r'NT\$?[\s]*([0-9,]+)',
            r'([0-9,]+)[\s]*元',
            r'價值[約為]*[\s]*NT\$?[\s]*([0-9,]+)',
            r'估值[約為]*[\s]*([0-9,]+)[\s]*元'
        ]
        
        for pattern in single_price_patterns:
            match = re.search(pattern, text)
            if match:
                value = int(match.group(1).replace(',', ''))
                min_value = value
                max_value = value
                break
    
    # 提取推理邏輯
    reasoning_patterns = [
        r'因為([^。]+)',
        r'由於([^。]+)',
        r'基於([^。]+)',
        r'根據([^。]+)'
    ]
    
    for pattern in reasoning_patterns:
        match = re.search(pattern, text)
        if match:
            reasoning = match.group(1).strip()
            break
    
    return {
        "min": min_value or 0,
        "max": max_value or 0,
        "reasoning": reasoning or "基於市場行情分析"
    }

def extract_pricing(text: str) -> dict:
    """提取報價信息"""
    
    pricing = {
        "post": 0,
        "story": 0,
        "reels": 0
    }
    
    # Post 報價
    post_patterns = [
        r'Post[^0-9]*NT\$?[\s]*([0-9,]+)',
        r'貼文[^0-9]*NT\$?[\s]*([0-9,]+)',
        r'單篇[^0-9]*NT\$?[\s]*([0-9,]+)'
    ]
    
    for pattern in post_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            pricing["post"] = int(match.group(1).replace(',', ''))
            break
    
    # Story 報價
    story_patterns = [
        r'Story[^0-9]*NT\$?[\s]*([0-9,]+)',
        r'限時動態[^0-9]*NT\$?[\s]*([0-9,]+)'
    ]
    
    for pattern in story_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            pricing["story"] = int(match.group(1).replace(',', ''))
            break
    
    # Reels 報價
    reels_patterns = [
        r'Reels[^0-9]*NT\$?[\s]*([0-9,]+)',
        r'短影片[^0-9]*NT\$?[\s]*([0-9,]+)'
    ]
    
    for pattern in reels_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            pricing["reels"] = int(match.group(1).replace(',', ''))
            break
    
    return pricing

def extract_analysis_data(text: str) -> dict:
    """提取分析數據"""
    
    analysis = {
        "visual_quality": {"overall": 7.5},
        "content_type": {"primary": "生活記錄", "commercial_potential": "medium"},
        "professionalism": {"brand_identity": 7.0},
        "uniqueness": {"creativity_score": 7.0},
        "audience_value": {"audience_tier": "一般用戶"},
        "improvement_tips": []
    }
    
    # 提取改進建議
    tips_pattern = r'建議[：:]?\s*([^。]+)'
    tips_matches = re.findall(tips_pattern, text)
    if tips_matches:
        analysis["improvement_tips"] = [tip.strip() for tip in tips_matches[:3]]
    
    return analysis

def build_user_prompt(followers, following, posts):
    return f"""我的IG帳號如果要賣掉的話值多少錢，為什麼怎麼精算出來的？Post和reels應該怎麼計價？請詳細解釋。

**基本數據：**
- 粉絲數：{followers:,}
- 追蹤數：{following:,}
- 貼文數：{posts:,}

請用繁體中文詳細分析，不限字數，提供完整的估值邏輯和計算方法。"""

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
        "temperature": 0.3
    }
    
    resp = requests.post(url, headers=headers, json=payload, timeout=90)
    resp.raise_for_status()
    
    data = resp.json()
    raw_text = data["choices"][0]["message"]["content"]
    return raw_text

@app.route("/bd/analyze", methods=["POST"])
def analyze():
    """主分析端點 - 新版本"""
    
    try:
        # 1. 獲取上傳的圖片
        if 'profile' not in request.files:
            return jsonify({"ok": False, "error": "請上傳 Instagram 個人頁截圖"}), 400
        
        profile_file = request.files['profile']
        if profile_file.filename == '':
            return jsonify({"ok": False, "error": "請選擇要上傳的檔案"}), 400
        
        # 2. 處理圖片
        try:
            profile_img = Image.open(profile_file.stream)
        except Exception as e:
            return jsonify({"ok": False, "error": "圖片格式不支援，請上傳 JPG 或 PNG 格式的截圖。"}), 400
        
        # 3. 轉換為 base64
        profile_b64 = resize_and_encode_b64(profile_img)
        all_images = [profile_b64]
        
        # 4. 進行 OCR 提取基本資訊
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
            ocr_data = json.loads(ocr_result)
            
            if not ocr_data:
                return jsonify({"ok": False, "error": "無法從截圖中讀取 IG 資訊。請確保截圖清晰且包含完整的個人頁面資訊（用戶名、粉絲數、追蹤數、貼文數）。"}), 400
            
            username = ocr_data.get("username", "")
            display_name = ocr_data.get("display_name", "")
            followers = int(ocr_data.get("followers", 0))
            following = int(ocr_data.get("following", 0))
            posts = int(ocr_data.get("posts", 0))
            
        except Exception as e:
            return jsonify({"ok": False, "error": "截圖解析失敗。請確保上傳的是清晰的 IG 個人頁截圖，包含完整的用戶資訊。"}), 400
        
        # 5. 進行開放式 AI 分析
        try:
            user_prompt = build_user_prompt(followers, following, posts)
            ai_response = call_openai_vision(all_images, user_prompt, "")
            
            # 6. 從 AI 回答中提取數據
            extracted_data = extract_data_from_ai_response(ai_response)
            
        except Exception as e:
            return jsonify({"ok": False, "error": "AI 分析服務暫時無法使用。請稍後再試，或檢查截圖是否清晰完整。"}), 500
        
        # 7. 構建回傳結果
        result = {
            "ok": True,
            "username": username,
            "display_name": display_name,
            "followers": followers,
            "following": following,
            "posts": posts,
            "analysis_text": ai_response,
            "value_estimation": {
                "account_value_min": extracted_data["account_value"]["min"],
                "account_value_max": extracted_data["account_value"]["max"],
                "account_value_reasoning": extracted_data["account_value"]["reasoning"],
                "post_value": extracted_data["pricing"]["post"],
                "story_value": extracted_data["pricing"]["story"],
                "reels_value": extracted_data["pricing"]["reels"]
            },
            "analysis": extracted_data["analysis"],
            "improvement_tips": extracted_data["analysis"]["improvement_tips"],
            "diagnose": {
                "ai_on": True,
                "model": OPENAI_MODEL,
                "version": "v6",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"ok": False, "error": f"分析失敗: {str(e)}"}), 500

def resize_and_encode_b64(pil_img: Image.Image, max_side=MAX_SIDE, quality=JPEG_Q):
    w, h = pil_img.size
    if max(w, h) > max_side:
        if w > h:
            nw, nh = max_side, int(h * max_side / w)
        else:
            nw, nh = int(w * max_side / h), max_side
        pil_img = pil_img.resize((nw, nh), Image.Resampling.LANCZOS)
    
    if pil_img.mode in ('RGBA', 'LA', 'P'):
        bg = Image.new('RGB', pil_img.size, (255, 255, 255))
        if pil_img.mode == 'P':
            pil_img = pil_img.convert('RGBA')
        bg.paste(pil_img, mask=pil_img.split()[-1] if pil_img.mode in ('RGBA', 'LA') else None)
        pil_img = bg
    
    buf = io.BytesIO()
    pil_img.save(buf, format='JPEG', quality=quality)
    return base64.b64encode(buf.read()).decode('utf-8')

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
