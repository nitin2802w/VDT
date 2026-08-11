from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.upload import router as upload_router
from app.routes.symbol import router as symbol_router

app = FastAPI(
    title="Visual Data Transfer API",
    description="Fountain-coded QR-based local file transfer backend.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router, prefix="/api")
app.include_router(symbol_router, prefix="/api")


@app.get("/ping")
def ping():
    return {"status": "ok"}
