from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import staff, tools, webhooks
from app.seed import seed_if_empty


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(title="Clinic OS API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(staff.router)
app.include_router(tools.router)
app.include_router(webhooks.router)


@app.get("/health")
def health():
    return {
        "ok": True,
        "sarvam_key": bool(settings.sarvam_api_key),
        "exotel_key": bool(settings.exotel_api_key and settings.exotel_api_token),
        "exotel_sid": bool(settings.exotel_account_sid),
    }
