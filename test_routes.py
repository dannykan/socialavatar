#!/usr/bin/env python3
# 測試路由是否正確註冊

import requests

BASE_URL = 'http://localhost:8000'

print("測試路由...")
print("=" * 50)

# 測試健康檢查
print("\n1. 測試 /health")
try:
    r = requests.get(f'{BASE_URL}/health', timeout=2)
    print(f"   狀態: {r.status_code}")
    if r.status_code == 200:
        print("   ✅ 正常")
    else:
        print(f"   ❌ 異常: {r.text[:100]}")
except Exception as e:
    print(f"   ❌ 錯誤: {e}")

# 測試管理員 API（無認證）
print("\n2. 測試 /api/admin/stats (無認證)")
try:
    r = requests.get(f'{BASE_URL}/api/admin/stats', timeout=2)
    print(f"   狀態: {r.status_code}")
    print(f"   Content-Type: {r.headers.get('content-type', 'unknown')}")
    if r.status_code == 404:
        print("   ❌ 路由不存在 (404)")
        print(f"   回應: {r.text[:200]}")
    elif r.status_code in [401, 403]:
        print(f"   ✅ 路由存在，正確拒絕未認證請求 ({r.status_code})")
        try:
            data = r.json()
            print(f"   錯誤訊息: {data.get('error', 'unknown')}")
        except:
            print(f"   回應: {r.text[:200]}")
    else:
        print(f"   ⚠️  意外狀態碼: {r.status_code}")
        print(f"   回應: {r.text[:200]}")
except Exception as e:
    print(f"   ❌ 錯誤: {e}")

# 測試其他端點
print("\n3. 測試 /api/user/stats (用戶端點，應該存在)")
try:
    r = requests.get(f'{BASE_URL}/api/user/stats', timeout=2)
    print(f"   狀態: {r.status_code}")
    if r.status_code == 404:
        print("   ❌ 路由不存在")
    elif r.status_code == 401:
        print("   ✅ 路由存在，需要認證")
    else:
        print(f"   ⚠️  狀態: {r.status_code}")
except Exception as e:
    print(f"   ❌ 錯誤: {e}")

print("\n" + "=" * 50)
print("測試完成")

