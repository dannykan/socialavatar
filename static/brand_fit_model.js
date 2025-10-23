/**
 * IG 品牌契合度模組
 * 根據內容類型、視覺品質、專業度等因素計算與不同品牌類別的契合度
 */

export function computeBrandFit({ topic, visual, multipliers }) {
  // 定義品牌類別和基礎契合度
  const brandCategories = [
    { key: '旅遊', label: '旅宿/觀光', baseScore: 0.82, boostFactors: ['旅遊', '自然', '戶外', '度假'] },
    { key: '美食', label: '餐飲/食品', baseScore: 0.78, boostFactors: ['美食', '餐廳', '料理', '小吃'] },
    { key: '生活', label: '生活家電/日用品', baseScore: 0.75, boostFactors: ['生活', '日常', '居家', '家電'] },
    { key: '時尚', label: '服飾/配件', baseScore: 0.70, boostFactors: ['時尚', '穿搭', '服飾', '配件'] },
    { key: '科技', label: '3C/電商', baseScore: 0.66, boostFactors: ['科技', '3C', '數位', '電商'] },
    { key: '美妝', label: '彩妝/保養', baseScore: 0.64, boostFactors: ['美妝', '彩妝', '保養', '美容'] }
  ];
  
  const scores = [];
  const suggested = [];
  
  // 計算每個品牌類別的契合度
  brandCategories.forEach(brand => {
    const score = calculateBrandScore(brand, topic, visual, multipliers);
    scores.push({
      key: brand.key,
      label: brand.label,
      score: Math.round(score * 100)
    });
    
    // 高契合度品牌加入建議列表
    if (score >= 0.75) {
      suggested.push(`適合：${brand.label}`);
    }
  });
  
  return {
    scores: scores.sort((a, b) => b.score - a.score), // 按契合度排序
    suggested: suggested.slice(0, 3), // 最多顯示3個建議
    totalCategories: scores.length,
    highFitCategories: scores.filter(s => s.score >= 75).length
  };
}

/**
 * 計算單一品牌類別的契合度
 */
function calculateBrandScore(brand, topic, visual, multipliers) {
  let score = brand.baseScore;
  
  // 內容類型匹配度調整
  const contentMatch = calculateContentMatch(brand, topic);
  score += contentMatch;
  
  // 視覺品質調整
  const visualAdjustment = calculateVisualAdjustment(brand, visual);
  score += visualAdjustment;
  
  // 專業度調整
  const professionalAdjustment = calculateProfessionalAdjustment(brand, multipliers);
  score += professionalAdjustment;
  
  // 粉絲品質調整
  const followerAdjustment = calculateFollowerAdjustment(brand, multipliers);
  score += followerAdjustment;
  
  return Math.max(0.3, Math.min(0.98, score)); // 限制在 30%-98% 不等
}

/**
 * 計算內容類型匹配度
 */
function calculateContentMatch(brand, topic) {
  const topicLower = (topic || '').toLowerCase();
  let match = 0;
  
  // 直接關鍵字匹配
  brand.boostFactors.forEach(factor => {
    if (topicLower.includes(factor.toLowerCase())) {
      match += 0.08; // 每個匹配的關鍵字增加 8%
    }
  });
  
  // 相關內容類型匹配
  if (brand.key === '旅遊') {
    if (topicLower.includes('生活') || topicLower.includes('日常')) {
      match += 0.03; // 生活內容與旅遊有一定關聯
    }
  } else if (brand.key === '美食') {
    if (topicLower.includes('旅遊') || topicLower.includes('生活')) {
      match += 0.04; // 旅遊和生活內容與美食有關聯
    }
  } else if (brand.key === '生活') {
    if (topicLower.includes('美食') || topicLower.includes('旅遊')) {
      match += 0.03; // 美食和旅遊與生活內容有關聯
    }
  } else if (brand.key === '時尚') {
    if (topicLower.includes('美妝') || topicLower.includes('生活')) {
      match += 0.04; // 美妝和生活與時尚有關聯
    }
  } else if (brand.key === '美妝') {
    if (topicLower.includes('時尚') || topicLower.includes('生活')) {
      match += 0.04; // 時尚和生活與美妝有關聯
    }
  }
  
  return Math.min(0.15, match); // 最大調整 15%
}

/**
 * 計算視覺品質調整
 */
function calculateVisualAdjustment(brand, visual) {
  const visualScore = visual.overall || 7;
  let adjustment = 0;
  
  // 不同品牌類型對視覺品質的要求不同
  if (brand.key === '時尚' || brand.key === '美妝') {
    // 時尚和美妝對視覺品質要求較高
    adjustment = (visualScore - 7) * 0.03;
  } else if (brand.key === '旅遊' || brand.key === '美食') {
    // 旅遊和美食對視覺品質要求中等
    adjustment = (visualScore - 7) * 0.02;
  } else {
    // 生活和科技對視覺品質要求相對較低
    adjustment = (visualScore - 7) * 0.015;
  }
  
  return Math.max(-0.05, Math.min(0.08, adjustment));
}

/**
 * 計算專業度調整
 */
function calculateProfessionalAdjustment(brand, multipliers) {
  const professionalMultiplier = multipliers.professional || 1.0;
  let adjustment = 0;
  
  // 不同品牌類型對專業度的要求不同
  if (brand.key === '科技' || brand.key === '時尚') {
    // 科技和時尚對專業度要求較高
    adjustment = (professionalMultiplier - 1.0) * 0.04;
  } else if (brand.key === '旅遊' || brand.key === '美食') {
    // 旅遊和美食對專業度要求中等
    adjustment = (professionalMultiplier - 1.0) * 0.03;
  } else {
    // 生活、美妝對專業度要求相對較低
    adjustment = (professionalMultiplier - 1.0) * 0.02;
  }
  
  return Math.max(-0.03, Math.min(0.06, adjustment));
}

/**
 * 計算粉絲品質調整
 */
function calculateFollowerAdjustment(brand, multipliers) {
  const followerMultiplier = multipliers.follower || 1.0;
  let adjustment = 0;
  
  // 所有品牌都受益於高品質粉絲
  adjustment = (followerMultiplier - 1.0) * 0.02;
  
  // 某些品牌類型更看重粉絲品質
  if (brand.key === '科技' || brand.key === '時尚') {
    adjustment *= 1.2; // 科技和時尚品牌更看重粉絲品質
  }
  
  return Math.max(-0.02, Math.min(0.04, adjustment));
}

/**
 * 獲取品牌建議文案
 */
export function getBrandSuggestions(brandFitResult, userValue) {
  const suggestions = [];
  const highFitBrands = brandFitResult.scores.filter(s => s.score >= 75);
  
  highFitBrands.forEach(brand => {
    let suggestion = '';
    
    switch (brand.key) {
      case '旅遊':
        suggestion = `與旅宿/觀光品牌合作，適合推廣度假村、民宿、旅遊景點等`;
        break;
      case '美食':
        suggestion = `與餐飲/食品品牌合作，適合推廣餐廳、特色小吃、食材等`;
        break;
      case '生活':
        suggestion = `與生活家電/日用品品牌合作，適合推廣居家用品、家電等`;
        break;
      case '時尚':
        suggestion = `與服飾/配件品牌合作，適合推廣服裝、包包、飾品等`;
        break;
      case '科技':
        suggestion = `與3C/電商品牌合作，適合推廣數位產品、電子設備等`;
        break;
      case '美妝':
        suggestion = `與彩妝/保養品牌合作，適合推廣化妝品、護膚品等`;
        break;
    }
    
    suggestions.push(suggestion);
  });
  
  return suggestions;
}

/**
 * 計算品牌合作潛力分數
 */
export function calculateBrandPotential(brandFitResult) {
  const avgScore = brandFitResult.scores.reduce((sum, s) => sum + s.score, 0) / brandFitResult.scores.length;
  const highFitCount = brandFitResult.highFitCategories;
  
  // 綜合評分：平均契合度 + 高契合度品牌數量獎勵
  const potentialScore = (avgScore + highFitCount * 5) / 100;
  
  let level = 'standard';
  if (potentialScore >= 0.8) level = 'high';
  else if (potentialScore >= 0.6) level = 'medium';
  else if (potentialScore < 0.4) level = 'low';
  
  return {
    score: Math.round(potentialScore * 100),
    level,
    description: getPotentialDescription(level)
  };
}

function getPotentialDescription(level) {
  switch (level) {
    case 'high': return '品牌合作潛力極高，適合多種類型品牌合作';
    case 'medium': return '品牌合作潛力良好，有明確的合作方向';
    case 'standard': return '品牌合作潛力標準，建議專注特定領域';
    case 'low': return '品牌合作潛力較低，建議提升內容專業度';
    default: return '品牌合作潛力評估中';
  }
}

// 導出工具函數供測試使用
export const utils = {
  calculateBrandScore,
  calculateContentMatch,
  calculateVisualAdjustment,
  calculateProfessionalAdjustment,
  calculateFollowerAdjustment,
  getBrandSuggestions,
  calculateBrandPotential
};
