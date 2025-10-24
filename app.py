# app_v5.py — IG Value Estimation System (v5) with Modular AI Analysis
import os
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from PIL import Image

# 導入新的 AI 分析模組
from ai_analyzer import IGAnalyzer

# -----------------------------------------------------------------------------
# App & Config
# -----------------------------------------------------------------------------
app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
MAX_SIDE = int(os.getenv("MAX_SIDE", "1280"))
JPEG_Q = int(os.getenv("JPEG_QUALITY", "72"))

# -----------------------------------------------------------------------------
# 12種IG社群帳號定位類型定義
# -----------------------------------------------------------------------------
PERSONALITY_TYPES = {
    "type_1": {"name_zh": "夢幻柔焦系", "name_en": "Dreamy Aesthetic", "emoji": "🌸"},
    "type_2": {"name_zh": "藝術實驗者", "name_en": "Artistic Experimenter", "emoji": "🎨"},
    "type_3": {"name_zh": "戶外探險家", "name_en": "Outdoor Adventurer", "emoji": "🏔️"},
    "type_4": {"name_zh": "知識策展人", "name_en": "Knowledge Curator", "emoji": "📚"},
    "type_5": {"name_zh": "生活記錄者", "name_en": "Everyday Chronicler", "emoji": "🍜"},
    "type_6": {"name_zh": "質感品味家", "name_en": "Refined Aesthete", "emoji": "✨"},
    "type_7": {"name_zh": "幽默創作者", "name_en": "Humor Creator", "emoji": "🎭"},
    "type_8": {"name_zh": "專業形象派", "name_en": "Professional Persona", "emoji": "💼"},
    "type_9": {"name_zh": "永續生活者", "name_en": "Sustainable Liver", "emoji": "🌿"},
    "type_10": {"name_zh": "次文化愛好者", "name_en": "Subculture Enthusiast", "emoji": "🎮"},
    "type_11": {"name_zh": "健康積極派", "name_en": "Fitness Motivator", "emoji": "💪"},
    "type_12": {"name_zh": "靈性探索者", "name_en": "Spiritual Seeker", "emoji": "🔮"}
}

# -----------------------------------------------------------------------------
# 工具函數
# -----------------------------------------------------------------------------
def save_user_avatar(user_id, image_data, image_format="JPEG"):
    """儲存用戶頭像"""
    try:
        # 創建用戶頭像目錄
        avatar_dir = os.path.join("static", "user_avatars")
        os.makedirs(avatar_dir, exist_ok=True)
        
        # 儲存頭像文件
        avatar_path = os.path.join(avatar_dir, f"{user_id}_avatar.{image_format.lower()}")
        
        if isinstance(image_data, str):
            import base64
            image_data = base64.b64decode(image_data)
        
        with open(avatar_path, "wb") as f:
            f.write(image_data)
        
        return avatar_path
    except Exception as e:
        print(f"Error saving user avatar: {e}")
        return None

def get_user_avatar_url(user_id):
    """獲取用戶頭像URL"""
    avatar_dir = os.path.join("static", "user_avatars")
    
    for ext in ["jpg", "jpeg", "png", "webp"]:
        avatar_path = os.path.join(avatar_dir, f"{user_id}_avatar.{ext}")
        if os.path.exists(avatar_path):
            return f"/static/user_avatars/{user_id}_avatar.{ext}"
    
    return None

# -----------------------------------------------------------------------------
# Last AI buffer（用於 debug）
# -----------------------------------------------------------------------------
LAST_AI_TEXT = {"raw": "", "text": "", "ts": None}

def save_last_ai(ai_dict=None, raw="", text=""):
    s_text = text or ""
    if not s_text and ai_dict is not None:
        try:
            import json
            s_text = json.dumps(ai_dict, ensure_ascii=False, indent=2)
        except:
            s_text = str(ai_dict)
    LAST_AI_TEXT["text"] = s_text or ""
    LAST_AI_TEXT["raw"] = raw or ""
    LAST_AI_TEXT["ts"] = datetime.now(timezone.utc).isoformat()

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "version": "v5-modular",
        "model": OPENAI_MODEL,
        "ai_enabled": bool(OPENAI_API_KEY),
        "max_side": MAX_SIDE,
        "jpeg_quality": JPEG_Q,
        "features": [
            "modular_architecture",
            "improved_error_handling",
            "better_json_parsing",
            "separated_concerns"
        ]
    })

@app.route("/debug/config")
def debug_config():
    return jsonify({
        "ai_on": bool(OPENAI_API_KEY),
        "model": OPENAI_MODEL,
        "max_side": MAX_SIDE,
        "jpeg_q": JPEG_Q,
        "version": "v5-modular"
    })

@app.route("/debug/last_ai")
def debug_last_ai():
    return jsonify(LAST_AI_TEXT)

@app.route("/bd/analyze", methods=["POST"])
def analyze():
    """主分析端點（V5 - 模組化架構）"""
    
    # 1. 檢查 OpenAI API Key
    if not OPENAI_API_KEY:
        return jsonify({"ok": False, "error": "OpenAI API key not configured"}), 500
    
    # 2. 獲取上傳的圖片
    profile_file = request.files.get("profile")
    if not profile_file:
        return jsonify({"ok": False, "error": "請上傳 IG 個人頁截圖。請確保截圖包含用戶名、粉絲數、追蹤數、貼文數等完整資訊。"}), 400
    
    try:
        profile_img = Image.open(profile_file.stream)
    except Exception as e:
        return jsonify({"ok": False, "error": "圖片格式不支援，請上傳 JPG 或 PNG 格式的截圖。"}), 400
    
    # 3. 處理其他貼文圖片（最多 6 張）
    post_files = request.files.getlist("posts")
    post_images = []
    
    for pf in post_files[:6]:
        try:
            post_img = Image.open(pf.stream)
            post_images.append(post_img)
        except:
            continue
    
    # 4. 使用新的 IGAnalyzer 進行分析
    try:
        analyzer = IGAnalyzer(
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            max_side=MAX_SIDE,
            quality=JPEG_Q
        )
        
        result = analyzer.analyze_profile(profile_img, post_images)
        
        # 5. 儲存用戶頭像（如果有提供 user_id）
        user_id = request.form.get("user_id")
        if user_id:
            # 使用 profile 圖片作為頭像
            avatar_saved = save_user_avatar(
                user_id, 
                profile_file.stream.getvalue(), 
                "JPEG"
            )
            if avatar_saved:
                print(f"User avatar saved: {avatar_saved}")
        
        # 6. 保存 AI 回應用於 debug
        save_last_ai(ai_dict=result)
        
        # 7. 添加診斷資訊
        result["diagnose"] = {
            "ai_on": True,
            "model": OPENAI_MODEL,
            "version": "v5-modular",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    return jsonify(result)
        
    except ValueError as e:
        # 業務邏輯錯誤（如無法解析截圖）
        print(f"[Error] ValueError: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        # 其他未預期的錯誤
        print(f"[Error] Exception: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "ok": False,
            "error": "AI 分析服務暫時無法使用。請稍後再試，或檢查截圖是否清晰完整。"
        }), 500

# -----------------------------------------------------------------------------
# User Avatar API
# -----------------------------------------------------------------------------
@app.route("/api/user/<user_id>/avatar", methods=["GET"])
def get_user_avatar(user_id):
    """獲取用戶頭像"""
    try:
        avatar_url = get_user_avatar_url(user_id)
        if avatar_url:
            return jsonify({
                "ok": True,
                "avatar_url": avatar_url
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Avatar not found"
            }), 404
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"Failed to get avatar: {str(e)}"
        }), 500

# -----------------------------------------------------------------------------
# Leaderboard API
# -----------------------------------------------------------------------------
@app.route("/api/leaderboard", methods=["GET"])
def get_leaderboard():
    """獲取排行榜數據"""
    try:
        # 模擬數據
        mock_data = [
            {
                "rank": 1,
                "username": "taylorswift",
                "displayName": "Taylor Swift",
                "followers": "282M",
                "accountValue": 9850000,
                "avatar": "TS",
                "avatar_url": get_user_avatar_url("taylorswift") or None
            },
            {
                "rank": 2,
                "username": "cristiano",
                "displayName": "Cristiano Ronaldo", 
                "followers": "631M",
                "accountValue": 9200000,
                "avatar": "CR",
                "avatar_url": get_user_avatar_url("cristiano") or None
            },
            {
                "rank": 3,
                "username": "therock",
                "displayName": "Dwayne Johnson",
                "followers": "395M", 
                "accountValue": 8750000,
                "avatar": "DJ",
                "avatar_url": get_user_avatar_url("therock") or None
            }
        ]
        
        return jsonify({
            "ok": True,
            "data": mock_data,
            "total": len(mock_data)
        })
        
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"獲取排行榜數據失敗: {str(e)}"
        }), 500

# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)