# app.py
import os, io, tempfile
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

VEHICLE_TIERS = [
    (0, 1000, "walk"),
    (1000, 5000, "tricycle"),
    (5000, 10000, "scooter"),
    (10000, 50000, "motorcycle"),
    (50000, 100000, "car"),
    (100000, 500000, "plane"),
    (500000, 1000000, "rocket"),
    (1000000, 10_000_000, "spaceship"),
    (10_000_000, 10_000_000_000, "mothership"),
]

def decide_tier(followers: int) -> str:
    for lo, hi, name in VEHICLE_TIERS:
        if lo <= followers < hi:
            return name
    return "walk"

@app.post("/api/analyze")
def analyze():
    if "ig_screenshot" not in request.files:
        return jsonify({"ok": False, "error": "MISSING_SCREENSHOT"}), 400

    ig_shot = request.files["ig_screenshot"]
    grids = request.files.getlist("grid[]")
    nickname = request.form.get("nickname", "")
    gender = request.form.get("gender", "")

    # 準備多模態訊息
    msgs = [
        {"role": "system", "content":
         "你是社群風格分析師。請僅根據使用者提供的 IG 截圖與首圖，"
         "辨識基本資料並推斷 MBTI 類型與 100 字內中文說明。"
         "請務必輸出 JSON，鍵：username,name,bio,followers,following,posts,mbti,reason100。"
         "followers/… 抽不到就填 0；name 抽不到就留空。reason100 僅 100 字內，口吻自然友善，不要英文字母密集。"
        }
    ]

    # 文字提示
    user_text = (
        "影像1是 IG 個人頁截圖。若有其他影像則為最近貼文首圖。"
        "請先從個人頁截圖中辨識 username、個人名稱(name)、bio、"
        "粉絲數(followers)、追蹤數(following)、貼文數(posts)。"
        "再觀察首圖風格（人物、旅遊、美食、健身、寵物、攝影等），"
        "最後輸出 MBTI（四字母）與 100 字以內中文說明。"
        "務必輸出 JSON，且 reason100 不得超過 100 字。"
    )
    content = [{"type": "text", "text": user_text}]

    # 影像（個人頁）
    content.append({
        "type": "input_image",
        "image": {"name": secure_filename(ig_shot.filename), "buffer": ig_shot.stream.read()}
    })
    ig_shot.stream.seek(0)

    # 影像（九宮格首圖）
    for f in grids[:9]:
        content.append({
            "type": "input_image",
            "image": {"name": secure_filename(f.filename), "buffer": f.stream.read()}
        })
        f.stream.seek(0)

    msgs.append({"role": "user", "content": content})

    # 呼叫多模態（依你帳號可用的模型名稱調整）
    resp = client.responses.create(
        model="gpt-4o-mini",  # 或 gpt-4.1 / gpt-4o
        input=msgs,
        temperature=0.3,
        max_output_tokens=400
    )

    # 解析 JSON
    import json
    text = resp.output_text
    try:
        data = json.loads(text)
    except Exception:
        # 容錯：嘗試從內容抽 JSON 區塊
        import re
        m = re.search(r"\{[\s\S]+\}", text)
        data = json.loads(m.group(0)) if m else {}

    username  = (data.get("username") or "").strip()
    name      = (data.get("name") or "").strip()
    bio       = (data.get("bio") or "").strip()
    followers = int(data.get("followers") or 0)
    following = int(data.get("following") or 0)
    posts     = int(data.get("posts") or 0)
    mbti      = (data.get("mbti") or "ISFJ").upper()[:4]
    reason    = (data.get("reason100") or "依公開截圖初步推斷，僅供娛樂參考。")[:120]

    tier = decide_tier(followers)

    return jsonify({
        "ok": True,
        "username": username,
        "name": name or nickname,
        "bio": bio,
        "followers": followers,
        "following": following,
        "posts": posts,
        "mbti": mbti,
        "reason100": reason,
        "tier": tier,
        "profile": {"nickname": nickname, "gender": gender}
    })
