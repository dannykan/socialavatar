#!/bin/bash
# 本地測試管理員 Dashboard 的腳本

echo "🔐 管理員 Dashboard 本地測試腳本"
echo "=================================="
echo ""

# 檢查是否設定了 ADMIN_EMAILS
if [ -z "$ADMIN_EMAILS" ]; then
    echo "⚠️  未設定 ADMIN_EMAILS 環境變數"
    echo ""
    echo "請先設定管理員 Email："
    echo "  export ADMIN_EMAILS=your-email@gmail.com"
    echo ""
    echo "或創建 .env.local 檔案並添加："
    echo "  ADMIN_EMAILS=your-email@gmail.com"
    echo ""
    read -p "是否要現在設定？(y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "請輸入管理員 Email: " admin_email
        export ADMIN_EMAILS="$admin_email"
        echo "✅ 已設定 ADMIN_EMAILS=$admin_email"
    else
        echo "❌ 請先設定 ADMIN_EMAILS 後再執行測試"
        exit 1
    fi
else
    echo "✅ ADMIN_EMAILS 已設定: $ADMIN_EMAILS"
fi

echo ""
echo "📋 測試步驟："
echo "1. 啟動 Flask 服務器（如果尚未啟動）"
echo "2. 使用管理員 Email 登入系統"
echo "3. 訪問 http://localhost:8000/static/admin-dashboard.html"
echo ""
echo "🚀 啟動服務器..."
echo ""

# 檢查是否已安裝依賴
if ! python3 -c "import flask" 2>/dev/null; then
    echo "⚠️  未安裝 Flask，正在安裝依賴..."
    pip3 install -r requirements.txt
fi

# 啟動服務器
export PORT=8000
export APP_BASE_URL=http://localhost:8000
python3 app.py

