/**
 * 認證工具函數
 * 用於管理 JWT token 和自動刷新
 */

/**
 * 解碼 JWT token（不驗證簽名，只用於讀取 payload）
 */
function decodeJWT(token) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    console.error('[Auth] Token 解碼失敗:', e);
    return null;
  }
}

/**
 * 檢查 token 是否即將過期（在 5 分鐘內過期）
 */
function isTokenExpiringSoon(token) {
  if (!token) return true;
  
  const payload = decodeJWT(token);
  if (!payload || !payload.exp) return true;
  
  const expirationTime = payload.exp * 1000; // 轉換為毫秒
  const currentTime = Date.now();
  const fiveMinutes = 5 * 60 * 1000; // 5 分鐘
  
  // 如果剩餘時間少於 5 分鐘，視為即將過期
  return (expirationTime - currentTime) < fiveMinutes;
}

/**
 * 檢查 token 是否已過期
 */
function isTokenExpired(token) {
  if (!token) return true;
  
  const payload = decodeJWT(token);
  if (!payload || !payload.exp) return true;
  
  const expirationTime = payload.exp * 1000;
  const currentTime = Date.now();
  
  return currentTime >= expirationTime;
}

/**
 * 刷新 JWT token
 * 使用 Firebase 用戶獲取新的 ID token，然後調用後端 API 獲取新的 JWT
 */
async function refreshAuthToken(firebaseUser) {
  if (!firebaseUser) {
    console.warn('[Auth] 無法刷新 token：沒有 Firebase 用戶');
    return null;
  }
  
  try {
    console.log('[Auth] 開始刷新 token...');
    
    // 獲取新的 Firebase ID token
    const idToken = await firebaseUser.getIdToken(true); // true 表示強制刷新
    console.log('[Auth] Firebase ID token 已刷新');
    
    // 調用後端 API 獲取新的 JWT token
    const response = await fetch('/api/auth/firebase-login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ id_token: idToken })
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `HTTP ${response.status}`);
    }
    
    const data = await response.json();
    console.log('[Auth] ✅ Token 刷新成功');
    
    // 更新 localStorage
    if (data.token) {
      localStorage.setItem('auth_token', data.token);
      console.log('[Auth] JWT token 已更新到 localStorage');
    }
    
    if (data.user) {
      localStorage.setItem('user_data', JSON.stringify(data.user));
    }
    
    return data.token;
  } catch (error) {
    console.error('[Auth] ❌ Token 刷新失敗:', error);
    return null;
  }
}

/**
 * 確保 token 有效，如果即將過期或已過期則自動刷新
 * @param {Object} firebaseUser - Firebase 用戶對象（可選）
 * @returns {Promise<string|null>} 有效的 token 或 null
 */
async function ensureValidToken(firebaseUser = null) {
  const token = localStorage.getItem('auth_token');
  
  // 如果沒有 token，返回 null（允許匿名使用）
  if (!token) {
    console.log('[Auth] 沒有 token，允許匿名使用');
    return null;
  }
  
  // 檢查是否已過期
  if (isTokenExpired(token)) {
    console.log('[Auth] Token 已過期，嘗試刷新...');
    if (firebaseUser) {
      return await refreshAuthToken(firebaseUser);
    } else {
      // 沒有 Firebase 用戶，無法刷新，清除過期 token
      console.warn('[Auth] Token 已過期且無法刷新，清除 token');
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user_data');
      return null;
    }
  }
  
  // 檢查是否即將過期
  if (isTokenExpiringSoon(token)) {
    console.log('[Auth] Token 即將過期（5 分鐘內），嘗試刷新...');
    if (firebaseUser) {
      return await refreshAuthToken(firebaseUser);
    } else {
      // 沒有 Firebase 用戶，但 token 還有效，繼續使用
      console.log('[Auth] Token 即將過期但無法刷新，繼續使用現有 token');
      return token;
    }
  }
  
  // Token 有效且未即將過期
  console.log('[Auth] Token 有效，無需刷新');
  return token;
}

/**
 * 獲取有效的 Authorization header
 * @param {Object} firebaseUser - Firebase 用戶對象（可選）
 * @returns {Promise<Object>} 包含 Authorization header 的對象
 */
async function getAuthHeaders(firebaseUser = null) {
  const token = await ensureValidToken(firebaseUser);
  const headers = {};
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  return headers;
}

// 導出函數（如果使用模組系統）
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    decodeJWT,
    isTokenExpiringSoon,
    isTokenExpired,
    refreshAuthToken,
    ensureValidToken,
    getAuthHeaders
  };
}

