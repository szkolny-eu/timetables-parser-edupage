import argparse
import asyncio
import json
import os

from timetables.parser.edupage.api import EdupageApi, Portal
from timetables.parser.edupage.parser import EdupageParser

parser = argparse.ArgumentParser(description="Edupage Parser CLI.")
subparsers = parser.add_subparsers(help="command", required=True, dest="command")

parser_check = subparsers.add_parser(name="check")
parser_check.add_argument("edupage", type=str, help="Edupage name")

parser_register = subparsers.add_parser(name="register")

parser_login = subparsers.add_parser(name="login")
parser_login.add_argument("email", type=str, help="Portal e-mail")
parser_login.add_argument("password", type=str, help="Password")

parser_join = subparsers.add_parser(name="join")
parser_join.add_argument("edupage", type=str, help="Edupage name")

parser_parse = subparsers.add_parser(name="parse")
parser_parse.add_argument("edupage", type=str, help="Edupage name")
parser_parse.add_argument(
    "--register", type=str, help="Class name", required=False, default=""
)

if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def a_check(edupage: str):
    async with EdupageApi() as api:
        exists = await api.v1.check_edupage(edupage)
        if exists:
            print(f"Edupage '{edupage}' exists.")
        else:
            print(f"Edupage '{edupage}' does NOT exist.")


async def a_register():
    async with EdupageApi() as api:
        await api.register_interactive()


async def a_login(email: str, password: str):
    async with EdupageApi() as api:
        portal = await api.login(login=email, password=password)
        with open("edupage.json", "w") as f:
            json.dump(portal.dict(), f)
        print(repr(portal))
        print("Sessions saved to edupage.json")


async def a_join(edupage: str):
    with open("edupage.json", "r") as f:
        portal = Portal(**json.load(f))
    print(f"Logged in as '{portal.user_email}'")
    async with EdupageApi() as api:
        account = await api.v2.join_account(portal, edupage)
        print("New account:")
        print(repr(account))
        print("Re-login to use the session")


async def a_parse(edupage: str, register_name: str):
    with open("edupage.json", "r") as f:
        portal = Portal(**json.load(f))
    session = portal.get_session(edupage)
    async with EdupageParser(session, enable_cache=True) as edupage:
        edupage.enqueue_all()
        ds = await edupage.run_all()
        lessons = sorted(ds.lessons, key=lambda x: (x.weekday, x.number))
        if register_name:
            print(
                "\n".join(str(s) for s in lessons if s.register_.name == register_name)
            )
        else:
            for lesson in lessons:
                print(str(lesson))


def main():
    args = parser.parse_args()
    if args.command == "check":
        check(args)
    elif args.command == "register":
        register()
    elif args.command == "login":
        login(args)
    elif args.command == "join":
        join(args)
    elif args.command == "parse":
        parse(args)


def check(args=None):
    if not args:
        args = parser_check.parse_args()
    asyncio.run(a_check(args.edupage))


def register():
    asyncio.run(a_register())


def login(args=None):
    if not args:
        args = parser_login.parse_args()
    asyncio.run(a_login(args.email, args.password))


def join(args=None):
    if not args:
        args = parser_join.parse_args()
    asyncio.run(a_join(args.edupage))


def parse(args=None):
    if not args:
        args = parser_parse.parse_args()
    asyncio.run(a_parse(args.edupage, args.register))


if __name__ == "__main__":
    main()
