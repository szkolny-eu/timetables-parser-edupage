import json
from base64 import b64decode
from datetime import datetime
from io import BytesIO
from math import log
from os.path import isfile
from typing import Dict, List, Union
from urllib.parse import urlparse
from zipfile import ZipFile

from timetables.parser.base import File, Parser
from timetables.schemas import Lesson, Register, Team, WeekDay

from .api import EdupageApi
from .api.model import Session

ID_STRIP = "* "


class EdupageParser(Parser):
    api_session: Session
    edupage: str
    cache: Dict[str, list] = {}
    cache_file: str = "cache.json"
    periods: Dict[int, dict] = {}
    lessons: Dict[int, dict] = {}

    def __init__(self, session: Session, enable_cache: bool = False):
        self.api = EdupageApi()
        self.api_session = session
        self.edupage = str(session.edupage)
        self.cache_file = f"cache_{self.edupage}.json" if enable_cache else None
        super().__init__()

    def enqueue_all(
        self, try_v1_teachers: bool = False, try_v1_full_teachers: bool = False
    ):
        if try_v1_full_teachers:
            self._enqueue_path("/get/v1/timetables/teachers")
        elif try_v1_teachers:
            self._enqueue_path("/get/v1/ucitel")
        self._enqueue_path(
            "/get/v2/Timetable/periods,classes,groups,subjects,teachers,classrooms,lessons,cards"
        )
        # ensure the teachers parsing order, so that v1's full names replace the v2's short names
        # also, v1's teachers obtained from "timetables" seem to be compatible with v2's teachers
        self._enqueue_path("/parse/v2/teachers")
        if not try_v1_full_teachers and try_v1_teachers:
            self._enqueue_path("/parse/v1/ucitel")

    def _enqueue_path(self, path: str) -> None:
        file = File(path=f"https://edupage.org/")
        file.path = f"edupage://{self.edupage}{path}"
        super().enqueue(file)

    def uncached_tables(self, tables: List[str]) -> List[str]:
        tables2 = list(tables)
        for table in tables:
            if table in self.cache:
                tables2.remove(table)
        return tables2

    async def _parse_file(self, file: File) -> None:
        session = self.api_session
        url = urlparse(file.path)

        path: List[Union[str, List[str]]]
        path = url.path[1:].split("/")

        if path[0] == "get":
            last = len(path) - 1
            path[last] = path[last].split(",")
            # enqueue parsing all tables
            for table in path[last]:
                self._enqueue_path(f"/parse/{path[1]}/{table}")
            path[last] = self.uncached_tables(path[last])
        elif path[0] == "parse" and path[2] not in self.cache:
            return

        match path:
            case ["get", "v1", "timetables", list(tables)] if tables:
                zip_cache = f"timetables.json"
                if not isfile(zip_cache):
                    data = await self.api.v1.sync(session, ["timetables"])
                    b64: str = data["timetables"]["data"]
                    zip_data = b64decode(b64.encode())
                    with ZipFile(BytesIO(zip_data), "r") as zf:
                        zf.extract("timetables.json")
                    del data
                    del b64
                    del zip_data
                with open(zip_cache, "rb") as f:
                    timetables: dict = json.load(f)
                    timetable: dict = next(v for v in timetables["timetables"].values())
                    dbi: dict = timetable["dbi"]
                    # cache all tables
                    for table in tables:
                        self.cache[table] = list(dbi[table].values())
                    del timetables
                    del timetable
                    del dbi

            case ["get", "v1", list(tables)] if tables:
                data = await self.api.v1.sync(session, tables)
                # cache all tables
                for table in tables:
                    self.cache[table] = list(data[table]["data"].values())
                del data

            case ["get", "v2", ("Dbi" | "Timetable") as source, list(tables)] if tables:
                data = await self.api.v2.sync(session, tables={source: [""]})
                # extract the table dicts from the structure
                if path[2] == "Dbi":
                    data = data["Dbi"]["data"][""]
                elif path[2] == "Timetable":
                    try:
                        data = data["Timetable"]["data"][""]["regularData"]["dbiAccessorRes"]["tables"]
                        data = {item["id"]: item["data_rows"] for item in data}
                    except KeyError:
                        return
                # cache all tables
                for table in tables:
                    if isinstance(data[table], dict):
                        self.cache[table] = list(data[table].values())
                    else:
                        self.cache[table] = data[table]
                del data

            case ["parse", "v1", "ucitel" as table]:
                await self._parse_teachers_v1(self.cache[table])
            case ["parse", "v2", "periods" as table]:
                await self._parse_periods_v2(self.cache[table])
            case ["parse", "v2", "classes" as table]:
                await self._parse_classes_v2(self.cache[table])
            case ["parse", "v2", "groups" as table]:
                await self._parse_groups_v2(self.cache[table])
            case ["parse", "v2", "subjects" as table]:
                await self._parse_subjects_v2(self.cache[table])
            case ["parse", "v2", "teachers" as table]:
                await self._parse_teachers_v2(self.cache[table])
            case ["parse", "v2", "classrooms" as table]:
                await self._parse_classrooms_v2(self.cache[table])
            case ["parse", "v2", "lessons" as table]:
                await self._parse_lessons_v2(self.cache[table])
            case ["parse", "v2", "cards" as table]:
                await self._parse_cards_v2(self.cache[table])

    async def _parse_teachers_v1(self, teachers: list) -> None:
        for teacher in teachers:
            teacher: dict
            name = " ".join(
                [
                    teacher["p_priezvisko"].strip(),
                    teacher["p_meno"].strip(),
                ]
            )
            tid = teacher["UcitelID"].strip(ID_STRIP)
            self.ds.get_teacher(name=name, internal_id=int(tid))

    async def _parse_periods_v2(self, periods: list) -> None:
        for period in periods:
            period: dict
            pid = period["id"].strip(ID_STRIP)
            self.periods[int(pid)] = period

    async def _parse_classes_v2(self, classes: list) -> None:
        for cls in classes:
            cls: dict
            name = cls["name"].strip()
            cid = cls["id"].strip(ID_STRIP)
            self.ds.get_register(
                type=Register.Type.CLASS, name=name, internal_id=int(cid)
            )

    async def _parse_groups_v2(self, groups: list) -> None:
        for group in groups:
            group: dict
            rid = group["classid"].strip(ID_STRIP)
            register = self.ds.get_register(
                type=Register.Type.CLASS, internal_id=int(rid)
            )
            if not group["entireclass"]:
                name = register.name + " " + group["name"].strip()
            else:
                name = "-"
            gid = group["id"].strip(ID_STRIP)
            self.ds.get_team(register=register, name=name, internal_id=int(gid))

    async def _parse_subjects_v2(self, subjects: list) -> None:
        for subject in subjects:
            subject: dict
            name = subject["name"].strip()
            sid = subject["id"].strip(ID_STRIP)
            self.ds.get_subject(name=name, internal_id=int(sid))

    async def _parse_teachers_v2(self, teachers: list) -> None:
        for teacher in teachers:
            teacher: dict
            if "firstname" in teacher:
                name = " ".join(
                    [teacher["firstname"].strip(), teacher["lastname"].strip()]
                )
            else:
                name = teacher["short"].strip()
            tid = teacher["id"].strip("* ")
            self.ds.get_teacher(name=name, internal_id=int(tid))

    async def _parse_classrooms_v2(self, classrooms: list) -> None:
        for classroom in classrooms:
            classroom: dict
            name = classroom["name"].strip()
            cid = classroom["id"].strip(ID_STRIP)
            self.ds.get_classroom(name=name, internal_id=int(cid))

    async def _parse_lessons_v2(self, lessons: list) -> None:
        for lesson in lessons:
            lesson: dict
            # if len(lesson["groupids"]) != len(lesson["classids"]):
            #     print(lesson)
            lid = lesson["id"].strip(ID_STRIP)
            lid = int(lid)
            sid = lesson["subjectid"].strip(ID_STRIP)
            sid = int(sid)
            cid = lesson["classroomidss"][0][0] if lesson["classroomidss"] else None
            cid = int(cid.strip(ID_STRIP)) if cid else None
            params = dict(
                registers=[
                    self.ds.get_register(
                        type=Register.Type.CLASS, internal_id=int(cid.strip(ID_STRIP))
                    )
                    for cid in lesson["classids"]
                ],
                teams=[
                    self.ds.get_team(
                        register=None, internal_id=int(gid.strip(ID_STRIP))
                    )
                    for gid in lesson["groupids"]
                ],
                teachers=[
                    self.ds.get_teacher(internal_id=int(tid.strip(ID_STRIP)))
                    for tid in lesson["teacherids"]
                ],
                subject=self.ds.get_subject(internal_id=sid),
                classroom=self.ds.get_classroom(internal_id=cid) if cid else None,
            )
            self.lessons[lid] = params

    async def _parse_cards_v2(self, cards: list) -> None:
        for card in cards:
            card: dict
            cid = card["id"].strip(ID_STRIP)
            cid = int(cid)
            lid = card["lessonid"].strip(ID_STRIP)
            lid = int(lid)
            params = self.lessons[lid]

            period_id = int(card["period"])
            period = self.periods[period_id]

            days = int(card["days"])
            days = int(4 - log(days, 10))
            weekday = WeekDay(days)

            params["weekday"] = weekday
            params["number"] = int(period["period"])
            params["time_start"] = datetime.strptime(
                period["starttime"], "%H:%M"
            ).time()
            params["time_end"] = datetime.strptime(period["endtime"], "%H:%M").time()

            for team in params["teams"]:
                team: Team
                params["register_"] = team.register_
                params["team"] = team if team.name != "-" else None
                params["internal_id"] = cid * 10000 + team.internal_id
                lesson = Lesson(**params)
                # apparently, constructing a model makes a copy of all its properties
                for k, v in params.items():
                    if k in lesson.__fields__:
                        lesson.__setattr__(k, v)
                self.ds.lessons.append(lesson)

    async def __aenter__(self) -> "EdupageParser":
        await self.api.__aenter__()
        if self.cache_file and isfile(self.cache_file):
            with open(self.cache_file, "r") as f:
                self.cache = json.load(f)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.api.__aexit__(exc_type, exc_val, exc_tb)
        if self.cache_file:
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f, indent=4)
        return await self.session.close()
