# ai_analyzer.py - 固定問題版本

import io
import base64
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
    DEFAULT_QUESTION = "此 IG 帳號如果要賣掉的話值多少錢，為什麼？怎麼精算出來的？Post 和 Reels 應該怎麼計價？"
    
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
        
        return f"""請根據這個 Instagram 截圖回答以下問題：

{final_question}

請詳細說明你的分析邏輯和計算過程，提供清晰的推理步驟。
請使用繁體中文回答，所有價格以新台幣 (NT$) 計算。"""


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


class OpenAIAnalyzer:
    """OpenAI 分析器"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.openai.com/v1/chat/completions"
    
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
        
        response = requests.post(
            self.api_url, 
            headers=headers, 
            json=payload, 
            timeout=90
        )
        response.raise_for_status()
        
        data = response.json()
        raw_text = data["choices"][0]["message"]["content"]
        
        print(f"[OpenAI] ✅ 回應長度: {len(raw_text)}")
        
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
        self.openai = OpenAIAnalyzer(api_key, model)
        self.cleaner = ResponseCleaner()
    
    def analyze_profile(self, profile_image: Image.Image) -> str:
        """
        分析 IG 截圖（使用預設問題）
        
        Args:
            profile_image: IG 個人頁截圖
            
        Returns:
            AI 的回答（純文字）
        """
        print("[IGAnalyzer] 開始分析流程")
        
        # 1. 處理圖片
        print("[IGAnalyzer] Step 1: 處理圖片")
        image_base64 = self.image_processor.resize_and_encode(profile_image)
        
        # 2. 使用固定問題調用 OpenAI
        print("[IGAnalyzer] Step 2: 調用 OpenAI API（使用固定問題）")
        raw_answer = self.openai.analyze_image(
            image_base64, 
            PromptBuilder.DEFAULT_QUESTION
        )
        
        # 3. 清理回應
        print("[IGAnalyzer] Step 3: 清理回應")
        clean_answer = self.cleaner.clean_response(raw_answer)
        
        print("[IGAnalyzer] ✅ 分析完成")
        return clean_answer