#!/usr/bin/env python3
"""
簡單的測試腳本，用於測試 /bd/analyze 端點
"""

import requests
import sys

def test_analyze_endpoint(image_path):
    """測試分析端點"""
    url = "http://localhost:8000/bd/analyze"
    
    print(f"測試文件: {image_path}")
    
    try:
        with open(image_path, 'rb') as f:
            files = {
                'profile': (image_path, f, 'image/jpeg')
            }
            
            print("發送請求...")
            response = requests.post(url, files=files, timeout=120)
            
            print(f"狀態碼: {response.status_code}")
            print(f"回應頭: {dict(response.headers)}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 成功!")
                print(f"回應數據: {data.get('ok', False)}")
                if not data.get('ok'):
                    print(f"錯誤: {data.get('error', '未知錯誤')}")
            else:
                print(f"❌ 錯誤: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"錯誤訊息: {error_data}")
                except:
                    print(f"回應內容: {response.text[:500]}")
                    
    except FileNotFoundError:
        print(f"❌ 文件不存在: {image_path}")
    except Exception as e:
        print(f"❌ 請求失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_analyze.py <圖片路徑>")
        print("例如: python test_analyze.py static/examples/correct-example.jpg")
        sys.exit(1)
    
    test_analyze_endpoint(sys.argv[1])



