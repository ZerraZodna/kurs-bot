const chat = document.getElementById('chat')
const userIdInput = document.getElementById('user_id')
const textInput = document.getElementById('text')
const sendBtn = document.getElementById('send')

// Text is already HTML - just sanitize for security

async function appendMessage(role, text) {
  const el = document.createElement('div')
  el.className = 'msg ' + role

  const prefix = role === 'user' ? 'You: ' : 'Bot: '

  if (role === 'user') {
    // keep user input as plain text to avoid injection
    el.textContent = prefix + text
  } else {
    // Text is already HTML - just sanitize for security
    if (window.DOMPurify && typeof DOMPurify.sanitize === 'function') {
      // Wrap prefix in a span to separate it from block-level HTML elements
      el.innerHTML = '<span class="msg-prefix">' + prefix + '</span>' + DOMPurify.sanitize(text)
    } else {
      // fallback: plain text
      el.textContent = prefix + text
    }
  }

  chat.appendChild(el)
  chat.scrollTop = chat.scrollHeight
}

async function send() {
  const user_id = parseInt(userIdInput.value || '1')
  const text = textInput.value || ''
  if (!text) return
  
  // Add user message immediately
  const userEl = document.createElement('div')
  userEl.className = 'msg user'
  userEl.textContent = 'You: ' + text
  chat.appendChild(userEl)
  chat.scrollTop = chat.scrollHeight
  
  textInput.value = ''

  try {
    const apiBaseRaw = (window.__DEV_API_BASE || '').trim()
    const apiBase = apiBaseRaw.endsWith('/') ? apiBaseRaw.slice(0, -1) : apiBaseRaw
    const url = apiBase ? `${apiBase}/dev/message` : '/dev/message'
    console.log('DEV UI fetch url:', url)
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, text }),
    })
    const raw = await resp.text()
    let data
    try { data = JSON.parse(raw) } catch (_) { data = null }
    const body = data && typeof data === 'object'
      ? (data.response || raw)
      : raw
    
    // Use async appendMessage for bot response
    await appendMessage('bot', body || '(empty response)')
  } catch (e) {
    await appendMessage('bot', `Request failed: ${e.message} (url=${window.__DEV_API_BASE || '/'}dev/message)`)
    console.error('DEV UI fetch error', e)
  }
}

sendBtn.addEventListener('click', send)
textInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') send() })
