from app.models.session import Session


class LabBlock:

    def __init__(self, subjects):
        self.sessions = [
            Session(subj, "LAB", 2) for subj in subjects
        ]