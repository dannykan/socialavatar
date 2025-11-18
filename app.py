# -----------------------------------------------------------------------------
# User Prompt (Safe Version)
# -----------------------------------------------------------------------------
def build_user_prompt(followers, following, posts):
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
