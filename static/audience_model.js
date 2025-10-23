/**
 * IG 受眾輪廓合成模組
 * 根據內容類型、視覺品質、專業度等數據推測受眾特徵
 */

export function synthesizeAudience({ topic, visual, mult, analysis }) {
  // 性別比例推測
  const maleRatio = calculateGenderRatio(topic, visual, analysis);
  
  // 年齡分布推測
  const ageDistribution = calculateAgeDistribution(topic, visual, mult, analysis);
  
  // 城市/風格偏好推測
  const cityStyles = calculateCityStyles(topic, visual, analysis);
  
  return {
    male_ratio: maleRatio,
    female_ratio: 1 - maleRatio,
    age_dist: ageDistribution,
    city_styles: cityStyles
  };
}

/**
 * 計算性別比例
 * 基於內容類型、視覺風格等因素推測
 */
function calculateGenderRatio(topic, visual, analysis) {
  let baseRatio = 0.52; // 預設男性比例
  
  // 根據內容類型調整
  if (topic.includes('時尚') || topic.includes('美妝')) {
    baseRatio = 0.38; // 時尚美妝類偏向女性
  } else if (topic.includes('科技') || topic.includes('3C')) {
    baseRatio = 0.62; // 科技類偏向男性
  } else if (topic.includes('美食') || topic.includes('旅遊')) {
    baseRatio = 0.48; // 美食旅遊類略微偏向女性
  }
  
  // 根據視覺品質調整
  const visualScore = visual.overall || 7;
  if (visualScore > 8) {
    baseRatio += 0.05; // 高品質內容吸引更多男性
  } else if (visualScore < 6) {
    baseRatio -= 0.03; // 低品質內容偏向女性
  }
  
  // 根據專業度調整
  const professionalScore = analysis.professional_score || 6;
  if (professionalScore > 7) {
    baseRatio += 0.04; // 專業內容吸引更多男性
  }
  
  return Math.max(0.25, Math.min(0.75, baseRatio));
}

/**
 * 計算年齡分布
 * 基於內容調性、視覺風格、粉絲品質等因素
 */
function calculateAgeDistribution(topic, visual, mult, analysis) {
  const visualScore = visual.overall || 7;
  const followerQuality = mult.follower || 1.0;
  
  // 基礎分布
  let distribution = [
    0.30 - (visualScore - 7) * 0.02,  // 18-24: 視覺品質越高，年輕人越多
    0.45 + (followerQuality - 1) * 0.1, // 25-34: 粉絲品質越好，主力年齡層越多
    0.18, // 35-44
    0.07  // 45+
  ];
  
  // 根據內容類型調整
  if (topic.includes('旅遊')) {
    distribution[1] += 0.05; // 旅遊內容吸引25-34歲
    distribution[2] += 0.03; // 也吸引35-44歲
    distribution[0] -= 0.08; // 年輕人較少
  } else if (topic.includes('美食')) {
    distribution[0] += 0.04; // 美食吸引年輕人
    distribution[1] += 0.02;
    distribution[2] -= 0.03;
    distribution[3] -= 0.03;
  } else if (topic.includes('時尚')) {
    distribution[0] += 0.06; // 時尚吸引年輕人
    distribution[1] += 0.01;
    distribution[2] -= 0.04;
    distribution[3] -= 0.03;
  }
  
  // 根據專業度調整
  const professionalScore = analysis.professional_score || 6;
  if (professionalScore > 7) {
    distribution[1] += 0.03; // 專業內容吸引25-34歲
    distribution[2] += 0.02; // 也吸引35-44歲
    distribution[0] -= 0.05; // 年輕人較少
  }
  
  // 正規化確保總和為1
  const total = distribution.reduce((sum, val) => sum + val, 0);
  return distribution.map(val => val / total);
}

/**
 * 計算城市/風格偏好
 * 基於內容主題和視覺風格推測
 */
function calculateCityStyles(topic, visual, analysis) {
  const styles = [];
  
  // 根據內容類型推測
  if (topic.includes('旅遊')) {
    styles.push('台北都會', '海島度假', '文化歷史');
    if (visual.overall > 7) {
      styles.push('網美打卡', '秘境探索');
    }
  } else if (topic.includes('美食')) {
    styles.push('熱門商圈', '夜市小吃', '網美咖啡');
    if (visual.overall > 7) {
      styles.push('米其林餐廳', '隱藏版小店');
    }
  } else if (topic.includes('時尚')) {
    styles.push('精品百貨', '設計選物', '潮流快閃');
    if (visual.overall > 7) {
      styles.push('時尚週', '設計師品牌');
    }
  } else {
    // 生活類內容
    styles.push('生活機能', '社區小店', '郊外踏青');
    if (visual.overall > 7) {
      styles.push('文青咖啡', '特色書店');
    }
  }
  
  // 根據視覺品質添加更多風格
  if (visual.overall > 8) {
    styles.push('藝術展覽', '文創園區');
  }
  
  // 根據專業度添加商務風格
  const professionalScore = analysis.professional_score || 6;
  if (professionalScore > 7) {
    styles.push('商務中心', '會議空間');
  }
  
  // 返回前4個最相關的風格
  return styles.slice(0, 4);
}

// 導出工具函數供測試使用
export const utils = {
  calculateGenderRatio,
  calculateAgeDistribution,
  calculateCityStyles
};
