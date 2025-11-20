# 🔧 Render 環境變數設定指南

## ✅ 步驟 1: 代碼已推送

代碼已成功推送到 GitHub：
- **Commit**: `64bc6ce - feat: 添加管理員 Dashboard 和性能優化`
- **分支**: `main`
- **倉庫**: `https://github.com/dannykan/socialavatar.git`

---

## 🔧 步驟 2: 在 Render 設定環境變數

### 2.1 登入 Render Dashboard

1. 前往 [Render Dashboard](https://dashboard.render.com)
2. 登入你的帳號
3. 找到服務 `socialavatar`

### 2.2 添加新的環境變數

1. 點擊服務名稱進入服務詳情頁
2. 點擊左側選單的 **Environment**
3. 點擊 **Add Environment Variable** 按鈕

### 2.3 設定 `ADMIN_EMAILS` 環境變數

**重要**：這是新增的必需環境變數！

- **Key**: `ADMIN_EMAILS`
- **Value**: `dannytjkan@gmail.com`

**說明**：
- 如果有多個管理員，用逗號分隔：`email1@example.com,email2@example.com`
- 這個 Email 必須與 Firebase 登入時使用的 Email 一致

### 2.4 確認現有環境變數

確認以下環境變數已設定（應該已經存在）：

- [ ] `OPENAI_API_KEY` - OpenAI API 金鑰
- [ ] `DATABASE_URL` - PostgreSQL 連線字串（Render 自動提供）
- [ ] `JWT_SECRET` - JWT 簽章密鑰
- [ ] `FIREBASE_SERVICE_ACCOUNT` - Firebase 服務帳號 JSON
- [ ] `APP_BASE_URL` - 應用程式 URL（例如：`https://socialavatar.onrender.com`）
- [ ] `OPENAI_MODEL` - 建議設定為 `gpt-4o`

---

## 🚀 步驟 3: 觸發部署

### 自動部署（推薦）

如果自動部署已啟用，Render 會自動檢測到 GitHub 的更新並開始部署。

**檢查自動部署狀態**：
1. 進入服務詳情頁
2. 點擊 **Settings** 標籤
3. 確認 **Auto-Deploy** 已啟用

### 手動部署

如果自動部署未啟用，手動觸發：

1. 進入服務詳情頁
2. 點擊 **Manual Deploy** 按鈕
3. 選擇 **Deploy latest commit**
4. 點擊 **Deploy**

---

## 📊 步驟 4: 監控部署進度

### 查看部署日誌

1. 在服務詳情頁，點擊 **Logs** 標籤
2. 查看實時部署日誌

### 部署成功的標誌

在日誌中應該看到：
```
[DB] ✅ 資料庫初始化完成
[Firebase] ✅ Firebase 初始化成功
✅ AI 分析器初始化成功 (模型: gpt-4o)
* Running on all addresses (0.0.0.0)
* Running on http://0.0.0.0:XXXX
```

### 如果部署失敗

常見問題：
1. **環境變數未設定** - 檢查所有必需變數
2. **依賴安裝失敗** - 檢查 `requirements.txt`
3. **資料庫連線失敗** - 檢查 `DATABASE_URL`
4. **Firebase 設定錯誤** - 檢查 `FIREBASE_SERVICE_ACCOUNT` JSON 格式

---

## 🧪 步驟 5: 測試部署

### 5.1 健康檢查

```bash
curl https://socialavatar.onrender.com/health
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

### 5.2 測試認證功能

1. 訪問：`https://socialavatar.onrender.com/static/landing.html`
2. 使用 Google/Facebook 登入
3. 檢查瀏覽器 Console（F12）確認沒有錯誤

### 5.3 測試管理員 Dashboard

1. 使用管理員 Email（`dannytjkan@gmail.com`）登入
2. 訪問：`https://socialavatar.onrender.com/static/admin-dashboard.html`
3. 測試以下功能：
   - [ ] 查看系統統計
   - [ ] 查看用戶列表
   - [ ] 查看分析記錄列表
   - [ ] 編輯分析記錄的價值和報價
   - [ ] 刪除分析記錄
   - [ ] 刪除用戶

---

## ✅ 部署完成檢查清單

- [ ] 代碼已推送到 GitHub
- [ ] `ADMIN_EMAILS` 環境變數已設定
- [ ] 所有其他環境變數已確認
- [ ] 部署已觸發
- [ ] 部署日誌顯示成功
- [ ] 健康檢查通過
- [ ] 認證功能正常
- [ ] 管理員 Dashboard 正常運作

---

## 🆘 需要幫助？

如果遇到問題：

1. **檢查 Render 日誌** - 查看詳細錯誤訊息
2. **檢查環境變數** - 確認所有變數格式正確
3. **查看文檔** - 參考 `DEPLOYMENT_CHECKLIST.md` 中的常見問題

---

**部署完成後，請告訴我結果！** 🎉

