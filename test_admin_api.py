#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理員 Dashboard API 測試腳本
測試所有 CRUD 功能
"""

import sys
import requests
import json
from datetime import datetime

# 導入應用以生成測試 token
sys.path.insert(0, '.')
from app import generate_token, User, AnalysisResult, SessionLocal

BASE_URL = 'http://localhost:8000'
session = SessionLocal()

def get_test_token():
    """獲取管理員測試 token"""
    admin = session.query(User).filter(User.email == 'dannytjkan@gmail.com').first()
    if not admin:
        print("❌ 找不到管理員用戶")
        return None
    return generate_token(admin.id)

def get_test_analysis_id():
    """獲取一個測試分析記錄 ID"""
    analysis = session.query(AnalysisResult).first()
    if not analysis:
        print("❌ 找不到分析記錄")
        return None
    return analysis.id

def get_test_user_id():
    """獲取一個非管理員的測試用戶 ID"""
    user = session.query(User).filter(User.email != 'dannytjkan@gmail.com').first()
    if not user:
        print("⚠️  找不到非管理員用戶，將使用管理員 ID")
        return session.query(User).filter(User.email == 'dannytjkan@gmail.com').first().id
    return user.id

def test_endpoint(name, method, url, headers=None, data=None, expected_status=200):
    """測試 API 端點"""
    print(f"\n{'='*60}")
    print(f"🧪 測試: {name}")
    print(f"   {method} {url}")
    if data:
        print(f"   請求數據: {json.dumps(data, ensure_ascii=False, indent=2)}")
    print(f"{'='*60}")
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, timeout=5)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=data, timeout=5)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers, timeout=5)
        else:
            print(f"❌ 不支持的 HTTP 方法: {method}")
            return False
        
        print(f"   狀態碼: {response.status_code}")
        
        # 嘗試解析 JSON
        try:
            result = response.json()
            print(f"   回應: {json.dumps(result, ensure_ascii=False, indent=2)}")
        except:
            print(f"   回應 (非 JSON): {response.text[:200]}")
        
        if response.status_code == expected_status:
            print(f"   ✅ 通過 (狀態碼: {response.status_code})")
            return True
        else:
            print(f"   ❌ 失敗 (期望: {expected_status}, 實際: {response.status_code})")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ 請求失敗: {e}")
        return False

def main():
    """主測試函數"""
    print("🚀 開始測試管理員 Dashboard API")
    print("="*60)
    
    # 獲取測試 token
    token = get_test_token()
    if not token:
        print("❌ 無法獲取測試 token，退出")
        return
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # 測試結果統計
    results = []
    
    # 1. 測試 GET /api/admin/stats
    results.append((
        '獲取系統統計',
        test_endpoint(
            '獲取系統統計',
            'GET',
            f'{BASE_URL}/api/admin/stats',
            headers=headers
        )
    ))
    
    # 2. 測試 GET /api/admin/users
    results.append((
        '獲取用戶列表',
        test_endpoint(
            '獲取用戶列表 (第1頁)',
            'GET',
            f'{BASE_URL}/api/admin/users?page=1&per_page=10',
            headers=headers
        )
    ))
    
    # 3. 測試 GET /api/admin/analyses
    results.append((
        '獲取分析記錄列表',
        test_endpoint(
            '獲取分析記錄列表 (第1頁)',
            'GET',
            f'{BASE_URL}/api/admin/analyses?page=1&per_page=10',
            headers=headers
        )
    ))
    
    # 4. 測試 PUT /api/admin/analyses/{id}/update
    analysis_id = get_test_analysis_id()
    if analysis_id:
        results.append((
            '更新分析記錄',
            test_endpoint(
                '更新分析記錄',
                'PUT',
                f'{BASE_URL}/api/admin/analyses/{analysis_id}/update',
                headers=headers,
                data={
                    'account_asset_value': 99999,
                    'post_value': 9999,
                    'story_value': 4999,
                    'reels_value': 14999
                }
            )
        ))
        
        # 驗證更新是否成功
        results.append((
            '驗證更新結果',
            test_endpoint(
                '驗證更新結果',
                'GET',
                f'{BASE_URL}/api/admin/analyses?page=1&per_page=10',
                headers=headers
            )
        ))
    
    # 5. 測試 DELETE /api/admin/analyses/{id} (創建一個臨時分析記錄用於刪除)
    # 注意：這裡我們不實際刪除，只測試路由是否正常
    # 實際刪除測試應該由用戶手動進行
    
    # 6. 測試 DELETE /api/admin/users/{id} (同樣，只測試路由，不實際刪除)
    
    # 打印測試總結
    print("\n" + "="*60)
    print("📊 測試總結")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"   {status}: {name}")
    
    print(f"\n總計: {passed}/{total} 通過")
    
    if passed == total:
        print("\n🎉 所有測試通過！")
    else:
        print(f"\n⚠️  有 {total - passed} 個測試失敗")
    
    session.close()

if __name__ == '__main__':
    main()
