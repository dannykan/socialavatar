# 管理員 Dashboard 設定指南

## 📋 功能說明

管理員 Dashboard 用於查看系統中所有用戶和分析記錄的統計資訊。

## 🔐 設定管理員權限

### 1. 在 Render 環境變數中設定

在 Render Dashboard 的環境變數設定中，新增：

```
ADMIN_EMAILS=your-email@gmail.com,another-admin@example.com
```

**注意事項：**
- 多個 Email 用**逗號分隔**（不要有空格）
- Email 必須與用戶登入時使用的 Email 完全一致（大小寫不敏感）
- 建議使用 Gmail 或 Facebook 登入的 Email

### 2. 本地測試設定

在本地開發時，可以在 `.env` 檔案中設定：

```bash
ADMIN_EMAILS=your-email@gmail.com
```

或在啟動時設定：

```bash
ADMIN_EMAILS=your-email@gmail.com python app.py
```

## 🚀 訪問管理員 Dashboard

1. 使用**管理員 Email**登入系統（在 `landing.html`）
2. 訪問 `/static/admin-dashboard.html`
3. 系統會自動驗證管理員權限

## 📊 Dashboard 功能

### 系統統計
- 總用戶數
- 有分析的用戶數
- 總分析次數
- 匿名分析次數
- 平均帳號價值
- 最高帳號價值

### 用戶列表
- 顯示所有註冊用戶
- 包含用戶資訊（Email、用戶名、顯示名稱）
- 顯示每個用戶的分析次數
- 支援分頁瀏覽

### 分析記錄
- 顯示所有分析記錄
- 包含 IG 帳號、用戶資訊、粉絲數、帳號價值
- 標記匿名分析
- 支援分頁瀏覽

## 🔒 安全說明

- 只有 `ADMIN_EMAILS` 中列出的 Email 可以訪問管理員功能
- 所有管理員 API 都需要有效的 JWT token
- 非管理員用戶訪問會收到 `403 Forbidden` 錯誤

## 🐛 故障排除

### 問題：顯示 "admin_access_required" 錯誤

**解決方法：**
1. 確認你的 Email 已加入 `ADMIN_EMAILS` 環境變數
2. 確認 Email 與登入時使用的 Email 完全一致
3. 重新登入以獲取新的 JWT token
4. 檢查 Render 環境變數是否已正確設定並重新部署

### 問題：無法載入數據

**解決方法：**
1. 檢查瀏覽器 Console 是否有錯誤訊息
2. 確認 JWT token 是否有效（檢查 `localStorage.getItem('auth_token')`）
3. 確認後端 API 是否正常運作（訪問 `/health` 端點）

## 📝 API 端點

### `GET /api/admin/stats`
獲取系統統計資訊

### `GET /api/admin/users?page=1&per_page=50`
獲取用戶列表（分頁）

### `GET /api/admin/analyses?page=1&per_page=50`
獲取分析記錄列表（分頁）

所有端點都需要：
- `Authorization: Bearer <JWT_TOKEN>` header
- 管理員權限

