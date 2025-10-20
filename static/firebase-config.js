// static/firebase-config.js
// Firebase configuration for Social Avatar project

export const firebaseConfig = {
  apiKey: "AIzaSyBI2-4yEwzxvYOvui9FZiGAzCE22OhKmU8",
  authDomain: "social-avatar-d13c8.firebaseapp.com",
  projectId: "social-avatar-d13c8",
  storageBucket: "social-avatar-d13c8.appspot.com",
  messagingSenderId: "280598358339",
  appId: "1:280598358339:web:214a0d4ca53793163367f6"
};

// Optional: Export auth helper functions
export function getUserFromSession() {
  try {
    const user = sessionStorage.getItem('user');
    return user ? JSON.parse(user) : null;
  } catch {
    return null;
  }
}

export function requireAuth() {
  const user = getUserFromSession();
  if (!user) {
    window.location.href = '/static/landing.html';
    return false;
  }
  return true;
}
