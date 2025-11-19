# Render 部署問題排查指南

## 🔍 快速診斷步驟

### 1. 檢查 Render 日誌

在 Render Dashboard → 你的服務 → Logs 查看：

**正常啟動日誌應包含**：
```
[DB] ✅ 資料庫初始化完成
[Firebase] ✅ 初始化成功
[初始化] ✅ AI 分析器初始化成功
```

**常見錯誤訊息**：
- `[Firebase] ❌ 初始化失敗`: Firebase 服務帳號設定錯誤
- `[DB] ❌ 初始化失敗`: 資料庫連線失敗
- `ModuleNotFoundError`: 依賴未安裝

### 2. 檢查環境變數格式

#### FIREBASE_SERVICE_ACCOUNT

**正確格式**（JSON 字串）：
```json
{"type":"service_account","project_id":"social-avatar-d13c8","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"...","client_id":"...","auth_uri":"...","token_uri":"...","auth_provider_x509_cert_url":"...","client_x509_cert_url":"..."}
```

**常見錯誤**：
- ❌ 多行格式（Render 環境變數不支援多行）
- ❌ 缺少引號
- ❌ JSON 格式錯誤（缺少逗號、引號等）

**解決方法**：
1. 將 JSON 檔案內容轉換為單行
2. 使用線上工具：https://jsonformatter.org/json-minify
3. 或使用 Python：
   ```python
   import json
   with open('service-account.json') as f:
       data = json.load(f)
   print(json.dumps(data))
   ```

#### DATABASE_URL

**PostgreSQL 格式**：
```
postgresql://user:password@hostname:5432/dbname
```

**常見錯誤**：
- ❌ 缺少 `postgresql://` 前綴
- ❌ 密碼包含特殊字符未編碼
- ❌ 端口號錯誤（應為 5432）

#### JWT_SECRET

**建議格式**：
- 至少 32 個字符的隨機字串
- 使用 `openssl rand -hex 32` 生成

**常見錯誤**：
- ❌ 使用預設值 `dev-secret-change-me`
- ❌ 太短（少於 16 字符）

### 3. 檢查 API 端點

#### 測試健康檢查
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

#### 測試 Firebase 登入（需要有效 token）
```bash
curl -X POST https://your-app.onrender.com/api/auth/firebase-login \
  -H "Content-Type: application/json" \
  -d '{"id_token":"your-firebase-token"}'
```

**成功回應**：
```json
{
  "ok": true,
  "token": "jwt-token-here",
  "user": {...},
  "new_user": false
}
```

**錯誤回應**：
```json
{
  "ok": false,
  "error": "firebase_not_configured"
}
```

## 🐛 常見問題與解決方案

### 問題 1: Firebase 初始化失敗

**錯誤訊息**：
```
[Firebase] ❌ 初始化失敗: Invalid JSON
```

**可能原因**：
1. JSON 格式錯誤
2. 環境變數包含換行符
3. 特殊字符未正確轉義

**解決步驟**：
1. 檢查 `FIREBASE_SERVICE_ACCOUNT` 是否為有效的 JSON
2. 確保是單行格式
3. 檢查 Render 環境變數設定頁面，確認沒有額外的引號或空格

**驗證方法**：
```python
import json
import os
try:
    data = json.loads(os.getenv('FIREBASE_SERVICE_ACCOUNT'))
    print("✅ JSON 格式正確")
except Exception as e:
    print(f"❌ JSON 格式錯誤: {e}")
```

### 問題 2: 資料庫連線失敗

**錯誤訊息**：
```
[DB] ❌ 初始化失敗: could not connect to server
```

**可能原因**：
1. `DATABASE_URL` 格式錯誤
2. 資料庫服務未啟動
3. 網路連線問題
4. 認證資訊錯誤

**解決步驟**：
1. 檢查 `DATABASE_URL` 格式
2. 確認 Render 資料庫服務正在運行
3. 檢查資料庫用戶名和密碼
4. 確認資料庫允許來自 Render 服務的連線

### 問題 3: JWT Token 驗證失敗

**錯誤訊息**：
```
AuthError: invalid_token
```

**可能原因**：
1. `JWT_SECRET` 在部署後改變
2. Token 已過期
3. Token 格式錯誤

**解決步驟**：
1. 確認 `JWT_SECRET` 在部署前後保持一致
2. 檢查 Token 是否在有效期內（預設 24 小時）
3. 確認前端正確傳遞 `Authorization: Bearer <token>` header

### 問題 4: 前端無法呼叫後端 API

**錯誤訊息**（瀏覽器 Console）：
```
[ERROR] Backend login failed: NetworkError
```

**可能原因**：
1. CORS 設定問題
2. API 端點路徑錯誤
3. Render 服務未正常運行

**解決步驟**：
1. 檢查 `APP_BASE_URL` 是否正確設定
2. 確認 Render 服務 URL 與 `APP_BASE_URL` 一致
3. 檢查瀏覽器 Network 標籤，查看實際請求 URL 和回應

### 問題 5: 分析結果未關聯到用戶

**症狀**：
- 分析完成但 `user_id` 為 `null`
- 資料庫中 `analysis_results.user_id` 為空

**可能原因**：
1. 前端未正確傳遞 JWT token
2. 後端未正確解析 token
3. Token 驗證失敗但未拋出錯誤

**排查步驟**：
1. 檢查瀏覽器 Network 標籤，確認 `/bd/analyze` 請求有 `Authorization` header
2. 檢查 Render 日誌，查看 `[分析]` 相關訊息
3. 確認 `current_user` 不為 `None`

## 🔧 除錯工具

### 使用檢查腳本

在本地運行（需要設定環境變數）：
```bash
python check_render_config.py
```

### 檢查 Render 日誌

1. 前往 Render Dashboard
2. 選擇你的服務
3. 點擊 "Logs" 標籤
4. 搜尋關鍵字：
   - `[Firebase]`: Firebase 相關訊息
   - `[DB]`: 資料庫相關訊息
   - `[分析]`: 分析流程訊息
   - `ERROR`: 所有錯誤訊息

### 測試 API 端點

使用 curl 或 Postman 測試：

```bash
# 健康檢查
curl https://your-app.onrender.com/health

# 檢查配置（如果實作了）
curl https://your-app.onrender.com/debug/config
```

## 📋 部署檢查清單

部署前確認：

- [ ] `FIREBASE_SERVICE_ACCOUNT` 已設定且格式正確
- [ ] `DATABASE_URL` 已設定且格式正確
- [ ] `JWT_SECRET` 已設定且足夠長（32+ 字符）
- [ ] `APP_BASE_URL` 已設定為 Render URL
- [ ] `OPENAI_API_KEY` 已設定
- [ ] 所有依賴已在 `requirements.txt` 中
- [ ] 代碼已推送到 GitHub
- [ ] Render 服務已連接到正確的 GitHub 分支

部署後確認：

- [ ] Render 部署成功（無錯誤）
- [ ] 健康檢查端點正常回應
- [ ] Firebase 初始化成功（查看日誌）
- [ ] 資料庫連線正常（查看日誌）
- [ ] 前端可以正常登入
- [ ] 分析功能正常運作
- [ ] 分析結果正確儲存到資料庫

## 🆘 需要協助？

如果以上步驟都無法解決問題，請提供：

1. Render 日誌中的錯誤訊息（完整錯誤堆疊）
2. 瀏覽器 Console 的錯誤訊息
3. Network 標籤中的請求/回應詳情
4. 環境變數設定（隱藏敏感資訊）

