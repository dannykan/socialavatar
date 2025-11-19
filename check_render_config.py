#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render 設定檢查腳本
用於檢查環境變數和配置是否正確
"""

import os
import json
import sys

def check_env_var(name, required=True, validator=None):
    """檢查環境變數"""
    value = os.getenv(name)
    if not value:
        if required:
            print(f"❌ {name}: 未設定（必需）")
            return False
        else:
            print(f"⚠️  {name}: 未設定（可選）")
            return True
    
    if validator:
        try:
            validator(value)
            print(f"✅ {name}: 已設定且格式正確")
            return True
        except Exception as e:
            print(f"❌ {name}: 格式錯誤 - {e}")
            return False
    else:
        # 只顯示前 50 個字符，避免顯示敏感資訊
        display_value = value[:50] + "..." if len(value) > 50 else value
        print(f"✅ {name}: 已設定 ({display_value})")
        return True

def validate_firebase_service_account(value):
    """驗證 Firebase 服務帳號 JSON"""
    try:
        if value.startswith('{'):
            # JSON 字串格式
            data = json.loads(value)
        else:
            # 檔案路徑格式
            if not os.path.exists(value):
                raise ValueError(f"檔案不存在: {value}")
            with open(value, 'r') as f:
                data = json.load(f)
        
        # 檢查必要欄位
        required_fields = ['type', 'project_id', 'private_key', 'client_email']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"缺少必要欄位: {field}")
        
        if data.get('type') != 'service_account':
            raise ValueError("type 必須是 'service_account'")
        
        return True
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 格式錯誤: {e}")

def validate_database_url(value):
    """驗證資料庫 URL"""
    if not value:
        raise ValueError("資料庫 URL 不能為空")
    
    # 基本格式檢查
    if value.startswith('sqlite:///'):
        print("  ℹ️  使用 SQLite 資料庫（本地開發）")
    elif value.startswith('postgresql://') or value.startswith('postgres://'):
        print("  ℹ️  使用 PostgreSQL 資料庫（生產環境）")
    else:
        raise ValueError("不支援的資料庫類型，應為 sqlite:/// 或 postgresql://")

def validate_jwt_secret(value):
    """驗證 JWT Secret"""
    if len(value) < 16:
        raise ValueError("JWT Secret 長度應至少 16 個字符（建議 32+）")
    if value == 'dev-secret-change-me':
        print("  ⚠️  警告：使用預設的開發用 Secret，生產環境應使用隨機字串")

def main():
    print("=" * 60)
    print("Render 設定檢查")
    print("=" * 60)
    print()
    
    checks = []
    
    # 必需環境變數
    print("【必需環境變數】")
    checks.append(check_env_var('FIREBASE_SERVICE_ACCOUNT', required=True, validator=validate_firebase_service_account))
    checks.append(check_env_var('DATABASE_URL', required=True, validator=validate_database_url))
    checks.append(check_env_var('JWT_SECRET', required=True, validator=validate_jwt_secret))
    checks.append(check_env_var('APP_BASE_URL', required=True))
    print()
    
    # 可選環境變數
    print("【可選環境變數】")
    check_env_var('OPENAI_API_KEY', required=False)
    check_env_var('OPENAI_MODEL', required=False)
    check_env_var('AUTH_SUCCESS_URL', required=False)
    check_env_var('AUTH_FAILURE_URL', required=False)
    check_env_var('GOOGLE_CLIENT_ID', required=False)
    check_env_var('GOOGLE_CLIENT_SECRET', required=False)
    check_env_var('FACEBOOK_CLIENT_ID', required=False)
    check_env_var('FACEBOOK_CLIENT_SECRET', required=False)
    print()
    
    # 檢查 Python 依賴
    print("【Python 依賴檢查】")
    dependencies = [
        'flask',
        'flask_cors',
        'PIL',
        'requests',
        'sqlalchemy',
        'jwt',
        'firebase_admin',
    ]
    
    for dep in dependencies:
        try:
            if dep == 'PIL':
                __import__('PIL')
            elif dep == 'jwt':
                __import__('jwt')
            else:
                __import__(dep)
            print(f"✅ {dep}: 已安裝")
        except ImportError:
            print(f"❌ {dep}: 未安裝")
            checks.append(False)
    print()
    
    # 總結
    print("=" * 60)
    if all(checks):
        print("✅ 所有必需設定檢查通過！")
        print()
        print("下一步：")
        print("1. 確認 Render 環境變數已設定")
        print("2. 部署應用程式到 Render")
        print("3. 檢查 Render 日誌確認沒有錯誤")
        return 0
    else:
        print("❌ 部分設定檢查失敗，請修正後重試")
        print()
        print("常見問題：")
        print("1. FIREBASE_SERVICE_ACCOUNT: 確保是完整的 JSON 字串")
        print("2. DATABASE_URL: 確保格式正確（postgresql://user:pass@host:port/dbname）")
        print("3. JWT_SECRET: 使用長隨機字串（建議使用 openssl rand -hex 32）")
        return 1

if __name__ == '__main__':
    sys.exit(main())

