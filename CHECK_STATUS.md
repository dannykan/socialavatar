# 🔍 檢查服務器狀態

## 當前狀態

服務器應該正在運行在 `http://localhost:8000`

## 快速檢查

### 1. 檢查服務器是否運行

```bash
curl http://localhost:8000/health
```

應該返回：
```json
{
  "status": "ok",
  "version": "v5",
  "ai_enabled": true
}
```

### 2. 檢查服務器日誌

```bash
tail -f /tmp/flask_admin.log
```

當你刷新 Dashboard 頁面時，應該會看到：
- `[Auth] ⚠️ Firebase 未配置，使用本地開發模式`
- `[Auth] 本地模式：從 token 提取 email=...`
- `[Auth] ✅ 本地模式登入成功: ...`

### 3. 測試 Firebase 登入 API

在瀏覽器 Console 中執行：

```javascript
// 獲取 Firebase ID token
const user = firebase.auth().currentUser;
if (user) {
  user.getIdToken().then(idToken => {
    console.log('ID Token 長度:', idToken.length);
    
    // 測試 API
    fetch('/api/auth/firebase-login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id_token: idToken })
    })
    .then(res => res.json())
    .then(data => {
      console.log('API 回應:', data);
      if (data.token) {
        localStorage.setItem('auth_token', data.token);
        console.log('✅ Token 已儲存');
        location.reload(); // 重新載入頁面
      }
    })
    .catch(err => console.error('錯誤:', err));
  });
}
```

## 如果 Dashboard 仍在載入

1. **檢查 Console 錯誤**：查看是否有新的錯誤訊息
2. **檢查 Network 標籤**：確認 API 請求是否成功
3. **檢查服務器日誌**：`tail -f /tmp/flask_admin.log`

## 常見問題

### 問題：仍然顯示 "認證失敗"

**解決方法**：
1. 清除瀏覽器緩存並強制刷新
2. 檢查服務器日誌是否有錯誤
3. 確認 Firebase 用戶已登入

### 問題：API 返回 500 錯誤

**檢查**：
```bash
tail -50 /tmp/flask_admin.log | grep -A 5 "Error\|Traceback"
```

### 問題：無法連接到服務器

**檢查**：
```bash
lsof -i :8000
```

如果沒有輸出，服務器可能沒有運行。

