const chat = document.getElementById('chat')
const userIdInput = document.getElementById('user_id')
const textInput = document.getElementById('text')
const sendBtn = document.getElementById('send')

// Use server-side markdown rendering for DRY principle
// All markdown processing is now done by the unified Python module
async function renderMarkdown(md) {
  if (!md) return ''
  
  try {
    const apiBaseRaw = (window.__DEV_API_BASE || '').trim()
    const apiBase = apiBaseRaw.endsWith('/') ? apiBaseRaw.slice(0, -1) : apiBaseRaw
    const url = apiBase ? `${apiBase}/api/render-markdown` : '/api/render-markdown'
    
    console.log('[renderMarkdown] Calling API:', url)
    console.log('[renderMarkdown] Input markdown length:', md.length)
    
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: md, for_telegram: false }),
    })
    
    console.log('[renderMarkdown] Response status:', resp.status)
    
    if (!resp.ok) {
      const errorText = await resp.text()
      console.error('[renderMarkdown] API error:', resp.status, errorText)
      throw new Error(`HTTP ${resp.status}: ${errorText}`)
    }
    
    const data = await resp.json()
    console.log('[renderMarkdown] Response data:', data)
    return data.html || ''
  } catch (e) {
    console.error('[renderMarkdown] Failed:', e)
    // Fallback: return plain text with HTML escaping
    return escapeHtml(md)
  }
}

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '<').replace(/>/g, '>')
}

async function appendMessage(role, text) {
  const el = document.createElement('div')
  el.className = 'msg ' + role

  const prefix = role === 'user' ? 'You: ' : 'Bot: '

  if (role === 'user') {
    // keep user input as plain text to avoid injection
    el.textContent = prefix + text
  } else {
    // Use server-side markdown rendering for consistent output with Telegram
    const html = await renderMarkdown(text)
    if (window.DOMPurify && typeof DOMPurify.sanitize === 'function') {
      // Wrap prefix in a span to separate it from block-level HTML elements
      el.innerHTML = '<span class="msg-prefix">' + prefix + '</span>' + DOMPurify.sanitize(html)
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
