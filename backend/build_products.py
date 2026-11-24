"""Çekilen tariflerdeki malzemelerden ürün kataloğunu oluşturur.

1) Her tarifin malzeme satırlarını ürün adlarına çevirir (recipes.ingredient_names)
2) Her adın kaç tarifte geçtiğini sayar
3) En az MIN_RECIPES tarifte geçen adları ürün yapar, kategorisini/alerjenini kurallarla bulur
4) `products` koleksiyonunu baştan yazar ve ingredient_report.csv'ye rapor çıkarır

Kuralları veya ALIASES'ı (text_utils.py) değiştirince tekrar çalıştırman yeterli.
"""
import csv
import os
import re
from collections import Counter

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne

from text_utils import ALIASES, ingredient_names, resolve, slugify, tr_lower

MIN_RECIPES = 15   # bir ad en az bu kadar tarifte geçerse ürün olur

# (id, ad, ebeveyn, emoji, sıra, saklama, varsayılan gün, kategoriden gelen alerjen/hayvansal)
CATEGORIES = [
    ("meat", "Et & Tavuk", None, "🍗", 1, "fresh", 2, [], ["meat"]),
    ("chicken", "Tavuk", "meat", "", 0, "fresh", 2, [], ["meat"]),
    ("red-meat", "Kırmızı Et", "meat", "", 0, "fresh", 2, [], ["meat"]),
    ("seafood", "Balık & Deniz Ürünleri", None, "🐟", 2, "fresh", 1, ["fish"], ["fish"]),
    ("dairy", "Süt Ürünleri", None, "🥛", 3, "packaged", 4, ["lactose"], ["dairy"]),
    ("cheese", "Peynir", "dairy", "", 0, "packaged", 7, ["lactose"], ["dairy"]),
    ("breakfast", "Kahvaltılık", None, "🍳", 4, "packaged", 14, [], []),
    ("vegetables", "Sebze", None, "🥕", 5, "fresh", 5, [], []),
    ("greens", "Yeşillik", "vegetables", "", 0, "fresh", 4, [], []),
    ("fruits", "Meyve", None, "🍎", 6, "fresh", 7, [], []),
    ("grains", "Bakliyat & Tahıl", None, "🌾", 7, "packaged", 180, [], []),
    ("bakery", "Ekmek & Hamur", None, "🍞", 8, "packaged", 4, ["gluten"], []),
    ("nuts", "Kuruyemiş", None, "🥜", 9, "packaged", 90, [], []),
    ("oils", "Yağlar", None, "🫒", 10, "packaged", 180, [], []),
    ("spices", "Baharatlar", None, "🌶️", 11, "packaged", 365, [], []),
    ("sauces", "Sos & Salça", None, "🥫", 12, "packaged", 30, [], []),
    ("baking", "Pastacılık", None, "🧁", 13, "packaged", 180, [], []),
    ("other", "Diğer", None, "🧺", 14, "packaged", 7, [], []),
    ("basics", "Temel", None, "", 99, "packaged", None, [], []),
]

# Ürün adında geçen anahtar kelime -> kategori. En uzun eşleşen kazanır
# ("kuru nane" > "nane", "bal kabağı" > "bal", "domates salçası" > "domates").
CATEGORY_KEYWORDS = {
    "chicken": ["tavuk", "piliç", "hindi"],
    "red-meat": ["kıyma", "dana", "kuzu", "et", "kuşbaşı", "biftek", "bonfile", "antrikot",
                 "sucuk", "pastırma", "salam", "sosis", "et suyu"],
    "seafood": ["balık", "somon", "hamsi", "levrek", "çipura", "karides", "midye", "kalamar",
                "ahtapot", "ton balığı", "uskumru", "palamut", "alabalık", "istavrit"],
    "cheese": ["peynir", "peyniri", "kaşar", "lor", "mozzarella", "parmesan", "cheddar", "labne"],
    "dairy": ["süt", "yoğurt", "tereyağı", "krema", "kaymak", "ayran", "süt tozu", "süzme yoğurt"],
    "breakfast": ["yumurta", "zeytin", "bal", "reçel", "pekmez", "çikolata kreması"],
    "greens": ["maydanoz", "dereotu", "roka", "marul", "nane", "taze nane", "yeşil soğan",
               "fesleğen", "reyhan", "tere", "semizotu", "kişniş"],
    "vegetables": ["soğan", "sarımsak", "domates", "biber", "patates", "havuç", "patlıcan",
                   "kabak", "bal kabağı", "mantar", "salatalık", "ıspanak", "pırasa", "lahana",
                   "karnabahar", "brokoli", "bezelye", "fasulye", "taze fasulye", "bamya",
                   "kereviz", "turp", "pancar", "mısır", "enginar", "kapya biber", "salatalık turşusu"],
    "fruits": ["limon", "elma", "muz", "portakal", "çilek", "armut", "üzüm", "nar", "ayva",
               "kivi", "ananas", "şeftali", "kiraz", "vişne", "kayısı", "mandalina", "avokado",
               "limon suyu", "portakal suyu", "limon kabuğu"],
    "grains": ["un", "buğday unu", "pirinç", "bulgur", "makarna", "şehriye", "irmik", "mercimek",
               "nohut", "kuru fasulye", "barbunya", "yulaf", "nişasta", "mısır unu", "galeta unu",
               "erişte", "kuskus", "kinoa", "mısır nişastası", "pirinç unu"],
    "bakery": ["ekmek", "yufka", "lavaş", "bazlama", "milföy", "pide", "tortilla", "ekmek içi",
               "baklava yufkası", "kadayıf", "kuru ekmek"],
    "nuts": ["ceviz", "badem", "fındık", "fıstık", "yer fıstığı", "antep fıstığı", "susam",
             "kaju", "kuru üzüm", "kuru kayısı", "hindistan cevizi", "çam fıstığı", "kuru incir"],
    "oils": ["yağ", "yağı", "sıvı yağ", "zeytinyağı", "zeytin yağı", "margarin"],
    "spices": ["karabiber", "pul biber", "toz biber", "kimyon", "kekik", "kuru nane", "tarçın",
               "zerdeçal", "sumak", "yenibahar", "karanfil", "zencefil", "köri", "isot", "defne",
               "defne yaprağı", "muskat", "çörek otu", "baharat"],
    "sauces": ["salça", "salçası", "domates salçası", "biber salçası", "ketçap", "mayonez",
               "hardal", "sirke", "nar ekşisi", "soya sosu", "sos", "sosu", "tahin",
               "domates püresi", "bulyon"],
    "baking": ["şeker", "toz şeker", "pudra şekeri", "esmer şeker", "kabartma tozu", "vanilin",
               "kakao", "maya", "kuru maya", "yaş maya", "çikolata", "bitter çikolata",
               "jelatin", "karbonat", "bisküvi", "kek", "krem şanti"],
    "basics": ["tuz", "su"],
}

# Ürün adında geçen kelime -> alerjen / hayvansal (kategoriden gelenlere eklenir)
ALLERGEN_KEYWORDS = {
    "gluten": ["un", "buğday", "bulgur", "makarna", "şehriye", "irmik", "erişte", "yulaf",
               "galeta", "bisküvi", "kuskus", "arpa", "çavdar", "soya sosu", "kadayıf", "kek"],
    "lactose": ["süt", "peynir", "peyniri", "kaymak", "krema", "tereyağı", "yoğurt", "krem şanti"],
    "egg": ["yumurta", "mayonez"],
    "shellfish": ["karides", "midye", "kalamar", "ahtapot", "yengeç"],
    "peanut": ["yer fıstığı", "fıstık ezmesi"],
    "almond": ["badem"],
    "hazelnut": ["fındık", "çikolata kreması"],
    "walnut": ["ceviz"],
    "sesame": ["susam", "tahin"],
    "soy": ["soya"],
}
ANIMAL_KEYWORDS = {
    "egg": ["yumurta", "mayonez"],
    "honey": ["bal"],
    "dairy": ["süt", "peynir", "tereyağı", "yoğurt", "krema", "kaymak"],
    "meat": ["jelatin", "et suyu", "tavuk suyu"],
}
# Bu ifadeler alerjen/hayvansal aramasından önce addan silinir (yanlış eşleşmeyi önler)
NOT_ALLERGEN = ["mısır unu", "pirinç unu", "nohut unu", "hindistan cevizi", "bal kabağı",
                "hindistan cevizi sütü", "badem sütü", "soya sütü", "çam fıstığı",
                "antep fıstığı", "kabak çekirdeği"]

# Ürüne özel gün / saklama (kategorinin varsayılanını ezer)
OVERRIDES = {
    "yumurta": {"shelf_life_days": 21, "storage": "fresh"},
    "tereyağı": {"shelf_life_days": 30},
    "ekmek": {"shelf_life_days": 3, "storage": "fresh"},
    "soğan": {"shelf_life_days": 21},
    "sarımsak": {"shelf_life_days": 21},
    "patates": {"shelf_life_days": 21},
    "havuç": {"shelf_life_days": 14},
    "limon": {"shelf_life_days": 14},
    "sucuk": {"shelf_life_days": 7, "storage": "packaged"},
    "bal": {"shelf_life_days": 365},
    "zeytin": {"shelf_life_days": 14},
    "süt": {"shelf_life_days": 3},
    "domates salçası": {"shelf_life_days": 14},
    "ton balığı": {"shelf_life_days": 2, "storage": "packaged"},
}
# Ürün olmasını istemediğiniz adlar (rapora bakıp ekleyin)
IGNORE = {"malzemeler", "hamuru", "sosu", "üzeri", "süslemek", "servis", "isteğe", "tarif"}


def _has(name: str, kw: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", name) is not None


def find_category(name: str) -> str:
    best, best_len = "other", 0
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if len(kw) > best_len and _has(name, kw):
                best, best_len = cat, len(kw)
    return best


def find_tags(name: str, table: dict) -> set:
    clean = name
    for phrase in NOT_ALLERGEN:
        clean = clean.replace(phrase, " ")
    return {tag for tag, kws in table.items() if any(_has(clean, kw) for kw in kws)}


def build_catalog(counts: Counter) -> list[dict]:
    cats = {c[0]: c for c in CATEGORIES}
    docs = []
    for id_, name, parent, emoji, order, storage, days, allergens, animal in CATEGORIES:
        top = parent or id_
        docs.append({
            "_id": id_, "name": name, "parent": parent, "selectable": False,
            "emoji": emoji, "order": order, "hidden": id_ == "basics",
            "category": top, "group": None, "storage": storage,
            "allergens": allergens, "animal": animal, "always_available": False,
            "shelf_life_days": None, "synonyms": [], "search_terms": [tr_lower(name)],
        })

    aliases_of = {}
    for alias, target in ALIASES.items():
        aliases_of.setdefault(target, []).append(alias)

    for name, count in counts.items():
        if count < MIN_RECIPES or name in IGNORE:
            continue
        cat_id = find_category(name)
        _, cat_name, parent, _, _, storage, days, cat_all, cat_animal = cats[cat_id]
        doc = {
            "_id": slugify(name),
            "name": display_name(name),
            "parent": cat_id,
            "selectable": True,
            "category": parent or cat_id,
            "group": cat_name if parent else None,
            "storage": storage,
            "shelf_life_days": days,
            "allergens": sorted(set(cat_all) | find_tags(name, ALLERGEN_KEYWORDS)),
            "animal": sorted(set(cat_animal) | find_tags(name, ANIMAL_KEYWORDS)),
            "always_available": cat_id == "basics",
            "synonyms": aliases_of.get(name, []),
            "search_terms": [name, *aliases_of.get(name, [])],
            "recipe_count": count,
        }
        doc.update(OVERRIDES.get(name, {}))
        docs.append(doc)
    return docs


def display_name(name: str) -> str:
    first = {"i": "İ", "ı": "I"}.get(name[0], name[0].upper())
    return first + name[1:]


def main():
    load_dotenv()
    db = MongoClient(os.getenv("MONGO_URI"), tz_aware=True)[os.getenv("DB_ADI", "dolap_app")]
    recipes, products = db["recipes"], db["products"]

    # 1. tur: satırlardan adları çıkar ve say
    per_recipe = {}
    for r in recipes.find({}, {"raw_ingredients": 1}):
        names = []
        for line in r["raw_ingredients"]:
            names.extend(n for n in ingredient_names(line) if n not in names)
        per_recipe[r["_id"]] = names
    if not per_recipe:
        raise SystemExit("Hiç tarif yok. Önce scrape_recipes.py'yi çalıştır.")
    first = Counter(n for names in per_recipe.values() for n in names)

    # 2. tur: nadir adların içindeki bilinen ürünü bul
    # ("tereyağı parçaları" -> "tereyağı", "erken hasat sızma zeytinyağı" -> "zeytinyağı")
    known = sorted((n for n, c in first.items() if c >= MIN_RECIPES and n not in IGNORE),
                   key=len, reverse=True)
    counts, updates = Counter(), []
    for rid, names in per_recipe.items():
        resolved = []
        for n in names:
            resolved.extend(x for x in resolve(n, known) if x not in resolved)
        counts.update(resolved)
        updates.append(UpdateOne({"_id": rid}, {"$set": {"ingredient_names": resolved}}))
    recipes.bulk_write(updates)

    docs = build_catalog(counts)
    products.delete_many({})
    products.insert_many(docs)
    products.create_index("parent")
    products.create_index("search_terms")

    with open("ingredient_report.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["ad", "tarif_sayisi", "urun_mu", "kategori", "alerjenler"])
        for name, count in counts.most_common():
            is_product = count >= MIN_RECIPES and name not in IGNORE
            w.writerow([name, count, "evet" if is_product else "",
                        find_category(name) if is_product else "",
                        ",".join(sorted(find_tags(name, ALLERGEN_KEYWORDS))) if is_product else ""])

    items = [d for d in docs if d["selectable"]]
    other = [d["name"] for d in items if d["parent"] == "other"]
    print(f"{len(updates)} tarif işlendi, {len(counts)} farklı malzeme adı bulundu.")
    print(f"{len(items)} ürün oluşturuldu (en az {MIN_RECIPES} tarifte geçenler).")
    print(f"Kategorisi bulunamayan ('Diğer'e düşen) {len(other)} ürün: {', '.join(other[:40])}")
    print("Ayrıntılı liste: ingredient_report.csv")


if __name__ == "__main__":
    main()