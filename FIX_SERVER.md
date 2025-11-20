# 🔧 修復服務器問題

## 問題診斷

服務器無法啟動，因為缺少 `sqlalchemy` 模組。

## 解決方法

### 方法 1: 安裝依賴（推薦）

```bash
cd /Users/dannykan/IG-valuation/socialavatar
pip3 install -r requirements.txt
```

### 方法 2: 只安裝必要的套件

```bash
pip3 install flask flask-cors sqlalchemy pyjwt firebase-admin
```

### 方法 3: 使用虛擬環境（最佳實踐）

```bash
# 創建虛擬環境
python3 -m venv venv

# 啟動虛擬環境
source venv/bin/activate

# 安裝依賴
pip install -r requirements.txt

# 啟動服務器
export ADMIN_EMAILS=dannytjkan@gmail.com
python app.py
```

## 啟動服務器

安裝依賴後，執行：

```bash
export ADMIN_EMAILS=dannytjkan@gmail.com
python3 app.py
```

服務器會在 `http://localhost:8000` 啟動。

## 驗證

1. 檢查服務器是否運行：
   ```bash
   curl http://localhost:8000/health
   ```

2. 測試管理員 API（應該返回 401 而不是 404）：
   ```bash
   curl http://localhost:8000/api/admin/stats
   ```

如果返回 401，表示路由已正確註冊！

