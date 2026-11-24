import hashlib
import hmac
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import bcrypt
import jwt
from bson import ObjectId
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

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

app = FastAPI(title="Dolap App API")
bearer = HTTPBearer()


# ---------- Request models ----------
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

# ---------- Helpers ----------
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
    except jwt.PyJWTError:
        raise HTTPException(401, "Oturum geçersiz veya süresi dolmuş.")
    user = users.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(401, "Kullanıcı bulunamadı.")
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
    msg["From"] = SMTP_USER
    msg["To"] = to
    msg.set_content(
        f"Merhaba {first_name},\n\n"
        f"DolApp hesabını doğrulamak için kodun: {code}\n\n"
        f"Kod {CODE_EXPIRE_MINUTES} dakika geçerlidir. "
        "Bu isteği sen yapmadıysan bu e-postayı yok sayabilirsin."
    )
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp:
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        print(f"[HATA] Doğrulama e-postası gönderilemedi ({to}): {e}")


# ---------- Endpoints ----------
@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/register", status_code=201)
def register(req: RegisterRequest, background_tasks: BackgroundTasks):
    email = str(req.email).lower()
    if users.find_one({"email": email}):
        raise HTTPException(409, "Bu e-posta ile kayıtlı bir hesap zaten var.")
    code, verification = new_verification()
    doc = {
        "first_name": req.first_name.strip(),
        "last_name": req.last_name.strip(),
        "email": email,
        "password_hash": bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode(),
        "email_verified": False,
        "verification": verification,
        "allergens": [],
        "diet": None,
        "preferences_completed": False,
        "created_at": datetime.now(timezone.utc),
    }
    try:
        result = users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "Bu e-posta ile kayıtlı bir hesap zaten var.")
    doc["_id"] = result.inserted_id
    background_tasks.add_task(send_verification_email, email, doc["first_name"], code)
    return {"token": create_token(str(result.inserted_id)), "user": user_to_json(doc)}


@app.post("/login")
def login(req: LoginRequest):
    user = users.find_one({"email": str(req.email).lower()})
    if not user or not bcrypt.checkpw(req.password.encode(), user["password_hash"].encode()):
        raise HTTPException(401, "E-posta veya şifre hatalı.")
    return {"token": create_token(str(user["_id"])), "user": user_to_json(user)}


@app.get("/me")
def me(user: dict = Depends(current_user)):
    return user_to_json(user)


@app.post("/verify-email")
def verify_email(req: VerifyRequest, user: dict = Depends(current_user)):
    if user.get("email_verified"):
        return user_to_json(user)
    v = user.get("verification")
    if not v:
        raise HTTPException(400, "Doğrulama kodu bulunamadı. Yeni kod iste.")
    attempts = v.get("attempts", 0)
    if attempts >= MAX_CODE_ATTEMPTS:
        raise HTTPException(429, "Çok fazla hatalı deneme. Yeni kod iste.")
    if datetime.now(timezone.utc) > v["expires_at"]:
        raise HTTPException(400, "Kodun süresi doldu. Yeni kod iste.")
    if not hmac.compare_digest(hash_code(req.code.strip()), v["code_hash"]):
        users.update_one({"_id": user["_id"]}, {"$inc": {"verification.attempts": 1}})
        remaining = MAX_CODE_ATTEMPTS - attempts - 1
        raise HTTPException(400, f"Kod hatalı. Kalan deneme hakkı: {remaining}")
    users.update_one(
        {"_id": user["_id"]},
        {"$set": {"email_verified": True}, "$unset": {"verification": ""}},
    )
    user["email_verified"] = True
    return user_to_json(user)


@app.post("/resend-code")
def resend_code(background_tasks: BackgroundTasks, user: dict = Depends(current_user)):
    if user.get("email_verified"):
        raise HTTPException(400, "E-posta zaten doğrulanmış.")
    now = datetime.now(timezone.utc)
    v = user.get("verification")
    if v:
        passed = (now - v["last_sent_at"]).total_seconds()
        if passed < RESEND_WAIT_SECONDS:
            raise HTTPException(429, f"Yeni kod için {int(RESEND_WAIT_SECONDS - passed) + 1} saniye bekle.")
    code, verification = new_verification()
    users.update_one({"_id": user["_id"]}, {"$set": {"verification": verification}})
    background_tasks.add_task(send_verification_email, user["email"], user["first_name"], code)
    return {"message": "Yeni kod gönderildi."}



@app.put("/me/preferences")
def update_preferences(req: PreferencesRequest, user: dict = Depends(current_user)):
    if not user.get("email_verified"):
        raise HTTPException(403, "Önce e-posta adresini doğrulamalısın.")
    unknown = set(req.allergens) - ALLERGENS
    if unknown:
        raise HTTPException(400, f"Bilinmeyen alerjen: {', '.join(sorted(unknown))}")
    if req.diet not in DIETS:
        raise HTTPException(400, "Geçersiz beslenme tercihi.")
    changes = {
        "allergens": sorted(set(req.allergens)),
        "diet": req.diet,
        "preferences_completed": True,
    }
    users.update_one({"_id": user["_id"]}, {"$set": changes})
    user.update(changes)
    return user_to_json(user)