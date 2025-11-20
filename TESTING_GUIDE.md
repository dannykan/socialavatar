# 管理員 Dashboard 測試指南

## 🚀 快速測試

### 1. 確認服務器運行

服務器應該已經在 `http://localhost:8000` 運行。

檢查服務器狀態：
```bash
curl http://localhost:8000/health
```

### 2. 測試管理員 Dashboard

#### 步驟 A: 登入系統

1. 打開瀏覽器，訪問：
   ```
   http://localhost:8000/static/landing.html
   ```

2. 使用管理員 Email 登入：
   - Email: `dannytjkan@gmail.com`
   - 使用 Gmail 或 Facebook 登入

#### 步驟 B: 訪問管理員 Dashboard

登入後，訪問：
```
http://localhost:8000/static/admin-dashboard.html
```

#### 步驟 C: 驗證功能

應該能看到：

1. **系統統計卡片**
   - 總用戶數: 4
   - 有分析的用戶: 3
   - 總分析次數: 6
   - 匿名分析: 3
   - 平均價值: ~$56,667
   - 最高價值: $100,000

2. **用戶列表表格**
   - 顯示 4 個用戶
   - 包含 Email、用戶名、顯示名稱、登入方式、分析次數
   - 可以分頁瀏覽

3. **分析記錄表格**
   - 顯示 6 筆分析記錄
   - 包含 IG 帳號、用戶資訊、粉絲數、帳號價值
   - 匿名分析會標記為「匿名」
   - 可以分頁瀏覽

### 3. 測試非管理員訪問

1. 登出當前帳號
2. 使用非管理員 Email 登入（例如：user1@example.com）
3. 訪問 `http://localhost:8000/static/admin-dashboard.html`
4. 應該顯示 "您沒有管理員權限" 錯誤

## 🧪 API 測試

### 獲取 JWT Token

1. 登入後，打開瀏覽器 Console（F12）
2. 執行：
   ```javascript
   localStorage.getItem('auth_token')
   ```
3. 複製返回的 token 值

### 測試 API 端點

#### 測試統計 API

```bash
# 替換 YOUR_TOKEN 為實際的 token
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/admin/stats | python3 -m json.tool
```

預期回應：
```json
{
  "ok": true,
  "stats": {
    "users": {
      "total": 4,
      "with_analyses": 3,
      "without_analyses": 1
    },
    "analyses": {
      "total": 6,
      "with_users": 3,
      "anonymous": 3
    },
    "values": {
      "total": 340000,
      "average": 56666.67,
      "max": 100000,
      "min": 20000,
      "count": 6
    },
    "recent_analyses": [...]
  }
}
```

#### 測試用戶列表 API

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     "http://localhost:8000/api/admin/users?page=1&per_page=10" | python3 -m json.tool
```

#### 測試分析記錄 API

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     "http://localhost:8000/api/admin/analyses?page=1&per_page=10" | python3 -m json.tool
```

## ✅ 測試檢查清單

### 基本功能
- [ ] 服務器正常啟動
- [ ] `/health` 端點正常回應
- [ ] 可以使用管理員 Email 登入
- [ ] 可以訪問 `/static/admin-dashboard.html`
- [ ] 統計卡片顯示正確數據
- [ ] 用戶列表正常顯示和分頁
- [ ] 分析記錄正常顯示和分頁

### 安全功能
- [ ] 未登入用戶無法訪問 Dashboard
- [ ] 非管理員用戶訪問被拒絕
- [ ] API 端點需要有效的 JWT token
- [ ] 無效 token 被正確拒絕

### 數據顯示
- [ ] 用戶列表包含所有必要欄位
- [ ] 分析記錄包含所有必要欄位
- [ ] 匿名分析正確標記
- [ ] 日期時間格式正確
- [ ] 金額格式正確（$符號、千位分隔符）

## 🐛 故障排除

### 問題 1: 無法訪問 Dashboard

**檢查：**
1. 服務器是否運行：`curl http://localhost:8000/health`
2. 是否已登入：檢查 `localStorage.getItem('auth_token')`
3. Email 是否正確：確認 `.env.local` 中的 `ADMIN_EMAILS`

### 問題 2: 顯示 "admin_access_required" 錯誤

**解決方法：**
1. 確認 Email 與登入時使用的 Email 一致
2. 確認 `.env.local` 中的 `ADMIN_EMAILS` 已設定
3. 重新登入以獲取新的 JWT token

### 問題 3: 數據不顯示

**檢查：**
1. 數據庫是否有數據：`python3 check_database.py`
2. 瀏覽器 Console 是否有錯誤
3. Network 標籤中 API 請求是否成功

### 問題 4: API 返回 401/403

**解決方法：**
1. 確認 JWT token 有效：`localStorage.getItem('auth_token')`
2. 重新登入獲取新 token
3. 確認 token 未過期

## 📊 測試數據說明

當前測試數據包含：

- **用戶**：4 個
  - dannytjkan@gmail.com (管理員)
  - user1@example.com
  - user2@example.com
  - user3@example.com

- **分析記錄**：6 筆
  - @dannytjkan ($50,000)
  - @foodie_taipei ($80,000)
  - @travel_lover ($60,000)
  - @fitness_guru ($100,000)
  - @anonymous1 ($30,000) - 匿名
  - @anonymous2 ($20,000) - 匿名

## 🎯 下一步

測試完成後，可以：
1. 部署到 Render
2. 在 Render 環境變數中設定 `ADMIN_EMAILS`
3. 在生產環境測試

