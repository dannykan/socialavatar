/**
 * IG 報價區間信心條模組
 * 根據視覺品質、專業度、內容類型與粉絲品質推估報價不確定性區間
 */

export function getConfidenceBands({ value, visual, mult, contentPrimary }) {
  // 計算基礎不確定性
  const baseUncertainty = calculateBaseUncertainty(visual, mult, contentPrimary);
  
  // 為不同內容類型計算信心區間
  const bands = {
    post: calculatePostConfidence(baseUncertainty, visual, mult, value),
    story: calculateStoryConfidence(baseUncertainty, visual, mult, value),
    reels: calculateReelsConfidence(baseUncertainty, visual, mult, value),
    monthly: calculateMonthlyConfidence(baseUncertainty, visual, mult, value)
  };
  
  return bands;
}

/**
 * 計算基礎不確定性
 * 基於視覺品質、專業度等因素
 */
function calculateBaseUncertainty(visual, mult, contentPrimary) {
  let uncertainty = 0.20; // 基礎不確定性 20%
  
  // 根據視覺品質調整
  const visualScore = visual.overall || 7;
  if (visualScore > 8) {
    uncertainty -= 0.05; // 高視覺品質降低不確定性
  } else if (visualScore < 6) {
    uncertainty += 0.08; // 低視覺品質增加不確定性
  }
  
  // 根據專業度調整
  const professionalMultiplier = mult.professional || 1.0;
  if (professionalMultiplier > 1.5) {
    uncertainty -= 0.06; // 高專業度降低不確定性
  } else if (professionalMultiplier < 1.2) {
    uncertainty += 0.04; // 低專業度增加不確定性
  }
  
  // 根據粉絲品質調整
  const followerMultiplier = mult.follower || 1.0;
  if (followerMultiplier > 1.5) {
    uncertainty -= 0.03; // 高粉絲品質降低不確定性
  } else if (followerMultiplier < 1.1) {
    uncertainty += 0.05; // 低粉絲品質增加不確定性
  }
  
  // 根據內容類型調整
  if (contentPrimary?.includes('旅遊')) {
    uncertainty += 0.03; // 旅遊內容市場波動較大
  } else if (contentPrimary?.includes('美食')) {
    uncertainty -= 0.02; // 美食內容相對穩定
  } else if (contentPrimary?.includes('時尚')) {
    uncertainty += 0.02; // 時尚內容受趨勢影響
  }
  
  return Math.max(0.08, Math.min(0.40, uncertainty)); // 限制在 8%-40% 不等
}

/**
 * 計算貼文信心區間
 */
function calculatePostConfidence(baseUncertainty, visual, mult, value) {
  let confidence = baseUncertainty;
  
  // 貼文相對穩定，基礎調整較小
  const postValue = Number(value.post_value || 0);
  
  // 高價值貼文通常更穩定
  if (postValue > 50000) {
    confidence -= 0.03;
  } else if (postValue < 10000) {
    confidence += 0.04; // 低價值貼文不確定性較高
  }
  
  // 根據視覺品質微調
  const visualScore = visual.overall || 7;
  confidence += (7 - visualScore) * 0.005;
  
  return Math.max(0.08, Math.min(0.35, confidence));
}

/**
 * 計算 Story 信心區間
 */
function calculateStoryConfidence(baseUncertainty, visual, mult, value) {
  let confidence = baseUncertainty + 0.02; // Story 通常比貼文不確定性稍高
  
  const storyValue = Number(value.story_value || 0);
  
  // Story 價值調整
  if (storyValue > 20000) {
    confidence -= 0.02;
  } else if (storyValue < 5000) {
    confidence += 0.05;
  }
  
  // Story 更依賴視覺效果
  const visualScore = visual.overall || 7;
  confidence += (7 - visualScore) * 0.008;
  
  return Math.max(0.10, Math.min(0.38, confidence));
}

/**
 * 計算 Reels 信心區間
 */
function calculateReelsConfidence(baseUncertainty, visual, mult, value) {
  let confidence = baseUncertainty + 0.05; // Reels 不確定性最高
  
  const reelsValue = Number(value.reels_value || 0);
  
  // Reels 價值調整
  if (reelsValue > 100000) {
    confidence -= 0.04;
  } else if (reelsValue < 20000) {
    confidence += 0.06;
  }
  
  // Reels 高度依賴創意和後製
  const editingScore = visual.editing || 6;
  confidence += (6 - editingScore) * 0.01;
  
  const visualScore = visual.overall || 7;
  confidence += (7 - visualScore) * 0.01;
  
  return Math.max(0.12, Math.min(0.40, confidence));
}

/**
 * 計算月配合信心區間
 */
function calculateMonthlyConfidence(baseUncertainty, visual, mult, value) {
  let confidence = baseUncertainty - 0.03; // 月配合相對最穩定
  
  const monthlyValue = Number(value.monthly_package || 0);
  
  // 月配合價值調整
  if (monthlyValue > 200000) {
    confidence -= 0.04;
  } else if (monthlyValue < 50000) {
    confidence += 0.03;
  }
  
  // 月配合更看重長期穩定性和專業度
  const professionalMultiplier = mult.professional || 1.0;
  confidence -= (professionalMultiplier - 1.0) * 0.02;
  
  const followerMultiplier = mult.follower || 1.0;
  confidence -= (followerMultiplier - 1.0) * 0.015;
  
  return Math.max(0.08, Math.min(0.30, confidence));
}

/**
 * 計算價格區間邊界
 */
export function calculatePriceBounds(centerPrice, confidencePercentage) {
  const lower = Math.max(0, Math.round(centerPrice * (1 - confidencePercentage)));
  const upper = Math.round(centerPrice * (1 + confidencePercentage));
  
  return {
    lower,
    upper,
    confidence: confidencePercentage,
    range: upper - lower
  };
}

/**
 * 格式化信心區間顯示
 */
export function formatConfidenceDisplay(centerPrice, confidencePercentage) {
  const bounds = calculatePriceBounds(centerPrice, confidencePercentage);
  return {
    display: `估計區間：NT$ ${bounds.lower.toLocaleString('zh-TW')} ~ NT$ ${bounds.upper.toLocaleString('zh-TW')}（±${Math.round(confidencePercentage * 100)}%）`,
    lower: bounds.lower,
    upper: bounds.upper,
    confidence: Math.round(confidencePercentage * 100)
  };
}

// 導出工具函數供測試使用
export const utils = {
  calculateBaseUncertainty,
  calculatePostConfidence,
  calculateStoryConfidence,
  calculateReelsConfidence,
  calculateMonthlyConfidence,
  calculatePriceBounds,
  formatConfidenceDisplay
};
