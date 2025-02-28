import os
import re
import requests
import tempfile
from bs4 import BeautifulSoup
import pandas as pd
from deep_translator import GoogleTranslator

translator = GoogleTranslator(source='cs', target='en')
base_url = 'https://www.pohary-bauer.cz'

def extract_model_sport(text):
    terms_to_clean = [
        'Akrylátová', 'medaile', 'ozdoba', 'Dřevěná', 'trofej',
        'plaketa', 'Plaketa', 'Medaile', 'Skleněná', '-', 'kombinace',
        'skla', 'a', 'dřeva', 's', 'potiskem', 'Kovová'
    ]
    for term in terms_to_clean:
        text = re.sub(r'\b' + re.escape(term) + r'\b', '', text)
    parts = text.strip().split('|')
    model = parts[0].strip() if parts else ""
    sport = parts[1].strip() if len(parts) > 1 else "Unknown Sport"
    return model, sport

def get_image_url(product_page_url):
    try:
        response = requests.get(product_page_url)
        soup = BeautifulSoup(response.content, 'html.parser')
        img_tag = soup.find('a', class_='product-gallery__link nounderline')
        if img_tag and img_tag.get('href'):
            return 'https:' + img_tag['href']
        return "Image Not Found"
    except Exception as e:
        print(f"Failed to retrieve image from {product_page_url}: {e}")
        return "Image Not Found"

def download_image(image_url, save_path):
    try:
        response = requests.get(image_url)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return True
        else:
            print(f"Failed to download image: {image_url} (Status code: {response.status_code})")
            return False
    except Exception as e:
        print(f"Error downloading image from {image_url}: {e}")
        return False

def scrape_product_range(url, range_name, range_code, product_category, product_material, progress_bar=None):
    temp_dir = tempfile.mkdtemp()
    product_info = []  # Step 1: collect basic info without downloading images.
    page = 1
    while True:
        if url.endswith('/'):
            page_url = f"{url}?strana={page}"
        else:
            page_url = f"{url}/?strana={page}"
        page_response = requests.get(page_url)
        page_soup = BeautifulSoup(page_response.content, 'html.parser')
        product_divs = page_soup.find_all('div', class_="swiper-slide cell cell--product")
        if not product_divs:
            break
        for prod_div in product_divs:
            h3_tag = prod_div.find('h3', class_="listing-item__headline")
            a_tag = prod_div.find('a', class_="listing-item__image")
            if h3_tag and h3_tag.a and a_tag:
                product_text = h3_tag.a.get_text(strip=True)
                model, sport = extract_model_sport(product_text)
                translated_sport = translator.translate(sport)
                product_page_relative = a_tag.get('href')
                product_page_url = base_url + product_page_relative if product_page_relative else ""
                image_url = get_image_url(product_page_url) if product_page_url else "Image Not Found"
                product_info.append({
                    "model": model,
                    "sport": translated_sport,
                    "product_page_url": product_page_url,
                    "image_url": image_url,
                })
        page += 1

    total_products = len(product_info)
    if progress_bar:
        progress_bar.progress(0)
    products = []
    for idx, info in enumerate(product_info):
        model = info["model"]
        translated_sport = info["sport"]
        image_url = info["image_url"]
        if image_url != "Image Not Found":
            _, ext = os.path.splitext(image_url)
            if not ext:
                ext = ".jpg"
            image_filename = model.replace(" ", "_") + ext
            save_path = os.path.join(temp_dir, image_filename)
            download_success = download_image(image_url, save_path)
            temp_image_path = save_path if download_success else None
        else:
            temp_image_path = None
        product_data = {
            "model": model,
            "name": range_name,
            "sport": translated_sport,
            "product_code": range_code,
            "type": f"{product_category}_{product_material}",
            "image_url": image_url,
            "temp_image_path": temp_image_path
        }
        products.append(product_data)
        if progress_bar:
            progress_bar.progress((idx + 1) / total_products)
    if progress_bar:
        progress_bar.progress(1.0)
    df = pd.DataFrame(products)
    return df, temp_dir
