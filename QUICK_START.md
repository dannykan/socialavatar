# 🚀 App V4 快速開始指南

## 📋 前置需求

### 必要項目
- ✅ Python 3.8+
- ✅ OpenAI API Key（支援 GPT-4o-mini）
- ✅ 終端機/命令提示字元訪問權限

### 可選項目
- 📱 Postman 或類似工具（用於測試 API）
- 🌐 前端頁面（用於圖形化介面）

---

## ⚡ 30 秒快速部署

### Step 1: 安裝依賴
```bash
pip install flask flask-cors pillow requests --break-system-packages
```

### Step 2: 設定環境變數
```bash
# Linux / macOS
export OPENAI_API_KEY="sk-your-api-key-here"
export OPENAI_MODEL="gpt-4o-mini"

# Windows (PowerShell)
$env:OPENAI_API_KEY="sk-your-api-key-here"
$env:OPENAI_MODEL="gpt-4o-mini"

# Windows (CMD)
set OPENAI_API_KEY=sk-your-api-key-here
set OPENAI_MODEL=gpt-4o-mini
```

### Step 3: 啟動服務
```bash
python app.py
```

### Step 4: 驗證部署
打開瀏覽器訪問：
```
http://localhost:8000/health
```

看到以下回應即表示成功：
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

---

## 🧪 測試 API

### 使用 cURL
```bash
curl -X POST http://localhost:8000/bd/analyze \
  -F "profile=@profile_screenshot.jpg" \
  -F "posts=@post1.jpg" \
  -F "posts=@post2.jpg" \
  -F "posts=@post3.jpg"
```

### 使用 Python
```python
import requests

url = "http://localhost:8000/bd/analyze"

files = {
    'profile': open('profile_screenshot.jpg', 'rb'),
    'posts': open('post1.jpg', 'rb'),
}

response = requests.post(url, files=files)
result = response.json()

if result['ok']:
    print(f"帳號: {result['username']}")
    print(f"粉絲: {result['followers']:,}")
    print(f"發文價值: NT$ {result['value_estimation']['post_value']:,}")
    print(f"互動潛力係數: {result['value_estimation']['multipliers']['engagement']}")
else:
    print(f"錯誤: {result['error']}")
```

### 使用 JavaScript (Fetch)
```javascript
const formData = new FormData();
formData.append('profile', profileFile);
formData.append('posts', post1File);
formData.append('posts', post2File);

fetch('http://localhost:8000/bd/analyze', {
  method: 'POST',
  body: formData
})
.then(res => res.json())
.then(data => {
  if (data.ok) {
    console.log('發文價值:', data.value_estimation.post_value);
    console.log('新係數:', {
      engagement: data.value_estimation.multipliers.engagement,
      niche: data.value_estimation.multipliers.niche,
      audience: data.value_estimation.multipliers.audience,
      cross_platform: data.value_estimation.multipliers.cross_platform
    });
  }
});
```

---

## 📸 測試圖片準備

### Profile 截圖要求
✅ **必須包含：**
- 用戶名
- 粉絲數、追蹤數、貼文數
- Bio 資訊
- 九宮格前 9 張貼文

✅ **推薦尺寸：**
- 寬度：1080-1440px
- 高度：1920-2560px
- 格式：JPG/PNG

### Posts 截圖要求
✅ **最多 6 張**
✅ **推薦尺寸：** 1080x1080px (正方形)
✅ **格式：** JPG/PNG
✅ **內容：** 代表性的貼文，展現帳號風格

---

## 🐛 常見問題排解

### Q1: "OpenAI API key not configured"
**原因：** 環境變數未設定
**解決：**
```bash
# 檢查環境變數
echo $OPENAI_API_KEY  # Linux/macOS
echo %OPENAI_API_KEY%  # Windows

# 重新設定
export OPENAI_API_KEY="your-key-here"
```

### Q2: "無法解析基本資訊"
**原因：** Profile 截圖不清晰或格式錯誤
**解決：**
- ✅ 確保截圖包含完整的個人頁資訊
- ✅ 檢查圖片是否清晰可讀
- ✅ 嘗試重新截圖並上傳

### Q3: API 回應慢
**原因：** GPT-4 Vision 處理需要時間
**預期時間：**
- 1 張圖片：5-10 秒
- 7 張圖片（1 profile + 6 posts）：15-25 秒

**優化建議：**
- ✅ 減少上傳的 posts 數量（3-4 張即可）
- ✅ 壓縮圖片尺寸（1280px 已足夠）

### Q4: 係數計算似乎不準確
**可能原因：**
- AI 判斷基於視覺內容，可能與主觀感受不同
- Bio 文字如果過於簡短，可能影響判斷

**改善方法：**
- ✅ 確保 Bio 資訊完整
- ✅ 上傳更多代表性貼文
- ✅ 檢查 `/debug/last_ai` 查看 AI 的原始分析

---

## 🔍 Debug 端點

### 查看 AI 原始回應
```bash
curl http://localhost:8000/debug/last_ai
```

### 查看系統配置
```bash
curl http://localhost:8000/debug/config
```

### Health Check
```bash
curl http://localhost:8000/health
```

---

## 🎯 實戰測試場景

### 場景 1: 美妝博主
**預期係數：**
- engagement: 1.2-1.4（高互動型）
- niche: 1.4-1.6（垂直領域）
- audience: 1.6-1.8（高消費力）
- cross_platform: 1.1-1.3（通常有 YouTube）

### 場景 2: 生活日常
**預期係數：**
- engagement: 0.9-1.1（中等互動）
- niche: 0.9-1.1（主題分散）
- audience: 0.9-1.1（一般受眾）
- cross_platform: 0.95-1.05（較少外連）

### 場景 3: 專業攝影師
**預期係數：**
- engagement: 0.8-1.0（作品展示型）
- niche: 1.4-1.6（高度專注）
- audience: 0.9-1.0（藝術受眾）
- cross_platform: 1.1-1.3（通常有作品網站）

---

## 📊 性能優化建議

### 1. 圖片預處理
```python
# 在上傳前先壓縮圖片
from PIL import Image

def compress_image(image_path, max_size=1280, quality=75):
    img = Image.open(image_path)
    
    # 調整尺寸
    w, h = img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    # 轉換為 RGB（去除透明通道）
    if img.mode in ('RGBA', 'LA', 'P'):
        bg = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        bg.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
        img = bg
    
    # 保存
    img.save('compressed_' + image_path, 'JPEG', quality=quality)
```

### 2. 批次處理
如果要分析多個帳號，建議：
- ✅ 設置請求間隔（避免 API rate limit）
- ✅ 使用異步請求（`aiohttp`）
- ✅ 實作錯誤重試機制

### 3. 結果快取
```python
import json
import hashlib

def cache_result(username, result):
    cache_key = hashlib.md5(username.encode()).hexdigest()
    with open(f'cache/{cache_key}.json', 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

def get_cached_result(username):
    cache_key = hashlib.md5(username.encode()).hexdigest()
    try:
        with open(f'cache/{cache_key}.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
```

---

## 🔐 生產環境部署

### 1. 環境變數管理
使用 `.env` 文件：
```bash
# .env
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini
PORT=8000
MAX_SIDE=1280
JPEG_QUALITY=72
```

安裝 `python-dotenv`：
```bash
pip install python-dotenv
```

在 `app.py` 頂部添加：
```python
from dotenv import load_dotenv
load_dotenv()
```

### 2. 使用 Gunicorn（推薦）
```bash
pip install gunicorn

# 啟動（4 workers）
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

### 3. Docker 部署
```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py .
COPY static/ static/

ENV PORT=8000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "app:app"]
```

---

## 📞 支援與反饋

### 遇到問題？
1. 📖 先查看 `V4_UPGRADE_NOTES.md`
2. 🔍 檢查 `/debug/last_ai` 端點
3. 📝 記錄錯誤訊息和輸入圖片

### 功能建議
歡迎提出新的係數建議或改進意見！

---

## ✅ 部署檢查清單

在正式上線前，請確認：

- [ ] OpenAI API Key 已設定且有效
- [ ] Health check 返回正常
- [ ] 至少測試過 3 種不同類型的帳號
- [ ] API 回應時間在可接受範圍內（<30 秒）
- [ ] 錯誤處理機制正常運作
- [ ] 已設定適當的 CORS 政策
- [ ] 生產環境使用 Gunicorn 或類似 WSGI server
- [ ] 已實作請求日誌記錄
- [ ] 已設置監控和告警機制

---

## 🎉 開始使用

現在你已經準備好使用 **App V4** 了！

```bash
# 一鍵啟動
export OPENAI_API_KEY="your-key"
python app.py
```

享受更精準的 IG 帳號估值體驗！🚀
