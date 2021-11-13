from hashlib import sha1
from typing import Dict, List, Optional, Union

from aiohttp import ClientSession

from .const import (
    URL_V2_APPLOGIN,
    URL_V2_MAUTH,
    URL_V2_SYNC,
    USER_AGENT_REACT,
    VERSION_V2_APP,
)
from .model import Account, Edupage, LoginError, Portal, Session, SessionExpiredError
from .utils import compress_v2, mauth_payload, stringify, sync_payload


class EdupageApiV2:
    def __init__(self, session: ClientSession):
        self.session = session

    @staticmethod
    def _headers() -> dict:
        return {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT_REACT,
            "x-requested-with": "XMLHttpRequest",
        }

    async def request(
        self,
        url: str,
        payload: dict,
        params: dict = None,
        raw: bool = False,
    ) -> Union[dict, str]:
        if params is None:
            params = {}
        eqap = compress_v2(stringify(payload))
        form = {
            "eqap": eqap,
            "eqacs": sha1(eqap.encode()).hexdigest(),
            "eqaz": 0,
        }
        params.update(
            {
                "eqav": "1",
                "maxEqav": "7",
            }
        )
        async with self.session.post(
            url,
            params=params,
            data=form,
            headers=self._headers(),
        ) as r:
            if raw:
                return await r.text()
            return await r.json(content_type="text/html")

    async def app_login(
        self,
        edupage: Union[Edupage, str],
        action: str,
        payload: dict = None,
        session: Optional[Session] = None,
        **kwargs,
    ) -> dict:
        url = URL_V2_APPLOGIN.format(edupage)
        params = dict(
            akcia=action,
            lang="en",
            **kwargs,
        )
        if session:
            params.update(
                mobile="2",
                mobileApp=VERSION_V2_APP,
                ESID=session.esid,
                fromEdupage=session.edupage_name(),
            )
        data = await self.request(url, payload=payload or {}, params=params)
        if not isinstance(data, dict):
            raise TypeError("Request V2 did not return a dict")
        if data["status"] != "ok":
            raise ValueError(f"Response status is not OK: {data}")
        return data

    async def mauth(
        self, login: str, password: str, **kwargs
    ) -> Union[Portal, Session]:
        payload = mauth_payload(login=login, password=password)
        data = await self.request(URL_V2_MAUTH, payload=payload)
        if not isinstance(data, dict):
            raise TypeError("Request V2 did not return a dict")
        if not data["users"]:
            raise LoginError()
        sessions = list(
            map(
                lambda user: Session(
                    edupage=Edupage(
                        name=user["edupage"],
                        country=user["appdata"]["edurequestProps"]["school_country"],
                        school_name=user["appdata"]["edurequestProps"]["school_name"],
                    ),
                    username=user["edumeno"],
                    password_hash=user["eduheslo"],
                    name_first=user["firstname"],
                    name_last=user["lastname"],
                    esid=user["esid"],
                    portal_id=user["portal_userid"]
                    if "portal_userid" in user
                    else None,
                    portal_email=user["portal_email"]
                    if "portal_email" in user
                    else None,
                ),
                data["users"],
            )
        )
        if "@" not in login and len(sessions) == 1:
            return sessions[0]
        main_user = data["users"][0]
        return Portal(
            user_id=main_user["portal_userid"],
            user_email=main_user["portal_email"],
            sessions=sessions,
        )

    async def sync(self, session: Session, tables: Dict[str, List[str]]) -> dict:
        param_tables = {table: {"keys": keys} for table, keys in tables.items()}
        payload = sync_payload(param_tables, session.edupage)
        url = URL_V2_SYNC.format(session.edupage)
        params = {
            "mobile": "2",
            "mobileApp": VERSION_V2_APP,
            "ESID": session.esid,
            "lang": "en",
            "fromEdupage": session.edupage_name(),
        }
        data = await self.request(url, payload=payload, params=params)
        if not isinstance(data, dict):
            raise TypeError("Request V2 did not return a dict")
        if data["status"] == "insufficient_privileges":
            raise SessionExpiredError(session)
        if data["status"] != "ok":
            raise ValueError(f"Response status is not OK: {data}")
        return data["tables"]

    async def check_edupage(self, edupage: Union[Edupage, str]) -> bool:
        # noinspection PyBroadException
        try:
            await self.app_login(edupage, action="checkEdupage", mobile="2")
            return True
        except Exception:
            return False

    async def send_verification_email(self, email: str) -> str:
        data = await self.app_login(
            "login1",
            action="sendVerificationEmail",
            payload={
                "email": email,
            },
        )
        return data["esid"]

    async def verify_email(self, email: str, code: str) -> bool:
        await self.app_login(
            "login1",
            action="verifyCode",
            payload={
                "email": email,
                "code": code,
            },
        )
        return True

    async def create_account(
        self, email: str, password: str, name_first: str, name_last: str
    ) -> Account:
        payload = {
            "userdata": {
                "firstname": name_first,
                "lastname": name_last,
                "password": password,
                "passwordConfirm": password,
                "email": email,
                "typ": "Student",
            },
        }
        data = await self.app_login("login1", action="createAccount", payload=payload)
        return Account(
            edupage="guests",
            username=data["n"],
            password_hash=data["p"],
        )

    async def join_account(self, portal: Portal, new_edupage: str) -> Account:
        session = portal.sessions[0]
        payload = {
            "userdata": {
                "firstname": session.name_first,
                "lastname": session.name_last,
                "email": portal.user_email,
                "edupage": new_edupage,
                "portal_userid": portal.user_id,
                "createguest": "1",
            },
            "accountdata": {
                "edupage": session.edupage_name(),
                "edumeno": session.username,
                "eduheslo": session.password_hash,
                "portal_userid": portal.user_id,
                "portal_email": portal.user_email,
            },
        }
        data = await self.app_login(
            "login1", action="joinAccount", payload=payload, session=session
        )
        return Account(
            edupage=new_edupage,
            username=data["n"],
            password_hash=data["p"],
            portal_id=data["portal_userid"],
            portal_email=data["portal_email"],
        )
