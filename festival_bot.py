import os
import time
import requests
import tweepy
from datetime import datetime
from googleapiclient.discovery import build

# =============================
# ENV VARIABLES
# =============================

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TEXT_MODEL = os.getenv("OPENROUTER_TEXT_MODEL")
IMAGE_MODEL = os.getenv("OPENROUTER_IMAGE_MODEL")
print("TEXT MODEL:", TEXT_MODEL)
print("IMAGE MODEL:", IMAGE_MODEL)
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")

# =============================
# GOOGLE FESTIVAL FETCH
# =============================

def get_today_festival():

    service = build(
        "calendar",
        "v3",
        developerKey=GOOGLE_API_KEY,
        cache_discovery=False
    )

    today = datetime.utcnow().date().isoformat()

    events = service.events().list(
        calendarId="en.indian#holiday@group.v.calendar.google.com",
        timeMin=today + "T00:00:00Z",
        timeMax=today + "T23:59:59Z",
        singleEvents=True
    ).execute().get("items", [])

    if not events:
        return None

    return events[0]["summary"]

# =============================
# OPENROUTER TEXT CALL
# =============================

def call_openrouter_text(prompt):

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com",
        "X-Title": "festival-bot"
    }

    payload = {
        "model": TEXT_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    for attempt in range(3):

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )

        data = response.json()

        if "choices" in data:
            return data["choices"][0]["message"]["content"].strip()

        if "error" in data and data["error"].get("code") == 429:
            print("⚠️ Rate limited, retrying in 10 seconds...")
            time.sleep(10)
            continue

        raise Exception(f"OpenRouter error: {data}")

    raise Exception("OpenRouter failed after retries.")

# =============================
# RESEARCH
# =============================

def research_festival(festival):

    prompt = f"""
Research the Indian festival: {festival}

Return:
CULTURAL_SIGNIFICANCE
KEY_SYMBOLS
TRADITIONAL_COLORS
DECORATIVE_ELEMENTS
"""

    return call_openrouter_text(prompt)

# =============================
# CAPTION
# =============================

def generate_caption(festival, research):

    prompt = f"""
Using this research:

{research}

Write a warm human X post about {festival}.

Rules:
- under 220 characters
- 2–3 emojis
- natural tone
- end with 2 hashtags
"""

    return call_openrouter_text(prompt)

# =============================
# IMAGE PROMPT
# =============================

def generate_image_prompt(festival, research):

    prompt = f"""
Create a detailed AI art prompt for {festival}.

Use cultural elements:

{research}

Style:
traditional Indian decorative border,
festival colors,
cinematic lighting,
no text,
1024x1024
"""

    return call_openrouter_text(prompt)

# =============================
# IMAGE GENERATION
# =============================
def generate_image(prompt):

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": IMAGE_MODEL,
        "prompt": prompt
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/images/generations",
        headers=headers,
        json=payload,
        timeout=120
    )

    if response.status_code != 200:
        print("Image API error:", response.text)
        raise Exception("Image generation failed")

    data = response.json()

    if "data" not in data:
        raise Exception(f"Unexpected image response: {data}")

    image_url = data["data"][0]["url"]

    img = requests.get(image_url).content

    with open("festival.png", "wb") as f:
        f.write(img)

    return "festival.png"
# =============================
# POST TO X
# =============================

def post_to_x(caption, image_path):

    auth = tweepy.OAuth1UserHandler(
        X_API_KEY,
        X_API_SECRET,
        X_ACCESS_TOKEN,
        X_ACCESS_SECRET
    )

    api = tweepy.API(auth)

    media = api.media_upload(image_path)

    client = tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_SECRET
    )

    response = client.create_tweet(
        text=caption,
        media_ids=[media.media_id]
    )

    tweet_id = response.data["id"]

    username = api.verify_credentials().screen_name

    tweet_url = f"https://x.com/{username}/status/{tweet_id}"

    print("✅ Tweet Posted Successfully")
    print("🔗", tweet_url)

# =============================
# MAIN PIPELINE
# =============================

def main():

    print("🔎 Checking today's Indian festival...")

    festival = get_today_festival()

    if not festival:
        print("No festival today.")
        return

    print("🎉 Today's Festival:", festival)

    research = research_festival(festival)

    time.sleep(5)

    caption = generate_caption(festival, research)

    time.sleep(5)

    image_prompt = generate_image_prompt(festival, research)

    image_path = generate_image(image_prompt)

    post_to_x(caption, image_path)

# =============================

if __name__ == "__main__":
    main()
