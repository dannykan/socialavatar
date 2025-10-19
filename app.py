import os
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

# OpenAI 官方 SDK
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    client = None  # 沒設 key 時後面會走保底邏輯


# -----------------------------------------------------------------------------
# Flask 基本設定：同站提供前端（/static/index.html）與 API (/api/analyze)
# -----------------------------------------------------------------------------
app = Flask(__name__, static_folder="static", static_url_path="")

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


# -----------------------------------------------------------------------------
# 小工具：將前端傳來的檔案轉成 OpenAI 多模態可讀的 input_image
# -----------------------------------------------------------------------------
def file_to_input_image(file_storage):
    """把上傳檔案轉為 responses.create 的 input_image 結構（以記憶體 bytes 傳）"""
    name = secure_filename(file_storage.filename or "image")
    data = file_storage.read()
    # 讓後面還能重讀（保險）
    file_storage.stream.seek(0)
    return {"type": "input_image", "image": {"name": name, "buffer": data}}


# -----------------------------------------------------------------------------
# API：分析 IG 截圖（必要：ig_screenshot；可選：grid[] 1~9 張）
# 回傳：username/name/bio/followers/following/posts + MBTI + 100字說明 + 追隨者等級
# -----------------------------------------------------------------------------
@app.post("/api/analyze")
def analyze():
    if "ig_screenshot" not in request.files:
        return jsonify({"ok": False, "error": "MISSING_SCREENSHOT"}), 400

    shot = request.files["ig_screenshot"]
    if shot.mimetype not in ALLOWED_IMAGE_TYPES:
        return jsonify({"ok": False, "error": "UNSUPPORTED_IMAGE_TYPE"}), 400

    grid_list = request.files.getlist("grid[]")  # 最多 9 張即可
    grid_list = grid_list[:9]

    nickname = (request.form.get("nickname") or "").strip()
    gender = (request.form.get("gender") or "").strip()

    # 構建多模態訊息（system + user）
    sys_prompt = (
        "你是社群風格分析師。僅根據使用者提供的 IG 個人頁截圖與首圖，"
        "辨識基本資料並推斷 MBTI 類型與 100 字內中文說明。"
        "務必輸出嚴格 JSON（不加多餘文字），鍵："
        "username,name,bio,followers,following,posts,mbti,reason100。"
        "followers/following/posts 抽不到就填 0；name 抽不到留空；"
        "reason100 最多 100 字，口吻自然友善、避免術語。"
    )
    user_text = (
        "影像1是 IG 個人頁截圖；之後（若有）為最近貼文首圖。"
        "請先從個人頁截圖辨識 username、個人名稱(name)、bio、粉絲數(followers)、追蹤數(following)、貼文數(posts)。"
        "再觀察首圖風格（人物、旅遊、美食、健身、寵物、攝影…），給出 MBTI（四字母）與 100 字內中文說明。"
        "請只輸出 JSON。"
    )

    content = [{"type": "text", "text": user_text}]
    # 個人頁截圖
    content.append(file_to_input_image(shot))
    # 九宮格首圖（可選）
    for f in grid_list:
        if f.mimetype in ALLOWED_IMAGE_TYPES:
            content.append(file_to_input_image(f))

    # 預設結果（保底）
    result = {
        "username": "",
        "name": nickname,
        "bio": "",
        "followers": 0,
        "following": 0,
        "posts": 0,
        "mbti": "ISFJ",
        "reason100": "依上傳截圖初步推斷，僅供娛樂參考。",
    }

    # 呼叫 OpenAI（若沒有 API Key，就回傳保底結果）
    if client:
        try:
            resp = client.responses.create(
                model="gpt-4o-mini",         # 你的帳號可用的多模態模型（可換成 gpt-4o）
                input=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": content},
                ],
                temperature=0.3,
                max_output_tokens=450,
            )
            text = resp.output_text or ""
            # 解析 JSON
            import json, re
            parsed = None
            try:
                parsed = json.loads(text)
            except Exception:
                m = re.search(r"\{[\s\S]+\}", text)
                if m:
                    parsed = json.loads(m.group(0))
            if isinstance(parsed, dict):
                # 取值並清洗
                result["username"]  = (parsed.get("username") or "").strip()
                result["name"]      = (parsed.get("name") or result["name"]).strip()
                result["bio"]       = (parsed.get("bio") or "").strip()
                result["followers"] = int(parsed.get("followers") or 0)
                result["following"] = int(parsed.get("following") or 0)
                result["posts"]     = int(parsed.get("posts") or 0)
                mbti = (parsed.get("mbti") or "ISFJ").upper().strip()
                result["mbti"]      = mbti[:4]
                reason = (parsed.get("reason100") or result["reason100"]).strip()
                result["reason100"] = reason[:120]
        except Exception as e:
            # 後端保底，不讓整體失敗
            print("[OpenAI failed]", repr(e))

    # 依粉絲數決定載具等級（你可以改成自己的區間）
    tier = decide_tier(result["followers"])

    return jsonify({
        "ok": True,
        "username": result["username"],
        "name": result["name"] or nickname,
        "bio": result["bio"],
        "followers": result["followers"],
        "following": result["following"],
        "posts": result["posts"],
        "mbti": result["mbti"],
        "reason100": result["reason100"],
        "tier": tier,
        "profile": {"nickname": nickname, "gender": gender},
    })


def decide_tier(followers: int) -> str:
    tiers = [
        (0,          1_000,       "walk"),        # 步行
        (1_000,      5_000,       "tricycle"),    # 三輪車
        (5_000,      10_000,      "scooter"),     # 滑板車
        (10_000,     50_000,      "motorcycle"),  # 機車
        (50_000,     100_000,     "car"),         # 汽車
        (100_000,    500_000,     "plane"),       # 飛機
        (500_000,    1_000_000,   "rocket"),      # 火箭
        (1_000_000,  5_000_000,   "spaceship"),   # 飛船
        (5_000_000,  1_000_000_000, "mothership"),# 母艦
    ]
    for lo, hi, name in tiers:
        if lo <= followers < hi:
            return name
    return "walk"


# -----------------------------------------------------------------------------
# 健康檢查 & 入口：/ 直接回 static/index.html
# -----------------------------------------------------------------------------
@app.get("/health")
def health():
    return jsonify({"ok": True})

@app.get("/")
def index():
    # 讓 / 直接回前端頁
    return send_from_directory("static", "index.html")


# Render / gunicorn 入口
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=False)
