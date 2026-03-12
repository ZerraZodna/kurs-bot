const chat = document.getElementById('chat')
const userIdInput = document.getElementById('user_id')
const textInput = document.getElementById('text')
const sendBtn = document.getElementById('send')

function unescapeJsonString(text) {
  if (!text) return text
  // Mirror Python _unescape_json_string
  let result = text
  result = result.replace(/\\\\/g, '\\\\')  // \\\\ -> \\ first? No, Python does \\\\ -> \\ 
  result = result.replace(/\\\\n/g, '\\n')   // \\n -> \n (escaped newline)
  result = result.replace(/\\n/g, '\n')      // \n -> actual newline
  result = result.replace(/\\r/g, '\r')
  result = result.replace(/\\t/g, '\t')
  result = result.replace(/\\"/g, '"')
  result = result.replace(/\\'/g, "'")
  result = result.replace(/\\\//g, '/')
  return result
}

let streamBuffer = ''

async function appendMessage(role, text) {
  const el = document.createElement('div')
  el.className = 'msg ' + role

  const prefix = role === 'user' ? 'You: ' : 'Bot: '

  if (role === 'user') {
    el.textContent = prefix + text
  } else {
    if (window.DOMPurify && typeof DOMPurify.sanitize === 'function') {
      el.innerHTML = '<span class="msg-prefix">' + prefix + '</span>' + DOMPurify.sanitize(text)
    } else {
      el.textContent = prefix + text
    }
  }

  chat.appendChild(el)
  chat.scrollTop = chat.scrollHeight
}

async function* streamReader(reader) {
  let buffer = streamBuffer
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += new TextDecoder().decode(value)
    
    // Process complete lines (simulate buffering for escapes)
    let lines = buffer.split('\n')
    buffer = lines.pop() || ''  // last incomplete line to buffer
    for (let line of lines) {
      if (line.trim()) {
        yield unescapeJsonString(line)
      }
    }
  }
  if (buffer.trim()) {
    yield unescapeJsonString(buffer)
  }
  streamBuffer = ''
}

async function send() {
  const user_id = parseInt(userIdInput.value || '1')
  const text = textInput.value || ''
  if (!text) return
  
  // Add user message
  appendMessage('user', text)
  textInput.value = ''
  textInput.disabled = true
  sendBtn.disabled = true
  sendBtn.textContent = 'Sending...'

  // Create bot message container for streaming
  const botEl = document.createElement('div')
  botEl.className = 'msg bot streaming'
  botEl.innerHTML = '<span class="msg-prefix">Bot: </span><span class="streaming-text"></span>'
  const streamingText = botEl.querySelector('.streaming-text')
  chat.appendChild(botEl)
  chat.scrollTop = chat.scrollHeight

  try {
    const apiBaseRaw = (window.__DEV_API_BASE || '').trim()
    const apiBase = apiBaseRaw.endsWith('/') ? apiBaseRaw.slice(0, -1) : apiBaseRaw
    const url = `${apiBase}/dev/message` || '/dev/message'
    
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, text }),
    })

    if (!resp.body) {
      appendMessage('bot', '(no response body)')
      return
    }

    const reader = resp.body.getReader()
    for await (const chunk of streamReader(reader)) {
      streamingText.textContent += chunk
      chat.scrollTop = chat.scrollHeight
    }

    botEl.classList.remove('streaming')
    
  } catch (e) {
    streamingText.textContent = `Error: ${e.message}`
    console.error('Stream error', e)
  } finally {
    textInput.disabled = false
    sendBtn.disabled = false
    sendBtn.textContent = 'Send'
  }
}

sendBtn.addEventListener('click', send)
textInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') send() })
