# 本地測試管理員 Dashboard 指南

## 🚀 快速開始

### 方法 1: 使用環境變數（推薦）

```bash
# 1. 設定管理員 Email
export ADMIN_EMAILS=your-email@gmail.com

# 2. 啟動服務器
python3 app.py
```

### 方法 2: 使用 .env.local 檔案

1. 創建或編輯 `.env.local` 檔案：
```bash
ADMIN_EMAILS=your-email@gmail.com
```

2. 啟動服務器：
```bash
python3 app.py
```

**注意**：`.env.local` 檔案已被 `.gitignore` 忽略，不會被提交到 Git。

### 方法 3: 使用測試腳本

```bash
chmod +x test_admin_local.sh
./test_admin_local.sh
```

## 📋 測試步驟

### 1. 準備環境

確保已安裝所有依賴：
```bash
pip3 install -r requirements.txt
```

### 2. 設定管理員 Email

**重要**：使用你登入時使用的 Email（Gmail 或 Facebook 登入的 Email）

```bash
export ADMIN_EMAILS=your-email@gmail.com
```

或編輯 `.env.local`：
```
ADMIN_EMAILS=your-email@gmail.com
```

### 3. 啟動服務器

```bash
python3 app.py
```

服務器會在 `http://localhost:8000` 啟動。

### 4. 測試管理員 Dashboard

1. **登入系統**
   - 訪問 `http://localhost:8000/static/landing.html`
   - 使用**管理員 Email**登入（Gmail 或 Facebook）

2. **訪問管理員 Dashboard**
   - 訪問 `http://localhost:8000/static/admin-dashboard.html`
   - 應該能看到系統統計、用戶列表和分析記錄

3. **測試非管理員訪問**
   - 登出
   - 使用**非管理員 Email**登入
   - 訪問 `http://localhost:8000/static/admin-dashboard.html`
   - 應該顯示 "您沒有管理員權限" 錯誤

## 🧪 測試 API 端點

### 獲取 JWT Token

1. 登入後，在瀏覽器 Console 執行：
```javascript
localStorage.getItem('auth_token')
```

2. 複製 token 值

### 測試 API

```bash
# 設定 token
TOKEN="your-jwt-token-here"

# 測試統計 API
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/admin/stats

# 測試用戶列表 API
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/admin/users?page=1&per_page=10"

# 測試分析記錄 API
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/admin/analyses?page=1&per_page=10"
```

## 🐛 常見問題

### 問題 1: 顯示 "admin_access_required" 錯誤

**原因**：
- Email 未加入 `ADMIN_EMAILS`
- Email 與登入時使用的 Email 不一致

**解決方法**：
1. 確認 `ADMIN_EMAILS` 環境變數已設定
2. 確認 Email 與登入時使用的 Email 完全一致（大小寫不敏感）
3. 重新登入以獲取新的 JWT token

### 問題 2: 無法載入數據

**原因**：
- 本地數據庫沒有數據
- JWT token 無效或過期

**解決方法**：
1. 檢查數據庫是否有數據：
   ```bash
   sqlite3 data/results.db "SELECT COUNT(*) FROM users;"
   sqlite3 data/results.db "SELECT COUNT(*) FROM analysis_results;"
   ```

2. 重新登入以獲取新的 JWT token

3. 檢查瀏覽器 Console 是否有錯誤訊息

### 問題 3: 服務器無法啟動

**原因**：
- 缺少依賴套件
- 端口被占用

**解決方法**：
1. 安裝依賴：
   ```bash
   pip3 install -r requirements.txt
   ```

2. 檢查端口：
   ```bash
   lsof -i :8000
   ```

3. 使用其他端口：
   ```bash
   PORT=8001 python3 app.py
   ```

## 📊 檢查數據庫

### 查看用戶數據

```bash
sqlite3 data/results.db "SELECT id, email, username, created_at FROM users LIMIT 10;"
```

### 查看分析記錄

```bash
sqlite3 data/results.db "SELECT id, username, user_id, created_at FROM analysis_results LIMIT 10;"
```

### 查看特定用戶的分析

```bash
# 先找到用戶 ID
sqlite3 data/results.db "SELECT id, email FROM users WHERE email='your-email@gmail.com';"

# 查看該用戶的分析記錄（假設 user_id=1）
sqlite3 data/results.db "SELECT * FROM analysis_results WHERE user_id=1;"
```

## ✅ 測試檢查清單

- [ ] 環境變數 `ADMIN_EMAILS` 已設定
- [ ] 服務器成功啟動（`http://localhost:8000`）
- [ ] 使用管理員 Email 登入成功
- [ ] 可以訪問 `/static/admin-dashboard.html`
- [ ] 統計卡片顯示正確數據
- [ ] 用戶列表可以正常載入和分頁
- [ ] 分析記錄可以正常載入和分頁
- [ ] 非管理員訪問被正確拒絕
- [ ] API 端點返回正確的 JSON 數據

## 🎯 下一步

測試完成後，可以：
1. 部署到 Render
2. 在 Render 環境變數中設定 `ADMIN_EMAILS`
3. 在生產環境測試管理員 Dashboard

