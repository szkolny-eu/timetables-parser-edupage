from .session import Session


class SessionExpiredError(Exception):
    def __init__(self, session: Session) -> None:
        self.session = session
        super().__init__(f"Session expired: {session.edupage}#{session.esid}")


class LoginError(ValueError):
    def __init__(self) -> None:
        super().__init__(
            "Invalid login, password, or not connected to a Portal account"
        )
