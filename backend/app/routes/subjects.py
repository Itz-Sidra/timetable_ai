from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database.prisma import db

router = APIRouter()


class SubjectCreate(BaseModel):
    name: str
    code: str
    year: str = "SY"
    hasTheory: bool = False
    hasLab: bool = False
    hasTutorial: bool = False


@router.get("/subjects")
async def get_subjects():
    return await db.subject.find_many()


@router.post("/subjects")
async def create_subject(payload: SubjectCreate):
    # Auto-create year row if it doesn't exist
    year = await db.year.find_first(where={"name": payload.year})
    if not year:
        year = await db.year.create(data={"name": payload.year})

    existing = await db.subject.find_first(where={"code": payload.code})
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Subject code '{payload.code}' already exists."
        )

    subject = await db.subject.create(data={
        "name":        payload.name,
        "code":        payload.code,
        "theoryHours": 2 if payload.hasTheory  else 0,
        "labHours":    2 if payload.hasLab      else 0,
        "tutHours":    1 if payload.hasTutorial else 0,
        "year": {"connect": {"id": year.id}},
    })
    return subject