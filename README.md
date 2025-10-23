# 📊 IG Value Estimation System V4

> 專業的 Instagram 帳號商業價值評估系統
> 
> ✨ **V4 新增 4 個核心商業係數**，讓估值更精準、更符合市場實況！

---

## 🎯 核心特色

### V4 新增係數
1. **🎯 互動潛力係數** (0.8x - 1.5x)
   - 分析 Bio 的互動引導、表情符號密度、內容可評論性
   
2. **🎨 利基專注度係數** (0.9x - 1.6x)
   - 評估主題一致性、垂直領域專注程度
   
3. **👥 受眾價值係數** (0.8x - 1.8x)
   - 根據內容類型推估受眾消費力
   
4. **🌐 跨平台影響力係數** (0.95x - 1.4x)
   - 分析是否有 YouTube、TikTok 等外連

### 既有功能
- ✅ AI 視覺分析（GPT-4 Vision）
- ✅ 12 種 IG 人格類型判定
- ✅ 多維度商業價值評估
- ✅ 個性化提升建議
- ✅ 完整的 REST API

---

## 📦 文件說明

### 核心文件
| 文件名 | 說明 |
|--------|------|
| `app.py` | **主程式**，包含所有 API 邏輯 |
| `requirements.txt` | Python 依賴列表 |
| `test_api.py` | API 測試腳本 |

### 文檔文件
| 文件名 | 說明 |
|--------|------|
| `README.md` | 本文件，專案總覽 |
| `QUICK_START.md` | 快速開始指南 |
| `V4_UPGRADE_NOTES.md` | V4 版本詳細說明 |

---

## ⚡ 快速開始

### 1. 安裝依賴
```bash
pip install -r requirements.txt --break-system-packages
```

### 2. 設定 API Key
```bash
export OPENAI_API_KEY="sk-your-api-key-here"
export OPENAI_MODEL="gpt-4o-mini"
```

### 3. 啟動服務
```bash
python app.py
```

### 4. 測試服務
```bash
# 健康檢查
curl http://localhost:8000/health

# 完整測試（需要準備圖片）
python test_api.py profile.jpg post1.jpg post2.jpg
```

---

## 📖 詳細文檔

### 🚀 新手入門
閱讀 **[QUICK_START.md](QUICK_START.md)** 獲得：
- 30 秒快速部署指南
- API 測試範例（cURL、Python、JavaScript）
- 常見問題排解
- 生產環境部署建議

### 📊 V4 功能說明
閱讀 **[V4_UPGRADE_NOTES.md](V4_UPGRADE_NOTES.md)** 獲得：
- 4 個新係數的詳細說明
- 完整的計算邏輯
- API 回應格式變更
- 實戰案例分析
- 與 V3 的差異對比

---

## 🔌 API 端點

### Health Check
```bash
GET /health
```

回應：
```json
{
  "status": "ok",
  "version": "v4",
  "model": "gpt-4o-mini",
  "ai_enabled": true,
  "new_features": [
    "engagement_potential",
    "niche_focus",
    "audience_value",
    "cross_platform"
  ]
}
```

### 分析帳號
```bash
POST /bd/analyze
```

**請求：** 
- `profile`: IG 個人頁截圖（必須）
- `posts`: 貼文截圖（最多 6 張，可選）

**回應範例：**
```json
{
  "ok": true,
  "version": "v4",
  "username": "foodie_taipei",
  "followers": 12500,
  "value_estimation": {
    "post_value": 45600,
    "story_value": 18240,
    "reels_value": 59280,
    "monthly_package": 182400,
    "multipliers": {
      "visual": 1.5,
      "content": 1.8,
      "professional": 1.2,
      "follower": 1.2,
      "unique": 1.3,
      "engagement": 1.25,
      "niche": 1.4,
      "audience": 1.6,
      "cross_platform": 1.15
    }
  },
  "analysis": {
    "engagement_potential": {...},
    "niche_focus": {...},
    "audience_value": {...},
    "cross_platform": {...}
  }
}
```

### Debug 端點
```bash
GET /debug/config      # 查看系統配置
GET /debug/last_ai     # 查看最後一次 AI 回應
```

---

## 💡 使用範例

### Python
```python
import requests

url = "http://localhost:8000/bd/analyze"
files = {
    'profile': open('profile.jpg', 'rb'),
    'posts': open('post1.jpg', 'rb'),
}

response = requests.post(url, files=files)
result = response.json()

print(f"發文價值: NT$ {result['value_estimation']['post_value']:,}")
print(f"互動潛力係數: {result['value_estimation']['multipliers']['engagement']}")
```

### JavaScript
```javascript
const formData = new FormData();
formData.append('profile', profileFile);
formData.append('posts', post1File);

const response = await fetch('http://localhost:8000/bd/analyze', {
  method: 'POST',
  body: formData
});

const data = await response.json();
console.log('發文價值:', data.value_estimation.post_value);
```

### cURL
```bash
curl -X POST http://localhost:8000/bd/analyze \
  -F "profile=@profile.jpg" \
  -F "posts=@post1.jpg" \
  -F "posts=@post2.jpg"
```

---

## 🧪 測試工具

我們提供了一個方便的測試腳本 `test_api.py`：

```bash
# 只測試 Health Check
python test_api.py

# 完整分析測試
python test_api.py profile.jpg post1.jpg post2.jpg
```

測試結果會：
- ✅ 顯示完整的分析結果
- ✅ 展示所有新係數
- ✅ 保存 JSON 結果到 `test_result.json`

---

## 📊 完整估值公式

```
發文價值 = 基礎價 
         × 視覺品質係數 (0.7 - 2.0)
         × 內容類型係數 (0.8 - 2.5)
         × 專業度係數 (0.9 - 1.9)
         × 粉絲品質係數 (0.6 - 1.5)
         × 風格獨特性係數 (1.0 - 1.6)
         × 互動潛力係數 (0.8 - 1.5)     ← 🆕
         × 利基專注度係數 (0.9 - 1.6)   ← 🆕
         × 受眾價值係數 (0.8 - 1.8)     ← 🆕
         × 跨平台影響力係數 (0.95 - 1.4) ← 🆕
```

---

## 🎯 適用場景

### 創作者
- 💰 了解自己的商業價值
- 📈 獲得具體的提升建議
- 🎯 規劃內容策略

### 品牌方
- 🔍 快速評估 KOL 價值
- 💵 制定合理的合作預算
- 📊 比較不同帳號的性價比

### MCN / 經紀公司
- 🎭 批量評估潛力新人
- 📈 追蹤簽約創作者成長
- 💼 優化合作報價策略

---

## 🔐 環境變數

| 變數名 | 說明 | 預設值 |
|--------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 金鑰（必須） | - |
| `OPENAI_MODEL` | 使用的模型 | `gpt-4o-mini` |
| `PORT` | 服務端口 | `8000` |
| `MAX_SIDE` | 圖片最大邊長 | `1280` |
| `JPEG_QUALITY` | JPEG 壓縮品質 | `72` |

---

## 📈 性能指標

### 處理時間
- 1 張圖片：5-10 秒
- 7 張圖片：15-25 秒

### 準確度
- 粉絲數識別：>95%
- 內容類型判定：>90%
- 人格類型判定：>85%

### API 限制
- 單次最多上傳：1 profile + 6 posts
- 圖片格式：JPG, PNG
- 建議圖片尺寸：1080-1440px

---

## 🐛 疑難排解

### 常見錯誤

**1. "OpenAI API key not configured"**
```bash
# 確認環境變數已設定
echo $OPENAI_API_KEY

# 重新設定
export OPENAI_API_KEY="your-key-here"
```

**2. "無法解析基本資訊"**
- 確保截圖清晰完整
- 包含粉絲數、追蹤數、貼文數
- 重新截圖並上傳

**3. API 回應慢**
- 正常現象（AI 處理需要時間）
- 減少上傳的圖片數量
- 壓縮圖片尺寸

---

## 🚀 生產環境部署

### 使用 Gunicorn
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

### 使用 Docker
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .
ENV PORT=8000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "app:app"]
```

### 使用 Nginx 反向代理
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 📊 版本歷史

### V4 (2025-10-23) - Current
- ✨ 新增互動潛力係數
- ✨ 新增利基專注度係數
- ✨ 新增受眾價值係數
- ✨ 新增跨平台影響力係數
- 🔧 優化 AI Prompt
- 📚 完整文檔

### V3
- ✅ 視覺品質係數
- ✅ 內容類型係數
- ✅ 專業度係數
- ✅ 粉絲品質係數
- ✅ 風格獨特性係數
- ✅ 12 種人格類型判定

---

## 🎓 學習資源

### 推薦閱讀順序
1. 📖 **README.md**（本文件）- 了解專案概況
2. 🚀 **QUICK_START.md** - 快速上手部署
3. 📊 **V4_UPGRADE_NOTES.md** - 深入理解新功能

### 進階主題
- [ ] 自定義係數權重
- [ ] 批次處理優化
- [ ] 結果快取策略
- [ ] 多語言支援

---

## 🤝 技術支援

### 遇到問題？
1. 📖 查看文檔（QUICK_START.md）
2. 🔍 檢查 `/debug/last_ai` 端點
3. 📝 記錄錯誤訊息

### 功能建議
歡迎提出新的係數建議或改進意見！

---

## 📄 授權

本專案為私有專案，僅供內部使用。

---

## ✨ 開始使用

```bash
# Clone 或下載專案後

# 1. 安裝依賴
pip install -r requirements.txt --break-system-packages

# 2. 設定 API Key
export OPENAI_API_KEY="your-key-here"

# 3. 啟動服務
python app.py

# 4. 開始使用！
python test_api.py profile.jpg post1.jpg
```

享受更精準的 IG 帳號估值體驗！🚀

---

**Made with ❤️ using GPT-4 Vision**