import os
import requests
import tweepy
import logging
from datetime import datetime
from googleapiclient.discovery import build

# ==============================
# ENV VARIABLES
# ==============================

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TEXT_MODEL = os.getenv("OPENROUTER_TEXT_MODEL")
IMAGE_MODEL = os.getenv("OPENROUTER_IMAGE_MODEL")

X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")

# ==============================
# LOGGING
# ==============================

logging.basicConfig(level=logging.INFO)

# ==============================
# GET TODAY FESTIVAL
# ==============================

def get_today_festival():

    service = build("calendar", "v3", developerKey=GOOGLE_API_KEY)

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

# ==============================
# OPENROUTER TEXT CALL
# ==============================

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

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60
    )

    data = response.json()

    print("OpenRouter Response:", data)

    if "choices" not in data:
        raise Exception(f"OpenRouter error: {data}")

    return data["choices"][0]["message"]["content"].strip()

# ==============================
# RESEARCH FESTIVAL
# ==============================

def research_festival(festival):

    prompt = f"""
Research the Indian festival: {festival}

Return:

CULTURAL_SIGNIFICANCE:
2 short sentences

KEY_SYMBOLS:
comma separated

TRADITIONAL_COLORS:
comma separated

DECORATIVE_ELEMENTS:
comma separated
"""

    return call_openrouter_text(prompt)

# ==============================
# CAPTION GENERATION
# ==============================

def generate_caption(festival, research):

    prompt = f"""
Using this research:

{research}

Write a warm natural X post about {festival}.

Rules:
- Under 220 characters
- Use only 2-3 emojis
- Avoid robotic tone
- End with 2 meaningful hashtags
"""

    return call_openrouter_text(prompt)

# ==============================
# IMAGE PROMPT
# ==============================

def generate_image_prompt(festival, research):

    prompt = f"""
Create a high quality image prompt for {festival} festival.

Use this cultural research:

{research}

Requirements:
- elegant decorative border
- traditional Indian colors
- cinematic lighting
- centered composition
- no text
- no watermark
- 1024x1024
"""

    return call_openrouter_text(prompt)

# ==============================
# GENERATE IMAGE (FLUX)
# ==============================

def generate_image(image_prompt):

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": IMAGE_MODEL,
        "prompt": image_prompt,
        "size": "1024x1024"
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/images/generations",
        headers=headers,
        json=payload,
        timeout=120
    )

    data = response.json()

    print("Image API Response:", data)

    if "data" not in data:
        raise Exception(f"Image generation error: {data}")

    image_url = data["data"][0]["url"]

    image_data = requests.get(image_url).content

    filename = "festival.png"

    with open(filename, "wb") as f:
        f.write(image_data)

    return filename

# ==============================
# POST TO X
# ==============================

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
    print("🔗 Tweet URL:", tweet_url)

    return tweet_url

# ==============================
# MAIN PIPELINE
# ==============================

def main():

    print("🔎 Checking today's Indian festival...")

    festival = get_today_festival()

    if not festival:
        print("No festival today.")
        return

    print("🎉 Today's Festival:", festival)

    research = research_festival(festival)

    caption = generate_caption(festival, research)

    image_prompt = generate_image_prompt(festival, research)

    image_path = generate_image(image_prompt)

    tweet_url = post_to_x(caption, image_path)

    print("Tweet URL:", tweet_url)


if __name__ == "__main__":
    main()
