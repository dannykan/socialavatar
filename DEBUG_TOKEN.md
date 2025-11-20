# 🔍 Token 調試指南

## 當前問題

JWT token 已成功獲取，但後端返回 `invalid_token` 錯誤。

## 調試步驟

### 1. 檢查 Token 是否正確儲存

在瀏覽器 Console 中執行：

```javascript
const token = localStorage.getItem('auth_token');
console.log('Token 長度:', token ? token.length : 'null');
console.log('Token 前50字符:', token ? token.substring(0, 50) : 'null');
```

### 2. 檢查 Token 格式

Token 應該是 JWT 格式（三個部分用 `.` 分隔）：

```javascript
const token = localStorage.getItem('auth_token');
if (token) {
  const parts = token.split('.');
  console.log('Token 部分數:', parts.length);
  console.log('應該是 3 個部分（header.payload.signature）');
  
  // 嘗試解碼 payload（僅用於調試）
  try {
    const payload = JSON.parse(atob(parts[1]));
    console.log('Token payload:', payload);
    console.log('User ID:', payload.sub);
    console.log('過期時間:', new Date(payload.exp * 1000));
  } catch (e) {
    console.error('無法解析 payload:', e);
  }
}
```

### 3. 測試 API 請求

手動測試 API 請求：

```javascript
const token = localStorage.getItem('auth_token');
fetch('/api/admin/stats', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
})
.then(res => {
  console.log('狀態碼:', res.status);
  return res.json();
})
.then(data => {
  console.log('回應:', data);
})
.catch(err => console.error('錯誤:', err));
```

### 4. 查看服務器日誌

```bash
tail -f /tmp/flask_debug.log
```

當你刷新頁面時，應該會看到：
- `[Auth] 🔍 驗證 token，長度: ...`
- `[Auth] ✅ Token 驗證成功: user_id=...` 或
- `[Auth] ❌ Token 無效: ...`

## 可能的原因

1. **Token 格式問題**：Token 可能不是有效的 JWT 格式
2. **JWT_SECRET 不匹配**：但這不太可能，因為是同一個服務器
3. **Token 損壞**：在儲存或傳輸過程中可能被修改

## 解決方法

如果 token 有問題，可以：

1. **清除 token 並重新獲取**：
```javascript
localStorage.removeItem('auth_token');
location.reload();
```

2. **檢查服務器日誌**查看具體錯誤

