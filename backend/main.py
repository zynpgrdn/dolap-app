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
DB_ADI = os.getenv("DB_ADI", "dolap_app")
JWT_SECRET = os.getenv("JWT_SECRET")
TOKEN_GECERLILIK_GUN = 30

db = MongoClient(MONGO_URI)[DB_ADI]
kullanicilar = db["kullanicilar"]
kullanicilar.create_index("eposta", unique=True)

app = FastAPI(title="Dolap App API")
bearer = HTTPBearer()


class KayitIstegi(BaseModel):
    ad: str = Field(min_length=1, max_length=50)
    soyad: str = Field(min_length=1, max_length=50)
    eposta: EmailStr
    sifre: str = Field(min_length=6, max_length=64)


class GirisIstegi(BaseModel):
    eposta: EmailStr
    sifre: str


def token_olustur(kullanici_id: str) -> str:
    bitis = datetime.now(timezone.utc) + timedelta(days=TOKEN_GECERLILIK_GUN)
    return jwt.encode({"sub": kullanici_id, "exp": bitis}, JWT_SECRET, algorithm="HS256")


def kullanici_json(k: dict) -> dict:
    return {
        "id": str(k["_id"]),
        "ad": k["ad"],
        "soyad": k["soyad"],
        "eposta": k["eposta"],
        "alerjenler": k.get("alerjenler", []),
        "beslenme": k.get("beslenme"),
        "tercihler_tamam": k.get("tercihler_tamam", False),
    }


def aktif_kullanici(kimlik: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    try:
        veri = jwt.decode(kimlik.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Oturum geçersiz veya süresi dolmuş.")
    k = kullanicilar.find_one({"_id": ObjectId(veri["sub"])})
    if not k:
        raise HTTPException(401, "Kullanıcı bulunamadı.")
    return k


@app.get("/")
def saglik():
    return {"durum": "çalışıyor"}


@app.post("/kayit", status_code=201)
def kayit(istek: KayitIstegi):
    sifre_hash = bcrypt.hashpw(istek.sifre.encode(), bcrypt.gensalt()).decode()
    belge = {
        "ad": istek.ad.strip(),
        "soyad": istek.soyad.strip(),
        "eposta": str(istek.eposta).lower(),
        "sifre_hash": sifre_hash,
        "alerjenler": [],
        "beslenme": None,
        "tercihler_tamam": False,
        "olusturma_tarihi": datetime.now(timezone.utc),
    }
    try:
        sonuc = kullanicilar.insert_one(belge)
    except DuplicateKeyError:
        raise HTTPException(409, "Bu e-posta ile kayıtlı bir hesap zaten var.")
    belge["_id"] = sonuc.inserted_id
    return {"token": token_olustur(str(sonuc.inserted_id)), "kullanici": kullanici_json(belge)}


@app.post("/giris")
def giris(istek: GirisIstegi):
    k = kullanicilar.find_one({"eposta": str(istek.eposta).lower()})
    if not k or not bcrypt.checkpw(istek.sifre.encode(), k["sifre_hash"].encode()):
        raise HTTPException(401, "E-posta veya şifre hatalı.")
    return {"token": token_olustur(str(k["_id"])), "kullanici": kullanici_json(k)}


@app.get("/ben")
def ben(k: dict = Depends(aktif_kullanici)):
    return kullanici_json(k)