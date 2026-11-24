import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from bson import ObjectId
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_ADI", "dolap_app")
JWT_SECRET = os.getenv("JWT_SECRET")
TOKEN_EXPIRE_DAYS = 30

db = MongoClient(MONGO_URI)[DB_NAME]
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


# ---------- Endpoints ----------
@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/register", status_code=201)
def register(req: RegisterRequest):
    password_hash = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    doc = {
        "first_name": req.first_name.strip(),
        "last_name": req.last_name.strip(),
        "email": str(req.email).lower(),
        "password_hash": password_hash,
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