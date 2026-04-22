from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.database.prisma import db

router = APIRouter()


class TeacherCreate(BaseModel):
    name: str
    shortCode: str
    subjectIds: List[int] = []
    lectureTypes: List[str] = []


class TeacherUpdate(BaseModel):
    name: Optional[str] = None
    shortCode: Optional[str] = None


@router.get("/teachers")
async def get_teachers():
    return await db.teacher.find_many(
        include={"subjects": {"include": {"subject": True}}}
    )


@router.post("/teachers")
async def create_teacher(payload: TeacherCreate):
    existing = await db.teacher.find_first(where={"shortCode": payload.shortCode})

    if existing:
        teacher = existing
    else:
        teacher = await db.teacher.create(data={
            "name":      payload.name,
            "shortCode": payload.shortCode,
        })

    for subject_id in payload.subjectIds:
        for lecture_type in payload.lectureTypes:
            try:
                await db.teachersubject.create(data={
                    "lectureType": lecture_type,
                    "teacher": {"connect": {"id": teacher.id}},
                    "subject": {"connect": {"id": subject_id}},
                })
            except Exception:
                pass

    return await db.teacher.find_first(
        where={"id": teacher.id},
        include={"subjects": {"include": {"subject": True}}}
    )


@router.patch("/teachers/{teacher_id}")
async def update_teacher(teacher_id: int, payload: TeacherUpdate):
    existing = await db.teacher.find_first(where={"id": teacher_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Teacher not found.")

    if payload.shortCode and payload.shortCode != existing.shortCode:
        conflict = await db.teacher.find_first(where={"shortCode": payload.shortCode})
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"Short code '{payload.shortCode}' is already used by another teacher."
            )

    update_data = {}
    if payload.name:      update_data["name"]      = payload.name
    if payload.shortCode: update_data["shortCode"] = payload.shortCode

    if not update_data:
        return existing

    return await db.teacher.update(
        where={"id": teacher_id},
        data=update_data,
        include={"subjects": {"include": {"subject": True}}}
    )


@router.delete("/teachers/{teacher_id}")
async def delete_teacher(teacher_id: int):
    existing = await db.teacher.find_first(where={"id": teacher_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Teacher not found.")

    await db.timetableentry.delete_many(where={"teacherId": teacher_id})
    await db.teachersubject.delete_many(where={"teacherId": teacher_id})
    await db.teacher.delete(where={"id": teacher_id})
    return {"deleted": teacher_id}


@router.delete("/teacher-subjects/{ts_id}")
async def delete_teacher_subject(ts_id: int):
    existing = await db.teachersubject.find_first(where={"id": ts_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    await db.teachersubject.delete(where={"id": ts_id})
    return {"deleted": ts_id}