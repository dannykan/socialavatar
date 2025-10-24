#!/usr/bin/env python3
"""
環境設置腳本 - 幫助設置 OpenAI API Key
"""

import os
import sys

def setup_api_key():
    """設置 OpenAI API Key"""
    print("🔑 OpenAI API Key 設置")
    print("=" * 40)
    
    # 檢查是否已經設置
    current_key = os.getenv("OPENAI_API_KEY")
    if current_key:
        print(f"✅ 已設置 API Key: {current_key[:10]}...")
        return True
    
    print("請選擇設置方式：")
    print("1. 手動設置環境變數")
    print("2. 創建 .env 文件")
    print("3. 直接輸入 API Key")
    
    choice = input("\n請選擇 (1-3): ").strip()
    
    if choice == "1":
        print("\n📝 手動設置方法：")
        print("在終端機中執行：")
        print("export OPENAI_API_KEY='sk-your-actual-api-key-here'")
        print("python app.py")
        return False
    
    elif choice == "2":
        api_key = input("請輸入你的 OpenAI API Key: ").strip()
        if not api_key.startswith("sk-"):
            print("❌ API Key 格式不正確，應該以 'sk-' 開頭")
            return False
        
        # 創建 .env 文件
        with open(".env", "w") as f:
            f.write(f"OPENAI_API_KEY={api_key}\n")
            f.write("OPENAI_MODEL=gpt-4o\n")
            f.write("MAX_SIDE=1280\n")
            f.write("JPEG_QUALITY=72\n")
            f.write("PORT=8000\n")
        
        print("✅ .env 文件已創建")
        print("⚠️  請確保 .env 文件在 .gitignore 中，避免提交到版本控制")
        return True
    
    elif choice == "3":
        api_key = input("請輸入你的 OpenAI API Key: ").strip()
        if not api_key.startswith("sk-"):
            print("❌ API Key 格式不正確，應該以 'sk-' 開頭")
            return False
        
        # 設置環境變數
        os.environ["OPENAI_API_KEY"] = api_key
        print("✅ API Key 已設置（僅限當前會話）")
        return True
    
    else:
        print("❌ 無效選擇")
        return False

def test_api_key():
    """測試 API Key 是否有效"""
    print("\n🧪 測試 API Key...")
    
    try:
        from ai_analyzer import OpenAIAnalyzer
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ 未設置 API Key")
            return False
        
        analyzer = OpenAIAnalyzer(api_key)
        
        # 創建測試圖片
        from PIL import Image
        import io
        import base64
        
        test_img = Image.new('RGB', (100, 100), color='red')
        buf = io.BytesIO()
        test_img.save(buf, format='JPEG')
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode('utf-8')
        
        # 測試 API 調用
        result = analyzer.analyze_image(
            img_b64, 
            "請描述這張圖片的顏色",
            max_tokens=50
        )
        
        print("✅ API Key 有效，測試成功！")
        print(f"✅ AI 回應: {result[:100]}...")
        return True
        
    except Exception as e:
        print(f"❌ API Key 測試失敗: {e}")
        return False

def main():
    """主函數"""
    print("🚀 OpenAI API Key 設置工具")
    print("=" * 40)
    
    # 設置 API Key
    if not setup_api_key():
        return
    
    # 測試 API Key
    if test_api_key():
        print("\n🎉 設置完成！現在可以運行完整測試了")
        print("執行: python test_local.py")
    else:
        print("\n⚠️  API Key 設置有問題，請檢查")

if __name__ == "__main__":
    main()
