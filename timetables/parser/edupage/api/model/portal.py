from typing import List, Union

from pydantic import BaseModel

from .edupage import Edupage
from .session import Session


class Portal(BaseModel):
    user_id: int
    user_email: str
    sessions: List[Session] = []

    def get_session(self, edupage: Union[Edupage, str]) -> Session:
        return next(
            session for session in self.sessions if str(session.edupage) == str(edupage)
        )
