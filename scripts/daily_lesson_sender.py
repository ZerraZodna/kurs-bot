#!/usr/bin/env python3
"""
Daily ACIM Lesson Telegram Sender
Automates sending formatted HTML lessons via Telegram at 07:00 AM
"""

import sqlite3
import os
import datetime
import requests

# Configuration
DB_PATH = os.path.expanduser("~/kurs-bot/src/data/prod.db")
TELEGRAM_API = "https://api.telegram.org/bot"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Lesson counter (starts at 52)
LESSON_START = 52
# Last sent lesson (to avoid duplicates)
LAST_SENT_FILE = os.path.expanduser("~/kurs-bot/.last_lesson_sent")


def get_next_lesson():
    """Get the next lesson number to send"""
    try:
        with open(LAST_SENT_FILE) as f:
            last_lesson = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        last_lesson = LESSON_START - 1

    next_lesson = last_lesson + 1
    return next_lesson, last_lesson


def generate_html_lesson(lesson_id):
    """Generate HTML-formatted lesson content"""
    # Query database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT lesson_id, title, content, difficulty_level, duration_minutes
        FROM lessons
        WHERE lesson_id = ?
    """,
        (lesson_id,),
    )

    lesson = cursor.fetchone()
    conn.close()

    if not lesson:
        return None, f"Lesson {lesson_id} not found"

    lesson_id, title, content, difficulty, duration = lesson

    # Create HTML content with professional styling
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Lesson {lesson_id} - ACIM</title>
    <style>
        body {{
            font-family: 'Georgia', serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.8;
            color: #333;
        }}
        h1 {{
            color: #2c5f7c;
            border-bottom: 2px solid #e8e8e8;
            padding-bottom: 10px;
        }}
        .meta {{
            background: #f5f5f5;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
            font-style: italic;
        }}
        .point {{
            background: #f8f9fa;
            padding: 15px;
            margin: 20px 0;
            border-left: 4px solid #2c5f7c;
            border-radius: 0 5px 5px 0;
        }}
        .point-title {{
            font-weight: bold;
            color: #2c5f7c;
            margin-bottom: 10px;
        }}
        strong {{
            color: #198754;
        }}
    </style>
</head>
<body>
    <h1>Lesson {lesson_id}: {title}</h1>

    <div class="meta">
        <strong>Difficulty:</strong> {difficulty} | <strong>Duration:</strong> {duration} minutes
    </div>

    <div class="point">
        <div class="point-title">Lesson Content:</div>
        <p>{content}</p>
    </div>

    <p style="text-align: center; margin-top: 30px; color: #666;">
        <em>End of Lesson {lesson_id}</em>
    </p>
</body>
</html>"""

    return html_content, None


def send_lesson_to_telegram(lesson_id, html_content):
    """Send HTML lesson to Telegram"""
    # Save HTML file
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"lesson_{lesson_id}_{timestamp}.html"
    filepath = os.path.expanduser(f"~/kurs-bot/lessons/{filename}")

    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Send via Telegram API
    url = f"{TELEGRAM_API}{BOT_TOKEN}/sendDocument"
    files = {"document": open(filepath, "rb")}
    data = {"chat_id": CHAT_ID, "caption": f"📖 Lesson {lesson_id} - ACIM Daily Lesson", "parse_mode": "HTML"}

    try:
        response = requests.post(url, files=files, data=data, timeout=30)

        if response.status_code == 200:
            return True, f"Successfully sent Lesson {lesson_id}"
        else:
            return False, f"Failed to send lesson: {response.text}"
    except Exception as e:
        return False, f"Error sending lesson: {str(e)}"


def main():
    """Main execution"""
    print("=" * 60)
    print("Daily ACIM Lesson Telegram Sender")
    print("=" * 60)

    next_lesson, last_lesson = get_next_lesson()
    print(f"\nNext lesson to send: {next_lesson}")

    html_content, error = generate_html_lesson(next_lesson)

    if error:
        print(f"Error: {error}")
        return

    success, message = send_lesson_to_telegram(next_lesson, html_content)
    print(f"\n{message}")

    # Update last sent file
    with open(LAST_SENT_FILE, "w") as f:
        f.write(str(next_lesson))

    print(f"\nLast lesson sent: {next_lesson}")
    print("=" * 60)


if __name__ == "__main__":
    main()
