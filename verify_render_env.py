#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
驗證 Render 環境變數設定
根據用戶提供的環境變數列表進行檢查
"""

import json

# 用戶在 Render 上設定的環境變數列表
render_env_vars = [
    'AI_ON',
    'APP_BASE_URL',  # ✅ 必需
    'AUTH_FAILURE_URL',  # ✅ 可選
    'AUTH_SUCCESS_URL',  # ✅ 可選
    'AX_IMG_SIDE',
    'DATABASE_URL',  # ✅ 必需
    'FB_REDIRECT_URI',
    'FIREBASE_SERVICE_ACCOUNT',  # ✅ 必需
    'FRONTEND_ORIGIN',
    'IG_BASIC_APP_ID',
    'IG_BASIC_APP_SECRET',
    'JPEG_QUALITY',
    'JWT_SECRET',  # ✅ 必需
    'OPENAI_API_KEY',  # ✅ 已設定
    'PORT',
    'SESSION_SECRET',
    'SITE_URL',
    'THREADS',
    'TIMEOUT',
    'WEB_CONCURRENCY',
]

# 必需變數（根據我們的實作）
required_vars = {
    'FIREBASE_SERVICE_ACCOUNT': {
        'description': 'Firebase 服務帳號 JSON',
        'format': 'JSON 字串（單行）',
        'check': 'validate_json'
    },
    'DATABASE_URL': {
        'description': '資料庫連線字串',
        'format': 'postgresql://user:pass@host:port/dbname 或 sqlite:///path',
        'check': 'validate_db_url'
    },
    'JWT_SECRET': {
        'description': 'JWT 簽章密鑰',
        'format': '至少 32 字符的隨機字串',
        'check': 'validate_jwt_secret'
    },
    'APP_BASE_URL': {
        'description': '應用程式基礎 URL',
        'format': 'https://your-app.onrender.com',
        'check': 'validate_url'
    }
}

# 建議設定的變數
recommended_vars = {
    'OPENAI_API_KEY': 'OpenAI API 金鑰（已設定 ✅）',
    'AUTH_SUCCESS_URL': '登入成功後跳轉 URL（已設定 ✅）',
    'AUTH_FAILURE_URL': '登入失敗後跳轉 URL（已設定 ✅）',
}

# 可能不需要的變數（根據我們的實作）
unused_vars = [
    'FB_REDIRECT_URI',  # 我們使用 Firebase，不需要 Facebook OAuth redirect
    'IG_BASIC_APP_ID',  # 可能用於其他功能
    'IG_BASIC_APP_SECRET',  # 可能用於其他功能
    'FRONTEND_ORIGIN',  # 可能用於 CORS，但我們已經有 CORS 設定
    'SESSION_SECRET',  # 我們使用 JWT，不需要 session
    'SITE_URL',  # 可能與 APP_BASE_URL 重複
]

def validate_json(value):
    """驗證 JSON 格式"""
    try:
        data = json.loads(value)
        if data.get('type') != 'service_account':
            return False, "type 必須是 'service_account'"
        required_fields = ['project_id', 'private_key', 'client_email']
        for field in required_fields:
            if field not in data:
                return False, f"缺少必要欄位: {field}"
        return True, "JSON 格式正確"
    except json.JSONDecodeError as e:
        return False, f"JSON 格式錯誤: {e}"

def validate_db_url(value):
    """驗證資料庫 URL"""
    if value.startswith('postgresql://') or value.startswith('postgres://'):
        return True, "PostgreSQL 格式正確"
    elif value.startswith('sqlite:///'):
        return True, "SQLite 格式（本地開發）"
    else:
        return False, "不支援的資料庫類型"

def validate_jwt_secret(value):
    """驗證 JWT Secret"""
    if len(value) < 16:
        return False, "長度應至少 16 字符（建議 32+）"
    if value == 'dev-secret-change-me':
        return False, "不應使用預設值"
    return True, "格式正確"

def validate_url(value):
    """驗證 URL"""
    if not value.startswith('http://') and not value.startswith('https://'):
        return False, "必須以 http:// 或 https:// 開頭"
    if value.endswith('/'):
        return False, "不應包含尾隨斜線"
    return True, "URL 格式正確"

def main():
    print("=" * 70)
    print("Render 環境變數設定檢查")
    print("=" * 70)
    print()
    
    # 檢查必需變數
    print("【必需環境變數檢查】")
    print("-" * 70)
    all_required_set = True
    
    for var_name, info in required_vars.items():
        if var_name in render_env_vars:
            print(f"✅ {var_name}: 已設定")
            print(f"   {info['description']}")
            print(f"   格式: {info['format']}")
            print()
        else:
            print(f"❌ {var_name}: 未設定（必需）")
            print(f"   {info['description']}")
            print(f"   格式: {info['format']}")
            print()
            all_required_set = False
    
    # 檢查建議變數
    print("\n【建議環境變數檢查】")
    print("-" * 70)
    for var_name, description in recommended_vars.items():
        if var_name in render_env_vars:
            print(f"✅ {var_name}: {description}")
        else:
            print(f"⚠️  {var_name}: 未設定（建議設定）")
    
    # 檢查可能不需要的變數
    print("\n【可能不需要的變數】")
    print("-" * 70)
    print("以下變數在你的設定中存在，但根據目前的實作可能不需要：")
    for var_name in unused_vars:
        if var_name in render_env_vars:
            print(f"  • {var_name}")
    print("\n注意：這些變數不會造成問題，只是可能用於其他功能。")
    
    # 其他變數
    print("\n【其他環境變數】")
    print("-" * 70)
    other_vars = [v for v in render_env_vars 
                  if v not in required_vars 
                  and v not in recommended_vars 
                  and v not in unused_vars]
    for var_name in other_vars:
        print(f"  • {var_name}: 已設定（可能用於其他功能）")
    
    # 總結
    print("\n" + "=" * 70)
    if all_required_set:
        print("✅ 所有必需環境變數都已設定！")
        print()
        print("下一步：")
        print("1. 確認 FIREBASE_SERVICE_ACCOUNT 是有效的 JSON 字串（單行）")
        print("2. 確認 DATABASE_URL 格式正確")
        print("3. 確認 JWT_SECRET 足夠長（建議 32+ 字符）")
        print("4. 確認 APP_BASE_URL 是你的 Render 服務 URL")
        print("5. 部署後訪問 /debug/auth-status 驗證配置")
    else:
        print("❌ 部分必需環境變數未設定")
        print()
        print("請在 Render Dashboard → Environment 中設定缺少的變數")
    
    print("\n" + "=" * 70)
    print("驗證建議：")
    print("1. 部署後訪問: https://your-app.onrender.com/debug/auth-status")
    print("2. 檢查所有項目是否為 true")
    print("3. 如果 Firebase 初始化失敗，檢查 FIREBASE_SERVICE_ACCOUNT 格式")
    print("4. 如果資料庫連線失敗，檢查 DATABASE_URL 格式")
    print("=" * 70)

if __name__ == '__main__':
    main()

