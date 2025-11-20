#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
數據庫檢查和診斷腳本
"""

import os
import sys
import sqlite3
from datetime import datetime

def check_database():
    """檢查數據庫狀態"""
    db_path = 'data/results.db'
    
    if not os.path.exists(db_path):
        print(f"❌ 數據庫檔案不存在: {db_path}")
        print("   數據庫會在首次運行 app.py 時自動創建")
        return False
    
    print(f"✅ 數據庫檔案存在: {db_path}")
    print(f"   大小: {os.path.getsize(db_path) / 1024:.2f} KB")
    print()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 檢查表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"📊 數據庫表 ({len(tables)} 個):")
        for table in tables:
            print(f"   - {table}")
        print()
        
        # 檢查 users 表
        if 'users' in tables:
            cursor.execute("SELECT COUNT(*) FROM users;")
            user_count = cursor.fetchone()[0]
            print(f"👥 用戶數: {user_count}")
            
            if user_count > 0:
                cursor.execute("""
                    SELECT id, email, username, display_name, provider, created_at 
                    FROM users 
                    ORDER BY created_at DESC 
                    LIMIT 5;
                """)
                users = cursor.fetchall()
                print("   最近註冊的用戶:")
                for user in users:
                    print(f"      ID: {user[0]}, Email: {user[1]}, Username: {user[2]}")
                    print(f"            Display: {user[3]}, Provider: {user[4]}")
                    print(f"            Created: {user[5]}")
                    print()
        else:
            print("⚠️  users 表不存在")
        print()
        
        # 檢查 analysis_results 表
        if 'analysis_results' in tables:
            cursor.execute("SELECT COUNT(*) FROM analysis_results;")
            analysis_count = cursor.fetchone()[0]
            print(f"📋 分析記錄數: {analysis_count}")
            
            if analysis_count > 0:
                cursor.execute("""
                    SELECT id, username, user_id, display_name, created_at 
                    FROM analysis_results 
                    ORDER BY created_at DESC 
                    LIMIT 5;
                """)
                analyses = cursor.fetchall()
                print("   最近的分析記錄:")
                for analysis in analyses:
                    user_info = f"User ID: {analysis[2]}" if analysis[2] else "匿名"
                    print(f"      ID: {analysis[0]}, Username: @{analysis[1]}")
                    print(f"            {user_info}, Display: {analysis[3]}")
                    print(f"            Created: {analysis[4]}")
                    print()
                
                # 統計有用戶的分析 vs 匿名分析
                cursor.execute("SELECT COUNT(*) FROM analysis_results WHERE user_id IS NOT NULL;")
                with_user = cursor.fetchone()[0]
                anonymous = analysis_count - with_user
                print(f"   有用戶的分析: {with_user}")
                print(f"   匿名分析: {anonymous}")
        else:
            print("⚠️  analysis_results 表不存在")
        print()
        
        # 檢查表結構
        print("🔍 表結構檢查:")
        for table in ['users', 'analysis_results']:
            if table in tables:
                cursor.execute(f"PRAGMA table_info({table});")
                columns = cursor.fetchall()
                print(f"   {table} 表欄位:")
                for col in columns:
                    nullable = "NULL" if col[3] == 0 else "NOT NULL"
                    default = f" DEFAULT {col[4]}" if col[4] else ""
                    print(f"      - {col[1]} ({col[2]}) {nullable}{default}")
        
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"❌ 數據庫錯誤: {e}")
        return False

def check_env():
    """檢查環境變數"""
    print("🔧 環境變數檢查:")
    print("=" * 50)
    
    admin_emails = os.getenv('ADMIN_EMAILS', '')
    if admin_emails:
        print(f"✅ ADMIN_EMAILS: {admin_emails}")
    else:
        print("❌ ADMIN_EMAILS: 未設定")
        print("   請執行: ./setup_admin_local.sh")
        print("   或設定: export ADMIN_EMAILS=your-email@gmail.com")
    
    print()
    
    # 檢查其他重要變數
    important_vars = {
        'OPENAI_API_KEY': 'OpenAI API 金鑰',
        'DATABASE_URL': '數據庫 URL（可選，預設使用 SQLite）',
        'JWT_SECRET': 'JWT 密鑰（可選，有預設值）',
        'FIREBASE_SERVICE_ACCOUNT': 'Firebase 服務帳號（必須）'
    }
    
    for var, desc in important_vars.items():
        value = os.getenv(var)
        if value:
            if var in ['OPENAI_API_KEY', 'FIREBASE_SERVICE_ACCOUNT']:
                print(f"✅ {var}: 已設定 ({len(value)} 字符)")
            else:
                print(f"✅ {var}: 已設定")
        else:
            print(f"⚠️  {var}: 未設定 - {desc}")
    
    print()
    
    # 檢查 .env.local
    if os.path.exists('.env.local'):
        print("📄 .env.local 檔案存在")
        with open('.env.local', 'r') as f:
            content = f.read()
            if 'ADMIN_EMAILS' in content:
                print("✅ .env.local 包含 ADMIN_EMAILS")
                for line in content.split('\n'):
                    if line.startswith('ADMIN_EMAILS'):
                        print(f"   {line}")
            else:
                print("⚠️  .env.local 不包含 ADMIN_EMAILS")
    else:
        print("📄 .env.local 檔案不存在")
        print("   可以執行: ./setup_admin_local.sh 來創建")

if __name__ == '__main__':
    print("=" * 50)
    print("數據庫和環境檢查")
    print("=" * 50)
    print()
    
    check_env()
    print()
    check_database()
    
    print()
    print("=" * 50)
    print("檢查完成")
    print("=" * 50)

