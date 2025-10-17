# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import random
import time

app = Flask(__name__)
CORS(app)  # 允許跨網域，給前端 Vercel 呼叫

MBTI_TYPES = [
    ("INTJ", "策略型，重視結構與長期目標，貼文常見統一風格與邏輯"),
    ("INTP", "概念型，喜歡探索抽象與分析，圖片有思考與實驗感"),
    ("ENTJ", "領導型，目標導向，傳達效率與成就，圖像常有節奏感"),
    ("ENTP", "創意型，喜歡新穎與變化，貼文多樣、標題有趣"),
    ("INFJ", "洞察型，注重意義和價值，色調溫潤、敘事性強"),
    ("INFP", "理想型，重視自我表達與情感，圖片柔和、文案真誠"),
    ("ENFJ", "溝通型，善於連結他人，內容常以人為中心、正向"),
    ("ENFP", "靈感型，自由奔放，色彩鮮明、題材多元"),
    ("ISTJ", "務實型，結構分明，視覺整齊、重視一致性"),
    ("ISFJ", "照護型，溫暖踏實，圖片有細節與耐心"),
    ("ESTJ", "執行型，偏向規劃與管理，資訊清楚、強調效率"),
    ("ESFJ", "協作型，重視關係與互動，常見團體、活動照片"),
    ("ISTP", "工匠型，注重工具/技能，畫面俐落、偏實用"),
    ("ISFP", "美感型，重視審美與感受，色調乾淨、構圖講究"),
    ("ESTP", "行動型，喜歡刺激與現場感，運動/旅行元素多"),
    ("ESFP", "表演型，喜歡分享生活亮點，色彩鮮豔、活力滿滿"),
]

STYLE_KEYWORDS = [
    "簡約黑白", "奶油色調", "復古菲林", "高飽和霓虹", "自然光寫真", "旅行紀錄", "街頭紀實",
    "美食紀錄", "人像特寫", "運動瞬間", "風景廣角", "隨手生活", "專題策展", "拼貼風格"
]

@app.route("/", methods=["GET"])
def hello():
    return jsonify({"ok": True, "service": "SocialAvatar API", "health": "alive"})

@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    前端傳入：
      { "username": "dannytjkan" }
    回傳：
      {
        "ok": true,
        "username": "...",
        "mbti": "ENFP",
        "confidence": 0.73,
        "reason": "...",
        "style_keywords": [...],
        "samples": {
            "posts_used": 30,
            "images_used": 24
        },
        "generated_at": 1739777777
      }
    """
    try:
        payload = request.get_json(force=True, silent=True) or {}
        username = (payload.get("username") or "").strip()

        if not username:
            return jsonify({"ok": False, "error": "缺少參數 username"}), 400

        # 假分析（隨機產生）
        mbti, hint = random.choice(MBTI_TYPES)
        confidence = round(random.uniform(0.62, 0.88), 2)
        keywords = random.sample(STYLE_KEYWORDS, k=5)

        # 這裡可以接上你真正的 IG 抽取與圖像分析（待辦）
        # ex: fetch_ig_profile(username) → get posts/media → run image embeddings/labels → summarize
        # 現在先用 mock 結果
        result = {
            "ok": True,
            "username": username,
            "mbti": mbti,
            "confidence": confidence,
            "reason": f"根據最近貼文的色調、主題變化與敘事方式，呈現出「{hint}」的特徵。",
            "style_keywords": keywords,
            "samples": {
                "posts_used": random.randint(18, 45),
                "images_used": random.randint(12, 40),
            },
            "generated_at": int(time.time())
        }
        return jsonify(result)

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    # 本地啟動：python app.py
    app.run(host="0.0.0.0", port=8000, debug=True)
