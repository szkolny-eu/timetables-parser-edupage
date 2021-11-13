import json
from typing import Optional, Union

from aiohttp import ClientSession
from bs4 import BeautifulSoup

from .api_v1 import EdupageApiV1
from .api_v2 import EdupageApiV2
from .const import URL_EAUTH
from .model import Account, Edupage, Portal, Session
from .utils import mauth_payload


class EdupageApi:
    v1: EdupageApiV1
    v2: EdupageApiV2

    async def eauth(
        self,
        login: str,
        password: str,
        edupage: Union[Edupage, str],
        **kwargs,
    ) -> Session:
        payload = mauth_payload(login=login, password=password, edupage=edupage)
        url = URL_EAUTH.format(edupage)
        xml = await self.v2.request(url, payload=payload, raw=True)
        doc = BeautifulSoup(xml, "xml")
        sess = doc.select_one("login")
        if sess and "reason" in sess.attrs:
            raise ValueError(f"Invalid login or password: {sess['reason']}")
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
            portal_id=sess["portal_userid"] if "portal_userid" in sess.attrs else None,
            portal_email=sess["portal_email"] if "portal_email" in sess.attrs else None,
        )

    async def login(
        self,
        login: str,
        password: str,
        edupage: Optional[Union[Edupage, str]] = None,
        **kwargs,
    ) -> Union[Portal, Session]:
        if edupage and str(edupage) != "guests":
            return await self.eauth(login, password, edupage, **kwargs)
        return await self.v2.mauth(login, password, **kwargs)

    async def register_interactive(self) -> Account:
        email = input("Enter e-mail address: ")
        await self.v2.send_verification_email(email)
        print("Verification e-mail sent.")
        code = input("Enter verification code: ")
        await self.v2.verify_email(email, code)
        print("E-mail verified.")
        password1 = ""
        password2 = ""
        while not password1 or password1 != password2:
            password1 = input("New password: ")
            password2 = input("Confirm password: ")
        name_first = input("First name: ")
        name_last = input("Last name: ")
        print("Creating account...")
        account = await self.v2.create_account(email, password1, name_first, name_last)
        print("Account details: ")
        details = {
            "E-mail": email,
            "First name": name_first,
            "Last name": name_last,
            "Password": password1,
            "Password hash": account.password_hash,
        }
        print("\n".join(f" - {k}: {v}" for k, v in details.items()))
        return account

    def __enter__(self) -> None:
        raise TypeError("Use async with instead")

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    async def __aenter__(self) -> "EdupageApi":
        self.session = ClientSession()
        self.v1 = EdupageApiV1(self.session)
        self.v2 = EdupageApiV2(self.session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.session.close()
        # await self.v1.session.close()
        # await self.v2.session.close()
