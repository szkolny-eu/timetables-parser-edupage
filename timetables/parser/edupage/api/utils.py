import json
import zlib
from base64 import b64decode, b64encode
from datetime import datetime
from typing import Dict, Union
from urllib.parse import quote_plus

from .const import (
    DEVICE_ID,
    DEVICE_KEY,
    DEVICE_NAME,
    VERSION_V1_APP,
    VERSION_V1_OS,
    VERSION_V2_APP,
    VERSION_V2_NATIVE,
)
from .model import Edupage


def mauth_payload(
    login: str,
    password: str,
    edupage: Union[Edupage, str] = "",
    **kwargs,
) -> Dict[str, str]:
    return {
        "m": login,
        "h": password,
        "edupage": edupage,
        "plgc": "",
        "ajheslo": "1",
        "hasujheslo": "1",
        "ajportal": "1",
        "ajportallogin": "1",
        "mobileLogin": "1",
        "version": VERSION_V1_APP,
        "fromEdupage": "login1",
        "device_name": DEVICE_NAME,
        "device_id": DEVICE_ID,
        "device_key": DEVICE_KEY,
        "os": "Android",
        "murl": "",
        "edid": "",
        **kwargs,
    }


def connect_payload(tables: dict, table_status: dict, **kwargs) -> dict:
    return {
        "msgids": "",
        "psid": "",
        "hsid": "",
        "tables": tables,
        "version": VERSION_V1_APP,
        "appActive": "1",
        "tableStatus": table_status,
        "os": "android",
        "actions": "{}",
        "murl": "",
        "userType": "Guest",
        "murlasc": "",
        "fromNotification": "0",
        "device_id": DEVICE_ID,
        "osversion": VERSION_V1_OS,
        "device_name": DEVICE_NAME,
        **kwargs,
    }


def sync_payload(tables: dict, edupage: Union[Edupage, str], **kwargs) -> dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "tables": tables,
        "actions": {},
        "version": VERSION_V2_APP,
        "nativeVersion": VERSION_V2_NATIVE,
        "device_name": DEVICE_NAME,
        "device_id": DEVICE_ID,
        "device_key": DEVICE_KEY,
        "os": "Android",
        "murl": "",
        "fromEdupage": edupage,
        "lastSync0": now,
        "lang": "en",
        **kwargs,
    }


def stringify(data: dict) -> str:
    return "&".join(
        f"{k}={quote_plus(json.dumps(v, separators=(',', ':')) if isinstance(v, dict) else str(v))}"
        for k, v in data.items()
    )


def compress_v1(data: str) -> str:
    data = zlib.compress(data.encode())
    return b64encode(b"gz:" + data).decode()


def compress_v2(data: str) -> str:
    data = zlib.compress(data.encode())[2:-4]
    return "dz:" + b64encode(data).decode()


def decompress(data: str) -> str:
    wbits = zlib.MAX_WBITS
    if data.startswith("dz:"):
        data = data.partition("dz:")[2]
        wbits = -zlib.MAX_WBITS
    data = b64decode(data.encode())
    if data.startswith(b"gz:"):
        data = data.partition(b"gz:")[2]
    data = zlib.decompress(data, wbits=wbits)
    return data.decode()
