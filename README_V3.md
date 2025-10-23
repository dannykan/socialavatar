# 💰 IG 身價評估系統 v3.0

> 從一張截圖，算出你的 IG 商業價值！

---

## 🎯 這是什麼？

這是一個全新的 **Instagram 帳號商業價值評估系統**，只需上傳你的 IG 個人頁截圖，AI 就能幫你計算：

- 💵 **發文價值** - 你發一篇文值多少錢
- 🎬 **Story 價值** - 限動的報價
- 📹 **Reels 價值** - 短影音的身價
- 📦 **月配合價值** - 包月合作的行情

同時分析：
- 視覺品質（色彩、構圖、後製）
- 內容類型（美妝、美食、旅遊等）
- 專業程度（Bio、品牌識別）
- 粉絲品質（影響力評估）
- 風格獨特性（創意度）

---

## 📦 檔案結構

```
📁 IG 身價評估系統 v3.0/
├── 📄 app_v3.py                    # Backend（身價計算邏輯）
├── 📄 result_v3.html               # Frontend（身價展示介面）
├── 📄 upload_v2.html               # 上傳頁面（沿用 v2）
├── 📄 UPGRADE_TO_V3_GUIDE.md       # 完整升級指南
└── 📄 README_V3.md                 # 本說明文件
```

---

## 🚀 快速開始

### 1. 安裝依賴

```bash
pip install flask flask-cors pillow requests
```

### 2. 設定環境變數

```bash
export OPENAI_API_KEY="sk-your-openai-api-key"
export OPENAI_MODEL="gpt-4o-mini"
```

### 3. 替換檔案

```bash
# Backend
cp app_v3.py app.py

# Frontend
cp result_v3.html static/result.html
```

### 4. 啟動服務

```bash
python app.py
```

### 5. 開啟瀏覽器

```
http://localhost:8000
```

---

## 💡 使用流程

```
1. 登入
   └─> Google / Facebook 登入

2. 上傳截圖
   └─> IG 個人頁截圖（必填）
   └─> 貼文縮圖（選填，最多 6 張）

3. AI 分析中...
   └─> 10-20 秒

4. 查看結果 🎉
   └─> 你的發文價值：NT$ 12,500
   └─> Story：NT$ 5,000
   └─> Reels：NT$ 16,250
   └─> 月配合：NT$ 50,000
```

---

## 📊 估價邏輯

### 基礎價格階梯

| 粉絲數 | 基礎價 | 級別 |
|--------|--------|------|
| 100K+ | NT$ 80,000 | 名人級 |
| 50K-100K | NT$ 35,000 | 網紅級 |
| 10K-50K | NT$ 12,000 | 意見領袖 |
| 5K-10K | NT$ 3,500 | 微網紅 |
| 1K-5K | NT$ 1,200 | 潛力股 |
| 500-1K | NT$ 600 | 新星 |
| <500 | NT$ 200 | 素人 |

### 6 大加成係數

```
最終價值 = 基礎價 
          × 視覺品質 (0.7 - 2.0x)
          × 內容類型 (0.8 - 2.5x)
          × 專業程度 (0.9 - 1.9x)
          × 粉絲品質 (0.6 - 1.5x)
          × 風格獨特性 (1.0 - 1.6x)
```

### 內容類型商業係數

| 類型 | 係數 |
|------|------|
| 美妝時尚 | ×2.5 |
| 旅遊探店 | ×2.0 |
| 美食料理 | ×1.8 |
| 健身運動 | ×1.8 |
| 科技3C | ×1.6 |
| 生活日常 | ×1.0 |

---

## 🎨 視覺設計

### 顏色配置

- **主背景:** 紫色漸層 `#667eea → #764ba2`
- **價值卡:** 粉紅漸層 `#f093fb → #f5576c`
- **用戶卡:** 藍紫漸層 `#e0c3fc → #8ec5fc`

### 動畫效果

- 價值卡背景旋轉（20秒循環）
- 品質進度條填充（1秒）
- 按鈕 hover 提升

---

## 🔧 自訂設定

### 調整價格基準

編輯 `app_v3.py`:

```python
def calculate_base_price(followers):
    if followers >= 100000:
        return 100000  # 改為你的價格
    elif followers >= 50000:
        return 40000   # 調整階梯
    # ...
```

### 調整內容類型係數

```python
CONTENT_TYPE_MULTIPLIERS = {
    "美妝時尚": 3.0,  # 提高美妝類價值
    "旅遊探店": 2.2,  # 調整旅遊類
    # ...
}
```

### 調整視覺品質門檻

```python
if visual_overall >= 9.0:
    visual_mult = 2.5  # 提高專業級係數
elif visual_overall >= 7.5:
    visual_mult = 1.8  # 調整中間檔
```

---

## 📈 API 回應格式

```json
{
  "ok": true,
  "username": "foodie_queen",
  "display_name": "美食女王",
  "followers": 7200,
  "following": 850,
  "posts": 342,
  
  "primary_type": {
    "id": "type_5",
    "name_zh": "生活記錄者",
    "emoji": "🍜",
    "confidence": 0.75
  },
  
  "value_estimation": {
    "base_price": 3500,
    "follower_tier": "微網紅",
    "follower_quality": "有吸引力",
    "multipliers": {
      "visual": 1.5,
      "content": 1.8,
      "professional": 1.4,
      "follower": 1.2,
      "unique": 1.3
    },
    "post_value": 12500,
    "story_value": 5000,
    "reels_value": 16250,
    "monthly_package": 50000
  },
  
  "analysis": {
    "visual_quality": {
      "color_harmony": 8.5,
      "composition": 7.8,
      "editing": 8.2,
      "overall": 8.1
    },
    "content_type": {
      "primary": "美食料理",
      "focus_score": 8,
      "commercial_potential": "high"
    },
    "professionalism": {
      "has_business_tag": true,
      "has_contact": false,
      "has_link": true,
      "consistency_score": 7.5,
      "brand_identity": 8.0
    },
    "uniqueness": {
      "style_signature": "極簡美食攝影",
      "creativity_score": 7.8,
      "differentiation": 7.5
    }
  },
  
  "value_statement": "用鏡頭記錄城市角落的美味故事，溫暖親切的美食引路人",
  
  "improvement_tips": [
    "在 Bio 加入合作聯絡方式可提升 15% 價值",
    "增加 Reels 內容以把握當前流量紅利",
    "建立固定發文時間提高粉絲黏性",
    "嘗試與在地餐廳建立長期合作關係"
  ]
}
```

---

## ✅ 測試清單

### Backend
- [ ] `/health` 回應正常
- [ ] `/debug/config` 顯示 `ai_enabled: true`
- [ ] `/bd/analyze` 接受圖片上傳
- [ ] 回應包含 `value_estimation` 物件
- [ ] 所有係數 > 0

### Frontend
- [ ] 用戶資訊顯示正確
- [ ] 主價值卡金額正確
- [ ] 6 項加成係數都顯示
- [ ] 品質評分進度條動畫
- [ ] 改進建議列表顯示
- [ ] 重新評估按鈕功能正常

---

## 🐛 除錯技巧

### 查看 AI 原始回應

```bash
curl http://localhost:8000/debug/last_ai | jq .
```

### 檢查 sessionStorage

```javascript
// Chrome DevTools Console
console.log(JSON.parse(sessionStorage.getItem('sa_result')));
```

### 驗證價值計算

```python
# 在 Python shell
from app import calculate_value

result = calculate_value(
    followers=7200,
    following=850,
    ai_analysis={...}
)
print(result)
```

---

## 📚 延伸閱讀

- **完整升級指南:** `UPGRADE_TO_V3_GUIDE.md`
- **API 文檔:** 見 `app_v3.py` 註解
- **12 種人格類型:** 保留自 v2 系統

---

## 🎯 版本歷程

**v3.0 (2025-01-XX) - 身價評估系統**
- ✅ 新增發文/Story/Reels 價值計算
- ✅ 新增 6 大評分維度
- ✅ 新增價值組成分析
- ✅ 新增改進建議系統
- ✅ 全新視覺設計
- ✅ 保留 12 種人格類型

**v2.0 - 人格類型系統**
- 12 種 IG 人格類型
- 色彩基因分析
- 風格關鍵詞

**v1.0 - MBTI 系統**
- 16 種 MBTI 類型
- 載具卡系統

---

## 💬 常見問題

### Q: 估算準確嗎？

A: 這是基於 AI 視覺分析與產業行情的**參考估算**。實際商業價值受互動率、粉絲質量、品牌預算等多重因素影響。建議作為「起跳價」參考。

### Q: 可以調整價格嗎？

A: 可以！修改 `app_v3.py` 中的：
- `calculate_base_price()` - 基礎價格
- `CONTENT_TYPE_MULTIPLIERS` - 內容類型係數
- 各項係數計算邏輯

### Q: 支援其他社群平台嗎？

A: 目前只支援 Instagram。如需擴展到其他平台（YouTube、TikTok等），需要調整 prompt 和係數設定。

### Q: 如何提高身價？

A: 系統會給出個人化建議，通常包括：
- 提升視覺品質（學習攝影/後製）
- 專注垂直領域（提高內容一致性）
- 增加互動率（固定發文時間）
- 建立品牌識別（統一風格）

---

## 🤝 貢獻

歡迎提交 Issue 或 Pull Request！

---

## 📄 授權

MIT License

---

## 🎉 開始使用

```bash
# 1. 安裝依賴
pip install -r requirements.txt

# 2. 設定 API Key
export OPENAI_API_KEY="your-key"

# 3. 啟動服務
python app.py

# 4. 上傳截圖，查看身價！
```

---

**打造屬於你的 IG 身價評估系統！** 💰✨
