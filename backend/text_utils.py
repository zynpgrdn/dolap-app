"""Tarif malzeme satırlarını ürün adına çeviren yardımcılar.

Örnek: "2 su bardağı kırmızı mercimek"  ->  ["kırmızı mercimek"]
       "Tuz, karabiber (isteğe göre)"   ->  ["tuz", "karabiber"]
"""
import re

# Aynı şeyin farklı yazımları -> tek ad. Ekip olarak buraya ekleme yapın.
ALIASES = {
    "kuru soğan": "soğan",
    "tereyağ": "tereyağı",
    "zeytin yağı": "zeytinyağı",
    "sıvıyağ": "sıvı yağ",
    "ayçiçek yağı": "sıvı yağ",
    "ayçiçeği yağı": "sıvı yağ",
    "kara biber": "karabiber",
    "mozarella": "mozzarella",
    "dere otu": "dereotu",
    "taze soğan": "yeşil soğan",
    "şeker": "toz şeker",
    "salça": "domates salçası",
    "yumurta sarısı": "yumurta",
    "yumurta akı": "yumurta",
    "kaşar": "kaşar peyniri",
    "rendelenmiş kaşar": "kaşar peyniri",
    "kıyma": "dana kıyma",
    "kuşbaşı et": "dana kuşbaşı",
    "kuşbaşı": "dana kuşbaşı",
    "maya": "kuru maya",
    "vanilya": "vanilin",
    "kırmızı toz biber": "toz biber",
    "kırmızı pul biber": "pul biber",
    "un": "buğday unu",
    "sızma zeytinyağı": "zeytinyağı",
    "küncü": "susam",
    "pulbiber": "pul biber",
    "çörekotu": "çörek otu",
    "limonun suyu": "limon suyu",
    "zeytinyağ": "zeytinyağı",
    "maydonoz": "maydanoz",
    "kaya tuzu": "tuz",
    "şişe maden suyu": "maden suyu",
    "kornişon turşu": "kornişon turşusu",
}

# Miktar / ölçü / hazırlık sözcükleri (çok kelimeliler önce gelecek şekilde sıralanır)
_NOISE = [
    "su bardağı", "çay bardağı", "yemek kaşığı", "tatlı kaşığı", "çay kaşığı",
    "kahve kaşığı", "kahve fincanı", "orta boy", "büyük boy", "küçük boy",
    "bir tutam", "bir miktar", "yeteri kadar", "yeterince", "aldığı kadar",
    "göz kararı", "isteğe bağlı", "isteğe göre", "arzuya göre", "oda sıcaklığında",
    "küp küp", "ince ince", "çeyrek", "yarım", "buçuk", "birkaç", "biraz",
    "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "on",
    "tutam", "avuç", "demet", "diş", "adet", "tane", "paket", "kase", "kutu",
    "kavanoz", "dilim", "kepçe", "litre", "lt", "ml", "gr", "gram", "g", "kg",
    "kilo", "bardak", "fincan", "kaşık", "silme", "tepeleme", "dolusu", "kadar",
    "büyük", "orta", "küçük", "boy", "iri", "ince", "küp", "doğranmış",
    "rendelenmiş", "haşlanmış", "kıyılmış", "dilimlenmiş", "soyulmuş", "ezilmiş",
    "erimiş", "eritilmiş", "çekilmiş", "dövülmüş", "süzülmüş", "ılık", "sıcak",
    "soğuk", "kaynar", "kaynamış", "hazır", "dolu", "fazla", "az", "yaklaşık",
    "er", "ar", "şer", "şar", "birer", "ikişer", "üçer", "dörder", "beşer", "yarımşar",
    "parça", "parçası", "parçaları", "şeklinde", "naturel", "natürel",
    "yağlı", "yağsız", "tam yağlı", "az yağlı", "light", "tercihen", "opsiyonel",
    "kontrollü ekleyin", "kontrollü", "ekleyin", "şart değil", "oda ısısında", "yumuşak",
]
_NOISE_RE = re.compile(
    r"(?<!\w)(" + "|".join(re.escape(w) for w in sorted(_NOISE, key=len, reverse=True)) + r")(?!\w)"
)
_SPLIT_RE = re.compile(r",|;|/|(?<!\w)(?:ve|veya|ya da|yada|ile)(?!\w)")


def tr_lower(text: str) -> str:
    return text.replace("I", "ı").replace("İ", "i").lower()


def slugify(text: str) -> str:
    table = str.maketrans("çğıöşüâî", "cgiosuai")
    return re.sub(r"[^a-z0-9]+", "-", tr_lower(text).translate(table)).strip("-")


def canonical(name: str) -> str:
    return ALIASES.get(name, name)


def ingredient_names(line: str) -> list[str]:
    """Tek bir malzeme satırından ürün adlarını çıkarır."""
    text = tr_lower(line)
    if ":" in text:                                        # "İç harcı için: soğan"
        text = text.split(":", 1)[1]
    text = re.sub(r"^.*?(?<!\w)için(?!\w)", " ", text)       # "kızartmak için sıvı yağ"
    # Parantez içi ayrı bir aday olur: "küncü (susam) ezmesi" -> "küncü ezmesi" + "susam"
    inner = re.findall(r"\((.*?)\)|\[(.*?)\]", text)
    text = re.sub(r"\(.*?\)|\[.*?\]", " ", text)
    text = ",".join([text, *(a or b for a, b in inner)])
    text = re.sub(r"[\d½¼¾⅓⅔.,/-]*\d[\d½¼¾⅓⅔.,/-]*|[½¼¾⅓⅔]", " , ", text)  # sayılar (araya virgül)
    text = re.sub(r"['’`]", " ", text)                      # 1'er -> 1 er
    names = []
    for part in _SPLIT_RE.split(text):
        if not part:
            continue
        part = _NOISE_RE.sub(" ", part)
        part = re.sub(r"[^\wçğıöşü ]", " ", part)
        part = re.sub(r"\s+", " ", part).strip()
        if 2 <= len(part) <= 45 and len(part.split()) <= 6:
            name = canonical(part)
            if name not in names:
                names.append(name)
    return names


def resolve(name: str, known: list[str]) -> list[str]:
    """Bilinen ürün değilse içindeki bilinen ürünleri bulur.

    known: sık geçen adlar, uzundan kısaya sıralı.
    "tereyağı parçaları" -> ["tereyağı"], "kuru soğan tereyağı" -> ["tereyağı", "soğan"]
    """
    if name in known:
        return [name]
    found, rest = [], f" {name} "
    for k in known:
        if len(k) >= 3 and f" {k} " in rest:
            found.append(k)
            rest = rest.replace(f" {k} ", "  ")
    return found or [name]