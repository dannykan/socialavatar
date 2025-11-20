# 🚀 立即部署指南

## 📋 部署前最後檢查

### 1. 確認所有更改已提交

```bash
# 檢查未提交的更改
git status

# 如果有更改，提交它們
git add .
git commit -m "feat: 添加管理員 Dashboard 和性能優化

- 添加管理員 Dashboard 功能（查看、編輯、刪除）
- 優化數據庫查詢性能（避免 N+1 查詢）
- 添加管理員操作日誌
- 更新部署文檔和檢查清單"
```

### 2. 推送到 GitHub

```bash
git push origin main
# 或
git push origin master
```

---

## 🔧 Render 部署步驟

### 步驟 1: 確認 Render 服務設定

1. 登入 [Render Dashboard](https://dashboard.render.com)
2. 選擇你的服務 `socialavatar`
3. 進入 **Settings** 標籤

### 步驟 2: 檢查環境變數

確認以下環境變數已設定：

#### 必需變數
- [ ] `OPENAI_API_KEY` - 你的 OpenAI API 金鑰
- [ ] `DATABASE_URL` - PostgreSQL 連線字串（Render 會自動提供）
- [ ] `JWT_SECRET` - 長隨機字串（例如：使用 `openssl rand -hex 32` 生成）
- [ ] `FIREBASE_SERVICE_ACCOUNT` - Firebase 服務帳號 JSON（完整 JSON 字串）
- [ ] `ADMIN_EMAILS` - 管理員 Email（例如：`dannytjkan@gmail.com`）

#### 可選變數（有預設值）
- [ ] `OPENAI_MODEL` - 建議設定為 `gpt-4o`
- [ ] `APP_BASE_URL` - 你的 Render URL（例如：`https://socialavatar.onrender.com`）
- [ ] `JWT_EXPIRES_MINUTES` - 建議設定為 `1440`（24小時）

### 步驟 3: 生成 JWT_SECRET（如果還沒有）

```bash
# 在本地終端運行
openssl rand -hex 32
```

將生成的字符串複製到 Render 的 `JWT_SECRET` 環境變數。

### 步驟 4: 設定 Firebase 服務帳號

1. 前往 [Firebase Console](https://console.firebase.google.com)
2. 選擇專案：`social-avatar-d13c8`
3. 進入 **Settings** → **Service accounts**
4. 點擊 **Generate new private key**
5. 下載 JSON 檔案
6. 將整個 JSON 內容複製到 Render 的 `FIREBASE_SERVICE_ACCOUNT` 環境變數

**重要**：JSON 需要是單行格式。可以使用以下命令轉換：

```bash
# 在本地終端運行（假設 JSON 檔案名為 firebase-key.json）
cat firebase-key.json | jq -c
```

### 步驟 5: 確認 Build 和 Start 命令

在 Render Dashboard → Settings → Build & Deploy：

**Build Command**:
```bash
pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt
```

**Start Command**:
```bash
gunicorn app:app --bind 0.0.0.0:$PORT --threads 1 --timeout 120
```

**Health Check Path**: `/health`

### 步驟 6: 觸發部署

1. 如果自動部署已啟用，推送代碼後會自動部署
2. 或手動點擊 **Manual Deploy** → **Deploy latest commit**

---

## 🧪 部署後測試

### 1. 健康檢查

```bash
curl https://your-app.onrender.com/health
```

預期回應：
```json
{
  "status": "ok",
  "version": "v5",
  "ai_enabled": true,
  "model": "gpt-4o"
}
```

### 2. 測試認證

1. 訪問 `https://your-app.onrender.com/static/landing.html`
2. 使用 Google/Facebook 登入
3. 檢查瀏覽器 Console（F12）確認沒有錯誤

### 3. 測試管理員 Dashboard

1. 使用管理員 Email 登入
2. 訪問 `https://your-app.onrender.com/static/admin-dashboard.html`
3. 測試所有功能：
   - 查看統計
   - 查看用戶列表
   - 查看分析記錄
   - 編輯分析記錄
   - 刪除記錄/用戶

---

## 🔍 如果部署失敗

### 檢查 Render 日誌

1. 在 Render Dashboard → Logs 查看錯誤訊息
2. 常見問題：
   - **環境變數未設定**：檢查所有必需變數
   - **依賴安裝失敗**：檢查 `requirements.txt`
   - **資料庫連線失敗**：檢查 `DATABASE_URL`
   - **Firebase 設定錯誤**：檢查 `FIREBASE_SERVICE_ACCOUNT` JSON 格式

### 常見錯誤解決

**錯誤：`ModuleNotFoundError: No module named 'xxx'`**
- 解決：確認 `requirements.txt` 包含所有依賴

**錯誤：`Firebase not configured`**
- 解決：檢查 `FIREBASE_SERVICE_ACCOUNT` 環境變數格式

**錯誤：`Database connection failed`**
- 解決：確認 `DATABASE_URL` 正確，資料庫服務正在運行

---

## ✅ 部署完成檢查清單

- [ ] 所有代碼已推送到 GitHub
- [ ] 所有環境變數已設定
- [ ] Build 命令正確
- [ ] Start 命令正確
- [ ] 健康檢查通過
- [ ] 認證功能正常
- [ ] 管理員 Dashboard 正常
- [ ] 所有功能測試通過

---

## 📞 需要幫助？

如果遇到問題，請：
1. 檢查 Render 日誌
2. 查看 `DEPLOYMENT_CHECKLIST.md` 中的常見問題
3. 確認所有環境變數格式正確

---

**準備就緒！開始部署吧！** 🚀

