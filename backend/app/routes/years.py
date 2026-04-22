from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database.prisma import db

router = APIRouter()


class YearCreate(BaseModel):
    name: str


@router.get("/years")
async def get_years():
    return await db.year.find_many(order={"name": "asc"})


@router.post("/years")
async def create_year(payload: YearCreate):
    name = payload.name.strip().upper()
    if not name:
        raise HTTPException(status_code=400, detail="Year name cannot be empty.")

    existing = await db.year.find_first(where={"name": name})
    if existing:
        raise HTTPException(status_code=409, detail=f"Year '{name}' already exists.")

    year = await db.year.create(data={"name": name})
    return year


@router.delete("/years/{year_id}")
async def delete_year(year_id: int):
    existing = await db.year.find_first(where={"id": year_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Year not found.")

    # Check for dependent subjects
    subjects = await db.subject.find_many(where={"yearId": year_id})
    if subjects:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete — {len(subjects)} subject(s) are linked to this year."
        )

    await db.year.delete(where={"id": year_id})
    return {"deleted": year_id}