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
    DEFAULT_QUESTION = "請分析這個 Instagram 帳號的商業價值和影響力，包括內容品質、粉絲互動、品牌潛力等面向，並提供具體的評估指標和建議。"
    
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