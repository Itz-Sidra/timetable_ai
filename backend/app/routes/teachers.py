from fastapi import APIRouter
from app.database.prisma import db

router = APIRouter()

@router.get("/teachers")
async def get_teachers():
    teachers = await db.teacher.find_many()
    return teachers