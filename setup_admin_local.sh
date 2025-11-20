#!/bin/bash
# 設定本地管理員 Email 的腳本

echo "🔐 設定本地管理員 Email"
echo "========================"
echo ""

# 檢查 .env.local 是否存在
if [ -f ".env.local" ]; then
    echo "📄 找到 .env.local 檔案"
    if grep -q "ADMIN_EMAILS" .env.local; then
        echo "✅ ADMIN_EMAILS 已存在於 .env.local"
        echo ""
        echo "目前的設定："
        grep "ADMIN_EMAILS" .env.local
        echo ""
        read -p "是否要更新？(y/n) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "保持原設定"
            exit 0
        fi
        # 移除舊的 ADMIN_EMAILS 行
        sed -i.bak '/^ADMIN_EMAILS=/d' .env.local
    fi
else
    echo "📄 創建新的 .env.local 檔案"
fi

# 獲取 Email
echo "請輸入管理員 Email（必須與登入時使用的 Email 一致）："
read -p "Email: " admin_email

if [ -z "$admin_email" ]; then
    echo "❌ Email 不能為空"
    exit 1
fi

# 添加到 .env.local
echo "ADMIN_EMAILS=$admin_email" >> .env.local
echo ""
echo "✅ 已設定 ADMIN_EMAILS=$admin_email"
echo ""
echo "📝 .env.local 內容："
cat .env.local
echo ""
echo "🚀 現在可以啟動服務器："
echo "   python3 app.py"
echo ""
echo "💡 提示：訪問 http://localhost:8000/static/admin-dashboard.html 測試"

