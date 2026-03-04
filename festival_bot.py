import base64
import logging
import os
import time
from datetime import datetime

import requests
from googleapiclient.discovery import build
from requests import HTTPError
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TEXT_MODEL = os.getenv("OPENROUTER_TEXT_MODEL", "openai/gpt-4o-mini")
IMAGE_MODEL = os.getenv("OPENROUTER_IMAGE_MODEL", "black-forest-labs/flux-1-schnell")
DEFAULT_IMAGE_MODELS = [
    IMAGE_MODEL,
    "black-forest-labs/flux-1-schnell",
    "black-forest-labs/flux-1-dev",
]
X_USERNAME = os.getenv("X_USERNAME")
X_PASSWORD = os.getenv("X_PASSWORD")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
SKIP_EXTERNAL_CALLS = os.getenv("SKIP_EXTERNAL_CALLS", "false").lower() == "true"
TEST_FESTIVAL = os.getenv("TEST_FESTIVAL", "Diwali")
ALLOW_TEXT_ONLY_POST = os.getenv("ALLOW_TEXT_ONLY_POST", "true").lower() == "true"


def _write_placeholder_image(path: str = "festival.png") -> str:
    pixel_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WmN7i4AAAAASUVORK5CYII="
    )
    with open(path, "wb") as f:
        f.write(pixel_png)
    return path


def validate_environment() -> None:
    if SKIP_EXTERNAL_CALLS:
        logger.info("SKIP_EXTERNAL_CALLS=true, skipping API key validation.")
        return

    missing = [
        name
        for name, value in {
            "GOOGLE_API_KEY": GOOGLE_API_KEY,
            "OPENROUTER_API_KEY": OPENROUTER_API_KEY,
            "OPENROUTER_TEXT_MODEL": TEXT_MODEL,
        }.items()
        if not value
    ]

    if DRY_RUN:
        logger.info("DRY_RUN=true, skipping X credential validation and posting.")
    else:
        for name, value in {"X_USERNAME": X_USERNAME, "X_PASSWORD": X_PASSWORD}.items():
            if not value:
                missing.append(name)

    if missing:
        raise EnvironmentError(f"Missing required environment variable(s): {', '.join(sorted(missing))}")


def get_today_festival() -> str | None:
    if SKIP_EXTERNAL_CALLS:
        logger.info("SKIP_EXTERNAL_CALLS=true, using local test festival: %s", TEST_FESTIVAL)
        return TEST_FESTIVAL

    service = build("calendar", "v3", developerKey=GOOGLE_API_KEY, cache_discovery=False)
    today = datetime.utcnow().date().isoformat()

    events = (
        service.events()
        .list(
            calendarId="en.indian#holiday@group.v.calendar.google.com",
            timeMin=today + "T00:00:00Z",
            timeMax=today + "T23:59:59Z",
            singleEvents=True,
        )
        .execute()
        .get("items", [])
    )

    if not events:
        return None
    return events[0].get("summary")


def _openrouter_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com",
        "X-Title": "festival-bot",
    }


def call_openrouter(prompt: str, model: str | None = None, timeout: int = 60) -> str:
    if SKIP_EXTERNAL_CALLS:
        if "Write a warm human X post" in prompt:
            return "Celebrating Diwali with lights, love, and togetherness ✨🪔💛 #IndianFestival #Diwali"
        if "Create an AI poster prompt" in prompt:
            return "Traditional Indian festive poster, marigold borders, diyas, rangoli, warm cinematic lighting, rich saffron and royal blue palette, no text"
        return (
            "CULTURAL_SIGNIFICANCE: Celebrates light over darkness and hope over fear.\n"
            "KEY_SYMBOLS: Diyas, rangoli, sweets, family gatherings.\n"
            "TRADITIONAL_COLORS: Saffron, gold, red, deep blue.\n"
            "DECORATIVE_ELEMENTS: Floral torans, lamps, and decorative patterns."
        )

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=_openrouter_headers(),
        json={"model": model or TEXT_MODEL, "messages": [{"role": "user", "content": prompt}]},
        timeout=timeout,
    )
    response.raise_for_status()

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Unexpected OpenRouter response format: {data}") from exc


def research_festival(festival: str) -> str:
    return call_openrouter(
        f"""
Research the Indian festival: {festival}

Return:
CULTURAL_SIGNIFICANCE
KEY_SYMBOLS
TRADITIONAL_COLORS
DECORATIVE_ELEMENTS
"""
    )


def generate_caption(festival: str, research: str) -> str:
    return call_openrouter(
        f"""
Using this research:

{research}

Write a warm human X post about {festival}.

Rules:
- under 220 characters
- 2–3 emojis
- natural tone
- end with 2 hashtags
"""
    )


def generate_image_prompt(festival: str, research: str) -> str:
    return call_openrouter(
        f"""
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
    )


def _request_image_from_model(prompt: str, model: str) -> str:
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=_openrouter_headers(),
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["image"],
            "image": {"size": "1024x1024"},
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    try:
        return data["choices"][0]["message"]["images"][0]["url"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Unexpected image response format: {data}") from exc


def generate_image(prompt: str) -> str | None:
    if SKIP_EXTERNAL_CALLS:
        out_path = _write_placeholder_image()
        logger.info("🖼️ Generated local placeholder image at %s", out_path)
        return out_path

    tried = []
    for model in dict.fromkeys(DEFAULT_IMAGE_MODELS):
        tried.append(model)
        try:
            image_url = _request_image_from_model(prompt, model)
            image_resp = requests.get(image_url, timeout=60)
            image_resp.raise_for_status()
            out_path = "festival.png"
            with open(out_path, "wb") as f:
                f.write(image_resp.content)
            logger.info("🖼️ Generated image with model: %s", model)
            return out_path
        except HTTPError as exc:
            body = exc.response.text if exc.response is not None else ""
            logger.warning("Image generation failed for model '%s': %s", model, body)
            if exc.response is None or exc.response.status_code not in (400, 404):
                break
        except Exception as exc:
            logger.warning("Image generation failed for model '%s': %s", model, exc)
            break

    logger.error("All image generation attempts failed for models: %s", ", ".join(tried))
    if DRY_RUN:
        out_path = _write_placeholder_image()
        logger.info("Using placeholder image in DRY_RUN mode: %s", out_path)
        return out_path
    return None


def post_to_x(caption: str, image_path: str | None) -> None:
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    try:
        logger.info("Opening X login...")
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

        if image_path:
            upload = driver.find_element(By.XPATH, "//input[@type='file']")
            upload.send_keys(os.path.abspath(image_path))
            time.sleep(5)
        else:
            logger.warning("Posting without image.")

        post_button = driver.find_element(By.XPATH, "//div[@data-testid='tweetButton']")
        post_button.click()
        time.sleep(6)
        logger.info("✅ Tweet posted")
    finally:
        driver.quit()


def main() -> None:
    logger.info("TEXT MODEL: %s", TEXT_MODEL)
    validate_environment()
    logger.info("🔎 Checking today's Indian festival...")

    festival = get_today_festival()
    if not festival:
        logger.info("No festival today")
        return

    logger.info("🎉 Today's Festival: %s", festival)
    research = research_festival(festival)
    caption = generate_caption(festival, research)
    image_prompt = generate_image_prompt(festival, research)
    image_path = generate_image(image_prompt)

    if DRY_RUN:
        logger.info("DRY RUN OUTPUT")
        logger.info("Caption: %s", caption)
        logger.info("Image prompt: %s", image_prompt)
        logger.info("Image path: %s", image_path)
        return

    if image_path is None and not ALLOW_TEXT_ONLY_POST:
        raise RuntimeError("Image generation failed and ALLOW_TEXT_ONLY_POST=false")

    post_to_x(caption, image_path)


if __name__ == "__main__":
    main()
