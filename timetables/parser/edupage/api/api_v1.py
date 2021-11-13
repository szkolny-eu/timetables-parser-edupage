import json
from base64 import b64encode
from datetime import datetime
from random import randbytes
from typing import List, Optional, Union

from aiohttp import ClientSession
from bs4 import BeautifulSoup

from .const import (
    TABLES_V1,
    URL_V1_CONNECT,
    URL_V1_MAUTH,
    USER_AGENT_AIR,
    VERSION_V1_APP,
    VERSION_V1_FLASH,
    VERSION_V1_OS,
)
from .model import Edupage, LoginError, Portal, Session, SessionExpiredError
from .utils import compress_v1, connect_payload, mauth_payload, stringify


class EdupageApiV1:
    def __init__(self, session: ClientSession):
        self.session = session

    @staticmethod
    def _headers() -> dict:
        return {
            "Accept-Encoding": "gzip",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "app:/EdupageMobile.swf",
            "User-Agent": USER_AGENT_AIR,
            "x-flash-version": VERSION_V1_FLASH,
        }

    async def connect_mobile(
        self,
        edupage: Union[Edupage, str],
        action: Optional[str],
        payload: dict,
        session: Optional[Session],
        compress: bool = False,
    ) -> str:
        esid = session.esid if session else ""
        if action:
            eqa = f"akcia={action}&ESID={esid}&hsid=&lang=en"
        else:
            eqa = f"ESID={esid}&hsid=&lang=en"
        url = URL_V1_CONNECT.format(edupage)
        params = {"eqa": b64encode(eqa.encode()).decode()}
        if compress:
            payload = stringify(payload)
            payload = compress_v1(payload)
            payload = {"eqap": payload}
        payload["xhrnd"] = randbytes(15).hex()
        async with self.session.post(
            url,
            params=params,
            data=payload,
            headers=self._headers(),
        ) as r:
            return await r.text()

    async def mauth(
        self, login: str, password: str, **kwargs
    ) -> Union[Portal, Session]:
        payload = mauth_payload(login=login, password=password)
        async with self.session.post(
            URL_V1_MAUTH,
            data=stringify(payload),
            headers=self._headers(),
        ) as r:
            xml = await r.text()
            doc = BeautifulSoup(xml, "xml")
            sess = doc.select_one("login")
            if sess and "status" in sess.attrs and sess["status"] == "fail":
                raise LoginError()
            user_id = doc.select_one("userid")
            user_id = int(user_id.text) if user_id else None
            sessions = list(
                map(
                    lambda edupage: Session(
                        edupage=edupage["id"],
                        username=edupage["edumeno"],
                        password_hash=edupage["eduheslo"],
                        name_first=edupage["meno"],
                        name_last=edupage["priezvisko"],
                        esid=edupage["esid"],
                        portal_id=user_id,
                        portal_email=login,
                    ),
                    doc.select("edupage"),
                )
            )
            if not sessions:
                # if mauth returns a single session, it is definitely a single account connected to Portal
                app_data = json.loads(sess["appdata"])
                return Session(
                    edupage=Edupage(
                        name=sess["edupage"],
                        country=app_data["edurequestProps"]["school_country"],
                        school_name=app_data["edurequestProps"]["school_name"],
                    ),
                    username=sess["edumeno"],
                    password_hash=sess["eduheslo"],
                    name_first=sess["meno"],
                    name_last=sess["priezvisko"],
                    esid=sess["session"],
                    portal_id=None,
                    portal_email=app_data["email"],
                )
            portal = Portal(
                user_id=user_id,
                user_email=login,
                sessions=sessions,
            )
            return portal

    async def sync(self, session: Session, tables: List[str]) -> dict:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        never = "0000-00-00 00:00:00"
        param_tables = {
            table: {
                "params": {},
                "hash": False,
                "lastSync": never,
            }
            for table in tables
        }
        param_table_status = {
            table: {
                "hash": "",
                "lastSync": never if table in tables else now,
                "validity": validity,
            }
            for table, validity in TABLES_V1.items()
        }
        payload = connect_payload(param_tables, param_table_status)
        data = await self.connect_mobile(
            edupage=session.edupage,
            action="update",
            payload=payload,
            session=session,
            compress=True,
        )
        data = json.loads(data)
        if data["status"] == "notLogged":
            raise SessionExpiredError(session)
        if data["status"] != "ok":
            raise ValueError(f"Response status is not OK: {data}")
        return data["tables"]

    async def check_edupage(self, edupage: Union[Edupage, str]) -> bool:
        payload = {
            "lang": "en",
            "os": "android",
            "cmd": "checkEdupageExistsDbEdit",
            "version": VERSION_V1_APP,
            "osversion": VERSION_V1_OS,
        }
        data = await self.connect_mobile(
            edupage=edupage,
            action=None,
            payload=payload,
            session=None,
        )
        return data == "ok"
