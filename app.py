from flask import Flask, request, jsonify
from flask_cors import CORS
import os, re, requests, random

OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")
PAGE_ACCESS_TOKEN= os.getenv("PAGE_ACCESS_TOKEN")
IG_USER_ID       = os.getenv("IG_USER_ID")
GRAPH            = "https://graph.facebook.com/v24.0"

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # 上線後可改成你的前端網域

def ig_get(path, params):
    p = dict(params or {})
    p["access_token"] = PAGE_ACCESS_TOKEN
    r = requests.get(f"{GRAPH}/{path}", params=p, timeout=30)
    r.raise_for_status()
    return r.json()

def clean_caption(s):
    if not s: return ""
    s = re.sub(r"http\S+","", s)
    s = re.sub(r"#\S+|@\S+","", s)
    s = re.sub(r"\s+"," ", s).strip()
    return s

@app.route("/healthz")
def healthz():
    return {"ok": True}

@app.route("/run", methods=["POST"])
def run():
    body = request.json or {}
    ig_user_id = body.get("ig_user_id", IG_USER_ID)
    max_media  = int(body.get("max_media", 30))

    # A) Profile
    profile = ig_get(f"{ig_user_id}", {
        "fields": "id,username,biography,followers_count,follows_count,media_count,profile_picture_url,name"
    })

    # B) Media list（一次抓多些，必要時沿 paging.next 繼續）
    fields = "id,media_type,caption,permalink,media_url,thumbnail_url,timestamp,like_count,comments_count,children{media_type,media_url,thumbnail_url}"
    medias = ig_get(f"{ig_user_id}/media", {
        "fields": fields, "limit": min(max_media,50)
    }).get("data", [])

    # 整理 captions（給 AI）
    captions = [clean_caption(m.get("caption")) for m in medias if m.get("caption")]
    captions = [c for c in captions if c][:60]  # 上限 60 則，避免太長

    # 這裡示意呼叫 AI（你可改成自己的多模態分析）
    analysis = {
        "mbti": "ENTJ",
        "dimensions": {"E_I":"E","S_N":"N","T_F":"T","J_P":"J"},
        "confidence": 0.72,
        "rationale": [
          "貼文語氣偏外向與主動；多為規劃、分享、帶領活動",
          "主題集中於效率、成就、體育與旅行，顯示目標導向",
          "用字偏直接简洁，重視可執行與行動"
        ],
        "tags": ["運動","旅行","咖啡"]
    }

    return jsonify({
        "profile": {
            "username": profile.get("username"),
            "biography": profile.get("biography"),
            "followers_count": profile.get("followers_count"),
            "follows_count": profile.get("follows_count"),
            "media_count": profile.get("media_count"),
            "profile_picture_url": profile.get("profile_picture_url"),
        },
        "medias": [
            {
              "id": m["id"],
              "type": m.get("media_type"),
              "caption": m.get("caption"),
              "media_url": m.get("media_url") or m.get("thumbnail_url"),
              "permalink": m.get("permalink"),
              "timestamp": m.get("timestamp"),
              "like_count": m.get("like_count"),
              "comments_count": m.get("comments_count")
            } for m in medias
        ],
        "analysis": analysis
    })
