#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IG Value Estimation System V5
主應用程式 - Flask 服務器
"""

import os
import json
import re
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode, urljoin
import requests
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
from PIL import Image
import io
import jwt
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker, joinedload, relationship
from werkzeug.security import generate_password_hash, check_password_hash
from ai_analyzer import IGAnalyzer, PromptBuilder

# 載入 .env 檔案（如果存在）
try:
    from dotenv import load_dotenv
    load_dotenv('.env.local')  # 優先載入 .env.local
    load_dotenv()  # 然後載入 .env（如果存在）
except ImportError:
    pass  # dotenv 是可選的

# 初始化 Flask 應用
app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)

# 環境變數配置
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
# 模型選擇：
# - gpt-4o: 當前穩定版本，準確度高，支持視覺任務（推薦，GPT-5.1 可能不可用）
# - gpt-4o-mini: 較便宜，速度較快，適合預算有限的情況
# - gpt-5.1: 最新模型（如果可用）
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o')
PORT = int(os.getenv('PORT', 8000))
MAX_SIDE = int(os.getenv('MAX_SIDE', 1280))
JPEG_QUALITY = int(os.getenv('JPEG_QUALITY', 72))
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///data/results.db')
JWT_SECRET = os.getenv('JWT_SECRET', 'dev-secret-change-me')
JWT_EXPIRES_MINUTES = int(os.getenv('JWT_EXPIRES_MINUTES', 60 * 24))  # default 1 day
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
APP_BASE_URL = os.getenv('APP_BASE_URL', 'http://localhost:8000')
AUTH_SUCCESS_URL = os.getenv('AUTH_SUCCESS_URL', '/static/upload.html')
AUTH_FAILURE_URL = os.getenv('AUTH_FAILURE_URL', '/static/landing.html')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
# 管理員 Email 列表（用逗號分隔）
ADMIN_EMAILS = [email.strip().lower() for email in os.getenv('ADMIN_EMAILS', '').split(',') if email.strip()]
FACEBOOK_CLIENT_ID = os.getenv('FACEBOOK_CLIENT_ID')
FACEBOOK_CLIENT_SECRET = os.getenv('FACEBOOK_CLIENT_SECRET')
FACEBOOK_API_VERSION = os.getenv('FACEBOOK_API_VERSION', 'v18.0')
FIREBASE_SERVICE_ACCOUNT = os.getenv('FIREBASE_SERVICE_ACCOUNT')

# 初始化 AI 分析器
analyzer = None
last_ai_response = None

# -----------------------------------------------------------------------------
# Database Setup
# -----------------------------------------------------------------------------
engine_kwargs = {}
if DATABASE_URL.startswith('sqlite'):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    db_path = DATABASE_URL.replace('sqlite:///', '')
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
firebase_app = None

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    username = Column(String(255), nullable=False, unique=True, index=True)
    display_name = Column(String(255))
    password_hash = Column(String(255), nullable=False)
    avatar_url = Column(String(512))
    provider = Column(String(50))
    provider_id = Column(String(255), index=True)
    provider_data = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(255), nullable=False)
    username_key = Column(String(255), nullable=False, unique=True, index=True)
    display_name = Column(String(255))
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    data = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 關聯到 User
    user = relationship("User", backref="analyses")

def ensure_analysis_user_column():
    try:
        with engine.connect() as conn:
            dialect = engine.dialect.name
            if dialect == 'sqlite':
                cols = [row[1] for row in conn.execute(text("PRAGMA table_info(analysis_results)"))]
                if 'user_id' not in cols:
                    conn.execute(text("ALTER TABLE analysis_results ADD COLUMN user_id INTEGER"))
                user_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(users)"))}
                if 'provider' not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN provider TEXT"))
                if 'provider_id' not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN provider_id TEXT"))
                if 'provider_data' not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN provider_data TEXT"))
            else:
                conn.execute(text("ALTER TABLE analysis_results ADD COLUMN IF NOT EXISTS user_id INTEGER"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS provider VARCHAR(50)"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS provider_id VARCHAR(255)"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS provider_data TEXT"))
    except Exception as e:
        print(f"[DB] ⚠️ 檢查/新增 user_id 欄位失敗: {e}")

def init_db():
    try:
        Base.metadata.create_all(engine)
        ensure_analysis_user_column()
        print("[DB] ✅ 資料庫初始化完成")
    except SQLAlchemyError as e:
        print(f"[DB] ❌ 初始化失敗: {e}")

init_db()

def init_firebase():
    global firebase_app
    if not FIREBASE_SERVICE_ACCOUNT:
        print("[Firebase] ⚠️ 未設定 FIREBASE_SERVICE_ACCOUNT，略過 Firebase 初始化")
        return None
    if firebase_app:
        return firebase_app
    try:
        cred_source = FIREBASE_SERVICE_ACCOUNT.strip()
        if cred_source.startswith('{'):
            cred_data = json.loads(cred_source)
            cred = credentials.Certificate(cred_data)
        else:
            if not os.path.exists(cred_source):
                raise FileNotFoundError(f"找不到 Firebase 憑證檔案: {cred_source}")
            cred = credentials.Certificate(cred_source)
        firebase_app = firebase_admin.initialize_app(cred)
        print("[Firebase] ✅ 初始化成功")
        return firebase_app
    except Exception as e:
        print(f"[Firebase] ❌ 初始化失敗: {e}")
        firebase_app = None
        return None

init_firebase()

def init_analyzer():
    """初始化 AI 分析器"""
    global analyzer
    if not OPENAI_API_KEY:
        print("⚠️ 警告: OPENAI_API_KEY 未設置，部分功能可能無法使用")
        return None
    
    # 檢查 API Key 是否為佔位符
    if OPENAI_API_KEY in ['your-key', 'sk-your-api-key-here', '']:
        print("❌ 錯誤: OPENAI_API_KEY 是佔位符，請設置真實的 API Key")
        print("   請運行: export OPENAI_API_KEY='sk-...'")
        return None
    
    # 檢查 API Key 格式
    if not OPENAI_API_KEY.startswith('sk-'):
        print("⚠️ 警告: OPENAI_API_KEY 格式可能不正確（應該以 'sk-' 開頭）")
    
    # 支持的模型列表（按優先順序）
    supported_models = ['gpt-5.1', 'gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo']
    fallback_models = ['gpt-4o', 'gpt-4o-mini']
    
    model_to_try = OPENAI_MODEL
    models_tried = []
    
    while model_to_try:
        try:
            print(f"[初始化] 嘗試使用模型: {model_to_try}")
            analyzer = IGAnalyzer(
                api_key=OPENAI_API_KEY,
                model=model_to_try,
                max_side=MAX_SIDE,
                quality=JPEG_QUALITY
            )
            print(f"✅ AI 分析器初始化成功 (模型: {model_to_try})")
            return analyzer
        except Exception as e:
            error_msg = str(e)
            models_tried.append(model_to_try)
            print(f"⚠️ 模型 {model_to_try} 初始化失敗: {error_msg}")
            
            # 如果是模型不存在的錯誤，嘗試下一個備用模型
            if 'model' in error_msg.lower() or 'not found' in error_msg.lower() or 'invalid' in error_msg.lower():
                if model_to_try in supported_models:
                    # 找到當前模型在列表中的位置，嘗試下一個
                    try:
                        current_idx = supported_models.index(model_to_try)
                        if current_idx + 1 < len(supported_models):
                            model_to_try = supported_models[current_idx + 1]
                            print(f"[初始化] 嘗試備用模型: {model_to_try}")
                            continue
                    except ValueError:
                        pass
                
                # 如果不在列表中或沒有下一個，嘗試備用模型
                for fallback in fallback_models:
                    if fallback not in models_tried:
                        model_to_try = fallback
                        print(f"[初始化] 嘗試備用模型: {fallback}")
                        break
                else:
                    model_to_try = None
            else:
                # 其他錯誤（如 API Key 問題），不嘗試其他模型
                print(f"❌ AI 分析器初始化失敗: {e}")
                return None
    
    print(f"❌ 所有模型都無法使用。已嘗試: {', '.join(models_tried)}")
    return None

# 啟動時初始化
init_analyzer()

# -----------------------------------------------------------------------------
# Database Helpers
# -----------------------------------------------------------------------------
def normalize_username(value):
    if not value:
        return ""
    return str(value).replace('@', '').strip().lower()

def serialize_user(user):
    if not user:
        return None
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "provider": user.provider,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None
    }

def generate_unique_username(session, base):
    base = base or secrets.token_hex(4)
    base = base.strip().lower()
    if not base:
        base = secrets.token_hex(4)
    candidate = base
    counter = 1
    while session.query(User).filter_by(username=candidate).first():
        candidate = f"{base}{counter}"
        counter += 1
    return candidate

def generate_token(user_id):
    payload = {
        "sub": str(user_id),  # JWT sub 必須是字符串
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRES_MINUTES)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        print(f"[Auth] ✅ Token 驗證成功: user_id={payload.get('sub')}")
        return payload
    except jwt.ExpiredSignatureError:
        print(f"[Auth] ❌ Token 已過期")
        raise AuthError("token_expired", 401)
    except jwt.InvalidTokenError as e:
        print(f"[Auth] ❌ Token 無效: {e}")
        print(f"[Auth] Token 前50字符: {token[:50] if token else 'None'}...")
        raise AuthError("invalid_token", 401)

class AuthError(Exception):
    def __init__(self, message, status=401):
        super().__init__(message)
        self.message = message
        self.status = status
    
    def to_dict(self):
        return {"ok": False, "error": self.message}

def save_analysis_result(payload):
    if not payload:
        return
    username_key = normalize_username(payload.get("username") or payload.get("plain_username"))
    if not username_key:
        return
    session = SessionLocal()
    try:
        serialized = json.dumps(payload, ensure_ascii=False)
        record = session.query(AnalysisResult).filter_by(username_key=username_key).first()
        if record:
            record.username = payload.get("username", record.username)
            record.display_name = payload.get("display_name", record.display_name)
            record.user_id = payload.get("user_id", record.user_id)
            record.data = serialized
        else:
            record = AnalysisResult(
                username=payload.get("username", username_key),
                username_key=username_key,
                display_name=payload.get("display_name", ""),
                user_id=payload.get("user_id"),
                data=serialized
            )
            session.add(record)
        session.commit()
        print(f"[DB] ✅ 已儲存分析結果: {username_key}")
    except SQLAlchemyError as e:
        session.rollback()
        print(f"[DB] ❌ 儲存結果失敗: {e}")
    finally:
        session.close()

def get_analysis_result(username):
    username_key = normalize_username(username)
    if not username_key:
        return None
    session = SessionLocal()
    try:
        record = session.query(AnalysisResult).filter_by(username_key=username_key).first()
        if record:
            return json.loads(record.data)
    except SQLAlchemyError as e:
        print(f"[DB] ❌ 讀取結果失敗: {e}")
    finally:
        session.close()
    return None

def build_redirect_url(base_url, token, new_user=False):
    if not base_url.startswith('http'):
        base_url = urljoin(APP_BASE_URL.rstrip('/') + '/', base_url.lstrip('/'))
    sep = '&' if '?' in base_url else '?'
    url = f"{base_url}{sep}token={token}"
    if new_user:
        url += "&new_user=1"
    return url

def build_failure_redirect(message="auth_failed"):
    base_url = AUTH_FAILURE_URL or AUTH_SUCCESS_URL
    if not base_url.startswith('http'):
        base_url = urljoin(APP_BASE_URL.rstrip('/') + '/', base_url.lstrip('/'))
    sep = '&' if '?' in base_url else '?'
    return f"{base_url}{sep}error={message}"

def login_with_provider(provider, provider_id, profile):
    email = (profile.get("email") or "").strip().lower()
    display_name = profile.get("display_name") or profile.get("name") or email or provider_id
    avatar_url = profile.get("avatar_url")
    session = SessionLocal()
    try:
        user = session.query(User).filter(
            (User.provider == provider) & (User.provider_id == provider_id)
        ).first()
        if not user and email:
            user = session.query(User).filter(User.email == email).first()
        new_user = False
        if not user:
            new_user = True
            username_base = normalize_username(profile.get("username") or email or f"{provider}_{provider_id}")
            username = generate_unique_username(session, username_base)
            password_stub = generate_password_hash(secrets.token_hex(16))
            user = User(
                email=email or f"{provider_id}@{provider}.local",
                username=username,
                display_name=display_name or username,
                password_hash=password_stub,
                avatar_url=avatar_url,
                provider=provider,
                provider_id=provider_id,
                provider_data=json.dumps(profile, ensure_ascii=False)
            )
            session.add(user)
        else:
            if display_name:
                user.display_name = display_name
            if avatar_url:
                user.avatar_url = avatar_url
            if email and not user.email:
                user.email = email
            user.provider = provider
            user.provider_id = provider_id
            user.provider_data = json.dumps(profile, ensure_ascii=False)
        session.commit()
        serialized = serialize_user(user)
        token = generate_token(user.id)
        return token, serialized, new_user
    finally:
        session.close()

def get_authenticated_user(required=False):
    auth_header = request.headers.get('Authorization', '')
    if not auth_header:
        if required:
            print(f"[Auth] ❌ 缺少 Authorization header")
            raise AuthError("authorization_header_missing", 401)
        return None
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        if required:
            print(f"[Auth] ❌ Authorization header 格式錯誤: {auth_header[:50]}")
            raise AuthError("invalid_authorization_header", 401)
        # 如果不是 required，靜默返回 None（允許匿名使用）
        return None
    token = parts[1]
    print(f"[Auth] 🔍 驗證 token，長度: {len(token)}")
    try:
        payload = decode_token(token)
    except AuthError as e:
        # Token 驗證失敗
        if required:
            print(f"[Auth] ❌ Token 驗證失敗 (required=True): {e.message}")
            raise e
        # 如果不是 required，記錄警告但允許繼續（匿名使用）
        print(f"[Auth] ⚠️ Token 驗證失敗但允許匿名使用: {e.message}")
        return None
    except Exception as e:
        # 其他錯誤
        print(f"[Auth] ❌ Token 解析異常: {e}")
        import traceback
        traceback.print_exc()
        if required:
            raise AuthError("token_verification_failed", 401)
        print(f"[Auth] ⚠️ Token 解析失敗但允許匿名使用: {e}")
        return None
    
    user_id_str = payload.get("sub")
    if not user_id_str:
        if required:
            raise AuthError("invalid_token_payload", 401)
        return None
    # 將字符串轉換為整數（JWT sub 是字符串，但數據庫 ID 是整數）
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        if required:
            raise AuthError("invalid_user_id_in_token", 401)
        return None
    session = SessionLocal()
    try:
        user = session.get(User, user_id)
        if not user:
            if required:
                raise AuthError("user_not_found", 401)
            return None
        return serialize_user(user)
    finally:
        session.close()

def verify_firebase_token(id_token):
    if not firebase_app:
        raise AuthError("firebase_not_configured", 500)
    try:
        return firebase_auth.verify_id_token(id_token, app=firebase_app)
    except firebase_auth.ExpiredIdTokenError:
        raise AuthError("firebase_token_expired", 401)
    except firebase_auth.InvalidIdTokenError:
        raise AuthError("firebase_token_invalid", 401)
    except Exception:
        raise AuthError("firebase_token_verification_failed", 401)

# -----------------------------------------------------------------------------
# User Prompt Builder (Safe Version)
# -----------------------------------------------------------------------------
def build_user_prompt(followers, following, posts):
    """構建用戶提示詞"""
    # 第一部分：動態數據（使用 f-string）
    header = f"分析這個 IG 帳號截圖。數據：粉絲 {followers}, 追蹤 {following}, 貼文 {posts}。"
    
    # 第二部分：靜態指令（使用普通字符串，不需要雙括號轉義，更安全）
    body = """
請完成兩個任務：

1. **專業短評 (Analysis Text)**：
用 200 字以內，針對其「商業變現潛力」給出評價。指出優點與缺點。

2. **數據提取 (JSON)**：
請嚴格回傳以下 JSON：

```json
{
  "visual_quality": { 
    "overall": 7.5,  // 1.0-10.0，10分是頂級雜誌感
    "consistency": 8.0 
  },
  "content_type": {
    "primary": "美食",
    "category_tier": "mid" // high(金融/醫美/精品), mid_high(時尚/3C), mid(美食/旅遊), low(日記/迷因)
  },
  "content_format": {
    "video_focus": 3, // 1-10: 1=純圖文, 8-10=Reels創作者(影響Reels報價)
    "personal_connection": 6 // 1-10: 1=官方冷淡, 8-10=像朋友一樣(影響Story報價)
  },
  "professionalism": { 
    "has_contact": true,
    "is_business_account": false
  },
  "personality_type": { 
    "primary_type": "type_5", // 對應12型人格
    "reasoning": "簡短理由" 
  },
  "improvement_tips": [
    "建議...",
    "建議..."
  ]
}
```

請確保 JSON 格式正確，可以直接被解析。
"""
    return header + body

# -----------------------------------------------------------------------------
# Authentication Endpoints
# -----------------------------------------------------------------------------
def validate_registration_payload(data):
    email = (data.get("email") or "").strip().lower()
    username = normalize_username(data.get("username"))
    display_name = (data.get("display_name") or "").strip() or username
    password = data.get("password") or ""
    if not email or "@" not in email:
        raise AuthError("invalid_email", 400)
    if not username or len(username) < 3:
        raise AuthError("invalid_username", 400)
    if len(password) < 6:
        raise AuthError("password_too_short", 400)
    return email, username, display_name, password

@app.route('/api/auth/register', methods=['POST'])
def register_user():
    data = request.get_json() or {}
    email, username, display_name, password = validate_registration_payload(data)
    session = SessionLocal()
    try:
        existing = session.query(User).filter(
            (User.email == email) | (User.username == username)
        ).first()
        if existing:
            raise AuthError("user_exists", 400)
        user = User(
            email=email,
            username=username,
            display_name=display_name,
            password_hash=generate_password_hash(password)
        )
        session.add(user)
        session.commit()
        result = serialize_user(user)
        token = generate_token(user.id)
        return jsonify({"ok": True, "token": token, "user": result}), 201
    except AuthError as e:
        session.rollback()
        raise e
    except SQLAlchemyError as e:
        session.rollback()
        print(f"[DB] ❌ 註冊失敗: {e}")
        return jsonify({"ok": False, "error": "register_failed"}), 500
    finally:
        session.close()

@app.route('/api/auth/login', methods=['POST'])
def login_user():
    data = request.get_json() or {}
    identifier = (data.get("email") or data.get("username") or "").strip().lower()
    password = data.get("password") or ""
    if not identifier or not password:
        raise AuthError("missing_credentials", 400)
    session = SessionLocal()
    try:
        user = session.query(User).filter(
            (User.email == identifier) | (User.username == normalize_username(identifier))
        ).first()
        if not user or not check_password_hash(user.password_hash, password):
            raise AuthError("invalid_credentials", 401)
        token = generate_token(user.id)
        return jsonify({"ok": True, "token": token, "user": serialize_user(user)})
    finally:
        session.close()

@app.route('/api/auth/me')
def get_me():
    user = get_authenticated_user(required=True)
    return jsonify({"ok": True, "user": user})

@app.route('/api/auth/firebase-login', methods=['POST'])
def firebase_login():
    data = request.get_json() or {}
    id_token = (data.get("id_token") or "").strip()
    if not id_token:
        raise AuthError("missing_id_token", 400)
    
    # 如果 Firebase 未配置，使用本地開發模式
    if not firebase_app:
        print("[Auth] ⚠️ Firebase 未配置，使用本地開發模式")
        # 嘗試從 token 中提取信息（如果是 JWT）
        try:
            import base64
            # JWT token 格式：header.payload.signature
            parts = id_token.split('.')
            if len(parts) >= 2:
                # 解碼 payload
                payload = parts[1]
                # 添加 padding（如果需要）
                padding = 4 - (len(payload) % 4)
                if padding != 4:
                    payload += '=' * padding
                
                decoded_bytes = base64.urlsafe_b64decode(payload)
                decoded_payload = json.loads(decoded_bytes)
                
                # Firebase ID token 的字段名稱
                email = decoded_payload.get("email") or decoded_payload.get("email_address")
                name = decoded_payload.get("name") or decoded_payload.get("display_name")
                # Firebase 使用 'sub' 作為 user ID
                uid = decoded_payload.get("sub") or decoded_payload.get("user_id") or decoded_payload.get("uid")
                
                if not email:
                    print(f"[Auth] ⚠️ Token 中沒有 email，可用字段: {list(decoded_payload.keys())[:10]}")
                    # 如果沒有 email，嘗試使用其他方式
                    # 檢查是否有其他標識符
                    if not uid:
                        raise AuthError("email_not_found_in_token", 400)
                    # 使用 uid 創建一個臨時 email
                    email = f"{uid}@firebase.local"
                    print(f"[Auth] 使用臨時 email: {email}")
                
                print(f"[Auth] 本地模式：從 token 提取 email={email}, uid={uid}, name={name}")
                
                # 使用 email 作為 provider_id
                provider = "firebase"
                provider_id = uid or email
                profile = {
                    "email": email,
                    "display_name": name or email.split("@")[0],
                    "avatar_url": decoded_payload.get("picture"),
                    "username": email.split("@")[0] if email else "user"
                }
                token, user, new_user = login_with_provider(provider, provider_id, profile)
                print(f"[Auth] ✅ 本地模式登入成功: {email}")
                return jsonify({"ok": True, "token": token, "user": user, "new_user": new_user})
        except json.JSONDecodeError as e:
            print(f"[Auth] ❌ JSON 解析失敗: {e}")
            print(f"[Auth] Payload 長度: {len(payload) if 'payload' in locals() else 'N/A'}")
        except Exception as e:
            import traceback
            print(f"[Auth] ❌ 本地模式解析 token 失敗: {e}")
            traceback.print_exc()
        
        # 如果解析失敗，返回錯誤
        return jsonify({
            "ok": False, 
            "error": "firebase_not_configured", 
            "message": "Firebase 未配置且無法解析 token。請設定 FIREBASE_SERVICE_ACCOUNT 環境變數。"
        }), 500
    
    # 正常流程：使用 Firebase 驗證
    decoded = verify_firebase_token(id_token)
    provider = decoded.get("firebase", {}).get("sign_in_provider", "firebase")
    provider_id = decoded.get("uid")
    if not provider_id:
        raise AuthError("firebase_uid_missing", 400)
    profile = {
        "email": decoded.get("email"),
        "display_name": decoded.get("name"),
        "avatar_url": decoded.get("picture"),
        "username": decoded.get("email") or decoded.get("name") or provider_id
    }
    token, user, new_user = login_with_provider(provider, provider_id, profile)
    return jsonify({"ok": True, "token": token, "user": user, "new_user": new_user})

# -----------------------------------------------------------------------------
# OAuth Routes
# -----------------------------------------------------------------------------
def get_google_redirect_uri():
    return urljoin(APP_BASE_URL.rstrip('/') + '/', 'api/auth/google/callback')

def get_facebook_redirect_uri():
    return urljoin(APP_BASE_URL.rstrip('/') + '/', 'api/auth/facebook/callback')

@app.route('/api/auth/google/login')
def google_login():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return jsonify({"ok": False, "error": "google_oauth_not_configured"}), 500
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": get_google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account"
    }
    return redirect(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")

@app.route('/api/auth/google/callback')
def google_callback():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return redirect(build_failure_redirect("google_not_configured"))
    code = request.args.get('code')
    if not code:
        return redirect(build_failure_redirect("missing_code"))
    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": get_google_redirect_uri()
        },
        timeout=30
    )
    if token_resp.status_code != 200:
        return redirect(build_failure_redirect("google_token_failed"))
    tokens = token_resp.json()
    access_token = tokens.get("access_token")
    if not access_token:
        return redirect(build_failure_redirect("google_token_missing"))
    profile_resp = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30
    )
    if profile_resp.status_code != 200:
        return redirect(build_failure_redirect("google_profile_failed"))
    info = profile_resp.json()
    provider_id = info.get("sub")
    if not provider_id:
        return redirect(build_failure_redirect("google_profile_invalid"))
    profile = {
        "email": info.get("email"),
        "display_name": info.get("name"),
        "avatar_url": info.get("picture"),
        "username": info.get("preferred_username") or info.get("email")
    }
    token, user, new_user = login_with_provider("google", provider_id, profile)
    success_url = build_redirect_url(AUTH_SUCCESS_URL, token, new_user)
    return redirect(success_url)

@app.route('/api/auth/facebook/login')
def facebook_login():
    if not FACEBOOK_CLIENT_ID or not FACEBOOK_CLIENT_SECRET:
        return jsonify({"ok": False, "error": "facebook_oauth_not_configured"}), 500
    params = {
        "client_id": FACEBOOK_CLIENT_ID,
        "redirect_uri": get_facebook_redirect_uri(),
        "response_type": "code",
        "scope": "email,public_profile"
    }
    return redirect(f"https://www.facebook.com/{FACEBOOK_API_VERSION}/dialog/oauth?{urlencode(params)}")

@app.route('/api/auth/facebook/callback')
def facebook_callback():
    if not FACEBOOK_CLIENT_ID or not FACEBOOK_CLIENT_SECRET:
        return redirect(build_failure_redirect("facebook_not_configured"))
    code = request.args.get('code')
    if not code:
        return redirect(build_failure_redirect("missing_code"))
    token_params = {
        "client_id": FACEBOOK_CLIENT_ID,
        "client_secret": FACEBOOK_CLIENT_SECRET,
        "redirect_uri": get_facebook_redirect_uri(),
        "code": code
    }
    token_resp = requests.get(
        f"https://graph.facebook.com/{FACEBOOK_API_VERSION}/oauth/access_token",
        params=token_params,
        timeout=30
    )
    if token_resp.status_code != 200:
        return redirect(build_failure_redirect("facebook_token_failed"))
    access_token = token_resp.json().get("access_token")
    if not access_token:
        return redirect(build_failure_redirect("facebook_token_missing"))
    profile_resp = requests.get(
        f"https://graph.facebook.com/{FACEBOOK_API_VERSION}/me",
        params={
            "fields": "id,name,email,picture",
            "access_token": access_token
        },
        timeout=30
    )
    if profile_resp.status_code != 200:
        return redirect(build_failure_redirect("facebook_profile_failed"))
    info = profile_resp.json()
    provider_id = info.get("id")
    if not provider_id:
        return redirect(build_failure_redirect("facebook_profile_invalid"))
    picture = info.get("picture", {}).get("data", {}).get("url")
    profile = {
        "email": info.get("email"),
        "display_name": info.get("name"),
        "avatar_url": picture,
        "username": info.get("email") or info.get("name")
    }
    token, user, new_user = login_with_provider("facebook", provider_id, profile)
    success_url = build_redirect_url(AUTH_SUCCESS_URL, token, new_user)
    return redirect(success_url)

# -----------------------------------------------------------------------------
# 人格類型映射
# -----------------------------------------------------------------------------
PERSONALITY_TYPES = {
    "type_1": {"emoji": "🌸", "name_zh": "夢幻柔焦系", "name_en": "Dreamy Aesthetic"},
    "type_2": {"emoji": "🎨", "name_zh": "藝術實驗者", "name_en": "Artistic Experimenter"},
    "type_3": {"emoji": "🏔️", "name_zh": "戶外探險家", "name_en": "Outdoor Adventurer"},
    "type_4": {"emoji": "📚", "name_zh": "知識策展人", "name_en": "Knowledge Curator"},
    "type_5": {"emoji": "🍜", "name_zh": "生活記錄者", "name_en": "Everyday Chronicler"},
    "type_6": {"emoji": "✨", "name_zh": "質感品味家", "name_en": "Refined Aesthete"},
    "type_7": {"emoji": "🎭", "name_zh": "幽默創作者", "name_en": "Humor Creator"},
    "type_8": {"emoji": "💼", "name_zh": "專業形象派", "name_en": "Professional Persona"},
    "type_9": {"emoji": "🌿", "name_zh": "永續生活者", "name_en": "Sustainable Liver"},
    "type_10": {"emoji": "🎮", "name_zh": "次文化愛好者", "name_en": "Subculture Enthusiast"},
    "type_11": {"emoji": "💪", "name_zh": "健康積極派", "name_en": "Fitness Motivator"},
    "type_12": {"emoji": "🔮", "name_zh": "靈性探索者", "name_en": "Spiritual Seeker"}
}

# -----------------------------------------------------------------------------
# 價值計算函數
# -----------------------------------------------------------------------------
def calculate_base_price(followers):
    """計算基礎價格"""
    if followers < 1000:
        return 500
    elif followers < 5000:
        return 1000
    elif followers < 10000:
        return 2000
    elif followers < 50000:
        return 5000
    elif followers < 100000:
        return 10000
    elif followers < 500000:
        return 20000
    else:
        return 50000

def calculate_multipliers(analysis_data):
    """計算所有係數"""
    multipliers = {
        "visual": 1.0,
        "content": 1.0,
        "professional": 1.0,
        "follower": 1.0,
        "unique": 1.0,
        "engagement": 1.0,
        "niche": 1.0,
        "audience": 1.0,
        "cross_platform": 1.0,
        "ratio": 1.0,
        "commercial": 1.0
    }
    
    # 視覺品質係數 (0.7 - 2.0)
    visual_quality = analysis_data.get("visual_quality", {}).get("overall", 5.0)
    multipliers["visual"] = 0.7 + (visual_quality / 10.0) * 1.3
    
    # 內容類型係數 (0.8 - 2.5)
    category_tier = analysis_data.get("content_type", {}).get("category_tier", "mid")
    tier_map = {"high": 2.5, "mid_high": 1.8, "mid": 1.2, "low": 0.8}
    multipliers["content"] = tier_map.get(category_tier, 1.2)
    
    # 專業度係數 (0.9 - 1.9)
    has_contact = analysis_data.get("professionalism", {}).get("has_contact", False)
    is_business = analysis_data.get("professionalism", {}).get("is_business_account", False)
    multipliers["professional"] = 1.0
    if has_contact:
        multipliers["professional"] += 0.3
    if is_business:
        multipliers["professional"] += 0.6
    
    # 粉絲品質係數 (0.6 - 1.5) - 基於追蹤比
    # 這裡簡化處理，實際應該從截圖中提取
    multipliers["follower"] = 1.0
    
    # 風格獨特性係數 (1.0 - 1.6)
    consistency = analysis_data.get("visual_quality", {}).get("consistency", 5.0)
    multipliers["unique"] = 1.0 + (consistency / 10.0) * 0.6
    
    # 互動潛力係數 (0.8 - 1.5)
    personal_conn = analysis_data.get("content_format", {}).get("personal_connection", 5.0)
    multipliers["engagement"] = 0.8 + (personal_conn / 10.0) * 0.7
    
    # 利基專注度係數 (0.9 - 1.6)
    multipliers["niche"] = multipliers["content"] * 0.9  # 基於內容類型
    
    # 受眾價值係數 (0.8 - 1.8)
    multipliers["audience"] = multipliers["content"] * 1.1  # 基於內容類型
    
    # 跨平台影響力係數 (0.95 - 1.4)
    multipliers["cross_platform"] = 1.0
    
    # 粉絲含金量 (ratio) - 簡化為 1.0
    multipliers["ratio"] = 1.0
    
    # 商業意圖 (commercial) - 基於專業度
    multipliers["commercial"] = multipliers["professional"]
    
    return multipliers

def calculate_values(followers, multipliers, analysis_data):
    """計算各種報價"""
    base_price = calculate_base_price(followers)
    
    # 計算總係數
    total_multiplier = (
        multipliers["visual"] *
        multipliers["content"] *
        multipliers["professional"] *
        multipliers["follower"] *
        multipliers["unique"] *
        multipliers["engagement"] *
        multipliers["niche"] *
        multipliers["audience"] *
        multipliers["cross_platform"]
    )
    
    # 貼文價值
    post_value = int(base_price * total_multiplier)
    
    # Story 價值 (基於 personal_connection)
    personal_conn = analysis_data.get("content_format", {}).get("personal_connection", 5.0)
    story_multiplier = 0.3 + (personal_conn / 10.0) * 0.1
    story_value = int(post_value * story_multiplier)
    
    # Reels 價值 (基於 video_focus)
    video_focus = analysis_data.get("content_format", {}).get("video_focus", 1.0)
    reels_multiplier = 0.8 + (video_focus / 10.0) * 0.7
    reels_value = int(post_value * reels_multiplier)
    
    # 帳號總身價 (基於粉絲數和係數)
    account_asset_value = int(followers * 10 * (total_multiplier / 2.0))
    
    return {
        "post_value": post_value,
        "story_value": story_value,
        "reels_value": reels_value,
        "account_asset_value": account_asset_value,
        "multipliers": multipliers
    }

# -----------------------------------------------------------------------------
# JSON 提取函數
# -----------------------------------------------------------------------------
def extract_json_from_text(text):
    """從文本中提取 JSON"""
    # 嘗試找到 JSON 區塊
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # 嘗試找到 { ... } 區塊
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            return None
    
    # 清理註釋
    json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None

def extract_analysis_text(text, basic_info=None):
    """提取風趣短評（約 50 字）"""
    # 優先尋找「毒舌短評：」或「風趣短評：」標記
    patterns = [
        r'(?:毒舌|風趣)短評[：:]\s*([^\n]+(?:\n[^\n]+){0,2})',  # 匹配「毒舌短評：」或「風趣短評：」後的 1-3 行
        r'\*\*(?:毒舌|風趣)短評[：:]\*\*\s*([^\n]+(?:\n[^\n]+){0,2})',  # 匹配 markdown 格式
        r'(?:毒舌|風趣)短評[：:]\*\*\s*([^\n]+(?:\n[^\n]+){0,2})',  # 匹配混合格式
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            analysis = match.group(1).strip()
            # 清理 markdown 格式
            analysis = re.sub(r'\*\*', '', analysis)
            analysis = re.sub(r'^#+\s*', '', analysis, flags=re.MULTILINE)
            # 移除多餘的空白和換行
            analysis = re.sub(r'\s+', ' ', analysis)
            analysis = analysis.strip()
            
            # 限制在 60 字以內（留一點緩衝）
            if len(analysis) > 60:
                # 嘗試在句號、逗號處截斷
                for sep in ['。', '，', ',', '.']:
                    idx = analysis[:60].rfind(sep)
                    if idx > 30:  # 至少保留 30 字
                        analysis = analysis[:idx+1]
                        break
                else:
                    analysis = analysis[:57] + '...'
            
            if analysis and len(analysis) > 10:  # 確保不是空字串或太短
                print(f"[提取] ✅ 找到毒舌短評: {analysis[:50]}...")
                return analysis
    
    # 如果沒找到標記，檢查是否 AI 拒絕回答（支援多種格式）
    text_lower = text.lower()
    rejection_phrases = [
        "i'm sorry", "i cannot", "i can't assist", "無法協助", 
        "不能協助", "抱歉，我無法", "抱歉,我無法", "抱歉我無法",
        "無法識別", "無法提取", "無法分析", "無法協助",
        "can't identify", "cannot identify", "無法識別或",
        "如果你提供", "如果你能提供", "提供文字資訊"
    ]
    
    if any(phrase in text_lower for phrase in rejection_phrases):
        print("[提取] ⚠️ 檢測到 AI 拒絕訊息，嘗試從商業價值分析中提取")
        # 嘗試從「商業價值分析」中提取一段簡短內容
        business_analysis_patterns = [
            r'商業價值分析[：:]\s*([^。]+。?)',
            r'根據提供的數據[，,]?([^。]+。?)',
            r'這個帳號[，,]?([^。]+。?)',
        ]
        
        for pattern in business_analysis_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                analysis = match.group(1).strip()
                # 清理
                analysis = re.sub(r'\*\*', '', analysis)
                analysis = re.sub(r'\s+', ' ', analysis)
                # 限制長度
                if len(analysis) > 60:
                    analysis = analysis[:57] + '...'
                if len(analysis) > 15:  # 確保有足夠內容
                    print(f"[提取] ✅ 從商業分析中提取: {analysis[:50]}...")
                    return analysis
        
        # 如果還是找不到，基於基本資訊生成風趣短評
        if basic_info:
            followers = basic_info.get('followers', 0)
            username = basic_info.get('username', 'unknown')
            
            if followers > 0:
                if followers < 1000:
                    return f"這個帳號有 {followers} 個粉絲，雖然不多但起步不錯，繼續努力說不定哪天就爆紅了（笑）"
                elif followers < 10000:
                    return f"這個帳號有 {followers//1000}K 粉絲，已經算是小有名氣了，內容再精緻一點應該能吸引更多品牌合作（笑）"
                else:
                    return f"這個帳號有 {followers//1000}K 粉絲，已經有一定的影響力了，建議多發 Reels 提升互動率，商業價值會更高（笑）"
            elif username != 'unknown':
                # 即使粉絲數為 0，如果有用戶名也能生成短評
                return f"這個帳號 @{username} 看起來剛起步，建議多發優質內容累積粉絲，說不定哪天就爆紅了（笑）"
        
    # 如果都找不到，返回預設文字（即使基本資訊為空也顯示）
    return "這個帳號看起來還不錯，但 AI 偵探今天有點害羞，建議你重新上傳一張更清晰的截圖，讓我能好好分析一下（笑）"


def finalize_short_review(text):
    """確保短評以完整句子結尾"""
    if not text:
        return ""
    text = str(text).strip()
    if not text:
        return ""
    # 移除尾端多餘的逗號、頓號或分號
    while text and text[-1] in ['，', ',', '、', '；', ';']:
        text = text[:-1].rstrip()
    # 如果最後仍無終止符號，補上一個句號
    if text and text[-1] not in "。.!?！？":
        text = text + "。"
    return text

# -----------------------------------------------------------------------------
# Helper: 將帶有 K/M 或字串格式的數字轉為整數
# -----------------------------------------------------------------------------
def parse_numeric_count(value, default=0):
    """將粉絲/追蹤/貼文數字統一轉為整數"""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except Exception:
            return default
    try:
        text = str(value).strip()
        if not text:
            return default
        multiplier = 1
        last_char = text[-1].lower()
        if last_char in ('k', 'm'):
            if last_char == 'k':
                multiplier = 1000
            elif last_char == 'm':
                multiplier = 1000000
            text = text[:-1].strip()
        text = text.replace(',', '').replace('，', '')
        if not text:
            return default
        return int(float(text) * multiplier)
    except Exception:
        return default
    
    # 如果沒找到標記，嘗試提取 JSON 之前的簡短文字（作為備用）
    json_start = text.find('```json')
    if json_start == -1:
        json_start = text.find('{')
    
    if json_start > 0:
        analysis = text[:json_start].strip()
        # 清理 markdown 格式
        analysis = re.sub(r'^#+\s*', '', analysis, flags=re.MULTILINE)
        analysis = re.sub(r'\*\*(.*?)\*\*', r'\1', analysis)
        # 移除任務標題和拒絕訊息
        analysis = re.sub(r'任務\s*\d+[：:].*?\n', '', analysis, flags=re.MULTILINE)
        analysis = re.sub(r'任務\s*\d+[：:].*?$', '', analysis, flags=re.MULTILINE)
        analysis = re.sub(r'抱歉[，,]?.*?但我可以', '', analysis, flags=re.DOTALL)
        analysis = re.sub(r'無法識別.*?但我可以', '', analysis, flags=re.DOTALL)
        # 只取第一段有意義的文字（過濾拒絕訊息）
        lines = [line.strip() for line in analysis.split('\n') 
                if line.strip() and not line.strip().startswith('**') 
                and '抱歉' not in line and '無法' not in line
                and 'i\'m sorry' not in line.lower() and 'cannot' not in line.lower()
                and '如果你提供' not in line and '提供文字' not in line]
        if lines:
            analysis = lines[0]
            # 限制長度
            if len(analysis) > 60:
                analysis = analysis[:57] + '...'
            if len(analysis) > 15:
                return analysis
    
    # 如果都找不到，返回預設文字
    return "這個帳號...嗯，還需要更多觀察才能給出風趣評價（笑）"

# -----------------------------------------------------------------------------
# 從文字中提取基本資訊（備用方法）
# -----------------------------------------------------------------------------
def extract_basic_info_from_text(text):
    """從 AI 回應文字中提取基本資訊（備用方法）"""
    info = {
        "username": "unknown",
        "display_name": "未知用戶",
        "followers": 0,
        "following": 0,
        "posts": 0
    }
    
    print("[提取] 開始從文字中提取基本資訊...")
    
    # 提取帳號名稱/用戶名（優先匹配「帳號名稱」）
    username_patterns = [
        r'帳號名稱[：:]\s*([a-zA-Z0-9_.]+)',  # 新增：匹配「帳號名稱: dannytjkan」
        r'用戶名[：:]\s*@?([a-zA-Z0-9_.]+)',
        r'@([a-zA-Z0-9_.]+)',
        r'username[：:]\s*([a-zA-Z0-9_.]+)',
        r'帳號[：:]\s*([a-zA-Z0-9_.]+)',
    ]
    for pattern in username_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            info["username"] = match.group(1).strip()
            print(f"[提取] ✅ 找到用戶名: {info['username']}")
            break
    
    # 提取顯示名稱（如果沒有找到，使用用戶名）
    display_name_patterns = [
        r'顯示名稱[：:]\s*([^\n]+)',
        r'名稱[：:]\s*([^\n]+)',
        r'display[_\s]name[：:]\s*([^\n]+)',
    ]
    for pattern in display_name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            info["display_name"] = match.group(1).strip()
            print(f"[提取] ✅ 找到顯示名稱: {info['display_name']}")
            break
    
    # 如果沒有找到顯示名稱，使用用戶名
    if info["display_name"] == "未知用戶" and info["username"] != "unknown":
        info["display_name"] = info["username"]
    
    # 提取粉絲數（優先匹配「粉絲數」）
    followers_patterns = [
        r'(\d+(?:\.\d+)?)\s*[Kk]的粉絲',  # 匹配「10.1K的粉絲」
        r'粉絲數[：:]\s*(\d+(?:[,，]\d+)*)',  # 匹配「粉絲數: 10,100」
        r'粉絲[數]?[：:]\s*(\d+(?:[,，]\d+)*)\s*[KM]?',
        r'followers[：:]\s*(\d+(?:[,，]\d+)*)\s*[KM]?',
        r'(\d+(?:[,，]\d+)*)\s*[Kk]?\s*粉絲',
        r'擁有(\d+(?:\.\d+)?)\s*[Kk]',  # 匹配「擁有10.1K」
    ]
    for pattern in followers_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            followers_str = match.group(1)
            # 檢查匹配的文本中是否包含 K 或 M
            matched_text = text[match.start():match.end()].upper()
            
            # 處理 K 格式（如 10.1K）
            if 'K' in matched_text and 'KM' not in matched_text:
                try:
                    # 保留小數點，因為可能是 10.1K
                    num = float(followers_str.replace(',', '').replace('，', ''))
                    info["followers"] = int(num * 1000)
                    print(f"[提取] ✅ 找到粉絲數 (K格式): {info['followers']} (原始: {followers_str}K)")
                except Exception as e:
                    print(f"[提取] ⚠️ 解析粉絲數失敗: {e}")
                    pass
            # 處理 M 格式
            elif 'M' in matched_text:
                try:
                    num = float(followers_str.replace(',', '').replace('，', ''))
                    info["followers"] = int(num * 1000000)
                    print(f"[提取] ✅ 找到粉絲數 (M格式): {info['followers']}")
                except Exception as e:
                    print(f"[提取] ⚠️ 解析粉絲數失敗: {e}")
                    pass
            # 純數字格式
            else:
                try:
                    info["followers"] = int(followers_str.replace(',', '').replace('，', '').replace('.', ''))
                    print(f"[提取] ✅ 找到粉絲數: {info['followers']}")
                except Exception as e:
                    print(f"[提取] ⚠️ 解析粉絲數失敗: {e}")
                    pass
            if info["followers"] > 0:
                break
    
    # 提取追蹤數（優先匹配「追蹤數」）
    following_patterns = [
        r'追蹤數[：:]\s*(\d+(?:[,，]\d+)*)',  # 新增：匹配「追蹤數: 914」
        r'追蹤[數]?[：:]\s*(\d+(?:[,，]\d+)*)\s*[KM]?',
        r'following[：:]\s*(\d+(?:[,，]\d+)*)\s*[KM]?',
    ]
    for pattern in following_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            following_str = match.group(1).replace(',', '').replace('，', '').replace('.', '')
            try:
                info["following"] = int(following_str)
                print(f"[提取] ✅ 找到追蹤數: {info['following']}")
            except:
                pass
            if info["following"] > 0:
                break
    
    # 提取貼文數（優先匹配「貼文數」）
    posts_patterns = [
        r'(\d+)\s*則貼文',  # 匹配「181則貼文」
        r'貼文數[：:]\s*(\d+(?:[,，]\d+)*)',  # 匹配「貼文數: 181」
        r'貼文[數]?[：:]\s*(\d+(?:[,，]\d+)*)\s*[KM]?',
        r'posts[：:]\s*(\d+(?:[,，]\d+)*)\s*[KM]?',
        r'(\d+)\s*貼文',  # 匹配「181貼文」
    ]
    for pattern in posts_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            posts_str = match.group(1).replace(',', '').replace('，', '').replace('.', '')
            try:
                info["posts"] = int(posts_str)
                print(f"[提取] ✅ 找到貼文數: {info['posts']}")
            except:
                pass
            if info["posts"] > 0:
                break
    
    print(f"[提取] 最終提取結果: {info}")
    return info

# -----------------------------------------------------------------------------
# Flask 路由
# -----------------------------------------------------------------------------
@app.route('/health', methods=['GET'])
def health():
    """健康檢查端點"""
    return jsonify({
        "status": "ok",
        "version": "v5",
        "model": OPENAI_MODEL,
        "ai_enabled": analyzer is not None,
        "new_features": [
            "open_ended_analysis",
            "natural_language_valuation",
            "contextual_reasoning"
        ]
    })

@app.route('/debug/config', methods=['GET'])
def debug_config():
    """查看系統配置"""
    return jsonify({
        "openai_model": OPENAI_MODEL,
        "max_side": MAX_SIDE,
        "jpeg_quality": JPEG_QUALITY,
        "port": PORT,
        "api_key_set": OPENAI_API_KEY is not None
    })

@app.route('/debug/last_ai', methods=['GET'])
def debug_last_ai():
    """查看最後一次 AI 回應"""
    global last_ai_response
    if last_ai_response:
        return jsonify({
            "response": last_ai_response,
            "length": len(last_ai_response)
        })
    return jsonify({"error": "尚未有 AI 回應"})

@app.route('/debug/auth-status', methods=['GET'])
def debug_auth_status():
    """檢查認證系統狀態"""
    status = {
        "firebase_configured": firebase_app is not None,
        "database_configured": DATABASE_URL is not None,
        "jwt_secret_set": JWT_SECRET is not None and JWT_SECRET != 'dev-secret-change-me',
        "app_base_url": APP_BASE_URL,
        "database_type": "sqlite" if DATABASE_URL.startswith('sqlite') else "postgresql" if DATABASE_URL.startswith('postgres') else "unknown"
    }
    
    # 檢查資料庫連線
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        status["database_connected"] = True
    except Exception as e:
        status["database_connected"] = False
        status["database_error"] = str(e)
    
    # 檢查 Firebase（不顯示敏感資訊）
    if firebase_app:
        try:
            # 嘗試獲取 Firebase 專案 ID（不涉及敏感操作）
            status["firebase_initialized"] = True
        except:
            status["firebase_initialized"] = False
    else:
        status["firebase_initialized"] = False
        if not FIREBASE_SERVICE_ACCOUNT:
            status["firebase_error"] = "FIREBASE_SERVICE_ACCOUNT 未設定"
        else:
            status["firebase_error"] = "Firebase 初始化失敗（檢查日誌）"
    
    return jsonify(status)

@app.route('/bd/analyze', methods=['POST'])
def analyze():
    """分析 IG 帳號"""
    global last_ai_response
    
    # 文件大小限制 (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    print("[分析] ========== 開始新的分析請求 ==========")
    print(f"[分析] 請求方法: {request.method}")
    print(f"[分析] Content-Type: {request.content_type}")
    print(f"[分析] 文件列表: {list(request.files.keys())}")
    
    try:
        current_user = get_authenticated_user(required=False)
        
        # 檢查必要文件
        if 'profile' not in request.files:
            print("[分析] ❌ 缺少 profile 文件")
            return jsonify({"ok": False, "error": "缺少 profile 圖片"}), 400
        
        profile_file = request.files['profile']
        print(f"[分析] Profile 文件名: {profile_file.filename}")
        
        if profile_file.filename == '':
            print("[分析] ❌ Profile 文件名為空")
            return jsonify({"ok": False, "error": "profile 文件為空"}), 400
        
        # 檢查文件類型
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        file_ext = os.path.splitext(profile_file.filename.lower())[1]
        if file_ext not in allowed_extensions:
            return jsonify({"ok": False, "error": f"不支援的文件格式，僅支援: {', '.join(allowed_extensions)}"}), 400
        
        # 檢查 AI 分析器
        if analyzer is None:
            return jsonify({"ok": False, "error": "AI 分析器未初始化，請檢查 OPENAI_API_KEY"}), 500
        
        # 讀取 profile 圖片（先讀取內容，然後檢查大小）
        print("[分析] 開始讀取 profile 文件...")
        try:
            profile_data = profile_file.read()
            profile_size = len(profile_data)
            print(f"[分析] Profile 文件大小: {profile_size} bytes ({profile_size / 1024 / 1024:.2f} MB)")
        except Exception as e:
            print(f"[分析] ❌ 讀取文件失敗: {e}")
            return jsonify({"ok": False, "error": f"讀取文件失敗: {str(e)}"}), 400
        
        if profile_size > MAX_FILE_SIZE:
            print(f"[分析] ❌ 文件過大: {profile_size} > {MAX_FILE_SIZE}")
            return jsonify({"ok": False, "error": f"文件過大，最大允許 {MAX_FILE_SIZE // 1024 // 1024}MB"}), 400
        
        if profile_size == 0:
            print("[分析] ❌ 文件為空")
            return jsonify({"ok": False, "error": "文件為空"}), 400
        
        # 讀取圖片
        print("[分析] 開始解析圖片...")
        try:
            profile_image = Image.open(io.BytesIO(profile_data))
            print(f"[分析] 圖片格式: {profile_image.format}, 尺寸: {profile_image.size}")
            profile_image = profile_image.convert('RGB')
            print("[分析] ✅ 圖片讀取成功")
        except Exception as e:
            print(f"[分析] ❌ 無法讀取圖片文件: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"ok": False, "error": f"無法讀取圖片文件: {str(e)}"}), 400
        
        # 讀取 posts 圖片（可選，最多 6 張）
        post_images = []
        if 'posts' in request.files:
            post_files = request.files.getlist('posts')
            for post_file in post_files[:6]:  # 最多 6 張
                if post_file.filename:
                    # 檢查文件類型
                    post_ext = os.path.splitext(post_file.filename.lower())[1]
                    if post_ext not in allowed_extensions:
                        print(f"⚠️ 不支援的貼文圖片格式，跳過: {post_file.filename}")
                        continue
                    
                    # 讀取文件內容並檢查大小
                    post_data = post_file.read()
                    post_size = len(post_data)
                    
                    if post_size > MAX_FILE_SIZE:
                        print(f"⚠️ 貼文圖片過大，跳過: {post_file.filename}")
                        continue
                    
                    if post_size == 0:
                        print(f"⚠️ 貼文圖片為空，跳過: {post_file.filename}")
                        continue
                    
                    try:
                        post_img = Image.open(io.BytesIO(post_data))
                        post_img = post_img.convert('RGB')
                        post_images.append(post_img)
                    except Exception as e:
                        print(f"⚠️ 無法讀取貼文圖片: {e}")
        
        # 使用 AI 分析（目前只分析 profile，posts 可作為額外上下文）
        print("[分析] 開始 AI 分析...")
        print(f"[分析] AI 分析器狀態: {analyzer is not None}")
        
        if analyzer is None:
            print("[分析] ❌ AI 分析器未初始化")
            return jsonify({
                "ok": False,
                "error": "AI 分析器未初始化，請檢查 OPENAI_API_KEY"
            }), 500
        
        witty_review = None  # 初始化變數
        try:
            # 使用兩階段處理：返回 (完整分析, 風趣短評)
            analysis_text, witty_review = analyzer.analyze_profile(profile_image)
            print(f"[分析] ✅ AI 分析完成，回應長度: {len(analysis_text)}")
            if witty_review:
                print(f"[分析] ✅ 風趣短評生成: {witty_review[:50]}...")
            
            # 檢查 AI 是否拒絕回答（完整分析部分）
            if any(phrase in analysis_text.lower() for phrase in [
                "i'm sorry", "i cannot", "i can't assist", "無法協助", 
                "不能協助", "抱歉", "無法直接"
            ]):
                print("[分析] ⚠️ 檢測到 AI 拒絕回答，但已有風趣短評")
                if "i'm sorry" in analysis_text.lower() or "i can't assist" in analysis_text.lower():
                    print("[分析] AI 回應可能被安全過濾，檢查回應內容...")
                    print(f"[分析] AI 回應前 200 字符: {analysis_text[:200]}")
            
            last_ai_response = analysis_text
        except Exception as e:
            error_msg = f"AI 分析失敗: {str(e)}"
            print(f"[分析] ❌ {error_msg}")
            import traceback
            traceback.print_exc()
            return jsonify({
                "ok": False,
                "error": error_msg
            }), 500
        
        # 提取 JSON 數據
        print("[分析] 開始提取 JSON 數據...")
        analysis_data = extract_json_from_text(analysis_text)
        if analysis_data:
            print("[分析] ✅ JSON 提取成功")
        else:
            print("[分析] ⚠️ JSON 提取失敗，將從文字中提取")
        
        # 優先從文字中提取基本資訊（因為 AI 通常在文字中更準確地提到這些資訊）
        print("[分析] 優先從文字中提取基本資訊...")
        print(f"[分析] AI 回應長度: {len(analysis_text)} 字符")
        basic_info = extract_basic_info_from_text(analysis_text)
        print(f"[分析] 文字提取結果: {basic_info}")
        
        # 如果 JSON 中有 basic_info，且文字提取不完整，則合併使用
        if analysis_data and "basic_info" in analysis_data:
            json_basic_info = analysis_data["basic_info"]
            print(f"[分析] JSON 中也包含基本資訊: {json_basic_info}")
            
            # 合併：優先使用文字提取的結果，如果文字中沒有則使用 JSON 的
            if basic_info.get("username") == "unknown" and json_basic_info.get("username"):
                basic_info["username"] = json_basic_info["username"]
            if basic_info.get("display_name") == "未知用戶" and json_basic_info.get("display_name"):
                basic_info["display_name"] = json_basic_info["display_name"]
            if basic_info.get("followers", 0) == 0 and json_basic_info.get("followers"):
                basic_info["followers"] = json_basic_info["followers"]
            if basic_info.get("following", 0) == 0 and json_basic_info.get("following"):
                basic_info["following"] = json_basic_info["following"]
            if basic_info.get("posts", 0) == 0 and json_basic_info.get("posts"):
                basic_info["posts"] = json_basic_info["posts"]
            
            print(f"[分析] ✅ 合併後的基本資訊: {basic_info}")
        
        # 確保 basic_info 是字典
        if not isinstance(basic_info, dict):
            print("[分析] ⚠️ basic_info 不是字典，重新初始化")
            basic_info = {}
        
        # 如果還是沒有提取到，使用預設值
        followers_value = parse_numeric_count(basic_info.get("followers", 0))
        if not basic_info or followers_value <= 0:
            print("[分析] ❌ basic_info 資料無效，返回錯誤讓使用者重新上傳")
            return jsonify({
                "ok": False,
                "error": "AI 無法可靠地讀取帳號基本資訊，請重新上傳更清晰的截圖再試一次"
            }), 400
        # 正規化所有數值
        basic_info["followers"] = parse_numeric_count(followers_value, 0)
        basic_info["following"] = parse_numeric_count(basic_info.get("following", 0), 0)
        basic_info["posts"] = parse_numeric_count(basic_info.get("posts", 0), 0)
        basic_info["username"] = str(basic_info.get("username", "unknown")).strip()
        basic_info["display_name"] = str(basic_info.get("display_name", basic_info.get("username", "未知用戶"))).strip()
        
        if not analysis_data:
            # 如果無法提取 JSON，使用預設值
            print("⚠️ 無法從 AI 回應中提取 JSON，使用預設值")
            print(f"[分析] AI 回應前 500 字符: {analysis_text[:500]}")
            analysis_data = {
                "visual_quality": {"overall": 5.0, "consistency": 5.0},
                "content_type": {"primary": "未知", "category_tier": "mid"},
                "content_format": {"video_focus": 1.0, "personal_connection": 5.0},
                "professionalism": {"has_contact": False, "is_business_account": False},
                "personality_type": {"primary_type": "type_5", "reasoning": "無法判斷"},
                "improvement_tips": ["請提供更清晰的截圖"]
            }
        
        # 使用兩階段處理生成的風趣短評（優先使用）
        # 如果兩階段處理失敗，才使用 extract_analysis_text 作為備用
        if witty_review and len(witty_review.strip()) > 10:
            clean_analysis_text = witty_review
            print(f"[分析] ✅ 使用兩階段處理生成的風趣短評")
        else:
            # 備用方案：從完整分析中提取
            print("[分析] ⚠️ 使用備用方案提取短評")
            clean_analysis_text = extract_analysis_text(analysis_text, basic_info)
        
        clean_analysis_text = finalize_short_review(clean_analysis_text)
        
        # 計算價值
        print("[分析] 開始計算價值...")
        try:
            multipliers = calculate_multipliers(analysis_data)
            print(f"[分析] 係數計算完成: {len(multipliers)} 個係數")
            value_estimation = calculate_values(
                basic_info["followers"],
                multipliers,
                analysis_data
            )
            print(f"[分析] ✅ 價值計算完成")
        except Exception as e:
            print(f"[分析] ❌ 價值計算失敗: {e}")
            import traceback
            traceback.print_exc()
            # 使用預設值
            multipliers = {
                "visual": 1.0, "content": 1.0, "professional": 1.0,
                "follower": 1.0, "unique": 1.0, "engagement": 1.0,
                "niche": 1.0, "audience": 1.0, "cross_platform": 1.0,
                "ratio": 1.0, "commercial": 1.0
            }
            value_estimation = {
                "post_value": 1000,
                "story_value": 300,
                "reels_value": 800,
                "account_asset_value": basic_info["followers"] * 5,
                "multipliers": multipliers
            }
        
        # 獲取人格類型資訊
        try:
            personality_type_id = analysis_data.get("personality_type", {}).get("primary_type", "type_5")
            if not personality_type_id or personality_type_id not in PERSONALITY_TYPES:
                personality_type_id = "type_5"
            personality_info = PERSONALITY_TYPES.get(personality_type_id, PERSONALITY_TYPES["type_5"])
        except Exception as e:
            print(f"[分析] ⚠️ 獲取人格類型失敗: {e}，使用預設值")
            personality_type_id = "type_5"
            personality_info = PERSONALITY_TYPES["type_5"]
        
        # 清理用戶輸入，防止 XSS（雖然這裡是從 AI 回應中提取，但還是要安全）
        def sanitize_string(s):
            if not isinstance(s, str):
                return str(s) if s else ""
            # 移除潛在的危險字符
            return s.replace('<', '&lt;').replace('>', '&gt;')[:1000]  # 限制長度
        
        # 構建回應
        result = {
            "ok": True,
            "version": "v5",
            "username": sanitize_string(basic_info.get("username", "unknown")),
            "display_name": sanitize_string(basic_info.get("display_name", "未知用戶")),
            "followers": int(basic_info["followers"]),
            "following": int(basic_info.get("following", 0)),
            "posts": int(basic_info.get("posts", 0)),
            "analysis_text": clean_analysis_text[:2000] if clean_analysis_text else "",  # 限制長度
            "primary_type": {
                "id": personality_type_id,
                "emoji": personality_info["emoji"],
                "name_zh": personality_info["name_zh"],
                "name_en": personality_info["name_en"]
            },
            "value_estimation": {
                **value_estimation,
                "follower_tier": get_follower_tier(basic_info["followers"])
            },
            "improvement_tips": [
                sanitize_string(tip) for tip in analysis_data.get("improvement_tips", [])[:10]  # 最多 10 條
            ]
        }
        result["value_subtitle"] = "基於 AI 智能鑑價模型 (TWD)"
        result["plain_username"] = normalize_username(result["username"])
        result["user_id"] = current_user["id"] if current_user else None
        
        save_analysis_result(result)
        
        print("[分析] ✅ 分析完成")
        return jsonify(result)
        
    except ValueError as e:
        # 處理值錯誤（如 AI API 錯誤）
        error_msg = str(e)
        print(f"[分析] ❌ ValueError: {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "ok": False,
            "error": error_msg
        }), 500
    except KeyError as e:
        # 處理鍵值錯誤
        error_msg = f"數據結構錯誤: 缺少 {str(e)}"
        print(f"[分析] ❌ KeyError: {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "ok": False,
            "error": error_msg
        }), 500
    except TypeError as e:
        # 處理類型錯誤
        error_msg = f"數據類型錯誤: {str(e)}"
        print(f"[分析] ❌ TypeError: {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "ok": False,
            "error": error_msg
        }), 500
    except Image.UnidentifiedImageError as e:
        # 處理圖片格式錯誤
        error_msg = f"無法識別圖片格式: {str(e)}"
        print(f"[分析] ❌ {error_msg}")
        return jsonify({
            "ok": False,
            "error": error_msg
        }), 400
    except Exception as e:
        # 處理其他未預期的錯誤
        error_msg = str(e)
        error_type = type(e).__name__
        print(f"[分析] ❌ 未預期錯誤 ({error_type}): {error_msg}")
        import traceback
        print("=" * 50)
        print("完整錯誤追蹤:")
        traceback.print_exc()
        print("=" * 50)
        return jsonify({
            "ok": False,
            "error": f"伺服器錯誤 ({error_type}): {error_msg}" if error_msg else "未知錯誤",
            "error_type": error_type
        }), 500

def get_follower_tier(followers):
    """獲取粉絲等級（舊版 Growth Creator 風格）"""
    if followers >= 10_000_000:
        return "🌟 Iconic Tier（傳奇級）"
    elif followers >= 1_000_000:
        return "⭐ Mega Star（超級影響者）"
    elif followers >= 500_000:
        return "👑 Elite Influencer（頂級影響者）"
    elif followers >= 100_000:
        return "🎬 Celebrity Influencer（明星級影響者）"
    elif followers >= 50_000:
        return "⭐ Prime Influencer（核心型影響者）"
    elif followers >= 10_000:
        return "📈 Growth Creator（成長型創作者）"
    elif followers >= 1_000:
        return "🌱 Seed Creator（萌芽創作者）"
    elif followers >= 500:
        return "🌱 新星"
    else:
        return "🌱 素人"

@app.route('/api/result')
def api_get_result():
    username = request.args.get('username', '').strip()
    if not username:
        return jsonify({"ok": False, "error": "username_required"}), 400
    data = get_analysis_result(username)
    if not data:
        return jsonify({"ok": False, "error": "not_found"}), 404
    return jsonify(data)

def login_required(f):
    """登入驗證裝飾器"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            user = get_authenticated_user(required=True)
            if not user:
                raise AuthError("authentication_required", 401)
        except AuthError as e:
            return jsonify({"ok": False, "error": e.message}), e.status
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """管理員驗證裝飾器"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            user = get_authenticated_user(required=True)
            if not user:
                raise AuthError("authentication_required", 401)
            
            # 檢查是否為管理員
            user_email = user.get("email", "").lower()
            if not ADMIN_EMAILS:
                print(f"[Admin] ⚠️ ADMIN_EMAILS 未設定，拒絕訪問")
                raise AuthError("admin_access_required", 403)
            
            if user_email not in ADMIN_EMAILS:
                print(f"[Admin] ⚠️ 用戶 {user_email} 嘗試訪問管理員功能，但不在管理員列表中")
                raise AuthError("admin_access_required", 403)
            
            print(f"[Admin] ✅ 管理員 {user_email} 訪問管理員功能")
        except AuthError as e:
            return jsonify({"ok": False, "error": e.message}), e.status
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/user/analyses', methods=['GET'])
@login_required
def get_user_analyses():
    """獲取當前用戶的所有分析記錄"""
    user = get_authenticated_user(required=True)
    session = SessionLocal()
    try:
        # 查詢該用戶的所有分析結果
        records = session.query(AnalysisResult).filter_by(user_id=user["id"]).order_by(AnalysisResult.created_at.desc()).all()
        
        analyses = []
        for record in records:
            try:
                data = json.loads(record.data)
                analyses.append({
                    "id": record.id,
                    "username": record.username,
                    "display_name": record.display_name,
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                    "updated_at": record.updated_at.isoformat() if record.updated_at else None,
                    "account_asset_value": data.get("value_estimation", {}).get("account_asset_value", 0),
                    "followers": data.get("followers", 0),
                    "analysis_text": data.get("analysis_text", "")[:100] + "..." if len(data.get("analysis_text", "")) > 100 else data.get("analysis_text", "")
                })
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[API] ⚠️ 解析分析記錄失敗 (ID: {record.id}): {e}")
                continue
        
        return jsonify({"ok": True, "analyses": analyses, "count": len(analyses)})
    except SQLAlchemyError as e:
        session.rollback()
        print(f"[API] ❌ 查詢用戶分析記錄失敗: {e}")
        return jsonify({"ok": False, "error": "database_error"}), 500
    finally:
        session.close()

@app.route('/api/user/me', methods=['GET'])
@login_required
def get_current_user():
    """獲取當前登入用戶的資訊"""
    user = get_authenticated_user(required=True)
    session = SessionLocal()
    try:
        db_user = session.get(User, user["id"])
        if not db_user:
            raise AuthError("user_not_found", 404)
        return jsonify({"ok": True, "user": serialize_user(db_user)})
    except SQLAlchemyError as e:
        session.rollback()
        print(f"[API] ❌ 查詢用戶資訊失敗: {e}")
        return jsonify({"ok": False, "error": "database_error"}), 500
    finally:
        session.close()

@app.route('/api/user/stats', methods=['GET'])
@login_required
def get_user_stats():
    """獲取當前用戶的統計資訊"""
    user = get_authenticated_user(required=True)
    session = SessionLocal()
    try:
        # 查詢該用戶的所有分析結果
        records = session.query(AnalysisResult).filter_by(user_id=user["id"]).order_by(AnalysisResult.created_at.desc()).all()
        
        if not records:
            return jsonify({
                "ok": True,
                "stats": {
                    "total_analyses": 0,
                    "latest_value": 0,
                    "highest_value": 0,
                    "first_analysis_date": None,
                    "latest_analysis_date": None,
                    "value_history": []
                }
            })
        
        # 計算統計資訊
        total_analyses = len(records)
        values = []
        dates = []
        value_history = []  # 用於圖表
        
        for record in records:
            try:
                data = json.loads(record.data)
                value = data.get("value_estimation", {}).get("account_asset_value", 0)
                values.append(value)
                if record.created_at:
                    dates.append(record.created_at)
                    value_history.append({
                        "date": record.created_at.isoformat(),
                        "value": value,
                        "username": record.username
                    })
            except (json.JSONDecodeError, KeyError):
                continue
        
        latest_value = values[0] if values else 0
        highest_value = max(values) if values else 0
        first_analysis_date = min(dates).isoformat() if dates else None
        latest_analysis_date = max(dates).isoformat() if dates else None
        
        # 反轉歷史記錄，讓最早的在前
        value_history.reverse()
        
        return jsonify({
            "ok": True,
            "stats": {
                "total_analyses": total_analyses,
                "latest_value": latest_value,
                "highest_value": highest_value,
                "first_analysis_date": first_analysis_date,
                "latest_analysis_date": latest_analysis_date,
                "value_history": value_history
            }
        })
    except SQLAlchemyError as e:
        session.rollback()
        print(f"[API] ❌ 查詢用戶統計失敗: {e}")
        return jsonify({"ok": False, "error": "database_error"}), 500
    finally:
        session.close()

# -----------------------------------------------------------------------------
# Admin API Routes
# -----------------------------------------------------------------------------

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_all_users():
    """獲取所有用戶列表（管理員專用）"""
    session = SessionLocal()
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        offset = (page - 1) * per_page
        
        # 搜索和篩選參數
        search_email = request.args.get('search_email', '').strip()
        search_username = request.args.get('search_username', '').strip()
        print(f"[Admin] 🔍 用戶搜索參數: email='{search_email}', username='{search_username}'")
        
        # 構建查詢
        query = session.query(User)
        
        # 按 Email 搜索
        if search_email:
            query = query.filter(User.email.ilike(f'%{search_email}%'))
        
        # 按 Username 搜索
        if search_username:
            query = query.filter(User.username.ilike(f'%{search_username}%'))
        
        # 查詢總數與結果
        total = query.count()
        print(f"[Admin] 🔍 用戶搜索結果總數: {total}")
        
        # 查詢用戶列表
        users = query.order_by(User.created_at.desc()).offset(offset).limit(per_page).all()
        
        users_data = []
        # 批量查詢所有用戶的分析次數（優化 N+1 查詢）
        user_ids = [u.id for u in users]
        analysis_counts = {}
        if user_ids:
            from sqlalchemy import func
            counts = session.query(
                AnalysisResult.user_id,
                func.count(AnalysisResult.id).label('count')
            ).filter(AnalysisResult.user_id.in_(user_ids)).group_by(AnalysisResult.user_id).all()
            analysis_counts = {uid: count for uid, count in counts}
        
        for user in users:
            users_data.append({
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "display_name": user.display_name,
                "avatar_url": user.avatar_url,
                "provider": user.provider,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "analysis_count": analysis_counts.get(user.id, 0)
            })
        
        return jsonify({
            "ok": True,
            "users": users_data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page
            }
        })
    except SQLAlchemyError as e:
        session.rollback()
        print(f"[Admin] ❌ 查詢用戶列表失敗: {e}")
        return jsonify({"ok": False, "error": "database_error"}), 500
    finally:
        session.close()

@app.route('/api/admin/analyses', methods=['GET'])
@admin_required
def admin_get_all_analyses():
    """獲取所有分析記錄（管理員專用）"""
    session = SessionLocal()
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        offset = (page - 1) * per_page
        
        # 搜索和篩選參數
        search_username = request.args.get('search_username', '').strip()
        min_value = request.args.get('min_value', type=int)
        max_value = request.args.get('max_value', type=int)
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()
        print(f"[Admin] 🔍 分析記錄搜索參數: username='{search_username}', min={min_value}, max={max_value}, from='{date_from}', to='{date_to}'")
        
        # 構建查詢
        query = session.query(AnalysisResult).options(
            joinedload(AnalysisResult.user)
        )
        
        # 按用戶名搜索
        if search_username:
            query = query.filter(AnalysisResult.username.ilike(f'%{search_username}%'))
        
        # 按日期範圍篩選
        if date_from:
            try:
                from datetime import datetime
                date_from_obj = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                query = query.filter(AnalysisResult.created_at >= date_from_obj)
            except (ValueError, AttributeError):
                pass
        
        if date_to:
            try:
                from datetime import datetime
                date_to_obj = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                query = query.filter(AnalysisResult.created_at <= date_to_obj)
            except (ValueError, AttributeError):
                pass
        
        # 如果指定了價值範圍，需要先獲取所有記錄進行過濾（因為價值在 JSON 中）
        if min_value is not None or max_value is not None:
            # 先獲取所有符合其他條件的記錄
            all_records = query.order_by(AnalysisResult.created_at.desc()).all()
            
            # 過濾價值範圍
            filtered_records = []
            for record in all_records:
                try:
                    data = json.loads(record.data)
                    value_est = data.get("value_estimation", {})
                    account_value = value_est.get("account_asset_value", 0)
                    
                    if min_value is not None and account_value < min_value:
                        continue
                    if max_value is not None and account_value > max_value:
                        continue
                    
                    filtered_records.append(record)
                except (json.JSONDecodeError, KeyError):
                    continue
            
            # 更新總數
            total = len(filtered_records)
            # 應用分頁
            records = filtered_records[offset:offset + per_page]
            print(f"[Admin] 🔍 分析記錄經價值篩選後: {total}")
        else:
            # 沒有價值篩選，直接使用數據庫查詢
            total = query.count()
            records = query.order_by(AnalysisResult.created_at.desc()).offset(offset).limit(per_page).all()
        
        print(f"[Admin] 🔍 分析記錄搜索結果數: {total}")
        
        analyses_data = []
        for record in records:
            try:
                data = json.loads(record.data)
                # 獲取用戶資訊（已通過 joinedload 預載入）
                user = None
                if record.user_id and record.user:
                    user = {
                        "id": record.user.id,
                        "email": record.user.email,
                        "username": record.user.username,
                        "display_name": record.user.display_name
                    }
                
                value_est = data.get("value_estimation", {})
                analyses_data.append({
                    "id": record.id,
                    "username": record.username,
                    "display_name": record.display_name,
                    "user": user,
                    "account_asset_value": value_est.get("account_asset_value", 0),
                    "post_value": value_est.get("post_value", 0),
                    "story_value": value_est.get("story_value", 0),
                    "reels_value": value_est.get("reels_value", 0),
                    "followers": data.get("followers", 0),
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                    "updated_at": record.updated_at.isoformat() if record.updated_at else None
                })
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[Admin] ⚠️ 解析分析記錄失敗 (ID: {record.id}): {e}")
                continue
        
        return jsonify({
            "ok": True,
            "analyses": analyses_data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page
            }
        })
    except SQLAlchemyError as e:
        session.rollback()
        print(f"[Admin] ❌ 查詢分析記錄失敗: {e}")
        return jsonify({"ok": False, "error": "database_error"}), 500
    finally:
        session.close()

@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def admin_get_stats():
    """獲取系統統計資訊（管理員專用）"""
    session = SessionLocal()
    try:
        # 用戶統計
        total_users = session.query(User).count()
        # 使用子查詢來獲取有分析的用戶數（避免 JOIN 重複計算）
        users_with_analyses = session.query(User.id).join(AnalysisResult, User.id == AnalysisResult.user_id).distinct().count()
        
        # 分析統計
        total_analyses = session.query(AnalysisResult).count()
        analyses_with_users = session.query(AnalysisResult).filter(AnalysisResult.user_id.isnot(None)).count()
        anonymous_analyses = total_analyses - analyses_with_users
        
        # 價值統計
        records = session.query(AnalysisResult).all()
        total_value = 0
        values = []
        for record in records:
            try:
                data = json.loads(record.data)
                value = data.get("value_estimation", {}).get("account_asset_value", 0)
                if value > 0:
                    values.append(value)
                    total_value += value
            except (json.JSONDecodeError, KeyError):
                continue
        
        avg_value = total_value / len(values) if values else 0
        max_value = max(values) if values else 0
        min_value = min(values) if values else 0
        
        # 最近活動
        recent_analyses = session.query(AnalysisResult).order_by(AnalysisResult.created_at.desc()).limit(10).all()
        recent_analyses_data = []
        for record in recent_analyses:
            try:
                data = json.loads(record.data)
                recent_analyses_data.append({
                    "username": record.username,
                    "value": data.get("value_estimation", {}).get("account_asset_value", 0),
                    "created_at": record.created_at.isoformat() if record.created_at else None
                })
            except (json.JSONDecodeError, KeyError):
                continue
        
        return jsonify({
            "ok": True,
            "stats": {
                "users": {
                    "total": total_users,
                    "with_analyses": users_with_analyses,
                    "without_analyses": total_users - users_with_analyses
                },
                "analyses": {
                    "total": total_analyses,
                    "with_users": analyses_with_users,
                    "anonymous": anonymous_analyses
                },
                "values": {
                    "total": total_value,
                    "average": avg_value,
                    "max": max_value,
                    "min": min_value,
                    "count": len(values)
                },
                "recent_analyses": recent_analyses_data
            }
        })
    except SQLAlchemyError as e:
        session.rollback()
        print(f"[Admin] ❌ 查詢統計資訊失敗: {e}")
        return jsonify({"ok": False, "error": "database_error"}), 500
    finally:
        session.close()

@app.route('/api/admin/analyses/<int:analysis_id>/update', methods=['PUT', 'PATCH'])
@admin_required
def admin_update_analysis(analysis_id):
    """更新分析記錄的價值和報價（管理員專用）"""
    admin_user = get_authenticated_user(required=True)
    session = SessionLocal()
    try:
        record = session.get(AnalysisResult, analysis_id)
        if not record:
            return jsonify({"ok": False, "error": "analysis_not_found"}), 404
        
        data = request.get_json() or {}
        
        # 記錄更新前的值（用於日誌）
        old_values = {}
        try:
            old_data = json.loads(record.data)
            old_est = old_data.get("value_estimation", {})
            old_values = {
                "account_asset_value": old_est.get("account_asset_value", 0),
                "post_value": old_est.get("post_value", 0),
                "story_value": old_est.get("story_value", 0),
                "reels_value": old_est.get("reels_value", 0)
            }
        except:
            pass
        
        # 解析現有數據
        try:
            analysis_data = json.loads(record.data)
        except json.JSONDecodeError:
            return jsonify({"ok": False, "error": "invalid_analysis_data"}), 400
        
        # 更新價值估算
        if "value_estimation" not in analysis_data:
            analysis_data["value_estimation"] = {}
        
        value_est = analysis_data["value_estimation"]
        
        # 更新帳號總價值
        if "account_asset_value" in data:
            value_est["account_asset_value"] = int(data["account_asset_value"])
        
        # 更新報價
        if "post_value" in data:
            value_est["post_value"] = int(data["post_value"])
        if "story_value" in data:
            value_est["story_value"] = int(data["story_value"])
        if "reels_value" in data:
            value_est["reels_value"] = int(data["reels_value"])
        
        # 保存更新後的數據
        record.data = json.dumps(analysis_data, ensure_ascii=False)
        record.updated_at = datetime.utcnow()
        session.commit()
        
        # 記錄管理員操作日誌
        changes = []
        if "account_asset_value" in data and old_values.get("account_asset_value") != value_est.get("account_asset_value"):
            changes.append(f"帳號價值: {old_values.get('account_asset_value')} → {value_est.get('account_asset_value')}")
        if "post_value" in data and old_values.get("post_value") != value_est.get("post_value"):
            changes.append(f"貼文報價: {old_values.get('post_value')} → {value_est.get('post_value')}")
        if "story_value" in data and old_values.get("story_value") != value_est.get("story_value"):
            changes.append(f"Story報價: {old_values.get('story_value')} → {value_est.get('story_value')}")
        if "reels_value" in data and old_values.get("reels_value") != value_est.get("reels_value"):
            changes.append(f"Reels報價: {old_values.get('reels_value')} → {value_est.get('reels_value')}")
        
        print(f"[Admin] ✅ 管理員 {admin_user.get('email', 'unknown')} 更新分析記錄 ID {analysis_id} (@{record.username}): {', '.join(changes) if changes else '無變更'}")
        
        return jsonify({
            "ok": True,
            "message": "分析記錄已更新",
            "analysis": {
                "id": record.id,
                "username": record.username,
                "account_asset_value": value_est.get("account_asset_value", 0),
                "post_value": value_est.get("post_value", 0),
                "story_value": value_est.get("story_value", 0),
                "reels_value": value_est.get("reels_value", 0)
            }
        })
    except ValueError as e:
        session.rollback()
        return jsonify({"ok": False, "error": "invalid_value", "message": str(e)}), 400
    except SQLAlchemyError as e:
        session.rollback()
        print(f"[Admin] ❌ 更新分析記錄失敗: {e}")
        return jsonify({"ok": False, "error": "database_error"}), 500
    finally:
        session.close()

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(user_id):
    """刪除用戶及其所有分析記錄（管理員專用）"""
    session = SessionLocal()
    try:
        user = session.get(User, user_id)
        if not user:
            return jsonify({"ok": False, "error": "user_not_found"}), 404
        
        # 獲取用戶的分析記錄數量（用於日誌）
        analysis_count = session.query(AnalysisResult).filter_by(user_id=user_id).count()
        
        # 刪除該用戶的所有分析記錄
        session.query(AnalysisResult).filter_by(user_id=user_id).delete()
        
        # 刪除用戶
        user_email = user.email
        admin_user = get_authenticated_user(required=True)
        session.delete(user)
        session.commit()
        
        print(f"[Admin] ✅ 管理員 {admin_user.get('email', 'unknown')} 刪除用戶 ID {user_id} ({user_email}) 及其 {analysis_count} 筆分析記錄")
        
        return jsonify({
            "ok": True,
            "message": f"用戶及其 {analysis_count} 筆分析記錄已刪除",
            "deleted_user": {
                "id": user_id,
                "email": user.email,
                "analysis_count": analysis_count
            }
        })
    except SQLAlchemyError as e:
        session.rollback()
        print(f"[Admin] ❌ 刪除用戶失敗: {e}")
        return jsonify({"ok": False, "error": "database_error"}), 500
    finally:
        session.close()

@app.route('/api/admin/analyses/<int:analysis_id>', methods=['DELETE'])
@admin_required
def admin_delete_analysis(analysis_id):
    """刪除單筆分析記錄（管理員專用）"""
    admin_user = get_authenticated_user(required=True)
    session = SessionLocal()
    try:
        record = session.get(AnalysisResult, analysis_id)
        if not record:
            return jsonify({"ok": False, "error": "analysis_not_found"}), 404
        
        username = record.username
        session.delete(record)
        session.commit()
        
        print(f"[Admin] ✅ 管理員 {admin_user.get('email', 'unknown')} 刪除分析記錄 ID {analysis_id} (@{username})")
        
        return jsonify({
            "ok": True,
            "message": "分析記錄已刪除",
            "deleted_analysis": {
                "id": analysis_id,
                "username": username
            }
        })
    except SQLAlchemyError as e:
        session.rollback()
        print(f"[Admin] ❌ 刪除分析記錄失敗: {e}")
        return jsonify({"ok": False, "error": "database_error"}), 500
    finally:
        session.close()

# -----------------------------------------------------------------------------
# Leaderboard API
# -----------------------------------------------------------------------------
@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    """取得排行榜資料"""
    session = SessionLocal()
    try:
        board_type = request.args.get('type', 'account_value')
        limit = min(max(int(request.args.get('limit', 50)), 1), 100)
        category = request.args.get('category')
        timeframe = request.args.get('timeframe', 'all')
        
        print(f"[Leaderboard] 請求: type={board_type}, limit={limit}, category={category}, timeframe={timeframe}")
        
        query = session.query(AnalysisResult)
        
        # 時間篩選
        if timeframe and timeframe != 'all':
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            if timeframe == '7d':
                query = query.filter(AnalysisResult.created_at >= now - timedelta(days=7))
            elif timeframe == '30d':
                query = query.filter(AnalysisResult.created_at >= now - timedelta(days=30))
        
        records = query.order_by(AnalysisResult.created_at.desc()).all()
        print(f"[Leaderboard] 找到分析記錄: {len(records)} 筆")
        
        leaderboard = {}
        
        for record in records:
            try:
                data = json.loads(record.data)
                value_est = data.get("value_estimation", {})
                account_value = value_est.get("account_asset_value")
                followers = data.get("followers")
                username = data.get("username") or record.username
                display_name = data.get("display_name") or record.display_name
                
                if account_value is None:
                    continue
                
                username_key = (username or '').lower()
                if not username_key:
                    continue
                
                entry = leaderboard.get(username_key)
                if entry:
                    if account_value > entry["account_value"]:
                        entry.update({
                            "account_value": account_value,
                            "followers": followers,
                            "display_name": display_name,
                            "record_id": record.id,
                            "created_at": record.created_at.isoformat() if record.created_at else None
                        })
                else:
                    leaderboard[username_key] = {
                        "username": username,
                        "display_name": display_name,
                        "followers": followers,
                        "account_value": account_value,
                        "record_id": record.id,
                        "created_at": record.created_at.isoformat() if record.created_at else None
                    }
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[Leaderboard] ⚠️ 解析分析記錄失敗 (ID: {record.id}): {e}")
                continue
        
        entries = list(leaderboard.values())
        entries.sort(key=lambda x: x["account_value"], reverse=True)
        top_entries = entries[:limit]
        
        for idx, entry in enumerate(top_entries, start=1):
            entry["rank"] = idx
            entry["avatar"] = (entry.get("display_name") or entry["username"] or "??")[:2].upper()
        
        print(f"[Leaderboard] 回傳排行榜筆數: {len(top_entries)}")
        
        return jsonify({
            "ok": True,
            "type": board_type,
            "limit": limit,
            "total": len(entries),
            "leaderboard": top_entries
        })
    except Exception as e:
        print(f"[Leaderboard] ❌ 取得排行榜失敗: {e}")
        return jsonify({"ok": False, "error": "leaderboard_error"}), 500
    finally:
        session.close()

@app.errorhandler(AuthError)
def handle_auth_error(err):
    return jsonify({"ok": False, "error": err.message}), err.status

# 靜態文件服務
@app.route('/')
def index():
    """首頁重定向到 landing.html"""
    return send_from_directory('static', 'landing.html')

@app.route('/static/auth-utils.js')
def serve_auth_utils():
    """提供認證工具 JavaScript 文件"""
    return send_from_directory('static', 'auth-utils.js', mimetype='application/javascript')

# -----------------------------------------------------------------------------
# 主程式入口
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    print("=" * 50)
    print("🚀 IG Value Estimation System V5")
    print("=" * 50)
    print(f"📡 服務端口: {PORT}")
    print(f"🤖 AI 模型: {OPENAI_MODEL}")
    
    # 檢查 API Key 狀態
    if not OPENAI_API_KEY:
        print(f"🔑 API Key: ❌ 未設置")
        print("=" * 50)
        print("⚠️  錯誤: 請設置 OPENAI_API_KEY 環境變數")
        print("   例如: export OPENAI_API_KEY='sk-...'")
        print("=" * 50)
    elif OPENAI_API_KEY in ['your-key', 'sk-your-api-key-here', '']:
        print(f"🔑 API Key: ❌ 佔位符（無效）")
        print("=" * 50)
        print("⚠️  錯誤: OPENAI_API_KEY 是佔位符，請設置真實的 API Key")
        print("   請運行: export OPENAI_API_KEY='sk-你的真實API密鑰'")
        print("=" * 50)
    else:
        # 只顯示前 10 個字符和後 4 個字符
        masked_key = f"{OPENAI_API_KEY[:10]}...{OPENAI_API_KEY[-4:]}" if len(OPENAI_API_KEY) > 14 else "***"
        print(f"🔑 API Key: ✅ 已設置 ({masked_key})")
        print("=" * 50)
    
    # 顯示模型選擇說明
    print(f"📋 模型配置: {OPENAI_MODEL}")
    print("   可用模型選項：")
    print("   - gpt-5.1: 最新模型，最強推理能力（推薦用於資訊提取）")
    print("   - gpt-4o: 穩定版本，準確度高")
    print("   - gpt-4o-mini: 較便宜，速度較快")
    print("   切換模型: export OPENAI_MODEL='模型名稱'")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
