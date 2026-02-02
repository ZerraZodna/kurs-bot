Kurs Bot prototype

Run locally:

```powershell
venv\Scripts\activate
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

Expose webhook with ngrok:

```powershell
ngrok http 8000
# then set Telegram webhook to https://<ngrok-id>.ngrok.io/webhook/telegram
```