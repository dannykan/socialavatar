#!/usr/bin/env python3
"""
從 AI 的開放式回答中提取關鍵數據
"""

import json
import re
from typing import Dict, Any, Optional

def extract_data_from_ai_response(ai_response: str) -> Dict[str, Any]:
    """
    從 AI 的開放式回答中提取關鍵數據
    """
    
    # 提取帳號價值
    account_value = extract_account_value(ai_response)
    
    # 提取報價信息
    pricing = extract_pricing(ai_response)
    
    # 提取其他分析數據
    analysis_data = extract_analysis_data(ai_response)
    
    return {
        "account_value": account_value,
        "pricing": pricing,
        "analysis": analysis_data
    }

def extract_account_value(text: str) -> Dict[str, Any]:
    """提取帳號價值信息"""
    
    # 尋找價格範圍
    price_patterns = [
        r'NT\$?[\s]*([0-9,]+)[\s]*[-~至到]\s*NT\$?[\s]*([0-9,]+)',
        r'([0-9,]+)[\s]*[-~至到]\s*([0-9,]+)[\s]*元',
        r'價值[約為]*[\s]*NT\$?[\s]*([0-9,]+)[\s]*[-~至到]\s*NT\$?[\s]*([0-9,]+)',
        r'估值[約為]*[\s]*([0-9,]+)[\s]*[-~至到]\s*([0-9,]+)[\s]*元'
    ]
    
    min_value = None
    max_value = None
    reasoning = ""
    
    for pattern in price_patterns:
        match = re.search(pattern, text)
        if match:
            min_value = int(match.group(1).replace(',', ''))
            max_value = int(match.group(2).replace(',', ''))
            break
    
    # 如果沒找到範圍，尋找單一價格
    if not min_value:
        single_price_patterns = [
            r'NT\$?[\s]*([0-9,]+)',
            r'([0-9,]+)[\s]*元',
            r'價值[約為]*[\s]*NT\$?[\s]*([0-9,]+)',
            r'估值[約為]*[\s]*([0-9,]+)[\s]*元'
        ]
        
        for pattern in single_price_patterns:
            match = re.search(pattern, text)
            if match:
                value = int(match.group(1).replace(',', ''))
                min_value = value
                max_value = value
                break
    
    # 提取推理邏輯
    reasoning_patterns = [
        r'因為([^。]+)',
        r'由於([^。]+)',
        r'基於([^。]+)',
        r'根據([^。]+)'
    ]
    
    for pattern in reasoning_patterns:
        match = re.search(pattern, text)
        if match:
            reasoning = match.group(1).strip()
            break
    
    return {
        "min": min_value or 0,
        "max": max_value or 0,
        "reasoning": reasoning or "基於市場行情分析"
    }

def extract_pricing(text: str) -> Dict[str, Any]:
    """提取報價信息"""
    
    pricing = {
        "post": 0,
        "story": 0,
        "reels": 0
    }
    
    # Post 報價
    post_patterns = [
        r'Post[^0-9]*NT\$?[\s]*([0-9,]+)',
        r'貼文[^0-9]*NT\$?[\s]*([0-9,]+)',
        r'單篇[^0-9]*NT\$?[\s]*([0-9,]+)'
    ]
    
    for pattern in post_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            pricing["post"] = int(match.group(1).replace(',', ''))
            break
    
    # Story 報價
    story_patterns = [
        r'Story[^0-9]*NT\$?[\s]*([0-9,]+)',
        r'限時動態[^0-9]*NT\$?[\s]*([0-9,]+)'
    ]
    
    for pattern in story_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            pricing["story"] = int(match.group(1).replace(',', ''))
            break
    
    # Reels 報價
    reels_patterns = [
        r'Reels[^0-9]*NT\$?[\s]*([0-9,]+)',
        r'短影片[^0-9]*NT\$?[\s]*([0-9,]+)'
    ]
    
    for pattern in reels_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            pricing["reels"] = int(match.group(1).replace(',', ''))
            break
    
    return pricing

def extract_analysis_data(text: str) -> Dict[str, Any]:
    """提取分析數據"""
    
    analysis = {
        "visual_quality": {"overall": 7.5},
        "content_type": {"primary": "生活記錄", "commercial_potential": "medium"},
        "professionalism": {"brand_identity": 7.0},
        "uniqueness": {"creativity_score": 7.0},
        "audience_value": {"audience_tier": "一般用戶"},
        "improvement_tips": []
    }
    
    # 提取改進建議
    tips_pattern = r'建議[：:]?\s*([^。]+)'
    tips_matches = re.findall(tips_pattern, text)
    if tips_matches:
        analysis["improvement_tips"] = [tip.strip() for tip in tips_matches[:3]]
    
    return analysis

if __name__ == "__main__":
    # 測試
    sample_text = """
    這個IG帳號價值約NT$200,000-300,000，因為有20萬粉絲且互動率良好。
    Post報價約NT$15,000，Story報價約NT$5,000，Reels報價約NT$25,000。
    建議增加與粉絲的互動，提升內容品質。
    """
    
    result = extract_data_from_ai_response(sample_text)
    print(json.dumps(result, indent=2, ensure_ascii=False))
