# Steps
```
git clone <repository_url>
cd <repository_name>
uv install
```
Then create a task for the project inside Windows Task Scheduler with the following settings:
- **Trigger**: On logon.
- **Action**: Command `& <path>/shutdown-enforcer/.venv/Scripts/python.exe <path>/shutdown-enforcer/src/shutdown_enforcer.pyw`. `uv` should have already created the virtual environment at `<path>/shutdown-enforcer/.venv/`.
- Run with highest privileges.

I will later make it so that the script can automatically inject itself into Task Scheduler.