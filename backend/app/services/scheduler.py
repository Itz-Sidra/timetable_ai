"""
Hybrid scheduler — labs independent per batch.

Each batch gets labs on different days (rotating):
  B1: ADS-Mon, POCACD-Tue, AI-Wed, OS-Thu
  B2: POCACD-Mon, AI-Tue, OS-Wed, ADS-Thu
  B3: AI-Mon, OS-Tue, ADS-Wed, POCACD-Thu

Theory: 2 slots per day (10:00-12:00) Mon-Thu, remaining on Fri
Tutorials: 12:00 slot on lab days, or Fri afternoon
Lunch: 13:00 only
"""
from app.models.session import Session

LUNCH      = {1300}
LAB_START  = 800
LAB_SUBJECTS = ["ADS", "POCACD", "AI", "OS"]
DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]

# Each batch gets a different lab each day (rotation)
BATCH_LAB_ROTATION = {
    # batch_index: {day: lab_subject}
    0: {"MONDAY": "ADS",    "TUESDAY": "POCACD", "WEDNESDAY": "AI",  "THURSDAY": "OS"},
    1: {"MONDAY": "POCACD", "TUESDAY": "AI",     "WEDNESDAY": "OS",  "THURSDAY": "ADS"},
    2: {"MONDAY": "AI",     "TUESDAY": "OS",     "WEDNESDAY": "ADS", "THURSDAY": "POCACD"},
}


def expand_sessions(subjects, division, batches):
    subj = {s.code: s for s in subjects}
    sessions = []

    # Theory
    for code in ["AI", "OS", "ADS", "POCACD", "RAAD", "FCTC", "DV"]:
        s = subj.get(code)
        if not s or s.theoryHours == 0:
            continue
        for _ in range(s.theoryHours):
            sessions.append(Session(s.code, s.name, "THEORY", 1,
                division_id=division.id,
                elective_group_id=getattr(s, 'electiveGroupId', None)))

    # Labs — each batch gets 4 labs on fixed days per rotation
    for bidx, batch in enumerate(batches):
        rotation = BATCH_LAB_ROTATION[bidx]
        for day, lab_code in rotation.items():
            s = subj.get(lab_code)
            if not s or s.labHours == 0:
                continue
            sess = Session(s.code, s.name, "LAB", 2,
                division_id=division.id, elective_group_id=None)
            sess.batch_index = bidx
            sess.assigned_day = day   # fixed day for this lab
            sessions.append(sess)

    # DT tutorial: per batch
    dt = subj.get("DT")
    if dt and dt.tutHours > 0:
        for bidx in range(len(batches)):
            sess = Session(dt.code, dt.name, "TUTORIAL", 1,
                division_id=division.id, elective_group_id=None)
            sess.batch_index = bidx
            sess.tut_subj = "DT"
            sessions.append(sess)

    # DV tutorial: per batch
    dv = subj.get("DV")
    if dv and dv.tutHours > 0:
        for bidx in range(len(batches)):
            sess = Session(dv.code, dv.name, "TUTORIAL", 1,
                division_id=division.id,
                elective_group_id=getattr(dv, 'electiveGroupId', None))
            sess.batch_index = bidx
            sess.tut_subj = "DV"
            sessions.append(sess)

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


def assign_greedy(lab_sessions, tut_sessions, batches, ts_map, l_rooms, t_rooms, slots_by_day):
    teacher_slot = set()
    room_slot    = set()
    batch_slot   = set()

    # ── Assign labs: each batch has a fixed day per subject ──
    for sess in lab_sessions:
        bidx  = sess.batch_index
        batch = batches[bidx]
        day   = sess.assigned_day
        tlist = ts_map.get((sess.subject_code, "LAB"), [])
        day_slots = slots_by_day.get(day, [])

        assigned = False
        for slot in day_slots:
            if slot.startTime < LAB_START or slot.startTime >= 1000:
                continue  # only 08:00-10:00
            nslot = nxt(slot, slots_by_day)
            if not nslot or nslot.startTime >= 1000:
                continue
            for t in tlist:
                if (t.id, slot.id) in teacher_slot or (t.id, nslot.id) in teacher_slot:
                    continue
                for r in l_rooms:
                    if (r.id, slot.id) in room_slot or (r.id, nslot.id) in room_slot:
                        continue
                    if (batch.id, slot.id) in batch_slot:
                        continue
                    for sid in (slot.id, nslot.id):
                        teacher_slot.add((t.id, sid))
                        room_slot.add((r.id, sid))
                        batch_slot.add((batch.id, sid))
                    sess.teacher_id=t.id; sess.teacher=t.shortCode
                    sess.room_id=r.id;    sess.room=r.roomNumber
                    sess.timeslot=slot.id; sess.timeslot_day=slot.day
                    sess.batch_assignments=[{
                        "teacher_id":t.id,"teacher":t.shortCode,
                        "room_id":r.id,"room":r.roomNumber,
                        "slots":[slot.id,nslot.id],
                        "slot_id":slot.id,"next_slot_id":nslot.id
                    }]
                    assigned=True; break
                if assigned: break
            if assigned: break

        if not assigned:
            print(f"  ⚠️  LAB {sess.subject_code} B{bidx+1} on {day} unassigned", flush=True)

    # ── Tutorials: 12:00 slots on Mon-Thu, or Fri afternoon ──
    tut_slots = []
    for day in DAYS:
        for slot in slots_by_day.get(day, []):
            if day != "FRIDAY" and slot.startTime == 1200:
                tut_slots.append(slot)
            elif day == "FRIDAY" and slot.startTime >= 1400 and not is_lunch(slot):
                tut_slots.append(slot)

    for sess in tut_sessions:
        bidx  = sess.batch_index
        batch = batches[bidx]
        tlist = ts_map.get((sess.tut_subj, "TUTORIAL"), [])
        assigned = False
        for slot in tut_slots:
            if (batch.id, slot.id) in batch_slot:
                continue
            for t in tlist:
                if (t.id, slot.id) in teacher_slot:
                    continue
                for r in t_rooms:
                    if (r.id, slot.id) in room_slot:
                        continue
                    teacher_slot.add((t.id, slot.id))
                    room_slot.add((r.id, slot.id))
                    batch_slot.add((batch.id, slot.id))
                    sess.teacher_id=t.id; sess.teacher=t.shortCode
                    sess.room_id=r.id;    sess.room=r.roomNumber
                    sess.timeslot=slot.id; sess.timeslot_day=slot.day
                    sess._batch_id=batch.id
                    assigned=True; break
                if assigned: break
            if assigned: break
        if not assigned:
            print(f"  ⚠️  TUT {sess.tut_subj} B{bidx+1} unassigned", flush=True)

    return True, teacher_slot, room_slot


def assign_theory(theory_sessions, batches, ts_map, t_rooms, slots_by_day,
                  used_teacher_slot, used_room_slot):
    teacher_slot  = set(used_teacher_slot)
    room_slot     = set(used_room_slot)
    div_slot      = set()
    div_subj_day  = set()
    div_day_count = {}
    room_count    = {}

    # Theory slots: 10:00-12:00 Mon-Thu (2 per day), all slots Fri
    allowed = {}
    for day in ["MONDAY","TUESDAY","WEDNESDAY","THURSDAY"]:
        allowed[day] = [s for s in slots_by_day.get(day, [])
                        if 1000 <= s.startTime < 1300 and s.startTime not in LUNCH]
    allowed["FRIDAY"] = [s for s in slots_by_day.get("FRIDAY", [])
                         if s.startTime < 1300 and s.startTime not in LUNCH]

    day_caps = {"MONDAY":2,"TUESDAY":2,"WEDNESDAY":2,"THURSDAY":2,"FRIDAY":4}
    day_order = ["MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY"]

    for sess in theory_sessions:
        tlist = ts_map.get((sess.subject_code, "THEORY"), [])
        sorted_rooms = sorted(t_rooms, key=lambda r: room_count.get(r.id, 0))
        assigned = False
        for day in day_order:
            if (sess.division_id, sess.subject_code, day) in div_subj_day:
                continue
            if div_day_count.get((sess.division_id, day), 0) >= day_caps[day]:
                continue
            for slot in allowed.get(day, []):
                if (sess.division_id, slot.id) in div_slot:
                    continue
                for t in tlist:
                    if (t.id, slot.id) in teacher_slot:
                        continue
                    for r in sorted_rooms:
                        if (r.id, slot.id) in room_slot:
                            continue
                        teacher_slot.add((t.id, slot.id))
                        room_slot.add((r.id, slot.id))
                        div_slot.add((sess.division_id, slot.id))
                        div_subj_day.add((sess.division_id, sess.subject_code, day))
                        k = (sess.division_id, day)
                        div_day_count[k] = div_day_count.get(k, 0) + 1
                        room_count[r.id] = room_count.get(r.id, 0) + 1
                        sess.teacher_id=t.id; sess.teacher=t.shortCode
                        sess.room_id=r.id;    sess.room=r.roomNumber
                        sess.timeslot=slot.id; sess.timeslot_day=slot.day
                        assigned=True; break
                    if assigned: break
                if assigned: break
            if assigned: break
        if not assigned:
            print(f"  ⚠️  THEORY {sess.subject_code} unassigned", flush=True)


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
    all_sessions = expand_sessions(subjects, division, batches)

    lab_sessions    = [s for s in all_sessions if s.lecture_type == "LAB"]
    tut_sessions    = [s for s in all_sessions if s.lecture_type == "TUTORIAL"]
    theory_sessions = [s for s in all_sessions if s.lecture_type == "THEORY"]

    print(f"  Sessions: {len(all_sessions)}  LAB={len(lab_sessions)} "
          f"TUT={len(tut_sessions)} THEORY={len(theory_sessions)}", flush=True)

    ok, used_t, used_r = assign_greedy(
        lab_sessions, tut_sessions, batches, ts_map, l_rooms, t_rooms, slots_by_day)
    if not ok:
        return None

    assign_theory(theory_sessions, batches, ts_map, t_rooms,
                  slots_by_day, used_t, used_r)

    print(f"  ✅ All {len(all_sessions)} sessions scheduled", flush=True)
    return all_sessions