import hashlib
import hmac
import os
import secrets
import smtplib
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage

import bcrypt
import jwt
from bson import ObjectId
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from pymongo import MongoClient

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_ADI", "dolap_app")
JWT_SECRET = os.getenv("JWT_SECRET")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

TOKEN_EXPIRE_DAYS = 30
CODE_EXPIRE_MINUTES = 10
MAX_CODE_ATTEMPTS = 5
RESEND_WAIT_SECONDS = 60

ALLERGENS = {
    "gluten", "lactose", "egg", "fish", "shellfish", "peanut",
    "almond", "hazelnut", "walnut", "sesame", "soy",
}
DIETS = {"none", "vegetarian", "vegan"}

db = MongoClient(MONGO_URI, tz_aware=True)[DB_NAME]
users = db["users"]
users.create_index("email", unique=True)
products = db["products"]

app = FastAPI(title="DolApp API")
bearer = HTTPBearer()


# ---------- İstek modelleri ----------

class RegisterRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=64)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class PreferencesRequest(BaseModel):
    allergens: list[str] = []
    diet: str = "none"


# ---------- Yardımcılar ----------

def create_token(user_id: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": user_id, "exp": expires}, JWT_SECRET, algorithm="HS256")


def user_to_json(u: dict) -> dict:
    return {
        "id": str(u["_id"]),
        "first_name": u["first_name"],
        "last_name": u["last_name"],
        "email": u["email"],
        "email_verified": u.get("email_verified", False),
        "allergens": u.get("allergens", []),
        "diet": u.get("diet"),
        "preferences_completed": u.get("preferences_completed", False),
    }


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user = users.find_one({"_id": ObjectId(payload["sub"])})
    except Exception:
        raise HTTPException(status_code=401, detail="Oturum geçersiz veya süresi dolmuş.")
    if not user:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı.")
    return user


def hash_code(code: str) -> str:
    return hmac.new(JWT_SECRET.encode(), code.encode(), hashlib.sha256).hexdigest()


def new_verification() -> tuple[str, dict]:
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = datetime.now(timezone.utc)
    return code, {
        "code_hash": hash_code(code),
        "expires_at": now + timedelta(minutes=CODE_EXPIRE_MINUTES),
        "attempts": 0,
        "last_sent_at": now,
    }


def send_verification_email(to: str, first_name: str, code: str) -> None:
    if not SMTP_USER or not SMTP_PASSWORD:
        print(f"[GELİŞTİRME] {to} için doğrulama kodu: {code}")
        return
    msg = EmailMessage()
    msg["Subject"] = "DolApp - E-posta doğrulama kodun"
    msg["From"] = f"DolApp <{SMTP_USER}>"
    msg["To"] = to
    msg.set_content(
        f"Merhaba {first_name},\n\n"
        f"DolApp hesabını doğrulamak için kodun: {code}\n\n"
        f"Kod {CODE_EXPIRE_MINUTES} dakika geçerlidir.\n"
        "Bu isteği sen yapmadıysan bu e-postayı yok sayabilirsin."
    )
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        print(f"[HATA] Doğrulama e-postası gönderilemedi ({to}): {e}")


# ---------- Uç noktalar ----------

@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/register", status_code=201)
def register(body: RegisterRequest, background: BackgroundTasks):
    email = body.email.lower()
    if users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Bu e-posta ile kayıtlı bir hesap zaten var.")
    code, verification = new_verification()
    user = {
        "first_name": body.first_name.strip(),
        "last_name": body.last_name.strip(),
        "email": email,
        "password_hash": bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode(),
        "email_verified": False,
        "verification": verification,
        "allergens": [],
        "diet": None,
        "preferences_completed": False,
        "created_at": datetime.now(timezone.utc),
    }
    result = users.insert_one(user)
    user["_id"] = result.inserted_id
    background.add_task(send_verification_email, email, user["first_name"], code)
    return {"token": create_token(str(result.inserted_id)), "user": user_to_json(user)}


@app.post("/login")
def login(body: LoginRequest):
    user = users.find_one({"email": body.email.lower()})
    if not user or not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı.")
    return {"token": create_token(str(user["_id"])), "user": user_to_json(user)}


@app.get("/me")
def me(user: dict = Depends(current_user)):
    return user_to_json(user)


@app.post("/verify-email")
def verify_email(body: VerifyRequest, user: dict = Depends(current_user)):
    if user.get("email_verified"):
        return user_to_json(user)
    v = user.get("verification")
    if not v:
        raise HTTPException(status_code=400, detail="Doğrulama kodu bulunamadı. Yeni kod iste.")
    if v["attempts"] >= MAX_CODE_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Çok fazla hatalı deneme. Yeni kod iste.")
    if datetime.now(timezone.utc) > v["expires_at"]:
        raise HTTPException(status_code=400, detail="Kodun süresi doldu. Yeni kod iste.")
    if not hmac.compare_digest(hash_code(body.code), v["code_hash"]):
        users.update_one({"_id": user["_id"]}, {"$inc": {"verification.attempts": 1}})
        left = MAX_CODE_ATTEMPTS - v["attempts"] - 1
        raise HTTPException(status_code=400, detail=f"Kod hatalı. Kalan deneme hakkı: {left}")
    users.update_one(
        {"_id": user["_id"]},
        {"$set": {"email_verified": True}, "$unset": {"verification": ""}},
    )
    return user_to_json(users.find_one({"_id": user["_id"]}))


@app.post("/resend-code")
def resend_code(background: BackgroundTasks, user: dict = Depends(current_user)):
    if user.get("email_verified"):
        raise HTTPException(status_code=400, detail="E-posta adresin zaten doğrulanmış.")
    v = user.get("verification")
    if v:
        passed = (datetime.now(timezone.utc) - v["last_sent_at"]).total_seconds()
        if passed < RESEND_WAIT_SECONDS:
            wait = int(RESEND_WAIT_SECONDS - passed) + 1
            raise HTTPException(status_code=429, detail=f"Yeni kod için {wait} saniye bekle.")
    code, verification = new_verification()
    users.update_one({"_id": user["_id"]}, {"$set": {"verification": verification}})
    background.add_task(send_verification_email, user["email"], user["first_name"], code)
    return {"message": "Yeni kod gönderildi."}


@app.put("/me/preferences")
def update_preferences(body: PreferencesRequest, user: dict = Depends(current_user)):
    if not user.get("email_verified"):
        raise HTTPException(status_code=403, detail="Önce e-posta adresini doğrulamalısın.")
    unknown = set(body.allergens) - ALLERGENS
    if unknown:
        raise HTTPException(status_code=400, detail=f"Bilinmeyen alerjen: {', '.join(sorted(unknown))}")
    if body.diet not in DIETS:
        raise HTTPException(status_code=400, detail="Geçersiz beslenme tercihi.")
    users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "allergens": sorted(set(body.allergens)),
            "diet": body.diet,
            "preferences_completed": True,
        }},
    )
    return user_to_json(users.find_one({"_id": user["_id"]}))


@app.get("/catalog")
def catalog():
    docs = list(products.find({}, {"search_terms": 0}))
    categories = sorted(
        (d for d in docs if d["parent"] is None and not d.get("hidden")),
        key=lambda d: d.get("order", 99),
    )
    items = [d for d in docs if d["selectable"] and not d["always_available"]]
    return {
        "categories": [
            {"id": c["_id"], "name": c["name"], "emoji": c.get("emoji", "")} for c in categories
        ],
        "products": [
            {
                "id": p["_id"],
                "name": p["name"],
                "category": p["category"],
                "group": p["group"],
                "storage": p["storage"],
                "shelf_life_days": p["shelf_life_days"],
            }
            for p in items
        ],
    }


# ---------- Dolap ----------

pantry = db["pantry"]
pantry.create_index([("user_id", 1), ("expires_at", 1)])

TR_TZ = timezone(timedelta(hours=3))   # Türkiye saati
EXPIRING_SOON_DAYS = 2                  # bu kadar gün veya daha az kaldıysa uyarı


class PantryAddRequest(BaseModel):
    product_id: str
    purchased_at: date | None = None    # boş bırakılırsa bugün
    opened: bool = False                # paketli ürün zaten açıksa True


def today() -> date:
    return datetime.now(TR_TZ).date()


def to_dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def pantry_item_to_json(item: dict, product: dict | None) -> dict:
    expires = item.get("expires_at")
    days_left = (expires.date() - today()).days if expires else None
    return {
        "id": str(item["_id"]),
        "product_id": item["product_id"],
        "name": product["name"] if product else item["product_id"],
        "category": product["category"] if product else None,
        "storage": item["storage"],
        "purchased_at": item["purchased_at"].date().isoformat(),
        "opened": item["opened"],
        "opened_at": item["opened_at"].date().isoformat() if item.get("opened_at") else None,
        "expires_at": expires.date().isoformat() if expires else None,
        "days_left": days_left,
        "expired": days_left is not None and days_left < 0,
        "expiring_soon": days_left is not None and 0 <= days_left <= EXPIRING_SOON_DAYS,
    }


def user_pantry(user: dict) -> list[dict]:
    items = list(pantry.find({"user_id": user["_id"]}))
    prods = {p["_id"]: p for p in products.find({"_id": {"$in": [i["product_id"] for i in items]}})}
    result = [pantry_item_to_json(i, prods.get(i["product_id"])) for i in items]
    # SKT'si en yakın olan en üstte, SKT'si başlamamış (açılmamış paketli) olanlar en altta
    result.sort(key=lambda x: (x["days_left"] is None, x["days_left"] or 0, x["name"]))
    return result


def find_own_item(item_id: str, user: dict) -> dict:
    try:
        item = pantry.find_one({"_id": ObjectId(item_id), "user_id": user["_id"]})
    except Exception:
        item = None
    if not item:
        raise HTTPException(status_code=404, detail="Ürün dolabında bulunamadı.")
    return item


@app.get("/pantry")
def get_pantry(user: dict = Depends(current_user)):
    return user_pantry(user)


@app.post("/pantry", status_code=201)
def add_to_pantry(body: PantryAddRequest, user: dict = Depends(current_user)):
    product = products.find_one({"_id": body.product_id, "selectable": True})
    if not product or product.get("always_available"):
        raise HTTPException(status_code=404, detail="Ürün katalogda bulunamadı.")
    purchased = body.purchased_at or today()
    if purchased > today():
        raise HTTPException(status_code=400, detail="Alış tarihi ileri bir tarih olamaz.")

    days = product["shelf_life_days"]
    item = {
        "user_id": user["_id"],
        "product_id": product["_id"],
        "storage": product["storage"],
        "purchased_at": to_dt(purchased),
        "opened": False,
        "opened_at": None,
        "expires_at": None,
        "added_at": datetime.now(timezone.utc),
    }
    if product["storage"] == "fresh":
        # Taze ürün: SKT alış tarihinden başlar
        item["expires_at"] = to_dt(purchased + timedelta(days=days))
    elif body.opened:
        # Paketli ama zaten açık: SKT bugünden başlar
        item["opened"] = True
        item["opened_at"] = to_dt(today())
        item["expires_at"] = to_dt(today() + timedelta(days=days))

    result = pantry.insert_one(item)
    item["_id"] = result.inserted_id
    return pantry_item_to_json(item, product)


@app.post("/pantry/{item_id}/open")
def open_item(item_id: str, user: dict = Depends(current_user)):
    item = find_own_item(item_id, user)
    if item["storage"] != "packaged":
        raise HTTPException(status_code=400, detail="Taze ürünlerde 'Açıldı' kullanılmaz.")
    if item["opened"]:
        raise HTTPException(status_code=400, detail="Bu ürün zaten açılmış.")
    product = products.find_one({"_id": item["product_id"]})
    days = product["shelf_life_days"] if product else 7
    update = {
        "opened": True,
        "opened_at": to_dt(today()),
        "expires_at": to_dt(today() + timedelta(days=days)),
    }
    pantry.update_one({"_id": item["_id"]}, {"$set": update})
    item.update(update)
    return pantry_item_to_json(item, product)


@app.delete("/pantry/{item_id}", status_code=204)
def delete_item(item_id: str, user: dict = Depends(current_user)):
    item = find_own_item(item_id, user)
    pantry.delete_one({"_id": item["_id"]})


@app.get("/alerts")
def alerts(user: dict = Depends(current_user)):
    items = user_pantry(user)
    return {
        "expired": [i for i in items if i["expired"]],
        "expiring_soon": [i for i in items if i["expiring_soon"]],
    }