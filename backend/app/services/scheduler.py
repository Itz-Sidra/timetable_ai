from app.models.session import Session


# ---------------------------------------------------------------------------
# Session expansion
# ---------------------------------------------------------------------------

def expand_subject_sessions(subjects):
    sessions = []
    for subject in subjects:
        for _ in range(2):
            sessions.append(Session(subject.name, "THEORY", 1))

        if subject.electiveGroupId is not None:
            sessions.append(Session(subject.name, "TUTORIAL", 1))
        else:
            sessions.append(Session(subject.name, "LAB", 2))

    return sessions


# ---------------------------------------------------------------------------
# Room helpers
# ---------------------------------------------------------------------------

def valid_rooms_for_session(session, rooms):
    if session.lecture_type == "LAB":
        return [r for r in rooms if r.roomType == "LAB"]
    return [r for r in rooms if r.roomType == "THEORY"]


# ---------------------------------------------------------------------------
# Timeslot helpers
# ---------------------------------------------------------------------------

def consecutive_slots(slot, slots):
    index = slots.index(slot)
    if index + 1 >= len(slots):
        return None
    next_slot = slots[index + 1]
    if next_slot.day != slot.day:
        return None
    return next_slot


# ---------------------------------------------------------------------------
# Constraint checking
# ---------------------------------------------------------------------------

def is_valid(state, session, teacher, room, slot):
    for s in state:
        if s.teacher == teacher and s.timeslot == slot.id:
            return False
        if s.room == room and s.timeslot == slot.id:
            return False
        if (
            session.lecture_type == "THEORY"
            and s.subject == session.subject
            and s.lecture_type == "THEORY"
            and s.timeslot_day == slot.day
        ):
            return False
    return True


def is_valid_for_lab_batch(state, pending, teacher, room, slot_id):
    """
    Check (teacher, slot_id) and (room, slot_id) are free in committed state
    and in earlier batches of the current lab block being assembled.
    """
    for s in state:
        if s.teacher == teacher and s.timeslot == slot_id:
            return False
        if s.room == room and s.timeslot == slot_id:
            return False

    # pending entries use keys: slot_id, next_slot_id
    for entry in pending:
        if entry["teacher"] == teacher and slot_id in (entry["slot_id"], entry["next_slot_id"]):
            return False
        if entry["room"] == room and slot_id in (entry["slot_id"], entry["next_slot_id"]):
            return False

    return True


# ---------------------------------------------------------------------------
# Sentinel helpers
# ---------------------------------------------------------------------------

def _is_sentinel(s):
    """
    Sentinels are LAB stubs (duration=1, batch_assignments=[]).
    Original LAB sessions have batch_assignments populated when committed.
    """
    return s.lecture_type == "LAB" and not s.batch_assignments


def _make_lab_sentinels(session, batch_combo, slot, next_slot):
    """
    Create stub Sessions that occupy teacher/room/slot in state so that
    is_valid() correctly blocks those combinations for future sessions.
    """
    sentinels = []
    for bc in batch_combo:
        for slot_id, day in [(slot.id, slot.day), (next_slot.id, next_slot.day)]:
            sv = Session(session.subject, "LAB", 1)
            sv.teacher      = bc["teacher"]
            sv.room         = bc["room"]
            sv.timeslot     = slot_id
            sv.timeslot_day = day
            # batch_assignments stays [] → marks it as a sentinel
            sentinels.append(sv)
    return sentinels


# ---------------------------------------------------------------------------
# Lab batch assignment
# ---------------------------------------------------------------------------

def _assign_batches(state, teachers, lab_rooms, slot, next_slot, num_batches):
    """
    For a given consecutive slot pair, find a distinct (teacher, room) per batch.
    Returns list of dicts or None if impossible.

    Dict keys: teacher, room, slot_id, next_slot_id, slot_day
    """
    used_teachers = set()
    used_rooms    = set()
    combo = []

    for _ in range(num_batches):
        assigned = False
        for teacher in teachers:
            if teacher.name in used_teachers:
                continue
            for room in lab_rooms:
                if room.roomNumber in used_rooms:
                    continue
                if (
                    is_valid_for_lab_batch(state, combo, teacher.name, room.roomNumber, slot.id)
                    and is_valid_for_lab_batch(state, combo, teacher.name, room.roomNumber, next_slot.id)
                ):
                    combo.append({
                        "teacher":      teacher.name,
                        "room":         room.roomNumber,
                        "slot_id":      slot.id,
                        "next_slot_id": next_slot.id,
                        "slot_day":     slot.day,
                    })
                    used_teachers.add(teacher.name)
                    used_rooms.add(room.roomNumber)
                    assigned = True
                    break   # done with rooms for this batch
            if assigned:
                break       # done with teachers for this batch

        if not assigned:
            return None

    return combo


# ---------------------------------------------------------------------------
# DFS scheduler
# ---------------------------------------------------------------------------

def dfs_schedule(state, sessions, teachers, rooms, slots, batches):
    """
    state    – flat list of Session objects:
                 THEORY/TUTORIAL: the session itself
                 LAB: original Session (batch_assignments set) + N*2 sentinels
    sessions – ordered sessions to schedule (labs sorted first)
    batches  – determines how many parallel lab streams are needed
    """

    # Count real (non-sentinel) sessions placed so far
    scheduled_count = sum(1 for s in state if not _is_sentinel(s))

    if scheduled_count == len(sessions):
        return state

    session = sessions[scheduled_count]

    # ------------------------------------------------------------------ LAB
    if session.lecture_type == "LAB":
        lab_rooms   = [r for r in rooms if r.roomType == "LAB"]
        num_batches = len(batches)

        for slot in slots:
            next_slot = consecutive_slots(slot, slots)
            if not next_slot:
                continue

            batch_combo = _assign_batches(state, teachers, lab_rooms, slot, next_slot, num_batches)
            if batch_combo is None:
                continue

            # Commit
            session.timeslot          = slot.id
            session.timeslot_day      = slot.day
            session.batch_assignments = batch_combo

            # Original session first — main.py iterates state and reads batch_assignments
            state.append(session)

            # Sentinels block teacher/room/slots from being stolen by later sessions
            sentinels = _make_lab_sentinels(session, batch_combo, slot, next_slot)
            for sv in sentinels:
                state.append(sv)

            result = dfs_schedule(state, sessions, teachers, rooms, slots, batches)
            if result:
                return result

            # Backtrack
            for _ in sentinels:
                state.pop()
            state.pop()

            session.timeslot          = None
            session.timeslot_day      = None
            session.batch_assignments = []

    # ---------------------------------------------------- THEORY / TUTORIAL
    else:
        for teacher in teachers:
            for room in valid_rooms_for_session(session, rooms):
                for slot in slots:
                    if not is_valid(state, session, teacher.name, room.roomNumber, slot):
                        continue

                    session.teacher      = teacher.name
                    session.room         = room.roomNumber
                    session.timeslot     = slot.id
                    session.timeslot_day = slot.day

                    state.append(session)

                    result = dfs_schedule(state, sessions, teachers, rooms, slots, batches)
                    if result:
                        return result

                    state.pop()
                    session.teacher      = None
                    session.room         = None
                    session.timeslot     = None
                    session.timeslot_day = None

    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_timetable(data):
    teachers = data["teachers"]
    subjects = data["subjects"]
    rooms    = data["rooms"]
    slots    = data["timeslots"]
    batches  = data.get("batches", [])

    sessions = expand_subject_sessions(subjects)

    # Heuristic: schedule harder (lab) sessions first
    sessions.sort(key=lambda s: s.duration, reverse=True)

    return dfs_schedule([], sessions, teachers, rooms, slots, batches)