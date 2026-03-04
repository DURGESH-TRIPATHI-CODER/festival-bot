import os
import time
import requests
import urllib.parse
from datetime import datetime
from googleapiclient.discovery import build

# selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


# =============================
# ENV VARIABLES
# =============================

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TEXT_MODEL = os.getenv("OPENROUTER_TEXT_MODEL")

X_USERNAME = os.getenv("X_USERNAME")
X_PASSWORD = os.getenv("X_PASSWORD")

print("TEXT MODEL:", TEXT_MODEL)

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
# OPENROUTER TEXT
# =============================

def call_openrouter(prompt):

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

    if "choices" not in data:
        raise Exception(f"OpenRouter error: {data}")

    return data["choices"][0]["message"]["content"].strip()


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

    return call_openrouter(prompt)


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

    return call_openrouter(prompt)


# =============================
# IMAGE PROMPT
# =============================

def generate_image_prompt(festival, research):

    prompt = f"""
Create an AI poster prompt for {festival}.

Use:

{research}

Style:
Indian festive poster
traditional border
festival colors
cinematic lighting
no text
"""

    return call_openrouter(prompt)


# =============================
# IMAGE GENERATION (FLUX)
# =============================

def generate_image(prompt):

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com",
        "X-Title": "festival-bot"
    }

    payload = {
        "model": "black-forest-labs/flux-1-schnell",
        "prompt": prompt,
        "size": "1024x1024"
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/images/generations",
        headers=headers,
        json=payload,
        timeout=120
    )

    if response.status_code != 200:
        print("Flux API error:", response.text)
        raise Exception("Flux image generation failed")

    data = response.json()

    if "data" not in data:
        raise Exception(f"Unexpected Flux response: {data}")

    image_url = data["data"][0]["url"]

    img = requests.get(image_url).content

    with open("festival.png", "wb") as f:
        f.write(img)

    print("🖼️ Flux image generated")

    return "festival.png"
# =============================
# POST USING SELENIUM
# =============================

def post_to_x(caption, image_path):

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    print("Opening X login...")

    driver.get("https://x.com/login")

    time.sleep(10)

    username = driver.find_element(By.NAME, "text")
    username.send_keys(X_USERNAME)
    username.submit()

    time.sleep(6)

    password = driver.find_element(By.NAME, "password")
    password.send_keys(X_PASSWORD)
    password.submit()

    time.sleep(10)

    driver.get("https://x.com/compose/tweet")

    time.sleep(8)

    tweet_box = driver.find_element(By.XPATH, "//div[@role='textbox']")
    tweet_box.send_keys(caption)

    upload = driver.find_element(By.XPATH, "//input[@type='file']")
    upload.send_keys(os.path.abspath(image_path))

    time.sleep(5)

    post_button = driver.find_element(By.XPATH, "//div[@data-testid='tweetButton']")
    post_button.click()

    time.sleep(6)

    print("✅ Tweet posted")

    driver.quit()


# =============================
# MAIN
# =============================

def main():

    print("🔎 Checking today's Indian festival...")

    festival = get_today_festival()

    if not festival:
        print("No festival today")
        return

    print("🎉 Today's Festival:", festival)

    research = research_festival(festival)

    time.sleep(3)

    caption = generate_caption(festival, research)

    time.sleep(3)

    image_prompt = generate_image_prompt(festival, research)

    image_path = generate_image(image_prompt)

    post_to_x(caption, image_path)


# =============================

if __name__ == "__main__":
    main()
