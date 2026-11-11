from fastapi import FastAPI
from backend.routers.hs_finished import router as hs_finished_router
from backend.routers.hs_raw import router as hs_raw_router

app = FastAPI(title="FTA Platform API", version="0.1.0")
app.include_router(hs_finished_router)
app.include_router(hs_raw_router)

@app.get("/health")
def health():
    return {"status": "ok"}
