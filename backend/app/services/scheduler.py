"""
Hybrid scheduler: Greedy labs + DFS theory/tutorial.

Weekly schedule for Division A:
  THEORY (div-wide):  AI×2, OS×2, ADS×2, POCACD×2, RAAD×1, FCTC×1, DV×2  = 12
  LAB (per-batch):    AI, OS, ADS, POCACD — each batch gets all 4            = 12
  TUTORIAL (per-batch): DT × 3 batches = 3  (one per batch, different slots)
  TUTORIAL (div-wide):  DV × 1                                               =  1
  TOTAL: 28 sessions

Lunch: 13:00 only (single 1-hour lunch)
Theory: morning 08:00-12:00 (slots 800,900,1000,1100)
        + 12:00 slot available (before lunch)
Labs:   afternoon 14:00-16:00
DT tut: afternoon, one per batch at different slots
DV tut: afternoon, div-wide
"""
from app.models.session import Session

LUNCH        = {1300}          # only 13:00 is lunch
THEORY_END   = 1300            # theory before lunch
LAB_START    = 1400            # labs after lunch
LAB_SUBJECTS = ["ADS", "POCACD", "AI", "OS"]
DAYS         = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]
MAX_THEORY_PER_DAY = 3


def expand_sessions(subjects, division, batches):
    subj = {s.code: s for s in subjects}
    sessions = []

    # Division-wide theory
    for code in ["AI", "OS", "ADS", "POCACD", "RAAD", "FCTC", "DV"]:
        s = subj.get(code)
        if not s or s.theoryHours == 0:
            continue
        for _ in range(s.theoryHours):
            sessions.append(Session(s.code, s.name, "THEORY", 1,
                division_id=division.id,
                elective_group_id=getattr(s, 'electiveGroupId', None)))

    # Per-batch labs: all 4 subjects per batch
    for bidx, batch in enumerate(batches):
        for lab_code in LAB_SUBJECTS:
            s = subj.get(lab_code)
            if not s or s.labHours == 0:
                continue
            sess = Session(s.code, s.name, "LAB", 2,
                division_id=division.id, elective_group_id=None)
            sess.batch_index = bidx
            sessions.append(sess)

    # DT tutorial: one per batch (3 sessions)
    dt = subj.get("DT")
    if dt and dt.tutHours > 0:
        for bidx, batch in enumerate(batches):
            sess = Session(dt.code, dt.name, "TUTORIAL", 1,
                division_id=division.id, elective_group_id=None)
            sess.batch_index = bidx
            sess.tut_type = "per_batch"
            sessions.append(sess)

    # DV tutorial: per-batch (3 sessions, one per batch)
    dv = subj.get("DV")
    if dv and dv.tutHours > 0:
        for bidx, batch in enumerate(batches):
            sess = Session(dv.code, dv.name, "TUTORIAL", 1,
                division_id=division.id,
                elective_group_id=getattr(dv, 'electiveGroupId', None))
            sess.batch_index = bidx
            sess.tut_type = "per_batch"
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


# ── Greedy lab + per-batch tutorial assignment ────────────────────────────────

def assign_greedy(lab_sessions, dt_tut_sessions, batches, ts_map, l_rooms, t_rooms, slots_by_day):
    teacher_slot = set()
    room_slot    = set()
    batch_slot   = set()
    div_slot     = set()
    batch_day    = set()  # (batch_id, day) — one lab per batch per day

    # Afternoon slot pairs for labs
    afternoon_pairs = []
    for day in DAYS:
        for slot in slots_by_day.get(day, []):
            if slot.startTime < LAB_START:
                continue
            nslot = nxt(slot, slots_by_day)
            if nslot:
                afternoon_pairs.append((day, slot, nslot))

    # Afternoon single slots for tutorials
    afternoon_singles = []
    for day in DAYS:
        for slot in slots_by_day.get(day, []):
            if slot.startTime >= LAB_START and not is_lunch(slot):
                afternoon_singles.append((day, slot))

    # Sort: same lab subject goes on same day for all batches
    lab_by_subject = {}
    for sess in lab_sessions:
        lab_by_subject.setdefault(sess.subject_code, []).append(sess)

    # Assign each lab subject's 3 batches to the same day (different rooms/teachers)
    for lab_code in LAB_SUBJECTS:
        batch_labs = lab_by_subject.get(lab_code, [])
        assigned_day = None
        assigned_slot = None
        assigned_nslot = None

        for (day, slot, nslot) in afternoon_pairs:
            # Try to fit all 3 batches on this day/slot
            can_fit = True
            temp = []
            for sess in batch_labs:
                bidx  = getattr(sess, 'batch_index', 0)
                batch = batches[bidx]
                if (batch.id, day) in batch_day:
                    can_fit = False; break
                tlist = ts_map.get((lab_code, "LAB"), [])
                assigned_t = None
                assigned_r = None
                for t in tlist:
                    if (t.id, slot.id) in teacher_slot or (t.id, nslot.id) in teacher_slot:
                        continue
                    for r in l_rooms:
                        if (r.id, slot.id) in room_slot or (r.id, nslot.id) in room_slot:
                            continue
                        if (batch.id, slot.id) in batch_slot:
                            continue
                        assigned_t = t; assigned_r = r; break
                    if assigned_t:
                        break
                if not assigned_t:
                    can_fit = False; break
                temp.append((sess, batch, assigned_t, assigned_r))

            if can_fit and len(temp) == len(batch_labs):
                # Commit all 3 batch labs on this slot
                for (sess, batch, t, r) in temp:
                    bidx = getattr(sess, 'batch_index', 0)
                    for sid in (slot.id, nslot.id):
                        teacher_slot.add((t.id, sid))
                        room_slot.add((r.id, sid))
                        batch_slot.add((batch.id, sid))
                    batch_day.add((batch.id, day))
                    sess.teacher_id = t.id; sess.teacher = t.shortCode
                    sess.room_id = r.id;    sess.room = r.roomNumber
                    sess.timeslot = slot.id; sess.timeslot_day = slot.day
                    sess.batch_assignments = [{
                        "teacher_id": t.id, "teacher": t.shortCode,
                        "room_id": r.id, "room": r.roomNumber,
                        "slots": [slot.id, nslot.id],
                        "slot_id": slot.id, "next_slot_id": nslot.id
                    }]
                assigned_day = day
                break

        if not assigned_day:
            print(f"  ⚠️  Could not assign LAB {lab_code} for all batches", flush=True)
            return False, teacher_slot, room_slot, div_slot

    # Assign all per-batch tutorials (DT + DV): one per batch, different slots
    for sess in dt_tut_sessions:
        bidx  = getattr(sess, 'batch_index', 0)
        batch = batches[bidx]
        tlist = ts_map.get((sess.subject_code, "TUTORIAL"), [])
        assigned = False
        for (day, slot) in afternoon_singles:
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
                    sess.teacher_id = t.id; sess.teacher = t.shortCode
                    sess.room_id = r.id;    sess.room = r.roomNumber
                    sess.timeslot = slot.id; sess.timeslot_day = slot.day
                    sess._batch_id = batch.id
                    assigned = True; break
                if assigned: break
            if assigned: break
        if not assigned:
            print(f"  ⚠️  Could not assign DT tutorial B{bidx+1}", flush=True)

    return True, teacher_slot, room_slot, div_slot


# ── DFS for theory + DV tutorial ─────────────────────────────────────────────

class CS:
    def __init__(self, teacher_slot, room_slot):
        self.teacher_slot  = set(teacher_slot)
        self.room_slot     = set(room_slot)
        self.div_slot      = set()
        self.div_subj_day  = set()
        self.div_day_count = {}
        self.room_count    = {}


def ok_th(cs, div_id, code, tid, rid, slot):
    return (
        slot.startTime < THEORY_END and
        not is_lunch(slot) and
        (tid, slot.id) not in cs.teacher_slot and
        (rid, slot.id) not in cs.room_slot and
        (div_id, slot.id) not in cs.div_slot and
        (div_id, code, slot.day) not in cs.div_subj_day and
        cs.div_day_count.get((div_id, slot.day), 0) < MAX_THEORY_PER_DAY
    )

def ok_tut_div(cs, tid, rid, div_id, slot_id):
    return (
        (tid, slot_id) not in cs.teacher_slot and
        (rid, slot_id) not in cs.room_slot and
        (div_id, slot_id) not in cs.div_slot
    )

def do_th(cs, s, t, r, slot):
    cs.teacher_slot.add((t.id, slot.id))
    cs.room_slot.add((r.id, slot.id))
    cs.div_slot.add((s.division_id, slot.id))
    cs.div_subj_day.add((s.division_id, s.subject_code, slot.day))
    k = (s.division_id, slot.day)
    cs.div_day_count[k] = cs.div_day_count.get(k, 0) + 1
    cs.room_count[r.id] = cs.room_count.get(r.id, 0) + 1
    s.teacher_id=t.id; s.teacher=t.shortCode
    s.room_id=r.id;    s.room=r.roomNumber
    s.timeslot=slot.id; s.timeslot_day=slot.day

def un_th(cs, s, t, r, slot):
    cs.teacher_slot.discard((t.id, slot.id))
    cs.room_slot.discard((r.id, slot.id))
    cs.div_slot.discard((s.division_id, slot.id))
    cs.div_subj_day.discard((s.division_id, s.subject_code, slot.day))
    k = (s.division_id, slot.day)
    cs.div_day_count[k] = max(0, cs.div_day_count.get(k, 1) - 1)
    cs.room_count[r.id] = max(0, cs.room_count.get(r.id, 1) - 1)
    s.teacher_id=s.teacher=s.room_id=s.room=s.timeslot=s.timeslot_day=None

def do_tut(cs, s, t, r, div_id, slot):
    cs.teacher_slot.add((t.id, slot.id))
    cs.room_slot.add((r.id, slot.id))
    cs.div_slot.add((div_id, slot.id))
    s.teacher_id=t.id; s.teacher=t.shortCode
    s.room_id=r.id;    s.room=r.roomNumber
    s.timeslot=slot.id; s.timeslot_day=slot.day
    s._batch_id=None

def un_tut(cs, s, t, r, div_id, slot):
    cs.teacher_slot.discard((t.id, slot.id))
    cs.room_slot.discard((r.id, slot.id))
    cs.div_slot.discard((div_id, slot.id))
    s.teacher_id=s.teacher=s.room_id=s.room=s.timeslot=s.timeslot_day=None
    s._batch_id=None

def dfs(sessions, idx, cs, ts_map, t_rooms, slots_by_day):
    if idx == len(sessions):
        return True
    s = sessions[idx]
    tlist = ts_map.get((s.subject_code, s.lecture_type), [])
    sorted_rooms = sorted(t_rooms, key=lambda r: cs.room_count.get(r.id, 0))

    if s.lecture_type == "THEORY":
        for day in DAYS:
            for slot in slots_by_day.get(day, []):
                if slot.startTime >= THEORY_END or is_lunch(slot):
                    continue
                for t in tlist:
                    for r in sorted_rooms:
                        if not ok_th(cs, s.division_id, s.subject_code, t.id, r.id, slot):
                            continue
                        do_th(cs, s, t, r, slot)
                        if dfs(sessions, idx+1, cs, ts_map, t_rooms, slots_by_day):
                            return True
                        un_th(cs, s, t, r, slot)

    elif s.lecture_type == "TUTORIAL":  # DV div-wide only
        for day in DAYS:
            for slot in slots_by_day.get(day, []):
                if slot.startTime < LAB_START or is_lunch(slot):
                    continue
                for t in tlist:
                    for r in t_rooms:
                        if not ok_tut_div(cs, t.id, r.id, s.division_id, slot.id):
                            continue
                        do_tut(cs, s, t, r, s.division_id, slot)
                        if dfs(sessions, idx+1, cs, ts_map, t_rooms, slots_by_day):
                            return True
                        un_tut(cs, s, t, r, s.division_id, slot)
    return False


# ── Entry point ───────────────────────────────────────────────────────────────

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
    batch_tut_sessions = [s for s in all_sessions
                          if s.lecture_type == "TUTORIAL" and getattr(s, 'tut_type', '') == "per_batch"]
    theory_sessions = [s for s in all_sessions if s.lecture_type == "THEORY"]

    print(f"  Sessions: {len(all_sessions)}  "
          f"LAB={len(lab_sessions)} TUT={len(batch_tut_sessions)} THEORY={len(theory_sessions)}", flush=True)

    # Step 1: Greedy — labs + all per-batch tutorials (DT + DV)
    print("  Assigning labs + tutorials (greedy)...", flush=True)
    ok, used_t, used_r, used_d = assign_greedy(
        lab_sessions, batch_tut_sessions, batches, ts_map, l_rooms, t_rooms, slots_by_day)
    if not ok:
        print("  ❌ Greedy assignment failed", flush=True)
        return None
    print("  ✅ Labs + tutorials assigned", flush=True)

    # Step 2: DFS — theory only
    print("  Scheduling theory (DFS)...", flush=True)
    cs = CS(used_t, used_r)
    dfs_sessions = theory_sessions
    if not dfs(dfs_sessions, 0, cs, ts_map, t_rooms, slots_by_day):
        print("  ❌ Theory/DV tutorial scheduling failed", flush=True)
        return None

    print(f"  ✅ All {len(all_sessions)} sessions scheduled", flush=True)
    return all_sessions