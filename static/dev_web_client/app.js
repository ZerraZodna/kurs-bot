const chat = document.getElementById('chat')
const userIdInput = document.getElementById('user_id')
const textInput = document.getElementById('text')
const sendBtn = document.getElementById('send')

function appendMessage(role, text) {
  const el = document.createElement('div')
  el.className = 'msg ' + role

  const prefix = role === 'user' ? 'You: ' : 'Bot: '

  if (role === 'user') {
    // keep user input as plain text to avoid injection
    el.textContent = prefix + text
  } else {
    // render bot output as sanitized HTML when available
    if (window.DOMPurify && typeof DOMPurify.sanitize === 'function') {
      el.innerHTML = prefix + DOMPurify.sanitize(text)
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
  appendMessage('user', text)
  textInput.value = ''

  try {
    const apiBase = window.__DEV_API_BASE || ''
    const url = apiBase ? `${apiBase}/dev/message` : '/dev/message'
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, text }),
    })
    const data = await resp.json()
    appendMessage('bot', data.response || JSON.stringify(data))
  } catch (e) {
    appendMessage('bot', 'Request failed: ' + e.message)
  }
}

sendBtn.addEventListener('click', send)
textInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') send() })
