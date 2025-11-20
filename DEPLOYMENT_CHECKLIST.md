# 🚀 部署檢查清單

## 📋 部署前準備

### 1. 環境變數檢查

#### 必需變數（必須設定）
- [ ] `OPENAI_API_KEY` - OpenAI API 金鑰
- [ ] `DATABASE_URL` - 資料庫連線字串
  - SQLite (本地): `sqlite:///data/results.db`
  - PostgreSQL (生產): `postgresql://user:pass@host:5432/dbname`
- [ ] `JWT_SECRET` - JWT 簽章密鑰（建議使用長隨機字串）
- [ ] `FIREBASE_SERVICE_ACCOUNT` - Firebase 服務帳號 JSON（完整 JSON 字串）
- [ ] `ADMIN_EMAILS` - 管理員 Email 列表（逗號分隔，例如：`email1@example.com,email2@example.com`）

#### 可選變數（有預設值）
- [ ] `OPENAI_MODEL` - OpenAI 模型（預設：`gpt-4o`）
- [ ] `APP_BASE_URL` - 應用程式基礎 URL（預設：`http://localhost:8000`）
- [ ] `PORT` - 服務端口（Render 會自動設定）
- [ ] `MAX_SIDE` - 圖片最大邊長（預設：`1280`）
- [ ] `JPEG_QUALITY` - JPEG 壓縮品質（預設：`72`）
- [ ] `JWT_EXPIRES_MINUTES` - JWT 過期時間（預設：`1440`，24小時）

### 2. Firebase 設定

1. 前往 [Firebase Console](https://console.firebase.google.com)
2. 選擇專案：`social-avatar-d13c8`
3. 進入 **Settings** → **Service accounts**
4. 點擊 **Generate new private key**
5. 下載 JSON 檔案
6. 將整個 JSON 內容複製到 Render 的 `FIREBASE_SERVICE_ACCOUNT` 環境變數

**注意**：
- JSON 需要是單行格式，或使用 `\n` 表示換行
- 確保 JSON 格式正確，沒有多餘的空格或換行

### 3. 資料庫設定

#### 本地開發（SQLite）
- 資料庫檔案會自動創建在 `data/results.db`
- 確保 `data/` 目錄存在且有寫入權限

#### 生產環境（PostgreSQL）
- 在 Render 創建 PostgreSQL 資料庫
- 複製連線字串到 `DATABASE_URL`
- 應用程式會在首次啟動時自動創建表格

### 4. 依賴檢查

確認 `requirements.txt` 包含所有必需套件：
- flask>=3.0.0
- flask-cors>=4.0.0
- pillow>=10.0.0
- requests>=2.31.0
- gunicorn>=21.0.0
- sqlalchemy>=2.0.21
- pyjwt>=2.8.0
- firebase-admin>=6.5.0
- python-dotenv>=1.0.0
- openai>=1.0.0

---

## 🔧 Render 部署設定

### 1. 服務設定

**Build Command**:
```bash
pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt
```

**Start Command**:
```bash
gunicorn app:app --bind 0.0.0.0:$PORT --threads 1 --timeout 120
```

**Health Check Path**: `/health`

### 2. 環境變數設定

在 Render Dashboard → Environment 中設定所有必需的環境變數。

### 3. 自動部署

- [ ] 確認 GitHub 倉庫已連接
- [ ] 確認自動部署已啟用
- [ ] 確認部署分支正確（通常是 `main` 或 `master`）

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

### 2. 認證測試

1. 訪問 `https://your-app.onrender.com/static/landing.html`
2. 點擊 Google 或 Facebook 登入
3. 檢查瀏覽器 Console（F12）：
   - 應該看到 `[Auth] ✅ JWT token 已獲取並儲存`
   - 檢查 `localStorage` 是否有 `auth_token`

### 3. 分析功能測試

1. 登入後訪問 `https://your-app.onrender.com/static/upload.html`
2. 上傳 IG 截圖
3. 確認分析結果正確顯示
4. 確認數據已保存到資料庫

### 4. 管理員 Dashboard 測試

1. 使用管理員 Email 登入
2. 訪問 `https://your-app.onrender.com/static/admin-dashboard.html`
3. 測試以下功能：
   - [ ] 查看系統統計
   - [ ] 查看用戶列表
   - [ ] 查看分析記錄列表
   - [ ] 編輯分析記錄的價值和報價
   - [ ] 刪除分析記錄
   - [ ] 刪除用戶

---

## 🔍 常見問題排查

### 問題 1: 應用程式無法啟動

**檢查項目**：
- [ ] 所有必需的環境變數已設定
- [ ] `requirements.txt` 包含所有依賴
- [ ] Python 版本正確（建議 3.10+）
- [ ] 檢查 Render 日誌中的錯誤訊息

### 問題 2: Firebase 登入失敗

**檢查項目**：
- [ ] `FIREBASE_SERVICE_ACCOUNT` 環境變數格式正確
- [ ] Firebase 專案設定正確
- [ ] 檢查 Render 日誌中的 Firebase 錯誤

### 問題 3: 資料庫連線失敗

**檢查項目**：
- [ ] `DATABASE_URL` 格式正確
- [ ] 資料庫服務正在運行
- [ ] 資料庫用戶權限正確
- [ ] 檢查 Render 日誌中的資料庫錯誤

### 問題 4: 管理員 Dashboard 無法訪問

**檢查項目**：
- [ ] `ADMIN_EMAILS` 環境變數已設定
- [ ] 登入的 Email 在 `ADMIN_EMAILS` 列表中
- [ ] JWT token 有效且未過期
- [ ] 檢查瀏覽器 Console 中的錯誤訊息

---

## 📊 性能優化建議

### 1. 資料庫優化

- [x] 已添加索引（`user_id`, `username_key`, `email`, `provider_id`）
- [x] 已優化查詢（使用 `joinedload` 避免 N+1 查詢）
- [x] 已優化批量查詢（用戶分析記錄數量統計）

### 2. API 優化

- [x] 分頁查詢（避免一次載入過多數據）
- [x] 錯誤處理和日誌記錄
- [x] 管理員操作日誌

### 3. 前端優化

- [x] 減少不必要的 API 調用
- [x] 使用分頁減少數據載入
- [x] 錯誤提示和用戶反饋

---

## 📝 部署後維護

### 定期檢查

- [ ] 監控 Render 日誌，確認沒有錯誤
- [ ] 檢查資料庫大小和性能
- [ ] 監控 API 使用量（OpenAI）
- [ ] 檢查用戶反饋和錯誤報告

### 備份

- [ ] 定期備份資料庫
- [ ] 保存環境變數配置
- [ ] 保存 Firebase 服務帳號 JSON

### 更新

- [ ] 定期更新依賴套件
- [ ] 監控安全漏洞
- [ ] 測試新功能後再部署

---

## ✅ 部署完成檢查

- [ ] 所有環境變數已設定
- [ ] 應用程式成功啟動
- [ ] 健康檢查通過
- [ ] 認證功能正常
- [ ] 分析功能正常
- [ ] 管理員 Dashboard 正常
- [ ] 所有測試通過

---

**最後更新**: 2025-11-20  
**版本**: v5 with Admin Dashboard

