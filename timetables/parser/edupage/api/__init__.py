from .api import EdupageApi
from .api_v1 import EdupageApiV1
from .api_v2 import EdupageApiV2
from .model import Account, Edupage, LoginError, Portal, Session, SessionExpiredError

__all__ = [
    "Account",
    "Edupage",
    "EdupageApi",
    "EdupageApiV1",
    "EdupageApiV2",
    "LoginError",
    "Portal",
    "Session",
    "SessionExpiredError",
    "model",
]
