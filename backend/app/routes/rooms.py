from fastapi import APIRouter
from app.database.prisma import db

router = APIRouter()

@router.get("/rooms")
async def get_rooms():
    return await db.room.find_many()