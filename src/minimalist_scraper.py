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
                if len(tag_stripped) > 2 and not tag_stripped.replace(":", "").replace(".", "").isdigit():
                    cleaned.append(tag_stripped)
        return ", ".join(cleaned)

    def extract_description(self, soup) -> str:
        """
        Extracts product description from the page HTML.
        Targets span.metafield-multi_line_text_field inside span.product__subtitle
        which is where Minimalist stores their product blurb (confirmed via inspector).
        Grabs only the FIRST match to avoid pulling ingredient text.
        """
        # Target the product subtitle container first for specificity
        subtitle_spans = soup.find_all('span', class_='product__subtitle')
        for span in subtitle_spans:
            desc_span = span.find('span', class_='metafield-multi_line_text_field')
            if desc_span:
                text = desc_span.get_text(separator=' ', strip=True)
                text = re.sub(r'\s+', ' ', text).strip()
                if text:
                    return text

        # Fallback: first metafield-multi_line_text_field on page
        # (less specific but better than nothing)
        fallback = soup.find('span', class_='metafield-multi_line_text_field')
        if fallback:
            text = fallback.get_text(separator=' ', strip=True)
            return re.sub(r'\s+', ' ', text).strip()

        return ""

    def extract_ingredients(self, soup) -> str:
        """
        Extracts active ingredient descriptions from Shopify toggle tabs.
        Stops before FAQ/specification sections to avoid noise.
        """
        ingredients_list = []
        tabs = soup.find_all('toggle-tab', class_=lambda c: c and 'toggle--faq' in c)

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

            # Stop when we hit FAQ territory
            if any(kw in title.lower() for kw in stop_keywords):
                break

            content_div = tab.find('div', class_='toggle__content')
            desc = ""
            if content_div:
                desc_span = content_div.find('span', class_='metafield-multi_line_text_field')
                desc = desc_span.get_text(strip=True) if desc_span else content_div.get_text(strip=True)

            # Safety net — truncate if specs section sneaks through
            if "what are product specifications" in desc.lower():
                desc = desc[:desc.lower().find("what are product specifications")].strip()

            if title and desc:
                ingredients_list.append(f"{title}: {desc}")

        return " | ".join(ingredients_list)

    def extract_rating(self, soup) -> tuple:
        """
        Extracts Yotpo product ID from static HTML, then calls
        Yotpo's public API to get rating and review count.
        Returns (rating, review_count) or (None, None) if unavailable.
        """
        try:
            yotpo_div = soup.find(attrs={"data-yotpo-product-id": True})
            if not yotpo_div:
                return None, None

            yotpo_product_id = yotpo_div["data-yotpo-product-id"]

            yotpo_url = (
                f"https://staticw2.yotpo.com/batch/apps/"
                f"Z0GGWM6QFIM4z2FNJbPwCOeXGKjUdkAhT2CCNVTY/domain_bottom_line"
                f"?methods=%5B%7B%22method%22%3A%22products%22%2C%22params%22"
                f"%3A%7B%22pid%22%3A%22{yotpo_product_id}%22%7D%7D%5D"
            )
            response = requests.get(yotpo_url, headers=self.headers, timeout=5)

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                if results:
                    widget_data = results[0].get("widget", {})
                    bottomline = widget_data.get("bottomline", {})
                    rating = bottomline.get("average_score")
                    review_count = bottomline.get("total_reviews")
                    return rating, review_count

        except Exception as e:
            print(f"    ⚠️  Rating fetch failed: {e}")

        return None, None

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
            # 1. Shopify .js endpoint for structured data (price, title, image)
            js_response = requests.get(f"{product_url}.js", headers=self.headers)
            if js_response.status_code != 200:
                print(f"  ⚠️  Could not fetch .js for {product_url}")
                return None
            json_data = js_response.json()

            # 2. Full HTML page for description, ingredients, and rating ID
            html_response = requests.get(product_url, headers=self.headers)
            soup = BeautifulSoup(html_response.text, 'html.parser')

            # 3. Price (Shopify returns in paise, divide by 100)
            price = json_data.get("price", 0)
            formatted_price = round(price / 100, 2) if price else 0.0

            # 4. Image URL
            featured_image = json_data.get("featured_image", "")
            image_url = (
                f"https:{featured_image}"
                if featured_image and not featured_image.startswith("http")
                else featured_image
            )

            # 5. Description from HTML metafield (body_html is empty for Minimalist)
            description = self.extract_description(soup)

            # 6. Clean concerns from tags
            concerns = self.clean_tags_to_concerns(catalog_tags)

            # 7. Ingredients from toggle tabs
            ingredients = self.extract_ingredients(soup)

            # 8. Rating from Yotpo API (non-blocking — None if unavailable)
            rating, review_count = self.extract_rating(soup)

            product_data = {
                "brand": "Minimalist",
                "product_name": json_data.get("title", "").strip(),
                "description": description,
                "price": formatted_price,
                "rating": rating,
                "review_count": review_count,
                "product_url": product_url,
                "image_url": image_url,
                "category": json_data.get("type", "").strip(),
                "target_concerns": concerns,
                "ingredients": ingredients,
                "tags": ", ".join(catalog_tags),
            }

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

    # 2. Fetch visible product URLs with tags (hidden ones pre-filtered)
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