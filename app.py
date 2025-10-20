# --- app.py (開頭) -----------------------------------------------------------
import os, io, base64, json, re, time
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory
from PIL import Image

# 1) 先建立 Flask app
app = Flask(__name__, static_folder="static", static_url_path="/static")

# 2) 設定（環境變數）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# 3) 全域：最近一次 AI 回應（給 /debug/last_ai）
LAST_AI_TEXT = {
    "raw":  "",
    "text": "",
    "ts":   None,
}
def _set_last_ai(text: str = "", raw: str = ""):
    LAST_AI_TEXT["text"] = text or ""
    LAST_AI_TEXT["raw"]  = raw or ""
    LAST_AI_TEXT["ts"]   = datetime.now(timezone.utc).isoformat()

def save_last_ai(ai_dict=None, raw="", text=""):
    """
    你可以在 /bd/analyze 成功或失敗時呼叫：
      save_last_ai(ai_dict=parsed_dict, raw=raw_response, text=ai_text)
    若 ai_dict 是 dict，會盡力把它序列化成 json 字串塞到 text 方便前端 fallback 解析。
    """
    s_text = text or ""
    if not s_text and ai_dict is not None:
        try:
            s_text = json.dumps(ai_dict, ensure_ascii=False)
        except Exception:
            s_text = ""
    _set_last_ai(text=s_text, raw=raw or "")

# 4) 共用工具：圖片壓縮→base64
def _pil_compress_to_b64(im: Image.Image, max_side=1280, jpeg_q=72) -> str:
    im = im.convert("RGB")
    w, h = im.size
    scale = min(1.0, float(max_side) / float(max(w, h)))
    if scale < 1.0:
        im = im.resize((int(w*scale), int(h*scale)))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=jpeg_q, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

# 5) 偵錯/健康檢查 API（注意：這些 route 要在 app 建立之後宣告）
@app.route("/debug/last_ai")
def debug_last_ai():
    # 回傳最近一次 AI 呼叫的原文 & 文字（給前端 fallback 用）
    return jsonify({
        "raw":  LAST_AI_TEXT.get("raw", ""),
        "text": LAST_AI_TEXT.get("text", ""),
        "ts":   LAST_AI_TEXT.get("ts", None)
    })

@app.route("/debug/config")
def debug_config():
    # 提供前端顯示診斷資訊
    return jsonify({
        "ai_on":        bool(OPENAI_API_KEY),
        "has_api_key":  bool(OPENAI_API_KEY),
        "model":        OPENAI_MODEL,
        "jpeg_q":       72,
        "max_side":     1280
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok", "max_side": 1280, "jpeg_q": 72})

# 6) （選）首頁導向
@app.route("/")
def root():
    return send_from_directory(app.static_folder, "landing.html")
    
def load_last_ai():
    """Read last ai result from disk; return empty skeleton if not exists."""
    try:
        if LAST_AI_FILE.exists():
            return json.loads(LAST_AI_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print("[last_ai] load failed:", e)
    return {"ai": None, "raw": "", "text": "", "ts": None}

# -----------------------------------------------------------------------------
# 小工具：影像壓縮與 base64
# -----------------------------------------------------------------------------
def _pil_compress_to_b64(img: Image.Image) -> str:
    """將 PIL 圖片壓縮成 JPEG（長邊 <= MAX_SIDE；quality=JPEG_Q）並回傳 base64 字串"""
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > MAX_SIDE and min(w, h) > 0:
        if w >= h:
            nh = int(h * (MAX_SIDE / float(w)))
            nw = MAX_SIDE
        else:
            nw = int(w * (MAX_SIDE / float(h)))
            nh = MAX_SIDE
        img = img.resize((nw, nh), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_Q, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")

def _extract_images_from_form(form_field: str, max_files: int = 6):
    """
    從 multipart/form-data 取多張圖（同名欄位），回傳 base64 字串陣列。
    前端請用：<input type="file" name="posts" multiple>
    """
    b64s = []
    files = request.files.getlist(form_field)
    for f in files[:max_files]:
        try:
            img = Image.open(f.stream)
            b64s.append(_pil_compress_to_b64(img))
        except Exception:
            continue
    return b64s

# -----------------------------------------------------------------------------
# JSON 區塊萃取（去除 ```json ... ``` 外殼）
# -----------------------------------------------------------------------------
def _extract_json_block(s: str):
    if not s:
        return None
    txt = s.strip()
    # 去掉三引號包裝
    if txt.startswith("```"):
        first_nl = txt.find("\n")
        if first_nl > 0:
            txt = txt[first_nl + 1 :]
        if txt.endswith("```"):
            txt = txt[:-3]
    # 取第一個 { 到最後一個 }
    l = txt.find("{")
    r = txt.rfind("}")
    if l != -1 and r != -1 and r > l:
        txt = txt[l : r + 1]
    try:
        return json.loads(txt)
    except Exception:
        return None

# -----------------------------------------------------------------------------
# 載具分級
# -----------------------------------------------------------------------------
def pick_vehicle(followers: int) -> str:
    if followers >= 1_000_000: return "太空船"
    if followers >=   100_000: return "火箭"
    if followers >=    50_000: return "飛機"
    if followers >=    10_000: return "汽車"
    if followers >=     5_000: return "機車"
    if followers >=     1_000: return "滑板車"
    if followers >=       500: return "三輪車"
    return "步行"

# -----------------------------------------------------------------------------
# OpenAI 視覺呼叫（Responses API）
# -----------------------------------------------------------------------------
def call_openai_vision(profile_b64: str, posts_b64_list: list[str]):
    """
    回傳：(純文字 output_text, 原始回應 text)
    失敗 raise RuntimeError（外層會接住並 fallback）
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("No OPENAI_API_KEY configured")

    url = "https://api.openai.com/v1/responses"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    # 角色設定（你最新的需求）
    sys_prompt = (
        "你是一位社群人格分析師。請用『第一次打開 IG 個人頁』的直覺來判讀此帳號："
        "只根據個人頁可見的資料（粉絲/追蹤/貼文數、名稱、自我介紹、首屏縮圖），"
        "判斷對方的社群 MBTI 類型（如：INTP/ESFJ 等），並用自然、有個性的口吻，"
        "給一段約 200 字的分析說明（為什麼會這樣覺得）。不要用制式報表語氣。\n"
        "請務必只輸出 JSON，不要加任何註解或 Markdown 區塊。\n"
        "欄位固定為：display_name, username, followers, following, posts, mbti, summary, vehicle。"
    )

    contents = [
        {"type": "input_text", "text": sys_prompt},
        {"type": "input_text", "text": "以下是 IG 個人頁截圖（含數字/名稱/bio/首屏格）：" },
        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{profile_b64}"},
    ]

    # 最多 3 張貼文縮圖
    for i, b64 in enumerate(posts_b64_list[:3], start=1):
        contents.append({"type": "input_text", "text": f"貼文首圖 #{i}：" })
        contents.append({"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}"})

    payload = {
        "model": OPENAI_MODEL,
        "input": [ { "role": "user", "content": contents } ],
        "max_output_tokens": 700
    }

    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=90)
    if not resp.ok:
        raise RuntimeError(f"OpenAI HTTP {resp.status_code}: {resp.text}")

    data = resp.json()

    # 擷取 output_text
    out_text = ""
    if "output" in data and isinstance(data["output"], list):
        for piece in data["output"]:
            for c in piece.get("content", []):
                if c.get("type") in ("output_text", "text") and c.get("text"):
                    out_text += c["text"]

    if not out_text:
        # 取不到就丟整包回去 debug
        out_text = json.dumps(data)

    return out_text.strip(), resp.text

# -----------------------------------------------------------------------------
# 路由
# -----------------------------------------------------------------------------
@app.get("/", endpoint="home")
def root():
    return send_from_directory(app.static_folder, "landing.html")

@app.get("/health")
def health():
    return jsonify({"status": "ok", "max_side": MAX_SIDE, "jpeg_q": JPEG_Q})

@app.get("/debug/config")
def debug_config():
    return jsonify({
        "ai_on": bool(OPENAI_API_KEY),
        "has_api_key": bool(OPENAI_API_KEY),
        "model": OPENAI_MODEL,
        "max_side": MAX_SIDE,
        "jpeg_q": JPEG_Q
    })

@app.get("/debug/last_ai")
def debug_last_ai():
    return jsonify(LAST_AI_TEXT)

@app.post("/bd/analyze")
def bd_analyze():
    """
    表單欄位：
      - profile: 必填（單檔）IG 個人頁截圖
      - posts  : 可選（多檔）首屏貼文縮圖
    回傳：
      { ok, mbti, summary, username, display_name, followers, following, posts, vehicle, diagnose }
    """
    diagnose = {
        "ai_on": bool(OPENAI_API_KEY),
        "model": OPENAI_MODEL,
        "used_fallback": False,
        "fail_reason": "",
        "posts_sent": 0,
    }

    # 1) 讀檔
    f_profile = request.files.get("profile")
    if not f_profile:
        return jsonify({"ok": False, "error": "missing_profile_image"}), 400

    try:
        img_profile = Image.open(f_profile.stream)
        profile_b64 = _pil_compress_to_b64(img_profile)
    except Exception as e:
        return jsonify({"ok": False, "error": "bad_profile_image", "detail": str(e)}), 400

    posts_b64 = _extract_images_from_form("posts", max_files=6)
    diagnose["posts_sent"] = len(posts_b64)

    # 2) 呼叫 OpenAI
    used_fallback = False
    parsed = None
    ai_text = ""
    raw = ""

    if OPENAI_API_KEY:
        try:
            ai_text, raw = call_openai_vision(profile_b64, posts_b64)  # <-- 取得「模型文字」與「完整原始回應(JSON字串)」
            parsed = _extract_json_block(ai_text)
            if not parsed:
                diagnose["fail_reason"] = "json_parse"
                used_fallback = True
        except Exception as e:
            raw = f"[OpenAI failed] {e}"
            diagnose["fail_reason"] = "openai_http"
            used_fallback = True
    else:
        raw = "[OpenAI disabled] Missing OPENAI_API_KEY"
        diagnose["fail_reason"] = "no_api_key"
        used_fallback = True

    # 3) 組合輸出（fallback）
    if not parsed:
        result = {
            "display_name": "使用者",
            "username": "",
            "followers": 0,
            "following": 0,
            "posts": 0,
            "mbti": "ESFJ",
            "summary": "依上傳截圖初步推斷，僅供娛樂參考。",
        }
    else:
        def _to_int(x):
            try:
                return int(x)
            except Exception:
                return 0

        result = {
            "display_name": str(parsed.get("display_name") or "").strip()[:100],
            "username":     str(parsed.get("username") or "").strip()[:100],
            "followers":    _to_int(parsed.get("followers")),
            "following":    _to_int(parsed.get("following")),
            "posts":        _to_int(parsed.get("posts")),
            "mbti":         str(parsed.get("mbti") or "").strip()[:10].upper(),
            "summary":      str(parsed.get("summary") or "").strip()[:600],
        }

    result["vehicle"] = pick_vehicle(result.get("followers", 0))
    diagnose["used_fallback"] = used_fallback

    # 4) 把這次結果持久化（/debug/last_ai 用得到）
    #    這裡把「最終要呈現的 result（dict）」當 ai_dict，
    #    raw = 完整原始回應（或錯誤字串），ai_text = 模型輸出的文本（含 JSON 區塊）
    save_last_ai(ai_dict=result, raw=raw, text=ai_text)

    # 5) 回傳前端
    return jsonify({"ok": True, **result, "diagnose": diagnose})

# -----------------------------------------------------------------------------
# 本地開發
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # 本地直接跑：python app.py
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=True)
