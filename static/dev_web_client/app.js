const chat = document.getElementById('chat')
const userIdInput = document.getElementById('user_id')
const textInput = document.getElementById('text')
const sendBtn = document.getElementById('send')

// Minimal Markdown -> HTML renderer for the dev web UI.
// Handles headings, bold (**text**), italic (*text*), bold-italic (***text***),
// inline code, paragraphs, line breaks, and simple unordered lists (- or *).
function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function markdownToHtml(md) {
  if (!md) return ''

  // Normalize line endings
  md = md.replace(/\r\n/g, '\n').replace(/\r/g, '\n')

  // Escape first to avoid accidental raw HTML; DOMPurify will still sanitize.
  md = escapeHtml(md)

  // Bold-italic ***text*** -> <strong><em>text</em></strong>
  md = md.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
  // Bold **text** or __text__
  md = md.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  md = md.replace(/__(.+?)__/g, '<strong>$1</strong>')
  // Italic *text* or _text_
  md = md.replace(/\*(.+?)\*/g, '<em>$1</em>')
  md = md.replace(/_(.+?)_/g, '<em>$1</em>')
  // Inline code `code`
  md = md.replace(/`([^`]+?)`/g, '<code>$1</code>')

  // Headings: # .. ######
  md = md.replace(/^######\s*(.+)$/gm, '<h6>$1</h6>')
  md = md.replace(/^#####\s*(.+)$/gm, '<h5>$1</h5>')
  md = md.replace(/^####\s*(.+)$/gm, '<h4>$1</h4>')
  md = md.replace(/^###\s*(.+)$/gm, '<h3>$1</h3>')
  md = md.replace(/^##\s*(.+)$/gm, '<h2>$1</h2>')
  md = md.replace(/^#\s*(.+)$/gm, '<h1>$1</h1>')

  // Lists: group consecutive lines starting with - or * into <ul>
  md = md.replace(/(^|\n)([ \t]*([-\*])\s+.+(?:\n[ \t]*[-\*]\s+.+)*)/g, function(_, pre, block) {
    const items = block.split(/\n/).map(l => l.replace(/^\s*[-\*]\s+/, ''))
    return pre + '<ul>' + items.map(i => '<li>' + i + '</li>').join('') + '</ul>'
  })

  // Paragraphs: split on double newlines
  const parts = md.split(/\n{2,}/g)
  const htmlParts = parts.map(p => {
    // If already a block element, leave as-is
    if (/^<h[1-6]>/.test(p) || /^<ul>/.test(p) ) return p.replace(/\n/g, '<br>')
    return '<p>' + p.replace(/\n/g, '<br>') + '</p>'
  })

  return htmlParts.join('\n')
}

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
      // Convert basic Markdown to HTML, then sanitize.
      const html = markdownToHtml(text)
      el.innerHTML = prefix + DOMPurify.sanitize(html)
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
