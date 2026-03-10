import asyncio
from app.database.prisma import db

TEACHERS = [
    {"name": "MR. ANKESH SURESH KHARE",       "shortCode": "ASK"},
    {"name": "DR. KAILASH SHAW",               "shortCode": "KS"},
    {"name": "RASHMI ANIKET ASOLE",            "shortCode": "RAA"},
    {"name": "DR. VIJAY UTTAM RATHOD",         "shortCode": "VUR"},
    {"name": "MRS. VANITA SHARAD BABANNE",     "shortCode": "VSB"},
    {"name": "MS. ASMITA BALASAHEB KALAMKAR",  "shortCode": "ABK"},
    {"name": "MS. GEETA BALKRUSHNA ZAWARE",    "shortCode": "GZZ"},
    {"name": "MS. ASHLESHA GOPINATH SAWANT",   "shortCode": "AGS"},
    {"name": "MRS. DIPTI AJITKUMAR GAIKWAD",   "shortCode": "DAG"},
    {"name": "OMKAR SHAILENDRA DUBAL",         "shortCode": "OSD"},
    {"name": "DR. AMRUTA CHANDRAKANT AMUNE",   "shortCode": "ACA"},
    {"name": "DR. KALYANI GHUGHE",             "shortCode": "KG"},
    {"name": "MR. VIVEKANAND SHARMA",          "shortCode": "VKS"},
]

SUBJECTS = [
    ("ARTIFICIAL INTELLIGENCE",             "AI",     2, 2, 0, False),
    ("OPERATING SYSTEM",                    "OS",     2, 2, 0, False),
    ("ADVANCED DATA STRUCTURE",             "ADS",    2, 2, 0, False),
    ("AUTOMATA THEORY AND COMPILER DESIGN", "POCACD", 2, 2, 0, False),
    ("REASONING AND APTITUDE DEVELOPMENT",  "RAAD",   1, 0, 0, False),
    ("FROM CAMPUS TO CORPORATE",            "FCTC",   1, 0, 0, False),
    ("DESIGN THINKING",                     "DT",     0, 0, 1, False),
    ("DATA VISUALIZATION",                  "DV",     2, 0, 1, True),
    ("INTERNET OF THINGS",                  "IOT",    2, 0, 1, True),
]

# Teacher mapping with there subjects and lecture types
TEACHER_SUBJECTS = [
    # Theory
    ("ASK", "AI",     "THEORY"),
    ("ASK", "RAAD",   "THEORY"),
    ("KS",  "ADS",    "THEORY"),
    ("VUR", "POCACD", "THEORY"),
    ("ABK", "FCTC",   "THEORY"),
    ("AGS", "OS",     "THEORY"),
    ("KG",  "DV",     "THEORY"),
    ("VKS", "IOT",    "THEORY"),
    # Labs 
    ("KS",  "ADS",    "LAB"),
    ("RAA", "ADS",    "LAB"),
    ("VUR", "POCACD", "LAB"),
    ("VSB", "AI",     "LAB"),
    ("DAG", "AI",     "LAB"),
    ("GZZ", "OS",     "LAB"),
    ("AGS", "OS",     "LAB"),
    ("OSD", "OS",     "LAB"),
    ("ACA", "OS",     "LAB"),
    # Tutorials
    ("VUR", "DT",     "TUTORIAL"),
    ("GZZ", "DT",     "TUTORIAL"),
    ("ASK", "DT",     "TUTORIAL"),
    ("KG",  "DV",     "TUTORIAL"),
    ("DAG", "DV",     "TUTORIAL"),
    ("VKS", "IOT",    "TUTORIAL"),
]

THEORY_ROOMS = ["4307", "4006", "4005"]
LAB_ROOMS    = ["4304", "4007", "4008", "4003", "4105"]
DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]
SLOTS = [
    (800,  900), (900,  1000), (1000, 1100), (1100, 1200),
    (1200, 1300), (1300, 1400),
    (1400, 1500), (1500, 1600), (1600, 1700),
]


async def seed():
    await db.timetableentry.delete_many()
    await db.batch.delete_many()
    await db.division.delete_many()
    await db.teachersubject.delete_many()
    await db.subject.delete_many()
    await db.teacher.delete_many()
    await db.room.delete_many()
    await db.timeslot.delete_many()
    await db.electivegroup.delete_many()
    await db.year.delete_many()
    print("  Cleared old data")

    year = await db.year.create(data={"name": "SY"})
    eg   = await db.electivegroup.create(data={"name": "DV_IOT"})

    teacher_map = {}
    for t in TEACHERS:
        obj = await db.teacher.create(data=t)
        teacher_map[t["shortCode"]] = obj
    print(f"  Teachers: {len(teacher_map)}")

    subject_map = {}
    for (name, code, th, lh, tut, is_elective) in SUBJECTS:
        cd = {"name": name, "code": code,
              "theoryHours": th, "labHours": lh, "tutHours": tut,
              "year": {"connect": {"id": year.id}}}
        if is_elective:
            cd["electiveGroup"] = {"connect": {"id": eg.id}}
        obj = await db.subject.create(data=cd)
        subject_map[code] = obj
    print(f"  Subjects: {len(subject_map)}")

    for (tc, sc, lt) in TEACHER_SUBJECTS:
        if tc not in teacher_map or sc not in subject_map:
            continue
        await db.teachersubject.create(data={
            "lectureType": lt,
            "teacher": {"connect": {"id": teacher_map[tc].id}},
            "subject": {"connect": {"id": subject_map[sc].id}},
        })
    print(f"  TeacherSubjects: {len(TEACHER_SUBJECTS)}")

    for r in THEORY_ROOMS:
        await db.room.create(data={"roomNumber": r, "roomType": "THEORY"})
    for r in LAB_ROOMS:
        await db.room.create(data={"roomNumber": r, "roomType": "LAB"})
    print(f"  Rooms: {len(THEORY_ROOMS)+len(LAB_ROOMS)}")

    for day in DAYS:
        for (st, en) in SLOTS:
            await db.timeslot.create(data={"day": day, "startTime": st, "endTime": en})
    print(f"  Timeslots: {len(DAYS)*len(SLOTS)}")

    div = await db.division.create(data={"name": "A", "year": {"connect": {"id": year.id}}})
    for n in [1, 2, 3]:
        await db.batch.create(data={"name": f"A-B{n}", "division": {"connect": {"id": div.id}}})
    print(f"  Division A  Batches: 3")
    print("✅ Seed complete")


if __name__ == "__main__":
    async def main():
        await db.connect()
        await seed()
        await db.disconnect()
    asyncio.run(main())