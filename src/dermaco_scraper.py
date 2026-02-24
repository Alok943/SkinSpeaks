import requests
from bs4 import BeautifulSoup
import json
import time
import os
import re

class DermaCoScraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.base_url = "https://thedermaco.com"
        
        # Filter out bundles, gifts, and hidden pages to keep our Latent Space clean
        self.skip_tags = {
            "hidden", "combo", "gift", "accessories", "search-hide", "b1g1"
        }

    def should_skip_product(self, tags: list) -> bool:
        tags_lower = {t.lower().strip() for t in tags}
        return bool(tags_lower & self.skip_tags)

    def extract_clean_text_from_html(self, html_content: str) -> str:
        """Utility to strip HTML tags and return pure text for Vector Embeddings."""
        if not html_content:
            return ""
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        return re.sub(r'\s+', ' ', text).strip()

    # --- DOM Extraction Helpers (Based on Inspector Screenshots) ---

    def extract_description(self, soup) -> str:
        """Extracts the main product description from the hidden full-text div."""
        desc_div = soup.find('div', class_=lambda c: c and 'hdt-full-des' in c)
        if desc_div:
            return self.extract_clean_text_from_html(str(desc_div))
        return ""

    def extract_ingredients(self, soup) -> str:
        """Extracts the full ingredients list from the accordion."""
        details = soup.find('details', class_=lambda c: c and 'ingredients-list' in c)
        if details:
            desc_div = details.find('div', class_='product-detail-card-description')
            if desc_div:
                return self.extract_clean_text_from_html(str(desc_div))
        return ""

    def extract_suitable_for(self, soup) -> str:
        """Extracts the 'Suitable For' data to boost skin-type intent matching."""
        details = soup.find('details', class_=lambda c: c and 'suitable-for' in c)
        if details:
            content_divs = details.find_all('div', class_='product-detail-card-content')
            suitability_texts = [div.get_text(separator=' ', strip=True) for div in content_divs if div.get_text(strip=True)]
            return ", ".join(suitability_texts)
        return ""

    # --- Core Scraping Logic ---

    def get_all_product_urls(self, limit=250):
        """Fetches product URLs + metadata using Shopify's products.json API."""
        print(f"Fetching product catalog from The Derma Co...")
        catalog_url = f"{self.base_url}/products.json?limit={limit}"
        try:
            response = requests.get(catalog_url, headers=self.headers)
            if response.status_code == 200:
                products = response.json().get('products', [])
                result = []
                for item in products:
                    tags = item.get("tags", [])
                    if not self.should_skip_product(tags):
                        # Pack basic metadata right away to save HTTP calls later
                        meta = {
                            "url": f"{self.base_url}/products/{item['handle']}",
                            "title": item.get('title', ''),
                            "type": item.get('product_type', ''),
                            "price": item['variants'][0]['price'] if item.get('variants') else "0.00",
                            "image": item['images'][0]['src'] if item.get('images') else "",
                            "tags": tags
                        }
                        result.append(meta)
                print(f"✅ Found {len(result)} valid products")
                return result
            else:
                print(f"Failed catalog fetch: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error: {e}")
            return []

    def scrape_product(self, meta: dict) -> dict | None:
        """Scrapes the HTML for a single product to get high-signal text."""
        product_url = meta["url"]
        print(f"  Scraping DOM: {product_url.split('/products/')[-1]}")
        try:
            # Fetch Full HTML page specifically for the clean Description/Ingredients
            html_response = requests.get(product_url, headers=self.headers)
            soup = BeautifulSoup(html_response.text, 'html.parser')
            
            clean_description = self.extract_description(soup)
            full_ingredients = self.extract_ingredients(soup)
            suitable_for = self.extract_suitable_for(soup)
            
            product_data = {
                "brand": "The Derma Co",
                "product_name": meta["title"].strip(),
                "description": clean_description[:800], # Truncated for mpnet-base-v2 token limits
                "price": float(meta["price"]),
                "rating": None, # Skipping Yotpo/Judge.me JS rendering for speed MVP
                "review_count": None,
                "product_url": product_url,
                "image_url": meta["image"],
                "category": meta["type"].strip(),
                "target_concerns": suitable_for if suitable_for else ", ".join([t for t in meta["tags"] if len(t) > 3]),
                "ingredients": full_ingredients,
                "tags": ", ".join(meta["tags"]),
            }
            return product_data

        except Exception as e:
            print(f"  ❌ Failed: {product_url} — {e}")
            return None

if __name__ == "__main__":
    scraper = DermaCoScraper()
    output_path = "data/dermaco_products.json"
    os.makedirs("data", exist_ok=True)

    # 1. Load existing data
    existing_data = []
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)

    existing_urls = {item["product_url"] for item in existing_data}
    print(f"\n📁 Already scraped: {len(existing_urls)} products")
    
    # 2. Fetch Catalog
    all_products = scraper.get_all_product_urls(limit=250)
    
    # 3. Delta Filter
    to_scrape = [meta for meta in all_products if meta["url"] not in existing_urls]

    if not to_scrape:
        print("✅ Database up to date.")
    else:
        print(f"\n🚀 Scraping {len(to_scrape)} new products...\n")
        newly_added = 0
        for idx, meta in enumerate(to_scrape, 1):
            print(f"[{idx}/{len(to_scrape)}]", end=" ")
            data = scraper.scrape_product(meta)
            if data:
                existing_data.append(data)
                newly_added += 1
            time.sleep(1.5) # Polite scraping to avoid IP bans

        # 4. Save combined dataset
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=4, ensure_ascii=False)
        print(f"\n✅ Done! Added {newly_added} products. Total: {len(existing_data)} in database.")
        print(f"📄 Saved to: {output_path}")