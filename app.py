import os
import io
import json
import math
from datetime import datetime
from PIL import Image, ImageOps
from flask import Flask, request, jsonify, send_from_directory, abort

# ---------- Config ----------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
AI_ON = bool(OPENAI_API_KEY)
MAX_IMG_SIDE = int(os.getenv("MAX_IMG_SIDE", "1280"))
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "72"))

app = Flask(__name__)

# 用來查看最後一次 AI 回傳內容（方便 debug）
_LAST_AI_TEXT = {"text": ""}

# ---------- Utils ----------
def clamp_int(x, lo=0, hi=10**12):
    try:
        x = int(x)
        return max(lo, min(hi, x))
    except:
        return 0

def resize_to_max_side(im: Image.Image, max_side: int) -> Image.Image:
    w, h = im.size
    if max(w, h) <= max_side:
        return im
    if w >= h:
        new_w = max_side
        new_h = int(h * (max_side / w))
    else:
        new_h = max_side
        new_w = int(w * (max_side / h))
    return im.resize((new_w, new_h), Image.LANCZOS)

def img_to_jpeg_bytes(im: Image.Image, q: int) -> bytes:
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=q, optimize=True)
    return out.getvalue()

def vehicle_from_profile(followers: int, posts: int) -> str:
    score = followers * 0.7 + posts * 0.3
    if score < 2000:
        return "步行"
    elif score < 10000:
        return "腳踏車"
    elif score < 50000:
        return "機車"
    elif score < 200000:
        return "汽車"
    elif score < 500000:
        return "跑車"
    return "飛機"

def mbti_fallback() -> str:
    # 簡單保底：固定一個，或照你喜歡隨機
    return "ISFJ"

def heuristic_summary(mbti: str) -> str:
    base = {
        "ISFJ":"根據截圖中的關鍵元素與風格，推斷此帳號偏向 ISFJ。內容呈現與互動線索顯示其社交取向、思維傾向與表達方式；此結果僅供娛樂參考。",
        "ESFJ":"粉絲量與內容安排顯示其外向、感覺與情感導向；貼文風格偏向判斷型。"
    }
    return base.get(mbti, base["ISFJ"])[:100]

# ---------- OpenAI ----------
def call_openai_vision(profile_bytes: bytes, post_bytes_list: list[bytes]) -> dict | None:
    """
    請 OpenAI 看圖並輸出結構化 JSON。
    失敗回傳 None；成功回傳 dict：
    {
      display_name, username, followers, following, posts, mbti, summary, vehicle
    }
    """
    if not AI_ON:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print("[OpenAI import failed]", e)
        return None

    # 建構 multi-part 圖像訊息
    # gpt-4o-mini 支援 image_url 與 image input；這裡用 base64 data url。
    import base64
    def b64url(b: bytes):
        return "data:image/jpeg;base64," + base64.b64encode(b).decode("utf-8")

    images_parts = [{"type":"image_url","image_url":{"url": b64url(profile_bytes)}}]
    for b in post_bytes_list[:4]:
        images_parts.append({"type":"image_url","image_url":{"url": b64url(b)}})

    system_prompt = (
        "你是一個嚴謹的資料擷取與性格分析助理。"
        "使用者會提供 Instagram 個人頁截圖與最多 4 張首圖。"
        "請從畫面中擷取可讀資訊（若不清楚或看不到請填 null 或 0），再綜合影像風格給出 MBTI 推斷與 100 字摘要。"
        "必須只輸出 JSON，鍵如下：\n"
        "{\n"
        '  "display_name": string|null,\n'
        '  "username": string|null,\n'
        '  "followers": number,\n'
        '  "following": number,\n'
        '  "posts": number,\n'
        '  "mbti": "ISTJ|ISFJ|INFJ|INTJ|ISTP|ISFP|INFP|INTP|ESTP|ESFP|ENFP|ENTP|ESTJ|ESFJ|ENFJ|ENTJ",\n'
        '  "summary": string,  // 繁體中文，不超過 100 字\n'
        '  "vehicle": "步行|腳踏車|機車|汽車|跑車|飛機"\n'
        "}\n"
        "注意：若無法辨識數值（粉絲/追蹤/貼文），請填 0；不要臆測精確數字。"
    )

    user_prompt = (
        "請閱讀這些圖像。從個人頁面截圖中嘗試擷取名稱、帳號、粉絲數、追蹤數、貼文數；"
        "綜合首圖風格推斷 MBTI，並產出 100 字以內的繁中摘要。"
        "若畫面不清楚，數字請給 0；不可輸出多餘文字，僅能輸出 JSON。"
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system","content": system_prompt},
                {"role":"user","content":[{"type":"text","text":user_prompt}, *images_parts]}
            ],
            temperature=0.2,
            max_tokens=400
        )
        text = resp.choices[0].message.content.strip()
        _LAST_AI_TEXT["text"] = text
        # 嘗試解析 JSON
        data = json.loads(text)
        # 基本清洗
        out = {
            "display_name": (data.get("display_name") or "")[:80],
            "username": (data.get("username") or "")[:80],
            "followers": clamp_int(data.get("followers", 0)),
            "following": clamp_int(data.get("following", 0)),
            "posts": clamp_int(data.get("posts", 0)),
            "mbti": (data.get("mbti") or "").upper()[:4],
            "summary": (data.get("summary") or "")[:200],
            "vehicle": (data.get("vehicle") or "")[:10],
        }
        return out
    except Exception as e:
        print("[OpenAI vision failed]", e)
        return None

# ---------- Routes ----------
@app.get("/health")
def health():
    return jsonify({"status":"ok","max_side":MAX_IMG_SIDE,"jpeg_q":JPEG_QUALITY})

@app.get("/debug/config")
def debug_config():
    return jsonify({
        "ai_on": AI_ON,
        "max_side": MAX_IMG_SIDE,
        "jpeg_q": JPEG_QUALITY
    })

@app.get("/debug/last_ai")
def debug_last_ai():
    return jsonify(_LAST_AI_TEXT)

@app.post("/bd/analyze")
def bd_analyze():
    """
    期待 form-data：
      - profile: 單一 IG 個人頁截圖（必填）
      - posts: 0~4 張首圖（可選）
    回傳：
    {
      ai_used: bool,
      display_name, username,
      followers, following, posts,
      mbti, summary, vehicle
    }
    """
    if "profile" not in request.files:
        return jsonify({"error":"profile image required"}), 400

    try:
        prof_img = Image.open(request.files["profile"].stream).convert("RGB")
    except Exception:
        return jsonify({"error":"invalid profile image"}), 400

    # 縮圖 + 壓縮
    prof_img = resize_to_max_side(prof_img, MAX_IMG_SIDE)
    prof_bytes = img_to_jpeg_bytes(prof_img, JPEG_QUALITY)

    # 讀取最多 4 張首圖
    posts_files = request.files.getlist("posts")
    post_bytes_list = []
    for f in posts_files[:4]:
        try:
            im = Image.open(f.stream).convert("RGB")
            im = resize_to_max_side(im, MAX_IMG_SIDE)
            post_bytes_list.append(img_to_jpeg_bytes(im, JPEG_QUALITY))
        except Exception:
            continue

    # 先試 AI
    ai_used = False
    result = None
    if AI_ON:
        result = call_openai_vision(prof_bytes, post_bytes_list)
        ai_used = bool(result)

    # 保底
    if not result:
        m = mbti_fallback()
        result = {
            "display_name": "",
            "username": "",
            "followers": 0,
            "following": 0,
            "posts": 0,
            "mbti": m,
            "summary": heuristic_summary(m),
            "vehicle": vehicle_from_profile(0, 0)
        }

    # 若 AI 沒產生 vehicle，用規則補
    if not result.get("vehicle"):
        result["vehicle"] = vehicle_from_profile(result.get("followers",0), result.get("posts",0))

    result["ai_used"] = ai_used
    return jsonify(result), 200

# ---------- Static (前端) ----------
@app.get("/")
def root():
    return send_from_directory("static", "index.html")

@app.get("/result")
def result_page():
    return send_from_directory("static", "index.html")

@app.get("/static/<path:fn>")
def static_files(fn):
    return send_from_directory("static", fn)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
