# ai_analyzer.py - 固定問題版本

import io
import base64
import json
import re
from PIL import Image
import requests


class ImageProcessor:
    """圖片預處理器（不變）"""
    
    def __init__(self, max_side: int = 1280, quality: int = 72):
        self.max_side = max_side
        self.quality = quality
    
    def resize_and_encode(self, pil_img: Image.Image) -> str:
        """調整大小並編碼為 base64"""
        w, h = pil_img.size
        
        if max(w, h) > self.max_side:
            ratio = self.max_side / max(w, h)
            nw, nh = int(w * ratio), int(h * ratio)
            pil_img = pil_img.resize((nw, nh), Image.Resampling.LANCZOS)
        
        if pil_img.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', pil_img.size, (255, 255, 255))
            if pil_img.mode == 'P':
                pil_img = pil_img.convert('RGBA')
            bg.paste(pil_img, mask=pil_img.split()[-1] if pil_img.mode in ('RGBA', 'LA') else None)
            pil_img = bg
        
        buf = io.BytesIO()
        pil_img.save(buf, format='JPEG', quality=self.quality)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')


class PromptBuilder:
    """Prompt 構建器 - 固定問題"""
    
    # 固定的問題（可以在這裡修改）
    DEFAULT_QUESTION = """請仔細分析這個 Instagram 帳號截圖，完成以下任務：

**任務 1: 提取基本資訊**
請從截圖中識別並提取以下資訊（必須準確）：
- 用戶名 (username): 例如 @username 或顯示在個人資料中的用戶名
- 顯示名稱 (display_name): 個人資料中的顯示名稱或全名
- 粉絲數 (followers): 數字，例如 12500 或 12.5K
- 追蹤數 (following): 數字
- 貼文數 (posts): 數字

**任務 2: 風趣短評（重要！）**
請以「幽默網紅評論員」的身份，用 50 字左右寫一段風趣、有趣、一針見血的短評。
- 風格：輕鬆幽默、帶點調侃但友善、讓人印象深刻
- 可以評論粉絲數、內容風格、商業價值等
- 用詞有趣但不冒犯，要讓人會心一笑
- 範例風格：「這個帳號的粉絲數雖然不算多，但內容質感倒是比我的生活還精緻，建議品牌方可以考慮合作，CP值不錯（笑）」

**任務 3: 結構化數據提取**
請在回應的最後，以 JSON 格式提供完整的分析結果。"""
    
    @staticmethod
    def build_analysis_prompt(question: str = None) -> str:
        """
        建構分析 prompt
        
        Args:
            question: 自定義問題（如果為 None，使用預設問題）
        
        Returns:
            完整的 prompt
        """
        final_question = question or PromptBuilder.DEFAULT_QUESTION
        
        return f"""你是一位專業的 Instagram 帳號分析師，同時也是一位風趣毒舌的網紅評論員。請仔細查看這張截圖，完成以下任務：

{final_question}

**重要要求：**
1. 首先，請仔細識別截圖中的所有文字資訊，特別是：
   - 用戶名（通常在 @ 符號後面或個人資料頂部）
   - 顯示名稱（個人資料中的名稱）
   - 粉絲數、追蹤數、貼文數（通常在個人資料下方以數字顯示）

2. **風趣短評（必須完成！）**：
   請以「幽默網紅評論員」的身份，用 50 字左右寫一段風趣、有趣、一針見血的短評。
   - 人設：你是 IG 圈的幽默評論員，風格輕鬆有趣、帶點調侃但友善
   - 要求：50 字左右，讓人印象深刻，會心一笑
   - 可以評論：粉絲數、內容風格、商業價值、貼文頻率等
   - 用詞有趣但不冒犯，要有梗、有笑點
   - 範例風格：「這個帳號的粉絲數雖然不算多，但內容質感倒是比我的生活還精緻，建議品牌方可以考慮合作，CP值不錯（笑）」
   - 請在回應開頭直接寫出這段短評，標題為「**風趣短評：**」或「**毒舌短評：**」

3. 最後，請以 JSON 格式回傳所有提取的資訊和分析結果：

```json
{{
  "basic_info": {{
    "username": "從截圖中識別的用戶名，例如 foodie_taipei",
    "display_name": "從截圖中識別的顯示名稱",
    "followers": 12500,
    "following": 400,
    "posts": 150
  }},
  "visual_quality": {{ 
    "overall": 7.5,
    "consistency": 8.0 
  }},
  "content_type": {{
    "primary": "美食",
    "category_tier": "mid"
  }},
  "content_format": {{
    "video_focus": 3,
    "personal_connection": 6
  }},
  "professionalism": {{ 
    "has_contact": true,
    "is_business_account": false
  }},
  "personality_type": {{ 
    "primary_type": "type_5",
    "reasoning": "簡短理由" 
  }},
  "improvement_tips": [
    "建議1",
    "建議2"
  ]
}}
```

**注意事項：**
- 如果截圖中無法識別某些資訊，請使用 null 或合理的預設值
- 粉絲數如果是 "12.5K" 格式，請轉換為數字 12500
- 請確保 JSON 格式完全正確，可以直接被解析
- 使用繁體中文回答，所有價格以新台幣 (NT$) 計算"""


class ResponseCleaner:
    """回應清理器"""
    
    @staticmethod
    def clean_response(raw_response: str) -> str:
        """清理 AI 回應"""
        cleaned = raw_response.strip()
        
        # 移除 markdown code block
        if cleaned.startswith("```") and cleaned.endswith("```"):
            lines = cleaned.split("\n")
            if len(lines) > 2:
                cleaned = "\n".join(lines[1:-1]).strip()
        
        cleaned = cleaned.replace("```markdown", "").replace("```", "")
        
        return cleaned.strip()


class DataExtractor:
    """從 AI 回應中提取結構化數據"""
    
    @staticmethod
    def extract_metrics(analysis_text: str) -> dict:
        """
        從分析文本中提取商業指標
        
        Args:
            analysis_text: AI 的分析回應文本
            
        Returns:
            包含提取的指標的字典
        """
        import re
        
        metrics = {
            "followers": None,
            "engagement_rate": None,
            "engagement_percentage": None,
            "likes": [],
            "content_quality": None,
            "brand_potential": None,
            "income_potential": {
                "min_per_post": None,
                "max_per_post": None,
                "avg_per_post": None,
                "monthly_posts": None,
                "monthly_income": None
            },
            "recommendations": [],
            "raw_text": analysis_text
        }
        
        # 提取粉絲數
        followers_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)\s*K', analysis_text)
        if followers_match:
            followers_str = followers_match.group(1).replace(',', '')
            try:
                followers_val = float(followers_str)
                metrics["followers"] = int(followers_val * 1000) if 'K' in analysis_text[followers_match.start():followers_match.end()] else int(followers_val)
            except:
                pass
        
        # 提取互動率（更多的變體）
        engagement_match = re.search(r'互動率[：:]\s*([0-9.]+)%', analysis_text)
        if not engagement_match:
            engagement_match = re.search(r'互動率約為\s*([0-9.]+)%', analysis_text)
        if not engagement_match:
            engagement_match = re.search(r'([0-9.]+)%[，,]?\s*(?:的)?互動率', analysis_text)
        
        if engagement_match:
            try:
                metrics["engagement_percentage"] = float(engagement_match.group(1))
                metrics["engagement_rate"] = float(engagement_match.group(1)) / 100
            except:
                pass
        
        # 提取點讚數（更多的變體）
        likes_matches = re.findall(r'(\d+(?:,\d+)*)\s*(?:點讚|👍|likes)', analysis_text)
        for like in likes_matches[:5]:  # 最多提取 5 個
            try:
                metrics["likes"].append(int(like.replace(',', '')))
            except:
                pass
        
        # 如果找不到點讚數，嘗試找到數字後跟"、"的模式
        if not metrics["likes"]:
            likes_matches = re.findall(r'點讚數為\s*([0-9,]+)(?:、|，)', analysis_text)
            for like in likes_matches[:5]:
                try:
                    metrics["likes"].append(int(like.replace(',', '')))
                except:
                    pass
        
        # 提取內容品質評估
        quality_match = re.search(r'照片品質[：:]\s*([^。\n]+)', analysis_text)
        if quality_match:
            metrics["content_quality"] = quality_match.group(1).strip()
        
        # 提取品牌潛力
        brand_match = re.search(r'(?:品牌潛力|潛在合作機會)[：:]\s*([^。\n]+)', analysis_text)
        if brand_match:
            metrics["brand_potential"] = brand_match.group(1).strip()
        
        # 提取收入潛力
        income_min_match = re.search(r'NT\$(\d+(?:,\d+)*)\s*至\s*NT\$(\d+(?:,\d+)*)', analysis_text)
        if income_min_match:
            try:
                metrics["income_potential"]["min_per_post"] = int(income_min_match.group(1).replace(',', ''))
                metrics["income_potential"]["max_per_post"] = int(income_min_match.group(2).replace(',', ''))
                metrics["income_potential"]["avg_per_post"] = (
                    metrics["income_potential"]["min_per_post"] + 
                    metrics["income_potential"]["max_per_post"]
                ) // 2
            except:
                pass
        
        # 提取平均合作費用和月收入
        avg_income_match = re.search(r'平均每篇合作費用為\s*NT\$(\d+(?:,\d+)*)', analysis_text)
        if avg_income_match:
            try:
                metrics["income_potential"]["avg_per_post"] = int(avg_income_match.group(1).replace(',', ''))
            except:
                pass
        
        monthly_income_match = re.search(r'月收入約為\s*NT\$(\d+(?:,\d+)*)', analysis_text)
        if monthly_income_match:
            try:
                metrics["income_potential"]["monthly_income"] = int(monthly_income_match.group(1).replace(',', ''))
            except:
                pass
        
        # 提取建議（改進的模式）
        suggestions_section = re.search(r'(?:###\s*)?(?:建議|推薦)[：:]?(.*?)(?:$|這些評估|---)', analysis_text, re.DOTALL)
        if suggestions_section:
            suggestions_text = suggestions_section.group(1)
            # 首先嘗試找到帶有編號、標題和描述的項目
            suggestions = re.findall(r'[0-9]+\.\s*\*?\*?([^：:。\n]+)\*?\*?[：:]\s*([^。\n]+)', suggestions_text)
            if suggestions:
                metrics["recommendations"] = [
                    f"{title.strip().replace('**', '')}: {desc.strip()}" 
                    for title, desc in suggestions
                ]
            else:
                # 如果沒找到完整的標題:描述，嘗試只找項目標題
                suggestions = re.findall(r'[0-9]+\.\s*\*?\*?([^。\n：]+)', suggestions_text)
                if suggestions:
                    metrics["recommendations"] = [
                        s.strip().replace('**', '') 
                        for s in suggestions if s.strip()
                    ]
                else:
                    # 最後的嘗試：找所有以數字和句號開頭的行
                    suggestions = re.findall(r'^\s*[0-9]+\.\s*(.+?)$', suggestions_text, re.MULTILINE)
                    metrics["recommendations"] = [
                        s.strip().replace('**', '') 
                        for s in suggestions if s.strip()
                    ]
        
        return metrics


class OpenAIAnalyzer:
    """OpenAI 分析器"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.openai.com/v1/chat/completions"
    
    def describe_image(self, image_base64: str) -> str:
        """
        第一階段：描述圖片內容（純文字描述）
        這個階段只要求 AI 描述看到的內容，不會被安全過濾拒絕
        
        Args:
            image_base64: base64 編碼的圖片
            
        Returns:
            AI 對圖片的文字描述
        """
        if not self.api_key:
            raise ValueError("OpenAI API key 未設置")
        
        prompt = """請仔細觀察這張 Instagram 帳號截圖，用文字詳細描述截圖中顯示的所有文字和數字資訊。

這是一個公開的社交媒體截圖，請描述你看到的：

**基本資訊（請按照以下格式列出）：**
- 用戶名（username）：如果看到 @ 符號或用戶名，請寫出，例如：用戶名：dannytjkan
- 顯示名稱（display_name）：個人資料中顯示的名稱，例如：顯示名稱：Danny TJ Kan
- 粉絲數（followers）：請寫出你看到的數字，例如：粉絲數：10.1K 或 粉絲數：10100
- 追蹤數（following）：例如：追蹤數：914
- 貼文數（posts）：例如：貼文數：181

**視覺內容：**
- 個人資料照片的風格（簡短描述）
- 貼文縮圖的內容類型（旅遊、美食、生活等）
- 整體色彩風格

**其他觀察：**
- 任何其他可見的資訊或特點

請用繁體中文，客觀、詳細地描述，使用「用戶名：xxx」、「粉絲數：xxx」這樣的格式。這是一個公開的社交媒體截圖分析任務，請描述你看到的所有文字和數字資訊。"""
        
        content = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}"
                }
            }
        ]
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 1000,
            "temperature": 0.3  # 較低溫度，確保描述準確
        }
        
        print("[OpenAI] 第一階段：描述圖片內容...")
        
        try:
            response = requests.post(
                self.api_url, 
                headers=headers, 
                json=payload, 
                timeout=60
            )
            
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {})
                    if isinstance(error_msg, dict):
                        error_detail = error_msg.get("message", str(error_data))
                    else:
                        error_detail = str(error_msg)
                    raise ValueError(f"OpenAI API 錯誤 ({response.status_code}): {error_detail}")
                except (json.JSONDecodeError, KeyError):
                    raise ValueError(f"OpenAI API 請求失敗 ({response.status_code}): {response.text[:500]}")
            
            response.raise_for_status()
            data = response.json()
            
            if "choices" not in data or len(data["choices"]) == 0:
                raise ValueError("OpenAI API 回應格式錯誤：缺少 choices")
            
            description = data["choices"][0]["message"]["content"]
            
            if not description:
                raise ValueError("OpenAI API 回應為空")
            
            print(f"[OpenAI] ✅ 圖片描述完成，長度: {len(description)}")
            return description
            
        except Exception as e:
            print(f"[OpenAI] ❌ 圖片描述失敗: {e}")
            raise
    
    def generate_review_from_description(self, description: str, basic_info: dict = None) -> str:
        """
        第二階段：基於文字描述生成風趣短評
        這個階段只處理文字，不會被安全過濾拒絕
        
        Args:
            description: 第一階段的圖片描述
            basic_info: 基本資訊（可選）
            
        Returns:
            風趣短評（約 50 字）
        """
        if not self.api_key:
            raise ValueError("OpenAI API key 未設置")
        
        # 構建 prompt
        info_context = ""
        if basic_info:
            info_context = f"""
已知資訊：
- 用戶名: {basic_info.get('username', '未知')}
- 顯示名稱: {basic_info.get('display_name', '未知')}
- 粉絲數: {basic_info.get('followers', 0)}
- 追蹤數: {basic_info.get('following', 0)}
- 貼文數: {basic_info.get('posts', 0)}
"""
        
        prompt = f"""你是一位幽默風趣的網紅評論員。請根據以下 Instagram 帳號的描述，寫一段風趣、有趣、一針見血的短評。

{info_context}

帳號描述：
{description}

要求：
- 風格：輕鬆幽默、帶點調侃但友善、讓人印象深刻
- 長度：不超過 70 個字（約兩行）
- 可以評論：粉絲數、內容風格、商業價值等
- 用詞有趣但不冒犯，要讓人會心一笑
- 直接寫出短評，不需要標題或前綴

範例風格：「這個帳號的粉絲數雖然不算多，但內容質感倒是比我的生活還精緻，建議品牌方可以考慮合作，CP值不錯（笑）」

請直接寫出你的短評："""
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
            "temperature": 0.8  # 較高溫度，讓回應更有創意
        }
        
        print("[OpenAI] 第二階段：生成風趣短評...")
        
        try:
            response = requests.post(
                self.api_url, 
                headers=headers, 
                json=payload, 
                timeout=30
            )
            
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {})
                    if isinstance(error_msg, dict):
                        error_detail = error_msg.get("message", str(error_data))
                    else:
                        error_detail = str(error_msg)
                    raise ValueError(f"OpenAI API 錯誤 ({response.status_code}): {error_detail}")
                except (json.JSONDecodeError, KeyError):
                    raise ValueError(f"OpenAI API 請求失敗 ({response.status_code}): {response.text[:500]}")
            
            response.raise_for_status()
            data = response.json()
            
            if "choices" not in data or len(data["choices"]) == 0:
                raise ValueError("OpenAI API 回應格式錯誤：缺少 choices")
            
            review = data["choices"][0]["message"]["content"].strip()
            
            if not review:
                raise ValueError("OpenAI API 回應為空")
            
            # 清理可能的標題或前綴
            review = re.sub(r'^(短評|評語|評論)[：:]\s*', '', review, flags=re.IGNORECASE)
            review = re.sub(r'^\*\*.*?\*\*\s*', '', review)
            
            # 僅處理結尾標點，完整保留內容
            if review and review[-1] in ['，', ',', '、']:
                review = review[:-1]
            if review and review[-1] not in "。.!?！？":
                review = review + "。"
            
            print(f"[OpenAI] ✅ 風趣短評生成完成: {review[:50]}...")
            return review
            
        except Exception as e:
            print(f"[OpenAI] ❌ 生成短評失敗: {e}")
            raise
    
    def analyze_image(
        self, 
        image_base64: str, 
        question: str,
        max_tokens: int = 1500,
        temperature: float = 0.7
    ) -> str:
        """
        使用 OpenAI Vision API 分析圖片
        
        Args:
            image_base64: base64 編碼的圖片
            question: 問題
            max_tokens: 最大 token 數
            temperature: 溫度參數
            
        Returns:
            AI 的純文字回答
        """
        if not self.api_key:
            raise ValueError("OpenAI API key 未設置")
        
        prompt = PromptBuilder.build_analysis_prompt(question)
        
        content = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}"
                }
            }
        ]
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        print(f"[OpenAI] 調用 API: {self.model}")
        print(f"[OpenAI] 問題: {question[:50]}...")
        
        try:
            response = requests.post(
                self.api_url, 
                headers=headers, 
                json=payload, 
                timeout=90
            )
            
            # 如果狀態碼不是 200，先嘗試獲取詳細錯誤信息
            if response.status_code != 200:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {})
                    if isinstance(error_msg, dict):
                        error_detail = error_msg.get("message", str(error_data))
                    else:
                        error_detail = str(error_msg)
                    print(f"[OpenAI] ❌ API 錯誤詳情: {error_detail}")
                    raise ValueError(f"OpenAI API 錯誤 ({response.status_code}): {error_detail}")
                except (json.JSONDecodeError, KeyError):
                    raise ValueError(f"OpenAI API 請求失敗 ({response.status_code}): {response.text[:500]}")
            
            response.raise_for_status()
            
            data = response.json()
            
            # 檢查回應格式
            if "choices" not in data or len(data["choices"]) == 0:
                raise ValueError("OpenAI API 回應格式錯誤：缺少 choices")
            
            raw_text = data["choices"][0]["message"]["content"]
            
            if not raw_text:
                raise ValueError("OpenAI API 回應為空")
            
            print(f"[OpenAI] ✅ 回應長度: {len(raw_text)}")
            
            return raw_text
            
        except requests.exceptions.Timeout:
            raise ValueError("OpenAI API 請求超時（90秒），請稍後再試")
        except requests.exceptions.HTTPError as e:
            # 處理 HTTP 錯誤，獲取詳細信息
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", {})
                if isinstance(error_msg, dict):
                    error_detail = error_msg.get("message", str(error_data))
                else:
                    error_detail = str(error_msg)
                print(f"[OpenAI] ❌ HTTP 錯誤詳情: {error_detail}")
                raise ValueError(f"OpenAI API 錯誤 ({e.response.status_code}): {error_detail}")
            except:
                raise ValueError(f"OpenAI API 請求失敗: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise ValueError(f"OpenAI API 請求失敗: {str(e)}")
        except KeyError as e:
            raise ValueError(f"OpenAI API 回應格式錯誤: 缺少 {str(e)}")
        except json.JSONDecodeError as e:
            raise ValueError(f"無法解析 OpenAI API 回應: {str(e)}")


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
        self.openai = OpenAIAnalyzer(api_key, model)
        self.cleaner = ResponseCleaner()
    
    def _extract_basic_info_from_description(self, description: str) -> dict:
        """
        從圖片描述中提取基本資訊
        
        Args:
            description: 第一階段的圖片描述文字
            
        Returns:
            包含基本資訊的字典
        """
        info = {
            "username": "unknown",
            "display_name": "未知用戶",
            "followers": 0,
            "following": 0,
            "posts": 0
        }
        
        # 提取用戶名
        username_patterns = [
            r'用戶名[：:]\s*([a-zA-Z0-9_.]+)',
            r'帳號名稱[：:]\s*([a-zA-Z0-9_.]+)',
            r'@([a-zA-Z0-9_.]+)',
            r'username[：:]\s*([a-zA-Z0-9_.]+)',
        ]
        for pattern in username_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                info["username"] = match.group(1).strip()
                break
        
        # 提取顯示名稱
        display_name_patterns = [
            r'顯示名稱[：:]\s*([^\n，,。]+)',
            r'名稱[：:]\s*([^\n，,。]+)',
            r'全名[：:]\s*([^\n，,。]+)',
        ]
        for pattern in display_name_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                info["display_name"] = match.group(1).strip()
                break
        
        # 提取粉絲數
        followers_patterns = [
            r'粉絲數[：:]\s*(\d+(?:[,，]\d+)*(?:\.\d+)?)\s*[Kk]?',
            r'(\d+(?:\.\d+)?)\s*[Kk]\s*粉絲',
            r'粉絲[：:]\s*(\d+(?:[,，]\d+)*(?:\.\d+)?)\s*[Kk]?',
            r'followers[：:]\s*(\d+(?:[,，]\d+)*(?:\.\d+)?)\s*[Kk]?',
        ]
        for pattern in followers_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                followers_str = match.group(1)
                matched_text = description[match.start():match.end()].upper()
                
                if 'K' in matched_text:
                    try:
                        num = float(followers_str.replace(',', '').replace('，', ''))
                        info["followers"] = int(num * 1000)
                    except:
                        pass
                elif 'M' in matched_text:
                    try:
                        num = float(followers_str.replace(',', '').replace('，', ''))
                        info["followers"] = int(num * 1000000)
                    except:
                        pass
                else:
                    try:
                        info["followers"] = int(followers_str.replace(',', '').replace('，', '').replace('.', ''))
                    except:
                        pass
                
                if info["followers"] > 0:
                    break
        
        # 提取追蹤數
        following_patterns = [
            r'追蹤數[：:]\s*(\d+(?:[,，]\d+)*)',
            r'追蹤[：:]\s*(\d+(?:[,，]\d+)*)',
            r'following[：:]\s*(\d+(?:[,，]\d+)*)',
        ]
        for pattern in following_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                following_str = match.group(1).replace(',', '').replace('，', '').replace('.', '')
                try:
                    info["following"] = int(following_str)
                except:
                    pass
                if info["following"] > 0:
                    break
        
        # 提取貼文數
        posts_patterns = [
            r'貼文數[：:]\s*(\d+(?:[,，]\d+)*)',
            r'(\d+)\s*則貼文',
            r'(\d+)\s*貼文',
            r'posts[：:]\s*(\d+(?:[,，]\d+)*)',
        ]
        for pattern in posts_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                posts_str = match.group(1).replace(',', '').replace('，', '').replace('.', '')
                try:
                    info["posts"] = int(posts_str)
                except:
                    pass
                if info["posts"] > 0:
                    break
        
        return info
    
    def analyze_profile(self, profile_image: Image.Image) -> tuple[str, str]:
        """
        分析 IG 截圖（使用兩階段處理）
        
        Args:
            profile_image: IG 個人頁截圖
            
        Returns:
            (完整分析文字, 風趣短評) 的元組
        """
        print("[IGAnalyzer] 開始分析流程（兩階段處理）")
        
        # 1. 處理圖片
        print("[IGAnalyzer] Step 1: 處理圖片")
        image_base64 = self.image_processor.resize_and_encode(profile_image)
        
        # 2. 第一階段：描述圖片內容
        print("[IGAnalyzer] Step 2: 第一階段 - 描述圖片內容")
        image_description = self.openai.describe_image(image_base64)
        
        # 3. 第二階段：基於描述生成完整分析和 JSON
        print("[IGAnalyzer] Step 3: 第二階段 - 生成完整分析")
        raw_answer = self.openai.analyze_image(
            image_base64, 
            PromptBuilder.DEFAULT_QUESTION
        )
        
        # 4. 清理完整分析回應
        print("[IGAnalyzer] Step 4: 清理完整分析回應")
        clean_answer = self.cleaner.clean_response(raw_answer)
        
        # 5. 從描述中提取基本資訊（用於生成更準確的短評）
        print("[IGAnalyzer] Step 5: 從描述中提取基本資訊")
        basic_info_from_desc = self._extract_basic_info_from_description(image_description)
        print(f"[IGAnalyzer] 提取的基本資訊: {basic_info_from_desc}")
        
        # 6. 第三階段：基於描述生成風趣短評
        print("[IGAnalyzer] Step 6: 第三階段 - 生成風趣短評")
        try:
            review = self.openai.generate_review_from_description(image_description, basic_info_from_desc)
        except Exception as e:
            print(f"[IGAnalyzer] ⚠️ 生成風趣短評失敗: {e}，使用備用方案")
            import traceback
            traceback.print_exc()
            # 如果生成失敗，基於提取的資訊生成備用短評
            if basic_info_from_desc and basic_info_from_desc.get('followers', 0) > 0:
                followers = basic_info_from_desc['followers']
                if followers < 1000:
                    review = f"這個帳號有 {followers} 個粉絲，雖然不多但起步不錯，繼續努力說不定哪天就爆紅了（笑）"
                elif followers < 10000:
                    review = f"這個帳號有 {followers//1000}K 粉絲，已經算是小有名氣了，內容再精緻一點應該能吸引更多品牌合作（笑）"
                else:
                    review = f"這個帳號有 {followers//1000}K 粉絲，已經有一定的影響力了，建議多發 Reels 提升互動率，商業價值會更高（笑）"
            else:
                review = "這個帳號看起來還不錯，但 AI 偵探今天有點害羞，建議你重新上傳一張更清晰的截圖，讓我能好好分析一下（笑）"
        
        print("[IGAnalyzer] ✅ 兩階段分析完成")
        return clean_answer, review