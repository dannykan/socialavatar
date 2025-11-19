# Render 部署檢查清單

## 📝 部署前檢查

### 1. 環境變數設定（Render Dashboard → Environment）

#### ✅ 必需變數

- [ ] **FIREBASE_SERVICE_ACCOUNT**
  - 格式：完整的 JSON 字串（單行）
  - 來源：Firebase Console → Settings → Service accounts → Generate new private key
  - 驗證：使用 `check_render_config.py` 驗證格式

- [ ] **DATABASE_URL**
  - 格式：`postgresql://user:password@hostname:5432/dbname`
  - 來源：Render Dashboard → Database → Internal Database URL
  - 注意：如果使用外部資料庫，確保格式正確

- [ ] **JWT_SECRET**
  - 格式：至少 32 個字符的隨機字串
  - 生成：`openssl rand -hex 32`
  - 注意：不要使用預設值 `dev-secret-change-me`

- [ ] **APP_BASE_URL**
  - 格式：`https://your-app-name.onrender.com`
  - 注意：不要包含尾隨斜線

#### ⚠️ 可選變數（建議設定）

- [ ] **OPENAI_API_KEY** - OpenAI API 金鑰
- [ ] **OPENAI_MODEL** - 模型名稱（預設：`gpt-4o`）
- [ ] **AUTH_SUCCESS_URL** - 登入成功後跳轉（預設：`/static/upload.html`）
- [ ] **AUTH_FAILURE_URL** - 登入失敗後跳轉（預設：`/static/landing.html`）

### 2. 代碼檢查

- [ ] 所有修改已提交到 GitHub
- [ ] `requirements.txt` 包含所有依賴
- [ ] 沒有語法錯誤
- [ ] 本地測試通過（可選）

### 3. Render 服務設定

- [ ] 服務連接到正確的 GitHub 倉庫
- [ ] 分支設定正確（通常是 `main`）
- [ ] 自動部署已啟用
- [ ] Build Command: `pip install -r requirements.txt`（或留空，Render 會自動執行）
- [ ] Start Command: `gunicorn app:app`（或留空，Render 會自動偵測）

## 🚀 部署步驟

### 1. 觸發部署

- 方式 1：推送到 GitHub（如果自動部署已啟用）
- 方式 2：Render Dashboard → Manual Deploy → Deploy latest commit

### 2. 監控部署過程

在 Render Dashboard → Logs 查看：

**正常啟動應看到**：
```
[DB] ✅ 資料庫初始化完成
[Firebase] ✅ 初始化成功
[初始化] ✅ AI 分析器初始化成功
```

**如果有錯誤**：
- 查看完整錯誤訊息
- 參考 `render_troubleshooting.md` 排查

### 3. 驗證部署

#### 步驟 1: 健康檢查
```bash
curl https://your-app.onrender.com/health
```

**預期回應**：
```json
{
  "status": "ok",
  "version": "v5",
  "model": "gpt-4o",
  "ai_enabled": true
}
```

#### 步驟 2: 認證狀態檢查
```bash
curl https://your-app.onrender.com/debug/auth-status
```

**預期回應**：
```json
{
  "firebase_configured": true,
  "firebase_initialized": true,
  "database_configured": true,
  "database_connected": true,
  "jwt_secret_set": true,
  "app_base_url": "https://your-app.onrender.com",
  "database_type": "postgresql"
}
```

#### 步驟 3: 前端測試

1. 開啟 `https://your-app.onrender.com/static/landing.html`
2. 打開瀏覽器開發者工具（F12）
3. 點擊「使用 Google 登入」或「使用 Facebook 登入」
4. 檢查 Console 是否有錯誤
5. 檢查 Application → Local Storage 是否有 `auth_token`

## ✅ 部署後驗證

### 功能測試

- [ ] **登入流程**
  - [ ] Google 登入正常
  - [ ] Facebook 登入正常
  - [ ] JWT token 正確儲存
  - [ ] 後端成功驗證 Firebase token

- [ ] **分析流程**
  - [ ] 可以上傳截圖
  - [ ] 分析請求帶上 JWT token
  - [ ] 分析結果正確儲存
  - [ ] 分析結果關聯到用戶（`user_id` 有值）

- [ ] **登出流程**
  - [ ] 登出按鈕正常運作
  - [ ] Token 正確清除

### 資料庫驗證

使用 Render 的資料庫管理介面或 psql：

```sql
-- 檢查用戶表
SELECT COUNT(*) FROM users;

-- 檢查分析結果表
SELECT COUNT(*) FROM analysis_results;

-- 檢查用戶關聯
SELECT 
  COUNT(*) as total,
  COUNT(user_id) as with_user,
  COUNT(*) - COUNT(user_id) as without_user
FROM analysis_results;
```

**預期結果**：
- `with_user` 應該等於或接近 `total`（新分析都應該有關聯）

## 🐛 常見問題快速修復

### Firebase 初始化失敗

**檢查**：
1. `FIREBASE_SERVICE_ACCOUNT` 是否為有效的 JSON
2. JSON 是否為單行格式
3. 是否有特殊字符未轉義

**修復**：
```bash
# 使用 Python 驗證 JSON
python -c "import json, os; json.loads(os.getenv('FIREBASE_SERVICE_ACCOUNT'))"
```

### 資料庫連線失敗

**檢查**：
1. `DATABASE_URL` 格式是否正確
2. 資料庫服務是否運行
3. 認證資訊是否正確

**修復**：
- 檢查 Render Dashboard → Database → Connection Pooling
- 確認使用 Internal Database URL（如果資料庫在同一專案）

### JWT Token 驗證失敗

**檢查**：
1. `JWT_SECRET` 是否足夠長（32+ 字符）
2. Token 是否過期
3. 前端是否正確傳遞 token

**修復**：
- 重新生成 `JWT_SECRET`：`openssl rand -hex 32`
- 確認前端正確設定 `Authorization` header

## 📊 監控建議

### 定期檢查

1. **Render 日誌**：每週檢查一次錯誤日誌
2. **資料庫**：確認分析結果正確儲存
3. **API 回應時間**：監控 `/bd/analyze` 端點效能

### 告警設定

建議在 Render 設定：
- 部署失敗通知
- 服務離線通知
- 錯誤率過高通知

## 📞 需要協助？

如果遇到問題：

1. 查看 `render_troubleshooting.md` 詳細排查指南
2. 檢查 Render 日誌中的完整錯誤訊息
3. 使用 `/debug/auth-status` 端點檢查配置狀態
4. 提供錯誤訊息和日誌截圖以便進一步協助

