/**
 * 認證工具函數
 * 用於管理 JWT token 和自動刷新
 */

// 配置：刷新時機（預設：在 token 過期前 10 分鐘刷新）
const TOKEN_REFRESH_THRESHOLD = 10 * 60 * 1000; // 10 分鐘（可調整）

// 配置：定期檢查間隔（預設：每 5 分鐘檢查一次）
const TOKEN_CHECK_INTERVAL = 5 * 60 * 1000; // 5 分鐘

// 全局變數：定期檢查的 timer
let tokenCheckTimer = null;

// 全局變數：錯誤通知回調函數
let errorNotificationCallback = null;

/**
 * 設定錯誤通知回調函數
 * @param {Function} callback - 接收錯誤訊息的回調函數 (message) => void
 */
function setErrorNotificationCallback(callback) {
  errorNotificationCallback = callback;
}

/**
 * 顯示錯誤通知
 */
function notifyError(message) {
  if (errorNotificationCallback) {
    errorNotificationCallback(message);
  } else {
    console.warn('[Auth] 錯誤通知:', message);
  }
}

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
 * 檢查 token 是否即將過期（在設定的時間內過期）
 */
function isTokenExpiringSoon(token) {
  if (!token) return true;
  
  const payload = decodeJWT(token);
  if (!payload || !payload.exp) return true;
  
  const expirationTime = payload.exp * 1000; // 轉換為毫秒
  const currentTime = Date.now();
  
  // 如果剩餘時間少於設定的閾值，視為即將過期
  return (expirationTime - currentTime) < TOKEN_REFRESH_THRESHOLD;
}

/**
 * 獲取 token 剩餘有效時間（毫秒）
 */
function getTokenRemainingTime(token) {
  if (!token) return 0;
  
  const payload = decodeJWT(token);
  if (!payload || !payload.exp) return 0;
  
  const expirationTime = payload.exp * 1000;
  const currentTime = Date.now();
  
  return Math.max(0, expirationTime - currentTime);
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
async function refreshAuthToken(firebaseUser, silent = false) {
  if (!firebaseUser) {
    const message = '無法刷新 token：沒有 Firebase 用戶';
    if (!silent) {
      notifyError(message);
    }
    console.warn('[Auth]', message);
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
      const errorMessage = errorData.error || `HTTP ${response.status}`;
      throw new Error(errorMessage);
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
    const message = `Token 刷新失敗: ${error.message}`;
    console.error('[Auth] ❌', message);
    if (!silent) {
      notifyError(message);
    }
    return null;
  }
}

/**
 * 確保 token 有效，如果即將過期或已過期則自動刷新
 * @param {Object} firebaseUser - Firebase 用戶對象（可選）
 * @param {boolean} silent - 是否靜默模式（不顯示錯誤通知）
 * @returns {Promise<string|null>} 有效的 token 或 null
 */
async function ensureValidToken(firebaseUser = null, silent = false) {
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
      return await refreshAuthToken(firebaseUser, silent);
    } else {
      // 沒有 Firebase 用戶，無法刷新，清除過期 token
      const message = 'Token 已過期且無法刷新，將以匿名方式使用';
      if (!silent) {
        notifyError(message);
      }
      console.warn('[Auth]', message);
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user_data');
      return null;
    }
  }
  
  // 檢查是否即將過期
  if (isTokenExpiringSoon(token)) {
    const remainingTime = getTokenRemainingTime(token);
    const minutes = Math.floor(remainingTime / 60000);
    console.log(`[Auth] Token 即將過期（剩餘 ${minutes} 分鐘），嘗試刷新...`);
    if (firebaseUser) {
      return await refreshAuthToken(firebaseUser, silent);
    } else {
      // 沒有 Firebase 用戶，但 token 還有效，繼續使用
      console.log('[Auth] Token 即將過期但無法刷新，繼續使用現有 token');
      return token;
    }
  }
  
  // Token 有效且未即將過期
  const remainingTime = getTokenRemainingTime(token);
  const minutes = Math.floor(remainingTime / 60000);
  console.log(`[Auth] Token 有效（剩餘 ${minutes} 分鐘），無需刷新`);
  return token;
}

/**
 * 獲取有效的 Authorization header
 * @param {Object} firebaseUser - Firebase 用戶對象（可選）
 * @param {boolean} silent - 是否靜默模式（不顯示錯誤通知）
 * @returns {Promise<Object>} 包含 Authorization header 的對象
 */
async function getAuthHeaders(firebaseUser = null, silent = false) {
  const token = await ensureValidToken(firebaseUser, silent);
  const headers = {};
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  return headers;
}

/**
 * 啟動定期檢查 token 狀態
 * 在頁面載入時自動檢查，並定期檢查 token 是否需要刷新
 * @param {Object} firebaseUser - Firebase 用戶對象（可選）
 */
function startTokenPeriodicCheck(firebaseUser = null) {
  // 清除現有的 timer（如果有的話）
  if (tokenCheckTimer) {
    clearInterval(tokenCheckTimer);
    tokenCheckTimer = null;
  }
  
  // 立即檢查一次
  ensureValidToken(firebaseUser, true).then(token => {
    if (token) {
      const remainingTime = getTokenRemainingTime(token);
      const minutes = Math.floor(remainingTime / 60000);
      console.log(`[Auth] 定期檢查：Token 有效（剩餘 ${minutes} 分鐘）`);
    } else {
      console.log('[Auth] 定期檢查：沒有有效的 token');
    }
  });
  
  // 設定定期檢查
  tokenCheckTimer = setInterval(() => {
    ensureValidToken(firebaseUser, true).then(token => {
      if (token) {
        const remainingTime = getTokenRemainingTime(token);
        const minutes = Math.floor(remainingTime / 60000);
        console.log(`[Auth] 定期檢查：Token 有效（剩餘 ${minutes} 分鐘）`);
      } else {
        console.log('[Auth] 定期檢查：沒有有效的 token');
      }
    });
  }, TOKEN_CHECK_INTERVAL);
  
  console.log(`[Auth] 已啟動定期檢查（每 ${TOKEN_CHECK_INTERVAL / 60000} 分鐘檢查一次）`);
}

/**
 * 停止定期檢查 token 狀態
 */
function stopTokenPeriodicCheck() {
  if (tokenCheckTimer) {
    clearInterval(tokenCheckTimer);
    tokenCheckTimer = null;
    console.log('[Auth] 已停止定期檢查');
  }
}

// 導出函數到全局作用域（瀏覽器環境）
if (typeof window !== 'undefined') {
  window.decodeJWT = decodeJWT;
  window.isTokenExpiringSoon = isTokenExpiringSoon;
  window.isTokenExpired = isTokenExpired;
  window.getTokenRemainingTime = getTokenRemainingTime;
  window.refreshAuthToken = refreshAuthToken;
  window.ensureValidToken = ensureValidToken;
  window.getAuthHeaders = getAuthHeaders;
  window.startTokenPeriodicCheck = startTokenPeriodicCheck;
  window.stopTokenPeriodicCheck = stopTokenPeriodicCheck;
  window.setErrorNotificationCallback = setErrorNotificationCallback;
}

// 導出函數（如果使用模組系統）
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    decodeJWT,
    isTokenExpiringSoon,
    isTokenExpired,
    getTokenRemainingTime,
    refreshAuthToken,
    ensureValidToken,
    getAuthHeaders,
    startTokenPeriodicCheck,
    stopTokenPeriodicCheck,
    setErrorNotificationCallback,
    TOKEN_REFRESH_THRESHOLD,
    TOKEN_CHECK_INTERVAL
  };
}

