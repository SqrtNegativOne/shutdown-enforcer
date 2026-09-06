# Steps
```
git clone <repository_url>
cd <repository_name>
uv sync
copy config.yaml.example config.yaml
```
Then configure your schedule in `config.yaml` (which is gitignored).

Next, create a task for the project inside Windows Task Scheduler with the following settings:
- **Trigger**: On logon.
- **Action**: Command `& <path>/shutdown-enforcer/.venv/Scripts/pythonw.exe <path>/shutdown-enforcer/src/setup.pyw`. `uv` should have already created the virtual environment at `<path>/shutdown-enforcer/.venv/`.
- Run with highest privileges.

# Timeline
Default times: `INITIAL_NOTIF = 23:00`, `APP_CLOSURE = 23:35`, `SHUTDOWN = 23:50`.

| Time | Event |
|------|-------|
| 23:00 | "Closure in 35 minutes (at 23:35)" |
| 23:25 | "Closure in 10 minutes (at 23:35)" |
| 23:30 | "Closure in 5 minutes (at 23:35)" |
| 23:33 | "Closure in 2 minutes (at 23:35)" |
| 23:34 | "Closure in 1 minute (at 23:35)" |
| 23:34:30 | "Closure in 30 seconds" |
| 23:35 | *(close all windows)* |
| 23:35:35 | "Closed. Shutdown in 15 minutes (at 23:50)" |
| 23:40 | "Shutdown in 10 minutes (at 23:50)" |
| 23:45 | "Shutdown in 5 minutes (at 23:50)" |
| 23:48 | "Shutdown in 2 minutes (at 23:50)" |
| 23:49 | "Shutdown in 1 minute (at 23:50)" |
| 23:49:30 | "Shutdown in 30 seconds" |
| 23:50 | *(shutdown)* |

# Caution
If you have too much caffeine in your system, you may delete the scheduled closure and shutdown directly from the Task Scheduler. But that's cheating don't do that