"""
AI Timetable Scheduler — Division A only.

Target weekly schedule:
  AI:     2 THEORY  (different days)
  OS:     2 THEORY  (different days)
  ADS:    2 THEORY  (different days)
  POCACD: 2 THEORY  (different days)
  RAAD:   1 THEORY
  DV:     2 THEORY  (different days) + 1 TUTORIAL
  LAB:    B1=ADS(2h), B2=POCACD(2h), B3=AI(2h) — all on different days from each other
  ───────────────────────────────────────────────
  Total: 11 theory + 3 lab + 1 tut = 15 sessions

Spread strategy:
  - Shuffle slots by day first so DFS doesn't pack Mon/Tue
  - Max 3 theory slots per day for the division
  - Labs on afternoons (prefer 14:00+) to leave mornings for theory
"""
from app.models.session import Session

LUNCH     = {1200, 1300}
BATCH_LAB = {0: "ADS", 1: "POCACD", 2: "AI"}
ELECTIVE  = "DV"
DAYS      = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]
MAX_THEORY_PER_DAY = 3


def expand_sessions(subjects, division, batches):
    subj = {s.code: s for s in subjects}
    sessions = []

    for code in ["AI", "OS", "ADS", "POCACD", "RAAD", ELECTIVE]:
        s = subj.get(code)
        if not s:
            continue
        for _ in range(s.theoryHours):
            sessions.append(Session(
                s.code, s.name, "THEORY", 1,
                division_id=division.id,
                elective_group_id=getattr(s, 'electiveGroupId', None)
            ))

    for bidx, batch in enumerate(batches):
        code = BATCH_LAB.get(bidx)
        s = subj.get(code)
        if not s:
            continue
        sess = Session(s.code, s.name, "LAB", 2,
                       division_id=division.id, elective_group_id=None)
        sess.batch_index = bidx
        sessions.append(sess)

    dv = subj.get(ELECTIVE)
    if dv and getattr(dv, 'tutHours', 0) > 0:
        sess = Session(dv.code, dv.name, "TUTORIAL", 1,
                       division_id=division.id,
                       elective_group_id=getattr(dv, 'electiveGroupId', None))
        sess.batch_index = 0
        sessions.append(sess)

    # THEORY first, then LAB, then TUTORIAL
    sessions.sort(key=lambda s: (
        0 if s.lecture_type == "THEORY" else
        1 if s.lecture_type == "LAB" else 2
    ))
    return sessions


def is_lunch(slot):
    return slot.startTime in LUNCH

def nxt(slot, by_day):
    day_slots = by_day.get(slot.day, [])
    idx = next((i for i, s in enumerate(day_slots) if s.id == slot.id), None)
    if idx is None or idx + 1 >= len(day_slots):
        return None
    n = day_slots[idx + 1]
    return None if n.startTime in LUNCH else n


class CS:
    def __init__(self):
        self.teacher_slot  = set()   # (teacher_id, slot_id)
        self.room_slot     = set()   # (room_id, slot_id)
        self.div_slot      = set()   # (division_id, slot_id)
        self.batch_slot    = set()   # (batch_id, slot_id)
        self.div_subj_day  = set()   # (division_id, code, day) — max 1 theory per subj per day
        self.div_day_count = {}      # (division_id, day) -> int — spread theory across days
        self.room_count    = {}      # room_id -> int


def ok_th(cs, div_id, code, tid, rid, slot):
    day_count = cs.div_day_count.get((div_id, slot.day), 0)
    return (
        (tid, slot.id) not in cs.teacher_slot and
        (rid, slot.id) not in cs.room_slot and
        (div_id, slot.id) not in cs.div_slot and
        (div_id, code, slot.day) not in cs.div_subj_day and
        day_count < MAX_THEORY_PER_DAY
    )

def ok_lab(cs, tid, rid, bid, div_id, s1, s2):
    return all(
        (tid, sid) not in cs.teacher_slot and
        (rid, sid) not in cs.room_slot and
        (bid, sid) not in cs.batch_slot and
        (div_id, sid) not in cs.div_slot
        for sid in (s1, s2)
    )

def ok_tut(cs, tid, rid, bid, sid):
    return (
        (tid, sid) not in cs.teacher_slot and
        (rid, sid) not in cs.room_slot and
        (bid, sid) not in cs.batch_slot
    )


def do_th(cs, s, t, r, slot):
    cs.teacher_slot.add((t.id, slot.id))
    cs.room_slot.add((r.id, slot.id))
    cs.div_slot.add((s.division_id, slot.id))
    cs.div_subj_day.add((s.division_id, s.subject_code, slot.day))
    key = (s.division_id, slot.day)
    cs.div_day_count[key] = cs.div_day_count.get(key, 0) + 1
    cs.room_count[r.id] = cs.room_count.get(r.id, 0) + 1
    s.teacher_id=t.id; s.teacher=t.shortCode
    s.room_id=r.id;    s.room=r.roomNumber
    s.timeslot=slot.id; s.timeslot_day=slot.day

def un_th(cs, s, t, r, slot):
    cs.teacher_slot.discard((t.id, slot.id))
    cs.room_slot.discard((r.id, slot.id))
    cs.div_slot.discard((s.division_id, slot.id))
    cs.div_subj_day.discard((s.division_id, s.subject_code, slot.day))
    key = (s.division_id, slot.day)
    cs.div_day_count[key] = max(0, cs.div_day_count.get(key, 1) - 1)
    cs.room_count[r.id] = max(0, cs.room_count.get(r.id, 1) - 1)
    s.teacher_id=s.teacher=s.room_id=s.room=s.timeslot=s.timeslot_day=None

def do_lab(cs, s, t, r, bid, slot, nslot):
    for sid in (slot.id, nslot.id):
        cs.teacher_slot.add((t.id, sid))
        cs.room_slot.add((r.id, sid))
        cs.batch_slot.add((bid, sid))
    s.teacher_id=t.id; s.teacher=t.shortCode
    s.room_id=r.id;    s.room=r.roomNumber
    s.timeslot=slot.id; s.timeslot_day=slot.day
    s.batch_assignments=[{
        "teacher_id":t.id,"teacher":t.shortCode,
        "room_id":r.id,"room":r.roomNumber,
        "slots":[slot.id,nslot.id],"slot_id":slot.id,"next_slot_id":nslot.id
    }]

def un_lab(cs, s, t, r, bid, slot, nslot):
    for sid in (slot.id, nslot.id):
        cs.teacher_slot.discard((t.id, sid))
        cs.room_slot.discard((r.id, sid))
        cs.batch_slot.discard((bid, sid))
    s.teacher_id=s.teacher=s.room_id=s.room=s.timeslot=s.timeslot_day=None
    s.batch_assignments=[]

def do_tut(cs, s, t, r, bid, slot):
    cs.teacher_slot.add((t.id, slot.id))
    cs.room_slot.add((r.id, slot.id))
    cs.batch_slot.add((bid, slot.id))
    s.teacher_id=t.id; s.teacher=t.shortCode
    s.room_id=r.id;    s.room=r.roomNumber
    s.timeslot=slot.id; s.timeslot_day=slot.day
    s._batch_id=bid

def un_tut(cs, s, t, r, bid, slot):
    cs.teacher_slot.discard((t.id, slot.id))
    cs.room_slot.discard((r.id, slot.id))
    cs.batch_slot.discard((bid, slot.id))
    s.teacher_id=s.teacher=s.room_id=s.room=s.timeslot=s.timeslot_day=None
    s._batch_id=None


def dfs(sessions, idx, cs, ts_map, t_rooms, l_rooms, slots_by_day, batches):
    if idx == len(sessions):
        return True

    s     = sessions[idx]
    tlist = ts_map.get((s.subject_code, s.lecture_type), [])

    if s.lecture_type == "THEORY":
        sorted_rooms = sorted(t_rooms, key=lambda r: cs.room_count.get(r.id, 0))
        # Iterate day by day to naturally spread sessions
        for day in DAYS:
            day_slots = slots_by_day.get(day, [])
            for slot in day_slots:
                if is_lunch(slot):
                    continue
                for t in tlist:
                    for r in sorted_rooms:
                        if not ok_th(cs, s.division_id, s.subject_code, t.id, r.id, slot):
                            continue
                        do_th(cs, s, t, r, slot)
                        if dfs(sessions, idx+1, cs, ts_map, t_rooms, l_rooms, slots_by_day, batches):
                            return True
                        un_th(cs, s, t, r, slot)

    elif s.lecture_type == "LAB":
        bidx  = getattr(s, "batch_index", 0)
        batch = batches[bidx] if bidx < len(batches) else None
        if not batch:
            return False
        # Labs: prefer afternoon slots (14:00+) to keep mornings for theory
        all_slots = []
        for day in DAYS:
            for slot in slots_by_day.get(day, []):
                all_slots.append(slot)
        afternoon = [s for s in all_slots if s.startTime >= 1400 and not is_lunch(s)]
        morning   = [s for s in all_slots if s.startTime < 1200 and not is_lunch(s)]
        ordered   = afternoon + morning

        for slot in ordered:
            nslot = nxt(slot, slots_by_day)
            if not nslot:
                continue
            for t in tlist:
                for r in l_rooms:
                    if not ok_lab(cs, t.id, r.id, batch.id, s.division_id, slot.id, nslot.id):
                        continue
                    do_lab(cs, s, t, r, batch.id, slot, nslot)
                    if dfs(sessions, idx+1, cs, ts_map, t_rooms, l_rooms, slots_by_day, batches):
                        return True
                    un_lab(cs, s, t, r, batch.id, slot, nslot)

    elif s.lecture_type == "TUTORIAL":
        bidx  = getattr(s, "batch_index", 0)
        batch = batches[bidx] if bidx < len(batches) else None
        if not batch:
            return False
        for day in DAYS:
            for slot in slots_by_day.get(day, []):
                if is_lunch(slot):
                    continue
                for t in tlist:
                    for r in t_rooms:
                        if not ok_tut(cs, t.id, r.id, batch.id, slot.id):
                            continue
                        do_tut(cs, s, t, r, batch.id, slot)
                        if dfs(sessions, idx+1, cs, ts_map, t_rooms, l_rooms, slots_by_day, batches):
                            return True
                        un_tut(cs, s, t, r, batch.id, slot)

    return False


def generate_timetable(data):
    teachers            = data["teachers"]
    subjects            = data["subjects"]
    rooms               = data["rooms"]
    slots               = data["timeslots"]
    divisions           = data["divisions"]
    batches             = data["batches"]
    teacher_assignments = data["teacher_assignments"]

    t_rooms = [r for r in rooms if r.roomType == "THEORY"]
    l_rooms = [r for r in rooms if r.roomType == "LAB"]

    slots_by_day = {}
    for s in slots:
        slots_by_day.setdefault(s.day, []).append(s)
    for d in slots_by_day:
        slots_by_day[d].sort(key=lambda x: x.startTime)

    teacher_obj = {t.id: t for t in teachers}
    subject_obj = {s.id: s for s in subjects}
    ts_map = {}
    for ts in teacher_assignments:
        subj = subject_obj.get(ts.subjectId)
        t    = teacher_obj.get(ts.teacherId)
        if not subj or not t:
            continue
        key = (subj.code, ts.lectureType)
        ts_map.setdefault(key, [])
        if t not in ts_map[key]:
            ts_map[key].append(t)

    division = divisions[0]
    sessions = expand_sessions(subjects, division, batches)

    labs   = sum(1 for s in sessions if s.lecture_type=="LAB")
    tuts   = sum(1 for s in sessions if s.lecture_type=="TUTORIAL")
    theory = sum(1 for s in sessions if s.lecture_type=="THEORY")
    print(f"  Sessions: {len(sessions)}  LAB={labs} TUT={tuts} THEORY={theory}", flush=True)

    cs = CS()
    ok = dfs(sessions, 0, cs, ts_map, t_rooms, l_rooms, slots_by_day, batches)

    if not ok:
        print("  ❌ No solution found", flush=True)
        return None

    print(f"  ✅ Scheduled {len(sessions)} sessions", flush=True)
    return sessions