import os
import re
import tempfile
import requests
from bs4 import BeautifulSoup
import pandas as pd
from deep_translator import GoogleTranslator

translator = GoogleTranslator(source="cs", target="en")
base_url = "https://www.pohary-bauer.cz"

# Reuse connections (faster + more reliable on hosted envs)
session = requests.Session()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}
TIMEOUT = (10, 30)  # (connect timeout, read timeout)


def extract_model_sport(text: str):
    terms_to_clean = [
        "Akrylátová",
        "medaile",
        "ozdoba",
        "Dřevěná",
        "trofej",
        "plaketa",
        "Plaketa",
        "Medaile",
        "Skleněná",
        "-",
        "kombinace",
        "skla",
        "a",
        "dřeva",
        "s",
        "potiskem",
        "Kovová",
        "Designová"
    ]
    for term in terms_to_clean:
        text = re.sub(r"\b" + re.escape(term) + r"\b", "", text)

    parts = text.strip().split("|")
    model = parts[0].strip() if parts else ""
    sport = parts[1].strip() if len(parts) > 1 else "Unknown Sport"
    return model, sport


def get_image_url(product_page_url: str, debug_fn=None) -> str:
    try:
        response = session.get(product_page_url, headers=HEADERS, timeout=TIMEOUT)
        if debug_fn:
            debug_fn(
                f"[PROD] {product_page_url} status={response.status_code} len={len(response.text)}"
            )
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        img_tag = soup.find("a", class_="product-gallery__link nounderline")

        if img_tag and img_tag.get("href"):
            href = img_tag["href"].strip()

            # Handle //..., /..., or https://...
            if href.startswith("//"):
                return "https:" + href
            if href.startswith("/"):
                return base_url + href
            if href.startswith("http"):
                return href

        return "Image Not Found"
    except Exception as e:
        if debug_fn:
            debug_fn(f"[PROD] Failed to retrieve image from {product_page_url}: {e}")
        return "Image Not Found"


def download_image(image_url: str, save_path: str, debug_fn=None) -> bool:
    try:
        response = session.get(image_url, headers=HEADERS, timeout=TIMEOUT)
        if debug_fn:
            debug_fn(
                f"[IMG] {image_url} status={response.status_code} bytes={len(response.content)}"
            )
        response.raise_for_status()

        with open(save_path, "wb") as f:
            f.write(response.content)
        return True
    except Exception as e:
        if debug_fn:
            debug_fn(f"[IMG] Error downloading {image_url}: {e}")
        return False


def _safe_ext_from_url(url: str) -> str:
    """
    Extract a safe extension from a URL, ignoring query strings.
    Falls back to .jpg.
    """
    clean = url.split("?", 1)[0].split("#", 1)[0]
    _, ext = os.path.splitext(clean)
    if not ext or len(ext) > 5:
        return ".jpg"
    return ext


def _safe_filename(name: str) -> str:
    """
    Make a filename safe across OSes by removing illegal characters.
    """
    # Replace spaces with underscores and strip illegal filename chars
    name = name.replace(" ", "_")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", name)
    return name.strip("_") or "image"


def scrape_product_range(
    url: str,
    range_name: str,
    range_code: str,
    product_category: str,
    product_material: str,
    progress_bar=None,
    debug_fn=None,
):
    temp_dir = tempfile.mkdtemp()

    # Step 1: collect basic info without downloading images
    product_info = []
    page = 1

    while True:
        page_url = f"{url}?strana={page}" if url.endswith("/") else f"{url}/?strana={page}"

        if debug_fn:
            debug_fn(f"[LIST] page={page} url={page_url}")

        # Heartbeat progress while we don't know total pages yet
        if progress_bar:
            progress_bar.progress(min(0.85, (page % 100) / 100))

        try:
            page_response = session.get(page_url, headers=HEADERS, timeout=TIMEOUT)
            if debug_fn:
                debug_fn(
                    f"[LIST] status={page_response.status_code} len={len(page_response.text)} "
                    f"head={page_response.text[:200]!r}"
                )
            page_response.raise_for_status()
        except Exception as e:
            if debug_fn:
                debug_fn(f"[LIST] Failed to fetch listing page {page_url}: {e}")
            break

        page_soup = BeautifulSoup(page_response.content, "html.parser")
        product_divs = page_soup.find_all("div", class_="swiper-slide cell cell--product")

        if debug_fn:
            debug_fn(f"[LIST] page={page} tiles_found={len(product_divs)}")

        if not product_divs:
            break

        for prod_div in product_divs:
            h3_tag = prod_div.find("h3", class_="listing-item__headline")
            a_tag = prod_div.find("a", class_="listing-item__image")

            if h3_tag and h3_tag.a and a_tag:
                product_text = h3_tag.a.get_text(strip=True)
                model, sport = extract_model_sport(product_text)

                # Translate sport (guarded; translation can fail on hosted envs)
                try:
                    translated_sport = translator.translate(sport)
                except Exception:
                    translated_sport = sport  # fallback

                product_page_relative = a_tag.get("href")
                product_page_url = (
                    base_url + product_page_relative if product_page_relative else ""
                )

                image_url = (
                    get_image_url(product_page_url, debug_fn=debug_fn)
                    if product_page_url
                    else "Image Not Found"
                )

                product_info.append(
                    {
                        "model": model,
                        "sport": translated_sport,
                        "product_page_url": product_page_url,
                        "image_url": image_url,
                    }
                )

        page += 1

    total_products = len(product_info)
    if total_products == 0:
        if debug_fn:
            debug_fn(
                "No products collected. Selectors may have failed or the site returned a block/consent page."
            )
        return pd.DataFrame([]), temp_dir

    if progress_bar:
        progress_bar.progress(0)

    # Step 2: download images and build final rows
    products = []
    for idx, info in enumerate(product_info):
        model = info["model"]
        translated_sport = info["sport"]
        image_url = info["image_url"]

        temp_image_path = None
        if image_url != "Image Not Found":
            ext = _safe_ext_from_url(image_url)
            image_filename = _safe_filename(model) + ext
            save_path = os.path.join(temp_dir, image_filename)

            download_success = download_image(image_url, save_path, debug_fn=debug_fn)
            temp_image_path = save_path if download_success else None

        product_data = {
            "model": model,
            "name": range_name,
            "sport": translated_sport,
            "product_code": range_code,
            "type": f"{product_category}_{product_material}",
            "image_url": image_url,
            "temp_image_path": temp_image_path,
        }
        products.append(product_data)

        if progress_bar:
            progress_bar.progress((idx + 1) / total_products)

    if progress_bar:
        progress_bar.progress(1.0)

    df = pd.DataFrame(products)
    return df, temp_dir
