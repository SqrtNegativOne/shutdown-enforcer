# Steps
```
git clone <repository_url>
cd <repository_name>
uv install
```
Then create a task for the project inside Windows Task Scheduler with the following settings:
- **Trigger**: On logon.
- **Action**: Command `& <path>/shutdown-enforcer/.venv/Scripts/pythonw.exe <path>/shutdown-enforcer/src/shutdown_enforcer.pyw`. `uv` should have already created the virtual environment at `<path>/shutdown-enforcer/.venv/`.
- Run with highest privileges.

# Caution
If you have too much caffeine in your system, you may delete the scheduled closure and shutdown directly from the Task Scheduler. But that's cheating don't do that