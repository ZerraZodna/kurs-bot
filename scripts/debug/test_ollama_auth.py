import os
from ollama import Client

client = Client(
    host="https://ollama.com",
    headers={'Authorization': 'Bearer ' + os.environ.get('OLLAMA_API_KEY')}
)

messages = [
  {
    'role': 'user',
    'content': 'Why is the sky blue?',
  },
]

print(os.environ.get('OLLAMA_API_KEY'))

try:
  resp = client.chat('gpt-oss:120b', messages=messages, stream=False)
  if hasattr(resp, '__iter__') and not isinstance(resp, (str, bytes)):
    parts = list(resp)
    text = "".join((p.get('message', {}).get('content', '') for p in parts if isinstance(p, dict)))
    print("text:", text)
  else:
    print("resp:", resp)
except Exception as e:
  import traceback
  print("Exception calling client.chat:")
  traceback.print_exc()
