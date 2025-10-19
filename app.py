import os, base64, json, re
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

# OpenAI SDK
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    client = None

app = Flask(__name__, static_folder="static", static_url_path="")

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_last_ai_text = ""  # 用於 /debug/last_ai 檢視最後一筆 AI 輸出


def to_data_url(file_storage):
    """把上傳檔轉為 data URL（image_url）給多模態"""
    mime = file_storage.mimetype or "image/jpeg"
    if mime not in ALLOWED_IMAGE_TYPES:
        mime = "image/jpeg"
    data = file_storage.read()
    file_storage.stream.seek(0)
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def decide_tier(followers: int) -> str:
    tiers = [
        (0,          1_000,        "walk"),
        (1_000,      5_000,        "tricycle"),
        (5_000,      10_000,       "scooter"),
        (10_000,     50_000,       "motorcycle"),
        (50_000,     100_000,      "car"),
        (100_000,    500_000,      "plane"),
        (500_000,    1_000_000,    "rocket"),
        (1_000_000,  5_000_000,    "spaceship"),
        (5_000_000,  1_000_000_000,"mothership"),
    ]
    for lo, hi, name in tiers:
        if lo <= followers < hi:
            return name
    return "walk"


@app.post("/api/analyze")
def analyze():
    global _last_ai_text

    if "ig_screenshot" not in request.files:
        return jsonify({"ok": False, "error": "MISSING_SCREENSHOT"}), 400

    shot = request.files["ig_screenshot"]
    if shot.mimetype not in ALLOWED_IMAGE_TYPES:
        return jsonify({"ok": False, "error": "UNSUPPORTED_IMAGE_TYPE"}), 400

    grid_list = request.files.getlist("grid[]")[:9]
    nickname = (request.form.get("nickname") or "").strip()
    gender = (request.form.get("gender") or "").strip()

    # 預設（保底）
    out = {
        "username": "",
        "name": nickname,
        "bio": "",
        "followers": 0,
        "following": 0,
        "posts": 0,
        "mbti": "ISFJ",
        "reason100": "依上傳截圖初步推斷，僅供娛樂參考。",
    }

    # 準備多模態內容（data URL）
    user_text = (
        "影像1是 IG 個人頁截圖；其後（若有）是最近貼文首圖。"
        "請只根據影像辨識以下欄位並輸出嚴格 JSON："
        "username（帳號）、name（顯示名稱）、bio（自我介紹）、"
        "followers（粉絲數，整數）、following（追蹤數，整數）、posts（貼文數，整數）、"
        "mbti（四字母）、reason100（100字內中文說明，口吻自然友善）。"
        "如影像看不到某數值，用 0；name 抽不到留空。不得輸出 JSON 以外的多餘文字。"
    )

    content = [{"type": "text", "text": user_text}]
    content.append({
        "type": "input_image",
        "image_url": {
            "url": to_data_url(shot)
        }
    })
    for f in grid_list:
        content.append({
            "type": "input_image",
            "image_url": { "url": to_data_url(f) }
        })

    sys_prompt = (
        "你是社群風格分析師。僅根據使用者提供的影像回答。"
        "務必輸出嚴格 JSON；不要加任何多餘說明或程式碼區塊。"
        "reason100 最多 100 字，避免專業術語、語氣自然。"
    )

    if client:
        try:
            resp = client.responses.create(
                model="gpt-4o-mini",   # 可換成你帳號可用的多模態模型，如 gpt-4o
                input=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": content},
                ],
                temperature=0.2,
                max_output_tokens=500,
            )
            _last_ai_text = resp.output_text or ""
            text = _last_ai_text

            # 嘗試解析嚴格 JSON
            parsed = None
            try:
                parsed = json.loads(text)
            except Exception:
                m = re.search(r"\{[\s\S]+\}", text)
                if m:
                    parsed = json.loads(m.group(0))

            if isinstance(parsed, dict):
                out["username"]  = (parsed.get("username") or "").strip()
                out["name"]      = (parsed.get("name") or out["name"]).strip()
                out["bio"]       = (parsed.get("bio") or "").strip()
                out["followers"] = int(parsed.get("followers") or 0)
                out["following"] = int(parsed.get("following") or 0)
                out["posts"]     = int(parsed.get("posts") or 0)
                out["mbti"]      = (parsed.get("mbti") or "ISFJ").upper()[:4]
                reason           = (parsed.get("reason100") or out["reason100"]).strip()
                out["reason100"] = reason[:120]
        except Exception as e:
            _last_ai_text = f"[OpenAI failed] {repr(e)}"

    tier = decide_tier(out["followers"])

    return jsonify({
        "ok": True,
        "username": out["username"],
        "name": out["name"] or nickname,
        "bio": out["bio"],
        "followers": out["followers"],
        "following": out["following"],
        "posts": out["posts"],
        "mbti": out["mbti"],
        "reason100": out["reason100"],
        "tier": tier,
        "profile": {"nickname": nickname, "gender": gender},
    })


@app.get("/debug/last_ai")
def debug_last_ai():
    """開發期用：看模型原始輸出（不含圖片）"""
    return jsonify({"text": _last_ai_text})


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=False)
