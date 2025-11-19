;(function (global) {
  const DEFAULT_DURATION = 4000
  let toastContainer = null

  function ensureContainer() {
    if (!toastContainer) {
      toastContainer = document.createElement('div')
      toastContainer.id = 'global-toast-container'
      toastContainer.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        z-index: 9999;
        pointer-events: none;
      `
      document.body.appendChild(toastContainer)
    }
  }

  function createToastElement(message, type) {
    const toast = document.createElement('div')
    const bgColor = {
      success: 'rgba(16, 185, 129, 0.95)',
      info: 'rgba(59, 130, 246, 0.95)',
      warning: 'rgba(245, 158, 11, 0.95)',
      error: 'rgba(239, 68, 68, 0.95)'
    }[type] || 'rgba(30, 64, 175, 0.95)'

    toast.style.cssText = `
      min-width: 260px;
      max-width: 360px;
      color: #fff;
      padding: 12px 16px;
      border-radius: 10px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.2);
      font-size: 14px;
      line-height: 1.4;
      backdrop-filter: blur(6px);
      background: ${bgColor};
      pointer-events: auto;
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      opacity: 0;
      transform: translateY(-10px);
      transition: opacity 0.25s ease, transform 0.25s ease;
    `

    const text = document.createElement('div')
    text.textContent = message

    const closeBtn = document.createElement('button')
    closeBtn.textContent = '×'
    closeBtn.style.cssText = `
      border: none;
      background: transparent;
      color: inherit;
      font-size: 16px;
      cursor: pointer;
      padding: 0;
    `
    closeBtn.onclick = () => removeToast(toast)

    toast.appendChild(text)
    toast.appendChild(closeBtn)
    return toast
  }

  function removeToast(toast) {
    toast.style.opacity = '0'
    toast.style.transform = 'translateY(-10px)'
    setTimeout(() => toast.remove(), 250)
  }

  function showToast(message, options = {}) {
    const { type = 'info', duration = DEFAULT_DURATION } = options
    if (!message) return
    ensureContainer()

    const toast = createToastElement(message, type)
    toastContainer.appendChild(toast)

    requestAnimationFrame(() => {
      toast.style.opacity = '1'
      toast.style.transform = 'translateY(0)'
    })

    if (duration > 0) {
      setTimeout(() => removeToast(toast), duration)
    }
  }

  // 將函數暴露到全域
  global.showToast = showToast
})(window)

