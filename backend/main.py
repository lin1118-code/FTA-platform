import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers.hs_finished import router as hs_finished_router
from backend.routers.platform import router as platform_router

app = FastAPI(title="FTA Platform API", version="0.1.0")
allowed_origins = os.getenv("FTA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.include_router(hs_finished_router)
app.include_router(platform_router)

@app.get("/health")
def health():
    return {"status": "ok"}
