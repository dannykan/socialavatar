#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
創建測試數據腳本
用於本地測試管理員 Dashboard
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# 設定管理員 Email
ADMIN_EMAIL = 'dannytjkan@gmail.com'

def create_test_data():
    """創建測試數據"""
    db_path = 'data/results.db'
    
    if not os.path.exists(db_path):
        print(f"❌ 數據庫檔案不存在: {db_path}")
        print("   請先運行 app.py 以創建數據庫")
        return False
    
    print("🔧 創建測試數據...")
    print("=" * 50)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. 創建管理員用戶
        print("\n1. 創建管理員用戶...")
        cursor.execute("""
            SELECT id FROM users WHERE email = ?
        """, (ADMIN_EMAIL,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            admin_user_id = existing_user[0]
            print(f"   ✅ 管理員用戶已存在 (ID: {admin_user_id})")
        else:
            cursor.execute("""
                INSERT INTO users (email, username, display_name, password_hash, provider, provider_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ADMIN_EMAIL,
                'dannytjkan',
                'Danny Kan',
                generate_password_hash('dummy-password'),
                'google',
                'google_123456',
                datetime.utcnow(),
                datetime.utcnow()
            ))
            admin_user_id = cursor.lastrowid
            print(f"   ✅ 創建管理員用戶 (ID: {admin_user_id}, Email: {ADMIN_EMAIL})")
        
        # 2. 創建其他測試用戶
        print("\n2. 創建測試用戶...")
        test_users = [
            ('user1@example.com', 'user1', 'User One', 'google', 'google_111'),
            ('user2@example.com', 'user2', 'User Two', 'facebook', 'fb_222'),
            ('user3@example.com', 'user3', 'User Three', 'google', 'google_333'),
        ]
        
        created_users = []
        for email, username, display_name, provider, provider_id in test_users:
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                print(f"   ⚠️  用戶已存在: {email}")
                continue
            
            cursor.execute("""
                INSERT INTO users (email, username, display_name, password_hash, provider, provider_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                email, username, display_name,
                generate_password_hash('dummy-password'),
                provider, provider_id,
                datetime.utcnow() - timedelta(days=len(created_users)),
                datetime.utcnow()
            ))
            user_id = cursor.lastrowid
            created_users.append(user_id)
            print(f"   ✅ 創建用戶: {email} (ID: {user_id})")
        
        # 3. 創建測試分析記錄
        print("\n3. 創建測試分析記錄...")
        
        # 為管理員創建一些分析記錄
        admin_analyses = [
            {
                'username': 'dannytjkan',
                'display_name': 'Danny Kan',
                'followers': 5000,
                'value': 50000
            },
            {
                'username': 'dannytjkan',
                'display_name': 'Danny Kan',
                'followers': 5500,
                'value': 55000
            },
        ]
        
        # 為其他用戶創建分析記錄
        other_analyses = [
            {'username': 'foodie_taipei', 'display_name': 'Foodie Taipei', 'followers': 12000, 'value': 80000, 'user_id': created_users[0] if created_users else None},
            {'username': 'travel_lover', 'display_name': 'Travel Lover', 'followers': 8000, 'value': 60000, 'user_id': created_users[1] if len(created_users) > 1 else None},
            {'username': 'fitness_guru', 'display_name': 'Fitness Guru', 'followers': 15000, 'value': 100000, 'user_id': created_users[2] if len(created_users) > 2 else None},
        ]
        
        # 創建一些匿名分析
        anonymous_analyses = [
            {'username': 'anonymous1', 'display_name': 'Anonymous User 1', 'followers': 3000, 'value': 30000},
            {'username': 'anonymous2', 'display_name': 'Anonymous User 2', 'followers': 2000, 'value': 20000},
        ]
        
        all_analyses = admin_analyses + other_analyses + anonymous_analyses
        
        created_analyses = 0
        for i, analysis in enumerate(all_analyses):
            username_key = analysis['username'].replace('@', '').strip().lower()
            
            # 檢查是否已存在
            cursor.execute("SELECT id FROM analysis_results WHERE username_key = ?", (username_key,))
            if cursor.fetchone():
                print(f"   ⚠️  分析記錄已存在: @{analysis['username']}")
                continue
            
            # 創建分析數據 JSON
            analysis_data = {
                'username': analysis['username'],
                'display_name': analysis['display_name'],
                'followers': analysis['followers'],
                'value_estimation': {
                    'account_asset_value': analysis['value'],
                    'post_value': analysis['value'] * 0.1,
                    'story_value': analysis['value'] * 0.05,
                    'reels_value': analysis['value'] * 0.15,
                },
                'analysis_text': f"這是 {analysis['display_name']} 的測試分析記錄。",
                'created_at': (datetime.utcnow() - timedelta(days=i)).isoformat()
            }
            
            cursor.execute("""
                INSERT INTO analysis_results (username, username_key, display_name, user_id, data, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis['username'],
                username_key,
                analysis['display_name'],
                analysis.get('user_id') or admin_user_id if 'user_id' not in analysis else None,
                json.dumps(analysis_data, ensure_ascii=False),
                datetime.utcnow() - timedelta(days=i),
                datetime.utcnow()
            ))
            created_analyses += 1
            user_info = f"User ID: {analysis.get('user_id', admin_user_id)}" if analysis.get('user_id') or i < len(admin_analyses) else "匿名"
            print(f"   ✅ 創建分析記錄: @{analysis['username']} ({user_info}, 價值: ${analysis['value']:,})")
        
        conn.commit()
        
        print("\n" + "=" * 50)
        print("✅ 測試數據創建完成！")
        print("=" * 50)
        
        # 顯示統計
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM analysis_results")
        analysis_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM analysis_results WHERE user_id IS NOT NULL")
        with_user_count = cursor.fetchone()[0]
        
        print(f"\n📊 數據統計:")
        print(f"   用戶數: {user_count}")
        print(f"   分析記錄數: {analysis_count}")
        print(f"   有用戶的分析: {with_user_count}")
        print(f"   匿名分析: {analysis_count - with_user_count}")
        print(f"\n🔐 管理員 Email: {ADMIN_EMAIL}")
        print(f"\n🚀 現在可以:")
        print(f"   1. 啟動服務器: python3 app.py")
        print(f"   2. 訪問: http://localhost:8000/static/admin-dashboard.html")
        
        conn.close()
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()
        conn.close()
        return False

if __name__ == '__main__':
    create_test_data()

