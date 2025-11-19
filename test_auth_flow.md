# 認證流程測試檢查清單

## 🧪 手動測試步驟

### 1. 登入流程測試

#### 測試 Google 登入
1. 開啟 `https://your-app.onrender.com/static/landing.html`
2. 點擊「使用 Google 登入」
3. 完成 Google 登入流程
4. **檢查點**：
   - [ ] 瀏覽器 Console 顯示 `[DEBUG] Getting Firebase ID token...`
   - [ ] 瀏覽器 Console 顯示 `[DEBUG] ID token obtained, calling backend...`
   - [ ] 瀏覽器 Console 顯示 `[DEBUG] ✅ Backend login successful`
   - [ ] 瀏覽器 Console 顯示 `[DEBUG] JWT token saved to localStorage`
   - [ ] 在 Application → Local Storage 中可以看到 `auth_token`
   - [ ] 在 Application → Local Storage 中可以看到 `user_data`

#### 測試 Facebook 登入
1. 開啟 `https://your-app.onrender.com/static/landing.html`
2. 點擊「使用 Facebook 登入」
3. 完成 Facebook 登入流程
4. **檢查點**：同上

### 2. 分析流程測試

1. 登入後，自動或手動跳轉到上傳頁面
2. 上傳 IG 個人頁截圖
3. 可選：上傳貼文縮圖
4. 點擊「開始分析我的 IG 社群價值」
5. **檢查點**：
   - [ ] 在 Network 標籤中，找到 `/bd/analyze` 請求
   - [ ] 檢查 Request Headers，確認有 `Authorization: Bearer <token>`
   - [ ] 分析完成後，檢查回應中的 `user_id` 欄位是否有值
   - [ ] 檢查資料庫中 `analysis_results` 表，確認 `user_id` 欄位有值

### 3. 登出流程測試

1. 在登入狀態下，點擊「登出」按鈕
2. **檢查點**：
   - [ ] `localStorage` 中的 `auth_token` 被清除
   - [ ] `localStorage` 中的 `user_data` 被清除
   - [ ] `sessionStorage` 被清除
   - [ ] 頁面重新載入並顯示登入選項

### 4. 資料庫驗證

使用資料庫查詢工具或 Render 的資料庫管理介面：

```sql
-- 檢查用戶是否正確建立
SELECT id, email, username, provider, created_at 
FROM users 
ORDER BY created_at DESC 
LIMIT 5;

-- 檢查分析結果是否關聯到用戶
SELECT 
  ar.id,
  ar.username,
  ar.user_id,
  u.email,
  ar.created_at
FROM analysis_results ar
LEFT JOIN users u ON ar.user_id = u.id
ORDER BY ar.created_at DESC
LIMIT 5;
```

**檢查點**：
- [ ] 新用戶登入後，`users` 表中出現新記錄
- [ ] 分析完成後，`analysis_results.user_id` 欄位有值
- [ ] `analysis_results.user_id` 對應到正確的 `users.id`

## 🐛 常見問題排查

### 問題 1：後端登入失敗

**症狀**：Console 顯示 `[ERROR] Backend login failed`

**排查步驟**：
1. 檢查 Render 日誌，查看 `/api/auth/firebase-login` 的錯誤訊息
2. 確認 `FIREBASE_SERVICE_ACCOUNT` 環境變數格式正確
3. 確認 Firebase 服務帳號有正確權限

### 問題 2：JWT token 未儲存

**症狀**：登入成功但 `localStorage` 中沒有 `auth_token`

**排查步驟**：
1. 檢查瀏覽器是否阻擋 `localStorage`
2. 檢查後端回應格式是否正確
3. 檢查 Console 是否有 JavaScript 錯誤

### 問題 3：分析結果未關聯用戶

**症狀**：分析完成但 `user_id` 為 `null`

**排查步驟**：
1. 檢查 Network 標籤，確認 `/bd/analyze` 請求有 `Authorization` header
2. 檢查後端日誌，確認 `current_user` 不為 `None`
3. 檢查 JWT token 是否過期

## 📊 預期行為

### 成功流程
1. 用戶點擊登入 → Firebase 驗證 → 後端驗證 Firebase token → 後端建立/更新用戶 → 回傳 JWT token → 前端儲存 token
2. 用戶上傳截圖 → 前端帶上 JWT token → 後端驗證 token → 後端分析 → 儲存結果並關聯 `user_id`
3. 用戶點擊登出 → 清除所有 token 和 session → 重新載入頁面

### 錯誤處理
- 如果後端登入失敗，前端仍會繼續流程（允許匿名使用）
- 如果 JWT token 過期，後端會回傳 401，前端應該提示重新登入
- 如果 Firebase token 無效，後端會回傳錯誤，前端會顯示錯誤訊息

