# 🚀 Render 部署快速指南

## 三步驟部署

### 步驟 1: 設定環境變數

在 Render Dashboard → 你的服務 → Environment 設定：

1. **FIREBASE_SERVICE_ACCOUNT**
   - 前往 [Firebase Console](https://console.firebase.google.com)
   - Settings → Service accounts → Generate new private key
   - 下載 JSON，將內容轉為單行後貼上

2. **DATABASE_URL**
   - 使用 Render 提供的 Internal Database URL
   - 格式：`postgresql://user:pass@host:5432/dbname`

3. **JWT_SECRET**
   - 生成：`openssl rand -hex 32`
   - 或使用任何 32+ 字符的隨機字串

4. **APP_BASE_URL**
   - 你的 Render 服務 URL
   - 例如：`https://socialavatar.onrender.com`

### 步驟 2: 部署

- Render 會自動偵測 GitHub push 並部署
- 或手動觸發：Render Dashboard → Manual Deploy

### 步驟 3: 驗證

```bash
# 1. 健康檢查
curl https://your-app.onrender.com/health

# 2. 認證狀態檢查
curl https://your-app.onrender.com/debug/auth-status
```

## 📋 檢查清單

部署前：
- [ ] 環境變數已設定（見步驟 1）
- [ ] 代碼已推送到 GitHub
- [ ] Render 服務連接到正確的倉庫

部署後：
- [ ] `/health` 端點正常回應
- [ ] `/debug/auth-status` 顯示所有項目為 `true`
- [ ] 前端可以正常登入
- [ ] 分析功能正常運作

## 🆘 遇到問題？

1. **查看日誌**：Render Dashboard → Logs
2. **檢查狀態**：訪問 `/debug/auth-status` 端點
3. **參考文檔**：
   - `RENDER_CHECKLIST.md` - 完整檢查清單
   - `render_troubleshooting.md` - 問題排查指南
   - `DEPLOYMENT_GUIDE.md` - 詳細部署指南

## 🔗 相關文檔

- `RENDER_CHECKLIST.md` - 部署檢查清單
- `render_troubleshooting.md` - 問題排查指南
- `DEPLOYMENT_GUIDE.md` - 完整部署指南
- `test_auth_flow.md` - 測試流程檢查清單
