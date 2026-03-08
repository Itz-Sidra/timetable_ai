from fastapi import APIRouter
from app.database.prisma import db

router = APIRouter()

@router.get("/subjects")
async def get_subjects():
    return await db.subject.find_many()