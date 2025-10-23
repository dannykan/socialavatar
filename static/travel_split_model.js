/**
 * IG 旅遊類別細分合成模組
 * 根據內容類型、視覺品質、風格獨特性等數據推測旅遊住宿偏好
 */

export function synthesizeTravelSplit({ topic, visual, uniqueness, analysis }) {
  // 計算各類旅遊住宿的適合度
  const cityHotel = calculateCityHotelScore(topic, visual, uniqueness, analysis);
  const resort = calculateResortScore(topic, visual, uniqueness, analysis);
  const designHotel = calculateDesignHotelScore(topic, visual, uniqueness, analysis);
  
  return {
    city_hotel: cityHotel,
    resort: resort,
    design_hotel: designHotel
  };
}

/**
 * 計算城市飯店適合度
 * 基於內容類型、構圖專業度、商務感等因素
 */
function calculateCityHotelScore(topic, visual, uniqueness, analysis) {
  let score = 0.65; // 基礎分數
  
  // 內容類型調整
  if (topic.includes('旅遊')) {
    score += 0.15; // 旅遊內容大幅提升城市飯店適合度
  } else if (topic.includes('商務') || topic.includes('工作')) {
    score += 0.20; // 商務內容更適合城市飯店
  } else if (topic.includes('美食')) {
    score += 0.08; // 美食內容適度提升
  }
  
  // 視覺品質調整
  const compositionScore = visual.composition || 6;
  score += (compositionScore - 6) * 0.02; // 構圖專業度影響
  
  const overallScore = visual.overall || 7;
  score += (overallScore - 7) * 0.015; // 整體視覺品質影響
  
  // 專業度調整
  const professionalScore = analysis.professional_score || 6;
  if (professionalScore > 7) {
    score += 0.10; // 高專業度更適合城市飯店
  }
  
  // 粉絲品質調整
  const followerQuality = analysis.follower_quality || 'standard';
  if (followerQuality === 'high' || followerQuality === 'influencer') {
    score += 0.05; // 高品質粉絲更適合商務住宿
  }
  
  return Math.min(96, Math.round(score * 100));
}

/**
 * 計算度假村適合度
 * 基於內容類型、色彩和諧度、休閒感等因素
 */
function calculateResortScore(topic, visual, uniqueness, analysis) {
  let score = 0.65; // 基礎分數
  
  // 內容類型調整
  if (topic.includes('旅遊')) {
    score += 0.15; // 旅遊內容提升度假村適合度
  } else if (topic.includes('休閒') || topic.includes('度假')) {
    score += 0.20; // 休閒度假內容更適合度假村
  } else if (topic.includes('自然') || topic.includes('戶外')) {
    score += 0.12; // 自然戶外內容適合度假村
  }
  
  // 視覺品質調整
  const colorHarmony = visual.color_harmony || 6;
  score += (colorHarmony - 6) * 0.025; // 色彩和諧度對度假村很重要
  
  const overallScore = visual.overall || 7;
  score += (overallScore - 7) * 0.02; // 整體視覺品質影響
  
  // 風格獨特性調整
  const styleSignature = uniqueness.style_signature || '';
  if (styleSignature.includes('自然') || styleSignature.includes('清新')) {
    score += 0.08; // 自然清新風格更適合度假村
  }
  
  // 內容調性調整
  const contentTone = analysis.content_tone || 'neutral';
  if (contentTone === 'relaxed' || contentTone === 'leisure') {
    score += 0.06; // 休閒調性更適合度假村
  }
  
  return Math.min(96, Math.round(score * 100));
}

/**
 * 計算設計旅店適合度
 * 基於風格獨特性、創意度、藝術感等因素
 */
function calculateDesignHotelScore(topic, visual, uniqueness, analysis) {
  let score = 0.65; // 基礎分數
  
  // 內容類型調整
  if (topic.includes('藝術') || topic.includes('設計')) {
    score += 0.20; // 藝術設計內容大幅提升設計旅店適合度
  } else if (topic.includes('文創') || topic.includes('創意')) {
    score += 0.15; // 文創創意內容適合設計旅店
  } else if (topic.includes('旅遊')) {
    score += 0.10; // 旅遊內容適度提升
  }
  
  // 風格獨特性調整
  const styleSignature = uniqueness.style_signature || '';
  const uniquenessLength = styleSignature.length;
  score += Math.min(0.10, uniquenessLength / 500); // 風格獨特性越強，設計旅店適合度越高
  
  // 視覺創意度調整
  const editingScore = visual.editing || 6;
  score += (editingScore - 6) * 0.02; // 後製創意度影響
  
  // 整體美感調整
  const overallScore = visual.overall || 7;
  score += (overallScore - 7) * 0.015; // 整體美感影響
  
  // 內容調性調整
  const contentTone = analysis.content_tone || 'neutral';
  if (contentTone === 'creative' || contentTone === 'artistic') {
    score += 0.08; // 創意藝術調性更適合設計旅店
  }
  
  // 粉絲品質調整
  const followerQuality = analysis.follower_quality || 'standard';
  if (followerQuality === 'high' || followerQuality === 'influencer') {
    score += 0.05; // 高品質粉絲更欣賞設計旅店
  }
  
  return Math.min(96, Math.round(score * 100));
}

/**
 * 計算綜合旅遊適合度
 * 提供整體旅遊內容適合度評估
 */
export function calculateOverallTravelScore(topic, visual, analysis) {
  let score = 0.5; // 基礎分數
  
  // 內容類型調整
  if (topic.includes('旅遊')) {
    score += 0.3; // 旅遊內容大幅提升
  } else if (topic.includes('美食') || topic.includes('生活')) {
    score += 0.1; // 美食生活內容適度提升
  }
  
  // 視覺品質調整
  const overallScore = visual.overall || 7;
  score += (overallScore - 7) * 0.05;
  
  // 專業度調整
  const professionalScore = analysis.professional_score || 6;
  score += (professionalScore - 6) * 0.03;
  
  return Math.min(1.0, Math.max(0.0, score));
}

// 導出工具函數供測試使用
export const utils = {
  calculateCityHotelScore,
  calculateResortScore,
  calculateDesignHotelScore,
  calculateOverallTravelScore
};
