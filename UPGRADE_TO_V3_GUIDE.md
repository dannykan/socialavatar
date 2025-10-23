# 🚀 IG 身價評估系統 v3.0 - 完整升級指南

## 📦 升級內容總覽

從「人格類型分析」→「身價評估系統」

### 核心變更

**舊版 (v2)：**
- ✅ 12 種人格類型判定
- ✅ 色彩基因分析
- ✅ 風格關鍵詞

**新版 (v3)：**
- ✅ **保留** 12 種人格類型
- ✅ **新增** 發文/Story/Reels 價值估算
- ✅ **新增** 6 大評分維度
- ✅ **新增** 價值組成分析
- ✅ **新增** 改進建議系統

---

## 📂 檔案清單

```
✅ app_v3.py           - 新版 Backend（身價計算邏輯）
✅ result_v3.html      - 新版結果頁（身價展示介面）
✅ upload_v2.html      - 上傳頁（保持不變）
```

---

## 🎯 快速部署（5 分鐘）

### Step 1: 備份舊檔案

```bash
# 在你的專案目錄
cp app.py app_backup_v2.py
cp static/result.html static/result_backup_v2.html
```

### Step 2: 替換新檔案

```bash
# Backend
cp app_v3.py app.py

# Frontend
cp result_v3.html static/result.html

# upload.html 保持使用 v2 版本（已移除性別選擇）
```

### Step 3: 本地測試

```bash
# 設定環境變數
export OPENAI_API_KEY="sk-your-key-here"
export OPENAI_MODEL="gpt-4o-mini"

# 啟動伺服器
python app.py

# 開啟瀏覽器
# http://localhost:8000
```

### Step 4: 測試流程

```
1. 登入 → landing.html
2. 上傳截圖 → upload.html
3. 等待分析（10-20秒）
4. 查看結果 → result.html
   ✅ 顯示發文價值
   ✅ 顯示 Story/Reels 價值
   ✅ 顯示價值組成
   ✅ 顯示品質評分
   ✅ 顯示改進建議
```

### Step 5: 部署到 Render

```bash
git add app.py static/result.html
git commit -m "feat: upgrade to value estimation system v3"
git push origin main

# Render 會自動偵測並部署
```

---

## 🔍 詳細變更說明

### A. Backend (app.py)

#### 新增功能

**1. 身價計算公式**

```python
最終價值 = 基礎價 × 視覺品質係數 × 內容類型係數 
          × 專業度係數 × 粉絲品質係數 × 獨特性係數

Story 價值 = 發文價值 × 0.4
Reels 價值 = 發文價值 × 1.3
月配合 = 發文價值 × 4
```

**2. 基礎價格階梯**

| 粉絲數 | 基礎價 | 級別 |
|--------|--------|------|
| 100K+ | NT$ 80,000 | 名人級 |
| 50K-100K | NT$ 35,000 | 網紅級 |
| 10K-50K | NT$ 12,000 | 意見領袖 |
| 5K-10K | NT$ 3,500 | 微網紅 |
| 1K-5K | NT$ 1,200 | 潛力股 |
| 500-1K | NT$ 600 | 新星 |
| <500 | NT$ 200 | 素人 |

**3. 內容類型商業係數**

```python
CONTENT_TYPE_MULTIPLIERS = {
    "美妝時尚": 2.5,
    "旅遊探店": 2.0,
    "美食料理": 1.8,
    "健身運動": 1.8,
    "科技3C": 1.6,
    "親子家庭": 1.7,
    "攝影藝術": 1.5,
    "寵物萌寵": 1.5,
    "知識教育": 1.4,
    "生活風格": 1.2,
    "生活日常": 1.0,
    "個人隨拍": 0.8
}
```

**4. 視覺品質評分**

```python
if visual_overall >= 9.0:   × 2.0  # 攝影師級
elif visual_overall >= 7.5: × 1.5  # 專業級
elif visual_overall >= 6.0: × 1.2  # 精緻級
elif visual_overall >= 4.0: × 1.0  # 標準級
else:                       × 0.7  # 素人級
```

**5. 粉絲品質係數**

```python
粉絲/追蹤比例：
>= 3.0  → × 1.5  # 高影響力
>= 1.5  → × 1.2  # 有吸引力
>= 1.0  → × 1.0  # 標準
>= 0.5  → × 0.8  # 需成長
< 0.5   → × 0.6  # 待建立
```

#### 新增 API 回應格式

**舊版 (v2):**
```json
{
  "primary_type": {...},
  "analysis": {...},
  "personality_statement": "..."
}
```

**新版 (v3):**
```json
{
  "primary_type": {...},
  "value_estimation": {
    "base_price": 8000,
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
  "analysis": {...},
  "value_statement": "用鏡頭記錄城市角落的美味故事...",
  "improvement_tips": [...]
}
```

---

### B. Frontend (result.html)

#### 視覺設計完全重做

**佈局結構：**

```
┌─────────────────────────────────┐
│ Header (白色半透明)              │
├─────────────────────────────────┤
│ 用戶資訊卡                       │
│ [Avatar] @username              │
│ 7.2K 粉絲 | 850 追蹤 | 342 貼文  │
├─────────────────────────────────┤
│ 主價值卡（漸層背景 + 旋轉動畫）   │
│ 🍜 生活記錄者                    │
│                                  │
│ 你的發文價值                     │
│ NT$ 12,500 / 篇                 │
│                                  │
│ Story | Reels | 月配合           │
├─────────────────────────────────┤
│ 📊 價值組成分析                  │
│ • 基礎身價 → NT$ 8,000          │
│ • 視覺品質加成 → ×1.5           │
│ • 內容類型加成 → ×1.8           │
│ • 專業度加成 → ×1.4             │
│ • 粉絲品質加成 → ×1.2           │
│ • 風格獨特性加成 → ×1.3         │
├─────────────────────────────────┤
│ ⭐ 品質評分                      │
│ [進度條] 色彩和諧度 8.5/10       │
│ [進度條] 構圖專業度 7.8/10       │
│ [進度條] 後製品質 8.2/10         │
│ [進度條] 整體美感 8.1/10         │
├─────────────────────────────────┤
│ 💬 你的價值定位                  │
│ "用鏡頭記錄城市角落的美味故事"   │
├─────────────────────────────────┤
│ 📈 價值提升建議                  │
│ 💡 在 Bio 加入聯絡方式 (+15%)   │
│ 💡 增加 Reels 內容              │
│ 💡 建立固定發文時間              │
└─────────────────────────────────┘
```

#### 新增視覺元素

**1. 漸層背景**
- 整體背景：紫色漸層 (#667eea → #764ba2)
- 價值卡：粉紅漸層 (#f093fb → #f5576c)
- 用戶卡：藍紫漸層 (#e0c3fc → #8ec5fc)

**2. 動畫效果**
- 價值卡背景旋轉動畫（20秒循環）
- 品質進度條填充動畫（1秒）
- 按鈕 hover 效果

**3. 響應式設計**
- 桌面版：900px 寬容器
- 手機版：自適應佈局，單欄顯示

---

## 📊 功能對比表

| 功能 | v2 (人格分析) | v3 (身價評估) |
|------|--------------|--------------|
| 人格類型判定 | ✅ | ✅ 保留 |
| 色彩基因 | ✅ | ❌ 移除（簡化） |
| 關鍵詞標籤 | ✅ | ❌ 移除（簡化） |
| 發文價值估算 | ❌ | ✅ **新增** |
| Story 價值 | ❌ | ✅ **新增** |
| Reels 價值 | ❌ | ✅ **新增** |
| 月配合價值 | ❌ | ✅ **新增** |
| 價值組成分析 | ❌ | ✅ **新增** |
| 6 大係數 | ❌ | ✅ **新增** |
| 品質評分 | ❌ | ✅ **新增** |
| 改進建議 | ❌ | ✅ **新增** |
| 雷達圖 | ✅ | ❌ 移除（簡化） |

---

## ✅ 測試清單

### Backend 測試

```bash
# 1. 健康檢查
curl http://localhost:8000/health

# 預期回應：
{
  "status": "ok",
  "model": "gpt-4o-mini",
  "ai_enabled": true,
  "max_side": 1280,
  "jpeg_quality": 72
}

# 2. 檢查上次 AI 回應
curl http://localhost:8000/debug/last_ai

# 預期：包含 value_estimation 物件
```

### Frontend 測試

**Upload Page:**
```
✅ 不顯示性別選擇
✅ 圖片上傳預覽正常
✅ Loading overlay 顯示
✅ 提交後導向 result.html
```

**Result Page:**
```
✅ 顯示用戶資訊（頭像、用戶名、統計數據）
✅ 顯示類型 badge（emoji + 名稱）
✅ 主價值卡顯示正確金額
✅ Story/Reels/月配合價值顯示
✅ 價值組成 6 項都顯示
✅ 品質評分進度條動畫
✅ 價值陳述文字顯示
✅ 改進建議列表顯示
✅ 重新評估按鈕功能正常
```

---

## 🐛 常見問題

### Q1: AI 回傳的價值為 0 或異常低？

**檢查點：**
1. 確認粉絲數是否正確提取
2. 檢查 `/debug/last_ai` 的 JSON 格式
3. 驗證各項係數是否正常計算

**Debug 方式：**
```bash
curl http://localhost:8000/debug/last_ai | jq .
```

查看：
- `value_estimation.base_price` 是否合理
- `value_estimation.multipliers` 各項是否 > 0
- `analysis` 物件是否完整

---

### Q2: 前端顯示「載入中...」不更新？

**原因：** sessionStorage 或 API 回應格式錯誤

**解決：**
```javascript
// 在 Chrome DevTools Console
console.log(sessionStorage.getItem('sa_result'));

// 檢查是否包含 value_estimation
```

---

### Q3: 價值計算邏輯如何調整？

**修改 app.py 中的常數：**

```python
# 調整基礎價格
def calculate_base_price(followers):
    if followers >= 100000:
        return 100000  # 改為 10 萬
    # ...

# 調整內容類型係數
CONTENT_TYPE_MULTIPLIERS = {
    "美妝時尚": 3.0,  # 改為 3.0
    # ...
}

# 調整視覺品質係數
if visual_overall >= 9.0:
    visual_mult = 2.5  # 改為 2.5
```

---

### Q4: 如何新增更多內容類型？

**在 app.py 中：**

```python
CONTENT_TYPE_MULTIPLIERS = {
    # ... 現有類型
    "音樂表演": 1.9,  # 新增
    "手作DIY": 1.4,   # 新增
}
```

**在 System Prompt 中：**

```python
def build_user_prompt(followers, following, posts):
    return f"""
    ...
    - primary: 主要類別（從以下選擇）
      * 美妝時尚, ..., 音樂表演, 手作DIY  # 加入新類型
    ...
    """
```

---

## 💡 進階功能建議

部署成功後，可以考慮：

### Phase 1 - 數據追蹤
- 記錄每個分析結果到 Firestore
- 統計各級別分佈
- 追蹤平均價值變化

### Phase 2 - 社群功能
- 分享到 IG Story（生成圖片）
- 排行榜（本週最高價值）
- 同級別比較

### Phase 3 - 進階分析
- 歷史價值追蹤（多次分析）
- 成長建議個人化
- 業配機會匹配

---

## 📚 相關文檔

- **系統設計文檔:** 見前面的「身價評估系統設計」
- **API 文檔:** 見 app_v3.py 註解
- **12 種類型定義:** 保留自 v2 系統

---

## 🎉 升級完成！

現在你擁有：
- ✅ 更有趣的身價評估系統
- ✅ 更直觀的價值展示
- ✅ 更實用的改進建議
- ✅ 更吸引人的視覺設計

**下一步：**
1. 測試完整流程
2. 調整價格基準（根據你的目標市場）
3. 收集用戶反饋
4. 持續優化 AI prompt

---

## 🆘 需要協助？

**常見錯誤排查：**
1. AI 回應格式錯誤 → 檢查 `/debug/last_ai`
2. 價值計算異常 → 檢查係數設定
3. 前端顯示錯誤 → 檢查 Console
4. Firestore 存儲失敗 → 檢查權限設定

**聯絡方式：**
- GitHub Issues
- 技術支援 Email

---

**祝你的 IG 身價評估系統大受歡迎！** 💰✨
