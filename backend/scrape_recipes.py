"""nefisyemektarifleri.com'dan tarifleri çekip `recipes` koleksiyonuna yazar.

Kullanım:
    python scrape_recipes.py --test          # 5 tarif çeker, sadece ekrana yazar (DB'ye yazmaz)
    python scrape_recipes.py --limit 3000    # 3000 tarif çeker ve kaydeder

Yarıda kesilirse aynı komutu tekrar çalıştır: kaydedilmiş tarifleri atlar, kaldığı yerden devam eder.
"""
import argparse
import json
import os
import random
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pymongo import MongoClient

from text_utils import ingredient_names, slugify

BASE = "https://www.nefisyemektarifleri.com"
SITEMAPS = [f"{BASE}/sitemap_index.xml", f"{BASE}/sitemap.xml"]
SKIP_SITEMAPS = ("category", "tag", "author", "page-sitemap", "image", "video", "attachment", "kategori")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 (DolApp bitirme projesi)",
    "Accept-Language": "tr-TR,tr;q=0.9",
}
WORKERS = 4


def get(url: str) -> requests.Response | None:
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r
            if r.status_code == 404:
                return None
        except requests.RequestException:
            pass
        time.sleep(2 * (attempt + 1))
    return None


# ---------- 1) Sitemap'ten tarif adreslerini topla ----------

def _locs(xml_bytes: bytes) -> tuple[str, list[str]]:
    root = ET.fromstring(xml_bytes)
    kind = root.tag.split("}")[-1]                     # "sitemapindex" veya "urlset"
    locs = [el.text.strip() for el in root.iter() if el.tag.endswith("loc") and el.text]
    return kind, locs


def collect_urls(max_urls: int) -> list[str]:
    queue, seen_maps, urls = [], set(), []
    for sm in SITEMAPS:
        if get(sm):
            queue.append(sm)
            break
    if not queue:
        raise SystemExit("Sitemap okunamadı. İnternet bağlantını kontrol et.")

    while queue and len(urls) < max_urls:
        sm_url = queue.pop(0)
        if sm_url in seen_maps:
            continue
        seen_maps.add(sm_url)
        r = get(sm_url)
        if not r:
            continue
        try:
            kind, locs = _locs(r.content)
        except ET.ParseError:
            continue
        print(f"  sitemap okundu: {sm_url}")
        if kind == "sitemapindex":
            queue.extend(loc for loc in locs if not any(s in loc.lower() for s in SKIP_SITEMAPS))
        else:
            for loc in locs:
                path = urlparse(loc).path.strip("/")
                if path and "/" not in path and not loc.endswith((".jpg", ".png", ".webp")):
                    urls.append(loc)
    # Tarif olma ihtimali yüksek olanlar ("...-tarifi") önce
    urls = list(dict.fromkeys(urls))
    urls.sort(key=lambda u: "tarif" not in u)
    return urls


# ---------- 2) Tek bir tarif sayfasını oku ----------

def _find_recipe_jsonld(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            obj = stack.pop()
            if isinstance(obj, list):
                stack.extend(obj)
            elif isinstance(obj, dict):
                t = obj.get("@type")
                if t == "Recipe" or (isinstance(t, list) and "Recipe" in t):
                    return obj
                stack.extend(v for v in obj.values() if isinstance(v, (list, dict)))
    return None


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _instructions(value) -> list[str]:
    steps = []
    for item in _as_list(value):
        if isinstance(item, str):
            steps.append(item)
        elif isinstance(item, dict):
            if item.get("itemListElement"):
                steps.extend(_instructions(item["itemListElement"]))
            elif item.get("text"):
                steps.append(item["text"])
    return [BeautifulSoup(s, "html.parser").get_text(" ", strip=True) for s in steps if s]


def _image(value) -> str | None:
    for item in _as_list(value):
        if isinstance(item, str):
            return item
        if isinstance(item, dict) and item.get("url"):
            return item["url"]
    return None


def parse_recipe(url: str, html: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    ld = _find_recipe_jsonld(soup) or {}

    title = ld.get("name") or (soup.h1.get_text(strip=True) if soup.h1 else None)
    ingredients = [str(x).strip() for x in _as_list(ld.get("recipeIngredient") or ld.get("ingredients"))]
    if not ingredients:   # JSON-LD yoksa sayfadaki listeden dene
        items = soup.select('[itemprop="recipeIngredient"], [itemprop="ingredients"], '
                            '.recipe-materials li, ul.malzemeler li')
        ingredients = [li.get_text(" ", strip=True) for li in items]
    ingredients = [i for i in ingredients if i]
    if not title or not ingredients:
        return None   # tarif sayfası değil

    steps = _instructions(ld.get("recipeInstructions"))
    if not steps:
        steps = [el.get_text(" ", strip=True) for el in
                 soup.select('[itemprop="recipeInstructions"] li, .recipe-instructions li, ol.tarif li')]

    category = _as_list(ld.get("recipeCategory"))
    if not category:   # yoksa "breadcrumb"tan al: Anasayfa > Çorbalar > ...
        crumbs = [a.get_text(strip=True) for a in soup.select(".breadcrumb a, .breadcrumbs a")]
        category = crumbs[1:2]

    return {
        "_id": slugify(urlparse(url).path.strip("/")),
        "url": url,
        "title": BeautifulSoup(title, "html.parser").get_text(strip=True),
        "category": category[0] if category else None,
        "image": _image(ld.get("image")),
        "servings": str(_as_list(ld.get("recipeYield"))[0]) if ld.get("recipeYield") else None,
        "raw_ingredients": ingredients,
        "instructions": steps,
        "scraped_at": datetime.now(timezone.utc),
    }


def fetch(url: str) -> tuple[str, dict | None]:
    time.sleep(random.uniform(0.3, 0.8))   # siteyi yormamak için
    r = get(url)
    return url, (parse_recipe(url, r.text) if r else None)


# ---------- 3) Ana akış ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=3000, help="kaç tarif kaydedilsin")
    ap.add_argument("--test", action="store_true", help="5 tarif çek, ekrana yaz, DB'ye yazma")
    args = ap.parse_args()
    limit = 5 if args.test else args.limit

    print("Sitemap okunuyor...")
    urls = collect_urls(max_urls=limit * 3 + 50)
    print(f"{len(urls)} aday adres bulundu.")

    if args.test:
        for url in urls[:15]:
            _, recipe = fetch(url)
            if not recipe:
                print(f"- atlandı (tarif değil): {url}")
                continue
            print(f"\n=== {recipe['title']}  [{recipe['category']}]\n{url}")
            for line in recipe["raw_ingredients"]:
                print(f"   {line:45} -> {ingredient_names(line)}")
            print(f"   ({len(recipe['instructions'])} adım)")
            limit -= 1
            if limit == 0:
                break
        return

    load_dotenv()
    db = MongoClient(os.getenv("MONGO_URI"), tz_aware=True)[os.getenv("DB_ADI", "dolap_app")]
    recipes, skipped = db["recipes"], db["scrape_skipped"]

    done = set(r["url"] for r in recipes.find({}, {"url": 1}))
    done |= set(s["_id"] for s in skipped.find({}, {"_id": 1}))
    saved = recipes.count_documents({})
    todo = [u for u in urls if u not in done]
    print(f"Zaten kayıtlı: {saved} tarif. Çekilecek aday: {len(todo)}")

    start = time.time()
    with ThreadPoolExecutor(WORKERS) as pool:
        for i in range(0, len(todo), 40):
            if saved >= limit:
                break
            for url, recipe in pool.map(fetch, todo[i:i + 40]):
                if recipe:
                    recipes.replace_one({"_id": recipe["_id"]}, recipe, upsert=True)
                    saved += 1
                else:
                    skipped.update_one({"_id": url}, {"$set": {"at": datetime.now(timezone.utc)}},
                                       upsert=True)
            mins = (time.time() - start) / 60
            print(f"  {saved}/{limit} tarif kaydedildi  ({mins:.1f} dk)")

    print(f"Bitti. Toplam {recipes.count_documents({})} tarif var.")


if __name__ == "__main__":
    main()