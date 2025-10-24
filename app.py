# app.py - 固定問題版本

import os
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from PIL import Image
from ai_analyzer import IGAnalyzer, PromptBuilder

app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
MAX_SIDE = int(os.getenv("MAX_SIDE", "1280"))
JPEG_Q = int(os.getenv("JPEG_QUALITY", "72"))


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "version": "v6-fixed-question",
        "model": OPENAI_MODEL,
        "ai_enabled": bool(OPENAI_API_KEY),
        "default_question": PromptBuilder.DEFAULT_QUESTION
    })


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    固定問題分析端點
    
    接收：
    - screenshot: IG 截圖檔案
    
    回傳：
    - 純文字回答
    """
    
    # 1. 檢查 API Key
    if not OPENAI_API_KEY:
        return jsonify({
            "error": "OpenAI API key 未設置"
        }), 500
    
    # 2. 獲取截圖
    screenshot_file = request.files.get("screenshot")
    
    if not screenshot_file:
        return jsonify({
            "error": "請上傳 IG 截圖"
        }), 400
    
    # 3. 處理圖片
    try:
        screenshot_img = Image.open(screenshot_file.stream)
    except Exception as e:
        return jsonify({
            "error": f"圖片格式不支援: {str(e)}"
        }), 400
    
    # 4. 分析（使用固定問題）
    try:
        analyzer = IGAnalyzer(
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            max_side=MAX_SIDE,
            quality=JPEG_Q
        )
        
        answer = analyzer.analyze_profile(screenshot_img)
        
        # 回傳純文字
        return answer, 200, {'Content-Type': 'text/plain; charset=utf-8'}
        
    except ValueError as e:
        return jsonify({
            "error": str(e)
        }), 400
    except Exception as e:
        print(f"[Error] {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "error": "分析失敗，請稍後再試"
        }), 500


@app.route("/debug/question")
def debug_question():
    """查看當前使用的固定問題"""
    return jsonify({
        "question": PromptBuilder.DEFAULT_QUESTION
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)