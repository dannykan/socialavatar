# 如何使用MP4動態圖功能

## 1. 準備視頻文件

將您的MP4動態圖文件放入 `static/videos/mbti/` 目錄中，按照以下命名規則：

```
static/videos/mbti/
├── ENFJ_male.mp4
├── ENFJ_female.mp4
├── ENFP_male.mp4
├── ENFP_female.mp4
├── ... (其他MBTI類型)
└── ISTP_female.mp4
```

## 2. 功能特色

### ✨ 文字疊加顯示
- IG username會自動疊加在視頻底部
- 具有發光動畫效果
- 半透明背景，不影響視頻觀看

### 🎮 視頻控制
- 播放/暫停控制
- 靜音/取消靜音
- 全螢幕播放
- 播放速度調整（0.5x, 1x, 1.5x, 2x）
- 循環播放開關

### 📱 響應式設計
- 支持手機和桌面設備
- 自動適應不同螢幕尺寸

## 3. 技術實現

### 視頻載入
```javascript
// 根據MBTI類型和性別載入對應視頻
const videoPath = `/static/videos/mbti/${mbtiType}_${gender}.mp4`;
```

### 文字疊加
```html
<div class="username-overlay">
  @dannyjkan
</div>
```

### CSS動畫效果
```css
@keyframes usernameGlow {
  0% { 
    box-shadow: 0 0 10px rgba(255, 255, 255, 0.3);
    transform: translateX(-50%) scale(1);
  }
  100% { 
    box-shadow: 0 0 20px rgba(255, 255, 255, 0.6);
    transform: translateX(-50%) scale(1.02);
  }
}
```

## 4. 測試步驟

1. 將您的MP4文件放入正確的目錄
2. 確保文件名符合命名規則
3. 訪問 `/static/avatar3d.html` 頁面
4. 檢查視頻是否正常載入和播放
5. 確認IG username正確顯示在視頻上
6. 測試各種控制功能

## 5. 故障排除

### 視頻無法載入
- 檢查文件路徑是否正確
- 確認文件名格式是否符合要求
- 檢查視頻文件是否損壞

### 文字不顯示
- 確認用戶數據中包含username字段
- 檢查CSS樣式是否正確載入

### 控制按鈕無響應
- 檢查JavaScript控制台是否有錯誤
- 確認事件監聽器是否正確綁定
