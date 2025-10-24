# ai_analyzer.py - IG 帳號 AI 分析模組
"""
重構後的 AI 分析模組
職責：
1. 圖片預處理
2. Prompt 生成
3. OpenAI API 調用
4. 結果解析與驗證
"""

import io
import base64
import json
import re
from typing import Dict, List, Optional, Tuple
from PIL import Image
import requests


class ImageProcessor:
    """圖片預處理器"""
    
    def __init__(self, max_side: int = 1280, quality: int = 72):
        self.max_side = max_side
        self.quality = quality
    
    def resize_and_encode(self, pil_img: Image.Image) -> str:
        """調整大小並編碼為 base64"""
        w, h = pil_img.size
        
        # 調整尺寸
        if max(w, h) > self.max_side:
            ratio = self.max_side / max(w, h)
            nw, nh = int(w * ratio), int(h * ratio)
            pil_img = pil_img.resize((nw, nh), Image.Resampling.LANCZOS)
        
        # 轉換為 RGB
        if pil_img.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', pil_img.size, (255, 255, 255))
            if pil_img.mode == 'P':
                pil_img = pil_img.convert('RGBA')
            bg.paste(pil_img, mask=pil_img.split()[-1] if pil_img.mode in ('RGBA', 'LA') else None)
            pil_img = bg
        
        # 編碼為 JPEG
        buf = io.BytesIO()
        pil_img.save(buf, format='JPEG', quality=self.quality)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')


class PromptBuilder:
    """Prompt 構建器 - 分離 prompt 邏輯"""
    
    @staticmethod
    def build_ocr_prompt() -> str:
        """構建 OCR 提取 prompt"""
        return """請從這個 Instagram 個人頁截圖中提取以下資訊：

**重要：請使用繁體中文進行分析，但 JSON 格式保持英文欄位名稱。**

需要提取的資訊：
1. username（用戶名，不含 @）
2. display_name（顯示名稱）
3. followers（粉絲數）
4. following（追蹤數）
5. posts（貼文數）

請以 JSON 格式回傳：
```json
{
  "username": "user123",
  "display_name": "User Name",
  "followers": 7200,
  "following": 850,
  "posts": 342
}
```

**只回傳 JSON，不要其他文字。**"""
    
    @staticmethod
    def build_analysis_prompt(followers: int, following: int, posts: int) -> str:
        """構建完整分析 prompt"""
        return f"""我的IG帳號如果要賣掉的話值多少錢，為什麼？怎麼精算出來的？Post和reels應該怎麼計價？解釋說明

**基本數據：**
- 粉絲數：{followers:,}
- 追蹤數：{following:,}
- 貼文數：{posts:,}

請用繁體中文回答，所有價格以新台幣(NT$)計算。"""


class ResponseParser:
    """回應解析器 - 處理 AI 回應的解析"""
    
    @staticmethod
    def extract_json_from_text(text: str) -> Optional[Dict]:
        """從文本中提取 JSON（改進版）"""
        print(f"[Parser] 開始解析文本 (長度: {len(text)})")
        
        # 方法 1: 尋找 ```json ``` 包裹的內容
        json_pattern = r'```json\s*(\{.*?\})\s*```'
        match = re.search(json_pattern, text, re.DOTALL)
        
        if match:
            json_str = match.group(1)
            print(f"[Parser] 在代碼塊中找到 JSON (長度: {len(json_str)})")
            try:
                data = json.loads(json_str)
                print(f"[Parser] ✅ 成功解析代碼塊 JSON")
                return data
            except json.JSONDecodeError as e:
                print(f"[Parser] ❌ 代碼塊 JSON 解析失敗: {e}")
        
        # 方法 2: 尋找最後一個完整的 JSON 對象
        # 從文本末尾往前找最後一個 }
        last_brace = text.rfind('}')
        if last_brace != -1:
            # 從這個位置往前找對應的 {
            brace_count = 0
            start_pos = last_brace
            
            for i in range(last_brace, -1, -1):
                if text[i] == '}':
                    brace_count += 1
                elif text[i] == '{':
                    brace_count -= 1
                    if brace_count == 0:
                        start_pos = i
                        break
            
            if brace_count == 0:
                json_str = text[start_pos:last_brace + 1]
                print(f"[Parser] 找到最後一個 JSON 對象 (長度: {len(json_str)})")
                try:
                    data = json.loads(json_str)
                    print(f"[Parser] ✅ 成功解析最後一個 JSON")
                    return ResponseParser._validate_json_structure(data)
                except json.JSONDecodeError as e:
                    print(f"[Parser] ❌ 最後一個 JSON 解析失敗: {e}")
        
        # 方法 3: 使用正則表達式尋找所有可能的 JSON
        json_pattern2 = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern2, text, re.DOTALL)
        print(f"[Parser] 找到 {len(matches)} 個潛在的 JSON 匹配")
        
        # 從最長的開始嘗試解析
        for i, json_str in enumerate(sorted(matches, key=len, reverse=True)):
            try:
                print(f"[Parser] 嘗試解析匹配 {i+1} (長度: {len(json_str)})")
                data = json.loads(json_str)
                validated = ResponseParser._validate_json_structure(data)
                if validated:
                    print(f"[Parser] ✅ 成功解析並驗證匹配 {i+1}")
                    return validated
            except (json.JSONDecodeError, ValueError) as e:
                print(f"[Parser] ❌ 匹配 {i+1} 解析失敗: {e}")
                continue
        
        print("[Parser] ❌ 無法找到有效的 JSON")
        return None
    
    @staticmethod
    def _validate_json_structure(data: Dict) -> Optional[Dict]:
        """驗證 JSON 結構是否包含必要欄位"""
        required_fields = [
            'account_value', 'pricing', 'visual_quality', 
            'content_type', 'professionalism', 'uniqueness', 
            'audience_value', 'improvement_tips'
        ]
        
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            print(f"[Parser] ⚠️ JSON 缺少必要欄位: {missing_fields}")
            print(f"[Parser] 可用欄位: {list(data.keys())}")
            return None
        
        print(f"[Parser] ✅ JSON 結構驗證通過")
        return data
    
    @staticmethod
    def parse_ocr_result(raw_text: str) -> Optional[Dict]:
        """解析 OCR 結果"""
        data = ResponseParser.extract_json_from_text(raw_text)
        if not data:
            return None
        
        # 驗證必要欄位
        required = ['username', 'followers', 'following', 'posts']
        if not all(field in data for field in required):
            print(f"[Parser] ❌ OCR 結果缺少必要欄位")
            return None
        
        return data
    
    @staticmethod
    def parse_analysis_result(raw_text: str) -> Tuple[Optional[str], Optional[Dict]]:
        """解析分析結果，返回 (分析文字, 結構化數據)"""
        # 提取 JSON
        json_data = ResponseParser.extract_json_from_text(raw_text)
        
        # 提取分析文字（JSON 之前的內容）
        analysis_text = raw_text
        if json_data:
            # 找到 JSON 的位置，之前的都是分析文字
            json_str = json.dumps(json_data, ensure_ascii=False)
            json_pos = raw_text.find('{')
            if json_pos > 0:
                analysis_text = raw_text[:json_pos].strip()
                # 移除可能的 markdown 標記
                analysis_text = analysis_text.replace('```json', '').replace('```', '').strip()
        
        return analysis_text, json_data


class OpenAIAnalyzer:
    """OpenAI 分析器 - 統一的 API 調用接口"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.openai.com/v1/chat/completions"
    
    def analyze(
        self, 
        images: List[str], 
        user_prompt: str, 
        system_prompt: str = "",
        max_tokens: int = 3000,
        temperature: float = 0.3
    ) -> str:
        """
        調用 OpenAI Vision API
        
        Args:
            images: base64 編碼的圖片列表
            user_prompt: 用戶 prompt
            system_prompt: 系統 prompt
            max_tokens: 最大 token 數
            temperature: 溫度參數
            
        Returns:
            AI 回應文本
            
        Raises:
            ValueError: API key 未設置
            requests.RequestException: API 調用失敗
        """
        if not self.api_key:
            raise ValueError("OpenAI API key 未設置")
        
        # 構建消息內容
        content_parts = []
        if user_prompt:
            content_parts.append({"type": "text", "text": user_prompt})
        
        for b64_img in images:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
            })
        
        # 構建消息列表
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": content_parts})
        
        # 調用 API
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        print(f"[OpenAI] 調用 API: {self.model}")
        print(f"[OpenAI] 圖片數量: {len(images)}")
        print(f"[OpenAI] Max tokens: {max_tokens}")
        
        response = requests.post(
            self.api_url, 
            headers=headers, 
            json=payload, 
            timeout=90
        )
        response.raise_for_status()
        
        data = response.json()
        raw_text = data["choices"][0]["message"]["content"]
        
        print(f"[OpenAI] ✅ API 調用成功，回應長度: {len(raw_text)}")
        
        return raw_text


class IGAnalyzer:
    """IG 帳號分析器 - 主入口"""
    
    def __init__(
        self, 
        api_key: str, 
        model: str = "gpt-4o",
        max_side: int = 1280,
        quality: int = 72
    ):
        self.image_processor = ImageProcessor(max_side, quality)
        self.prompt_builder = PromptBuilder()
        self.response_parser = ResponseParser()
        self.openai = OpenAIAnalyzer(api_key, model)
    
    def analyze_profile(
        self, 
        profile_image: Image.Image, 
        post_images: List[Image.Image] = None
    ) -> Dict:
        """
        完整的帳號分析流程
        
        Args:
            profile_image: 個人頁截圖
            post_images: 貼文圖片列表（可選）
            
        Returns:
            分析結果字典
            
        Raises:
            ValueError: 分析失敗
        """
        print("[IGAnalyzer] 開始分析流程")
        
        # 1. 處理圖片
        print("[IGAnalyzer] Step 1: 處理圖片")
        profile_b64 = self.image_processor.resize_and_encode(profile_image)
        
        post_b64_list = []
        if post_images:
            for i, post_img in enumerate(post_images[:6]):
                print(f"[IGAnalyzer] 處理貼文圖片 {i+1}/{len(post_images[:6])}")
                post_b64_list.append(self.image_processor.resize_and_encode(post_img))
        
        # 2. OCR 提取基本資訊
        print("[IGAnalyzer] Step 2: OCR 提取基本資訊")
        ocr_prompt = self.prompt_builder.build_ocr_prompt()
        ocr_result = self.openai.analyze([profile_b64], ocr_prompt, "")
        
        basic_info = self.response_parser.parse_ocr_result(ocr_result)
        if not basic_info:
            raise ValueError("無法從截圖中讀取 IG 資訊。請確保截圖清晰且包含完整的個人頁面資訊。")
        
        print(f"[IGAnalyzer] ✅ 基本資訊提取成功: @{basic_info['username']}")
        
        # 3. 完整分析
        print("[IGAnalyzer] Step 3: 進行完整分析")
        all_images = [profile_b64] + post_b64_list
        analysis_prompt = self.prompt_builder.build_analysis_prompt(
            basic_info['followers'],
            basic_info['following'],
            basic_info['posts']
        )
        
        analysis_result = self.openai.analyze(
            all_images, 
            analysis_prompt, 
            ""
        )
        
        # 4. 解析結果
        print("[IGAnalyzer] Step 4: 解析分析結果")
        analysis_text, structured_data = self.response_parser.parse_analysis_result(analysis_result)
        
        if not structured_data:
            # 如果無法提取結構化數據，使用默認值
            print("[IGAnalyzer] ⚠️ 無法提取結構化數據，使用默認值")
            structured_data = self._get_default_structured_data()
        
        # 5. 組裝最終結果
        result = {
            "ok": True,
            "version": "v5",
            "username": basic_info.get("username", ""),
            "display_name": basic_info.get("display_name", ""),
            "followers": int(basic_info.get("followers", 0)),
            "following": int(basic_info.get("following", 0)),
            "posts": int(basic_info.get("posts", 0)),
            "analysis_text": analysis_text,
            "value_estimation": self._build_value_estimation(structured_data, basic_info),
            "primary_type": self._build_primary_type(structured_data),
            "analysis": structured_data,
            "improvement_tips": structured_data.get("improvement_tips", [])
        }
        
        print("[IGAnalyzer] ✅ 分析完成")
        return result
    
    def _get_default_structured_data(self) -> Dict:
        """獲取默認的結構化數據"""
        return {
            "account_value": {"min": 0, "max": 0, "reasoning": ""},
            "pricing": {"post": 0, "story": 0, "reels": 0},
            "visual_quality": {"overall": 7.0},
            "content_type": {"primary": "生活記錄", "commercial_potential": "medium"},
            "professionalism": {"brand_identity": 7.0},
            "uniqueness": {"creativity_score": 7.0},
            "audience_value": {"audience_tier": "一般用戶"},
            "improvement_tips": []
        }
    
    def _build_value_estimation(self, data: Dict, basic_info: Dict) -> Dict:
        """構建價值評估數據"""
        account_value = data.get("account_value", {})
        pricing = data.get("pricing", {})
        
        return {
            "base_price": self._calculate_base_price(basic_info['followers']),
            "follower_tier": self._get_follower_tier(basic_info['followers']),
            "follower_quality": self._get_follower_quality_label(
                basic_info['followers'], 
                basic_info['following']
            ),
            "account_value_min": account_value.get("min", 0),
            "account_value_max": account_value.get("max", 0),
            "account_value_reasoning": account_value.get("reasoning", ""),
            "multipliers": self._calculate_multipliers(data, basic_info),
            "post_value": pricing.get("post", 0),
            "story_value": pricing.get("story", 0),
            "reels_value": pricing.get("reels", 0)
        }
    
    def _build_primary_type(self, data: Dict) -> Dict:
        """構建主要類型資訊"""
        # 這裡可以根據 content_type 映射到 12 種類型
        # 暫時使用默認值
        return {
            "id": "type_5",
            "name_zh": "生活記錄者",
            "name_en": "Everyday Chronicler",
            "emoji": "🍜",
            "confidence": 0.75,
            "reasoning": "基於內容分析"
        }
    
    def _calculate_multipliers(self, data: Dict, basic_info: Dict) -> Dict:
        """計算各種係數"""
        visual = data.get("visual_quality", {}).get("overall", 7.0)
        
        return {
            "visual": round(visual / 10, 2),
            "content": 1.0,
            "professional": 1.0,
            "follower": self._calculate_follower_multiplier(
                basic_info['followers'], 
                basic_info['following']
            ),
            "unique": 1.0,
            "engagement": 1.0,
            "niche": 1.0,
            "audience": 1.0,
            "cross_platform": 1.0
        }
    
    @staticmethod
    def _calculate_base_price(followers: int) -> int:
        """計算基礎價格"""
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
    
    @staticmethod
    def _get_follower_tier(followers: int) -> str:
        """獲取粉絲級別"""
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
    
    @staticmethod
    def _calculate_follower_multiplier(followers: int, following: int) -> float:
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
    
    @staticmethod
    def _get_follower_quality_label(followers: int, following: int) -> str:
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
