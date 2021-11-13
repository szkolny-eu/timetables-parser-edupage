# Edupage.org timetable parser library

This library provides access to public timetables provided by Edupage.
The resulting dataset is compatible with and based on [timetables-lib](https://github.com/szkolny-eu/timetables-lib).

## Usage examples

### Simple login
```python
async with EdupageApi() as api:
    # login with Edupage Portal (account for multiple schools)
    portal: Portal = await api.login(login="email@example.com", password="PortalPassword")
    # OR
    # login with a single-school Edupage account (i.e. https://example.edupage.com)
    session: Session = await api.login(login="user12345", password="EdupageUser123", edupage="example")
    # OR
    # login using a previously stored session (Portal login not possible here)
    session: Session = await api.login(**old_session.dict())

# list sessions joined to a Portal account
print(portal.sessions)
# get the first session (school)
session = portal.sessions[0]
```
**Note:** it is recommended to save sessions (portal.dict() or session.dict()) for future API calls.
The sessions expire after some (unknown to me) time, a `SessionExpiredError` is raised in that case.

### Parse timetables
```python
async with EdupageParser(session) as parser:
    # enqueue parsing all data (this is required)
    # - try_v1_teachers - whether to use the old API to get some teachers' full names
    # - try_v1_full_teachers - whether to use the old API to get all teachers' full names
    #   ^ this option requires to download and extract a large, zipped JSON payload, so keep this in mind
    parser.enqueue_all(try_v1_teachers=False, try_v1_full_teachers=True)

    # print the current queue, out of curiosity
    print("\n".join(str(s) for s in parser.ds.files))

    # run all enqueued tasks, get a Dataset
    # this typically performs up to two HTTP requests
    ds = await parser.run_all()
    
    # sort lessons, because why not
    lessons = sorted(ds.lessons, key=lambda x: (x.weekday, x.number))
    # print lessons for a specific class
    print("\n".join(str(s) for s in lessons if s.register_.name == "1A"))
```

### Check if Edupage exists
```python
async with EdupageApi() as api:
    exists = await api.v1.check_edupage("edupagename")
```

### Join a portal account to another Edupage
```python
async with EdupageApi() as api:
    # join a new Edupage to a portal account
    # (effectively creating a guest account on that Edupage)
    account = await api.v2.join_account(portal, "edupagename")
    print(repr(account))
    # get a session for the just-created account
    session = await api.login(**account.dict())
```

### Create a Portal account interactively
```python
async with EdupageApi() as api:
    await api.register_interactive()
```

## Command-line scripts

Available after installing the package (if scripts directory is in your `PATH`, or you're using a virtualenv). 
```shell
$ edupage check guests
Edupage 'guests' exists.
$ edupage register
Enter e-mail address: ...
$ edupage login email@example.com PortalPassword
Portal(user_id=12345, user_email='email@example.com', sessions=[])
Sessions saved to edupage.json
$ edupage join edupagename
Logged in as 'email@example.com'
New account:
Account(...)
Re-login to use the session
$ edupage parse othername --register 1A
Parsing 'edupage://othername/get/...'
Lesson(...)
Lesson(...)
...
```

