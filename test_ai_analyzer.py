# test_ai_analyzer.py - AI 分析模組測試
"""
測試和示範 ai_analyzer 模組的使用
"""

import os
from PIL import Image
from ai_analyzer import (
    ImageProcessor,
    PromptBuilder,
    ResponseParser,
    OpenAIAnalyzer,
    IGAnalyzer
)


def test_image_processor():
    """測試圖片處理器"""
    print("\n" + "="*60)
    print("測試 ImageProcessor")
    print("="*60)
    
    processor = ImageProcessor(max_side=1280, quality=72)
    
    # 創建一個測試圖片
    test_img = Image.new('RGB', (2000, 1500), color='red')
    
    print(f"原始圖片尺寸: {test_img.size}")
    
    b64_str = processor.resize_and_encode(test_img)
    
    print(f"✅ Base64 編碼完成，長度: {len(b64_str)}")
    print(f"✅ 圖片已調整大小並編碼")


def test_prompt_builder():
    """測試 Prompt 構建器"""
    print("\n" + "="*60)
    print("測試 PromptBuilder")
    print("="*60)
    
    builder = PromptBuilder()
    
    # 測試 OCR prompt
    ocr_prompt = builder.build_ocr_prompt()
    print(f"✅ OCR Prompt 長度: {len(ocr_prompt)}")
    print(f"前 100 字:\n{ocr_prompt[:100]}...\n")
    
    # 測試分析 prompt
    analysis_prompt = builder.build_analysis_prompt(
        followers=12000,
        following=800,
        posts=350
    )
    print(f"✅ Analysis Prompt 長度: {len(analysis_prompt)}")
    print(f"前 100 字:\n{analysis_prompt[:100]}...\n")


def test_response_parser():
    """測試回應解析器"""
    print("\n" + "="*60)
    print("測試 ResponseParser")
    print("="*60)
    
    parser = ResponseParser()
    
    # 測試案例 1: 標準 JSON
    test_text_1 = """
    這是一些分析文字。
    
    ```json
    {
        "account_value": {"min": 50000, "max": 80000, "reasoning": "test"},
        "pricing": {"post": 15000, "story": 6000, "reels": 20000},
        "visual_quality": {"overall": 7.5},
        "content_type": {"primary": "生活記錄", "commercial_potential": "medium"},
        "professionalism": {"brand_identity": 7.0},
        "uniqueness": {"creativity_score": 7.0},
        "audience_value": {"audience_tier": "一般用戶"},
        "improvement_tips": ["建議1", "建議2"]
    }
    ```
    """
    
    result = parser.extract_json_from_text(test_text_1)
    if result:
        print("✅ 測試案例 1: 標準 JSON - 通過")
    else:
        print("❌ 測試案例 1: 標準 JSON - 失敗")
    
    # 測試案例 2: 末尾 JSON（沒有代碼塊）
    test_text_2 = """
    這是一些分析文字。
    
    {"account_value": {"min": 50000, "max": 80000, "reasoning": "test"}, "pricing": {"post": 15000, "story": 6000, "reels": 20000}, "visual_quality": {"overall": 7.5}, "content_type": {"primary": "生活記錄", "commercial_potential": "medium"}, "professionalism": {"brand_identity": 7.0}, "uniqueness": {"creativity_score": 7.0}, "audience_value": {"audience_tier": "一般用戶"}, "improvement_tips": ["建議1", "建議2"]}
    """
    
    result = parser.extract_json_from_text(test_text_2)
    if result:
        print("✅ 測試案例 2: 末尾 JSON - 通過")
    else:
        print("❌ 測試案例 2: 末尾 JSON - 失敗")
    
    # 測試案例 3: 混合文字和 JSON
    test_text_3 = """
    根據分析，這個帳號有以下特點：
    1. 視覺品質良好
    2. 內容定位明確
    3. 粉絲互動活躍
    
    以下是詳細的評估數據：
    
    {
        "account_value": {
            "min": 50000,
            "max": 80000,
            "reasoning": "基於粉絲數和內容品質"
        },
        "pricing": {
            "post": 15000,
            "story": 6000,
            "reels": 20000
        },
        "visual_quality": {
            "overall": 7.5
        },
        "content_type": {
            "primary": "生活記錄",
            "commercial_potential": "medium"
        },
        "professionalism": {
            "brand_identity": 7.0
        },
        "uniqueness": {
            "creativity_score": 7.0
        },
        "audience_value": {
            "audience_tier": "一般用戶"
        },
        "improvement_tips": [
            "增加與粉絲的互動",
            "提升內容品質",
            "擴展內容類型"
        ]
    }
    
    以上是完整的分析結果。
    """
    
    analysis_text, json_data = parser.parse_analysis_result(test_text_3)
    if json_data:
        print("✅ 測試案例 3: 混合文字和 JSON - 通過")
        print(f"   分析文字長度: {len(analysis_text)}")
        print(f"   JSON 鍵: {list(json_data.keys())}")
    else:
        print("❌ 測試案例 3: 混合文字和 JSON - 失敗")


def test_openai_analyzer():
    """測試 OpenAI 分析器（需要 API key）"""
    print("\n" + "="*60)
    print("測試 OpenAIAnalyzer")
    print("="*60)
    
    api_key = os.getenv("OPENAI_API_KEY", "")
    
    if not api_key:
        print("⚠️  未設置 OPENAI_API_KEY，跳過此測試")
        return
    
    analyzer = OpenAIAnalyzer(api_key, model="gpt-4o-mini")
    
    # 創建一個簡單的測試圖片
    test_img = Image.new('RGB', (500, 500), color='blue')
    processor = ImageProcessor()
    b64_img = processor.resize_and_encode(test_img)
    
    try:
        result = analyzer.analyze(
            images=[b64_img],
            user_prompt="請描述這張圖片的顏色。",
            system_prompt="",
            max_tokens=100,
            temperature=0.3
        )
        
        print(f"✅ API 調用成功")
        print(f"回應長度: {len(result)}")
        print(f"回應內容: {result[:200]}...")
        
    except Exception as e:
        print(f"❌ API 調用失敗: {e}")


def test_ig_analyzer():
    """測試完整的 IG 分析器（需要 API key 和測試圖片）"""
    print("\n" + "="*60)
    print("測試 IGAnalyzer（完整流程）")
    print("="*60)
    
    api_key = os.getenv("OPENAI_API_KEY", "")
    
    if not api_key:
        print("⚠️  未設置 OPENAI_API_KEY，跳過此測試")
        return
    
    # 檢查是否有測試圖片
    test_profile_path = "test_profile.jpg"
    if not os.path.exists(test_profile_path):
        print(f"⚠️  找不到測試圖片: {test_profile_path}")
        print("提示: 請準備一張 IG 個人頁截圖命名為 test_profile.jpg")
        return
    
    try:
        # 載入測試圖片
        profile_img = Image.open(test_profile_path)
        
        # 創建分析器
        analyzer = IGAnalyzer(
            api_key=api_key,
            model="gpt-4o-mini",  # 使用較便宜的模型進行測試
            max_side=1280,
            quality=72
        )
        
        # 執行分析
        print("開始分析...")
        result = analyzer.analyze_profile(profile_img, post_images=None)
        
        print("\n✅ 分析完成！")
        print(f"用戶名: {result['username']}")
        print(f"粉絲數: {result['followers']:,}")
        print(f"追蹤數: {result['following']:,}")
        print(f"貼文數: {result['posts']:,}")
        print(f"帳號價值範圍: NT$ {result['value_estimation']['account_value_min']:,} ~ {result['value_estimation']['account_value_max']:,}")
        print(f"發文價值: NT$ {result['value_estimation']['post_value']:,}")
        print(f"\n分析文字:")
        print(result['analysis_text'][:300] + "...")
        
    except Exception as e:
        print(f"❌ 分析失敗: {e}")
        import traceback
        traceback.print_exc()


def run_all_tests():
    """運行所有測試"""
    print("\n")
    print("="*60)
    print("AI Analyzer 模組測試")
    print("="*60)
    
    test_image_processor()
    test_prompt_builder()
    test_response_parser()
    test_openai_analyzer()
    test_ig_analyzer()
    
    print("\n")
    print("="*60)
    print("測試完成")
    print("="*60)


if __name__ == "__main__":
    run_all_tests()
