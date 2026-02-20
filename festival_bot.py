====================================
from googleapiclient.discovery import build
from datetime import datetime
import requests
import urllib.parse
import os



GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL")

if not GOOGLE_API_KEY:
    raise ValueError("❌ GOOGLE_API_KEY not found in .env")

if not OPENROUTER_API_KEY:
    raise ValueError("❌ OPENROUTER_API_KEY not found in .env")


def get_today_festival():
    try:
        service = build("calendar", "v3", developerKey=GOOGLE_API_KEY)

        today = datetime.utcnow().date().isoformat()

        events_result = service.events().list(
            calendarId="en.indian#holiday@group.v.calendar.google.com",
            timeMin=today + "T00:00:00Z",
            timeMax=today + "T23:59:59Z",
            singleEvents=True
        ).execute()

        events = events_result.get("items", [])

        if not events:
            return None

        return events[0]["summary"]

    except Exception as e:
        print("❌ Error fetching festival:", e)
        return None



def generate_post(festival):

    prompt = f"""
    Write a short engaging X (Twitter) post for the Indian festival: {festival}.
    Keep it under 200 characters.
    Add emojis and 3 relevant hashtags.
    Make it warm and festive.
    """

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data
        )

        result = response.json()

        return result["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print("❌ OpenRouter error:", e)
        return None


def open_x_with_text(text):
    encoded_text = urllib.parse.quote_plus(text)
    url = f"https://twitter.com/intent/tweet?text={encoded_text}"
    print("\n🌐 Post on X using this link:\n")
    print(url)



def main():
    print("🔎 Checking today's Indian festival...")

    festival = get_today_festival()

    if not festival:
        print("📭 No Indian festival today.")
        return

    print(f"🎉 Today's Festival: {festival}")
    print("🤖 Generating caption via OpenRouter...")

    post_text = generate_post(festival)

    if not post_text:
        print("❌ Failed to generate post.")
        return

    print("\n📝 Generated Post:\n")
    print(post_text)

    print("\n🌐 Opening X...")
    open_x_with_text(post_text)


if __name__ == "__main__":
    main()