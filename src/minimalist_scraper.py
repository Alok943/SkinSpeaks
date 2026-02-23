import requests
from bs4 import BeautifulSoup
import json
import time
import os
import re

class MinimalistScraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.base_url = "https://beminimalist.co"

        # Tags that are internal/noise and should be removed from concerns
        self.noise_tags = {
            "treat", "score:99", "score:98", "score:97", "score:96", "score:95",
            "hidden", "hide", "bonsai_excluded", "exclude_rebuy",
            "exclude_recommendations", "exclude_review", "hidden recommendation",
            "hide-app", "hide_app", "judgeme_excluded", "kwikcart-freebie",
            "search-hide", "searchanise_ignore", "smart-cart-hide-bundle-options",
            "wizzy-ignore", "__hidden", "exclude from back in stock",
            "summer", "winter", "new", "bestseller", "serum", "moisturizer",
            "cleanser", "sunscreen", "toner", "peel", "oil", "lotion", "cream"
        }

        # Tags that indicate a product should be skipped entirely
        self.skip_tags = {
            "searchanise_ignore", "wizzy-ignore", "hidden", "__hidden",
            "search-hide", "kwikcart-freebie"
        }

    def should_skip_product(self, tags: list) -> bool:
        """Returns True if product is internal/hidden and should not be scraped."""
        tags_lower = {t.lower().strip() for t in tags}
        return bool(tags_lower & self.skip_tags)

    def clean_tags_to_concerns(self, tags: list) -> str:
        """
        Filters noise from Shopify tags and returns meaningful
        concern/benefit tags as a clean comma-separated string.
        Example output: "Dark spots, Hydration, Acne, Dullness, Skin texture"
        """
        cleaned = []
        for tag in tags:
            tag_stripped = tag.strip()
            if tag_stripped.lower() not in self.noise_tags:
                # Also skip tags that are purely numeric or very short
                if len(tag_stripped) > 2 and not tag_stripped.replace(":", "").replace(".", "").isdigit():
                    cleaned.append(tag_stripped)
        return ", ".join(cleaned)

    def extract_ingredients(self, soup) -> str:
        """
        Extracts active ingredient descriptions from Shopify toggle tabs.
        Stops before FAQ/specification sections to avoid noise.
        """
        ingredients_list = []
        tabs = soup.find_all('toggle-tab', class_=lambda c: c and 'toggle--faq' in c)

        # FAQ section headers we want to stop at
        stop_keywords = [
            "what are product specifications",
            "how does",
            "can i use",
            "is the product pregnancy",
            "what is the recommended age",
            "does this product cause",
            "can this product be used",
            "what kind of damage",
            "is lactic acid",
            "how to use",
        ]

        for tab in tabs:
            title_span = tab.find('span', class_='text-weight--bold')
            title = title_span.get_text(strip=True) if title_span else ""

            # Stop if we've hit FAQ territory
            if any(kw in title.lower() for kw in stop_keywords):
                break

            content_div = tab.find('div', class_='toggle__content')
            desc = ""
            if content_div:
                desc_span = content_div.find('span', class_='metafield-multi_line_text_field')
                desc = desc_span.get_text(strip=True) if desc_span else content_div.get_text(strip=True)

            # Clean up the "All Ingredients" raw list — keep it but truncate
            # at product specifications if it sneaks through
            if "what are product specifications" in desc.lower():
                desc = desc[:desc.lower().find("what are product specifications")].strip()

            if title and desc:
                ingredients_list.append(f"{title}: {desc}")

        return " | ".join(ingredients_list)

    def extract_description(self, json_data: dict) -> str:
        """
        Extracts clean product description from Shopify body_html field.
        Strips all HTML tags.
        """
        body_html = json_data.get("body_html", "")
        if not body_html:
            return ""
        soup = BeautifulSoup(body_html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        # Collapse multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def get_all_product_urls(self, limit=250):
        """
        Fetches product URLs and their tags using Shopify's products.json API.
        Returns a list of (url, tags) tuples so we can filter before scraping.
        """
        print(f"Fetching product catalog from Minimalist...")
        catalog_url = f"{self.base_url}/products.json?limit={limit}"
        try:
            response = requests.get(catalog_url, headers=self.headers)
            if response.status_code == 200:
                products = response.json().get('products', [])
                result = []
                for item in products:
                    tags = item.get("tags", [])
                    # Pre-filter hidden products before even visiting their pages
                    if not self.should_skip_product(tags):
                        url = f"{self.base_url}/products/{item['handle']}"
                        result.append((url, tags))
                print(f"✅ Found {len(result)} visible product URLs (filtered from {len(products)} total)")
                return result
            else:
                print(f"Failed to fetch catalog. Status: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error fetching catalog: {e}")
            return []

    def scrape_product(self, product_url: str, catalog_tags: list) -> dict | None:
        """
        Scrapes a single product page.
        catalog_tags: tags already fetched from products.json (avoids re-fetching)
        """
        print(f"  Scraping: {product_url.split('/products/')[-1]}")
        try:
            # 1. Shopify .js endpoint for structured data
            js_response = requests.get(f"{product_url}.js", headers=self.headers)
            if js_response.status_code != 200:
                print(f"  ⚠️  Could not fetch .js for {product_url}")
                return None
            json_data = js_response.json()

            # 2. Full HTML page for ingredients (metafields not in .js)
            html_response = requests.get(product_url, headers=self.headers)
            soup = BeautifulSoup(html_response.text, 'html.parser')

            # 3. Price (Shopify returns in paise, divide by 100)
            price = json_data.get("price", 0)
            formatted_price = round(price / 100, 2) if price else 0.0

            # 4. Image URL
            featured_image = json_data.get("featured_image", "")
            image_url = f"https:{featured_image}" if featured_image and not featured_image.startswith("http") else featured_image

            # 5. Clean concerns from tags (use catalog_tags which are more complete)
            concerns = self.clean_tags_to_concerns(catalog_tags)

            # 6. Description from body_html
            description = self.extract_description(json_data)

            # 7. Ingredients from toggle tabs
            ingredients = self.extract_ingredients(soup)

            product_data = {
                "brand": "Minimalist",
                "product_name": json_data.get("title", "").strip(),
                "description": description,
                "price": formatted_price,
                "product_url": product_url,
                "image_url": image_url,
                "category": json_data.get("type", "").strip(),
                "target_concerns": concerns,
                "ingredients": ingredients,
                "tags": ", ".join(catalog_tags),

                # Embedding text — pre-built concatenated field ready for embedder.py
                "embed_text": ""
            }

            # Build embed_text now so embedder.py just reads it directly
            product_data["embed_text"] = (
                f"Product: {product_data['product_name']}. "
                f"Description: {product_data['description']}. "
                f"Key Ingredients: {product_data['ingredients'][:800]}. "
                f"Good for: {product_data['target_concerns']}. "
                f"Category: {product_data['category']}."
            ).strip()

            return product_data

        except Exception as e:
            print(f"  ❌ Failed: {product_url} — {e}")
            return None


if __name__ == "__main__":
    scraper = MinimalistScraper()
    output_path = "data/minimalist_products.json"
    os.makedirs("data", exist_ok=True)

    # 1. Load existing scraped data
    existing_data = []
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)

    existing_urls = {item["product_url"] for item in existing_data}
    print(f"\n📁 Already scraped: {len(existing_urls)} products")

    # 2. Fetch visible product URLs with their tags (hidden ones already filtered)
    all_products = scraper.get_all_product_urls(limit=250)

    # 3. Delta filter — only scrape what's new
    to_scrape = [(url, tags) for url, tags in all_products if url not in existing_urls]

    if not to_scrape:
        print("✅ Database is up to date. Nothing new to scrape.")
    else:
        print(f"\n🚀 Scraping {len(to_scrape)} new products...\n")
        newly_added = 0

        for idx, (url, tags) in enumerate(to_scrape, 1):
            print(f"[{idx}/{len(to_scrape)}]", end=" ")
            data = scraper.scrape_product(url, tags)
            if data:
                existing_data.append(data)
                newly_added += 1

            # Be polite to the server
            time.sleep(2)

        # 4. Save combined dataset
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=4, ensure_ascii=False)

        print(f"\n✅ Done! Added {newly_added} products. Total: {len(existing_data)} in database.")
        print(f"📄 Saved to: {output_path}")