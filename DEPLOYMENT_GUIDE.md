# Firebase 登入整合 - 部署與測試指南

## 📋 部署前檢查清單

### 1. Render 環境變數設定

請確認以下環境變數已在 Render 上設定：

#### 必需變數
- `FIREBASE_SERVICE_ACCOUNT`: Firebase 服務帳號 JSON（完整 JSON 字串）
- `DATABASE_URL`: 資料庫連線字串（例如：`postgresql://user:pass@host:5432/dbname`）
- `JWT_SECRET`: JWT 簽章密鑰（建議使用長隨機字串）
- `APP_BASE_URL`: 應用程式基礎 URL（例如：`https://socialavatar.onrender.com`）

#### 可選變數（用於 OAuth，目前使用 Firebase）
- `AUTH_SUCCESS_URL`: 登入成功後跳轉 URL（預設：`/static/landing.html`）
- `AUTH_FAILURE_URL`: 登入失敗後跳轉 URL（預設：`/static/landing.html`）

#### 其他現有變數
- `OPENAI_API_KEY`: OpenAI API 金鑰
- `OPENAI_MODEL`: OpenAI 模型名稱
- `PORT`: 應用程式端口（Render 會自動設定）

### 2. Firebase 服務帳號設定

1. 前往 [Firebase Console](https://console.firebase.google.com)
2. 選擇專案：`social-avatar-d13c8`
3. 進入 **Settings** → **Service accounts**
4. 點擊 **Generate new private key**
5. 下載 JSON 檔案
6. 將整個 JSON 內容複製到 Render 的 `FIREBASE_SERVICE_ACCOUNT` 環境變數

**注意**：JSON 需要是單行格式，或使用 `\n` 表示換行。

### 3. 資料庫設定

確認資料庫已建立並包含以下表格：
- `users`: 使用者資料表
- `analysis_results`: 分析結果表

如果資料庫尚未初始化，應用程式會在啟動時自動建立表格。

## 🧪 測試步驟

### 本地測試（可選）

1. **設定本地環境變數**
   ```bash
   export FIREBASE_SERVICE_ACCOUNT='{"type":"service_account",...}'
   export DATABASE_URL='sqlite:///data/app.db'
   export JWT_SECRET='your-secret-key'
   export APP_BASE_URL='http://localhost:5000'
   ```

2. **啟動應用程式**
   ```bash
   python app.py
   ```

3. **測試登入流程**
   - 開啟 `http://localhost:5000/static/landing.html`
   - 點擊 Google 或 Facebook 登入
   - 檢查瀏覽器 Console 是否有錯誤
   - 檢查 `localStorage` 是否有 `auth_token`

### Render 部署測試

1. **確認部署成功**
   - 檢查 Render Dashboard 中的部署狀態
   - 確認沒有錯誤訊息

2. **測試健康檢查端點**
   ```bash
   curl https://your-app.onrender.com/health
   ```

3. **測試登入流程**
   - 開啟 `https://your-app.onrender.com/static/landing.html`
   - 點擊 Google 或 Facebook 登入
   - 檢查瀏覽器 Console（F12）：
     - 應該看到 `[DEBUG] Getting Firebase ID token...`
     - 應該看到 `[DEBUG] ✅ Backend login successful`
     - 應該看到 `[DEBUG] JWT token saved to localStorage`

4. **測試分析流程**
   - 登入後上傳 IG 截圖
   - 檢查分析結果是否正確儲存
   - 檢查資料庫中 `analysis_results` 表的 `user_id` 欄位是否有值

5. **測試登出**
   - 點擊登出按鈕
   - 檢查 `localStorage` 中的 `auth_token` 是否被清除

## 🔍 除錯指南

### 問題：Firebase 登入成功但後端登入失敗

**檢查項目**：
1. `FIREBASE_SERVICE_ACCOUNT` 環境變數是否正確設定
2. Firebase 服務帳號 JSON 格式是否正確
3. Render 日誌中是否有錯誤訊息

**解決方法**：
```bash
# 檢查 Render 日誌
# 在 Render Dashboard → Logs 查看錯誤訊息
```

### 問題：JWT token 未儲存

**檢查項目**：
1. 瀏覽器 Console 是否有錯誤
2. `localStorage` 是否被瀏覽器阻擋
3. 後端 `/api/auth/firebase-login` 是否回傳 `token`

**解決方法**：
- 檢查瀏覽器 Console 的錯誤訊息
- 確認後端回應格式：`{"ok": true, "token": "...", "user": {...}}`

### 問題：分析結果未關聯到用戶

**檢查項目**：
1. `upload.html` 是否正確帶上 `Authorization` header
2. 後端 `/bd/analyze` 是否正確讀取 token
3. 資料庫中 `analysis_results.user_id` 是否有值

**解決方法**：
- 檢查 Network 標籤中 `/bd/analyze` 請求的 Headers
- 確認 `Authorization: Bearer <token>` 存在
- 檢查後端日誌中的 `[分析]` 訊息

## 📝 API 端點說明

### POST /api/auth/firebase-login

**請求**：
```json
{
  "id_token": "firebase-id-token"
}
```

**回應**：
```json
{
  "ok": true,
  "token": "jwt-token",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "username": "user123",
    ...
  },
  "new_user": false
}
```

### POST /bd/analyze

**請求 Headers**：
```
Authorization: Bearer <jwt-token>
Content-Type: multipart/form-data
```

**請求 Body**：
- `profile`: 圖片檔案
- `posts`: 圖片檔案（可選，最多 6 張）

**回應**：
```json
{
  "ok": true,
  "username": "...",
  "user_id": 1,
  ...
}
```

## ✅ 驗證清單

- [ ] Firebase 服務帳號已設定
- [ ] 所有環境變數已設定
- [ ] 資料庫連線正常
- [ ] 應用程式部署成功
- [ ] 登入流程正常運作
- [ ] JWT token 正確儲存
- [ ] 分析結果正確關聯到用戶
- [ ] 登出功能正常

## 🚀 下一步

1. 監控 Render 日誌，確認沒有錯誤
2. 測試多個用戶登入和分析流程
3. 確認資料庫中的資料正確儲存
4. 考慮加入更多錯誤處理和用戶提示

