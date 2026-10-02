from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

app = FastAPI(title="VN Labor Market API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "message": "Labor Market API is running"}

@app.get("/jd-minimum")
async def get_minimum_jd(
    role: str = Query(..., example="accountant"),
    industry: str = Query("finance"),
    region: Optional[str] = None,
    level: Optional[str] = None,
    months: int = Query(3, ge=1, le=24)
):
    # This would connect to MongoDB and use MVJD builder
    return {
        "role": role,
        "status": "not_implemented",
        "message": "MVJD logic will be plugged in here."
    }

@app.get("/benefits-compare")
async def compare_benefits(
    level: Optional[str] = None,
    company_type: Optional[str] = None,
    role: Optional[str] = None,
    months: int = Query(3)
):
    return {
        "status": "not_implemented"
    }

@app.get("/trend")
async def get_trend(
    skill: str = Query(...),
    industry: str = Query("finance"),
    months: int = Query(6, ge=1, le=24)
):
    return {
        "skill": skill,
        "status": "not_implemented"
    }
