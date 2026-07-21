# Design: Fix Backend Audit Bugs

## Bug 1: destpath None Guard

### Current Flow
```
record.destpath (None for new records)
  → os.path.exists(record.destpath)  ← TypeError: expected str, bytes or os.PathLike object, not NoneType
```

### Fix
```python
# Before (line 360-363 and 390-393):
if record.destpath != destpath:
    if os.path.exists(record.destpath):
        os.remove(record.destpath)

# After:
if record.destpath and record.destpath != destpath:
    if os.path.exists(record.destpath):
        os.remove(record.destpath)
```

A `None` destpath means "new record, no previous file" — no cleanup needed. The `and` short-circuits, so `os.path.exists` is never called with None.

### Risk
Minimal. `record.destpath` being truthy is a safe proxy for "previously transferred".

---

## Bug 2: Logs Regex Mismatch

### Current Format
```python
# config.py:67
LOGGING_FORMAT = "[%(asctime)s] %(levelname)s in %(module)s: PID:%(process)d TID:%(thread)d [%(task_id)s] %(message)s"

# logs.py:93
log_pattern = r"\[(.*?)\] (\w+) in ([\w\.]+): (.*)"
```

A real log line looks like:
```
[2026-07-21 16:38:41,123] INFO in celery.app.trace: PID:1234 TID:5678 [abc123] Task started
```

The current regex:
- `\[(.*?)\]` → matches `[2026-07-21 16:38:41,123]` ✅
- `(\w+)` → matches `INFO` ✅
- ` in ` → literal ✅
- `([\w\.]+)` → matches `celery.app.trace` ✅ (`\.` is literal dot in character class)
- `: (.*)` → matches `: PID:1234 TID:5678 [abc123] Task started` ✅

Actually, the regex DOES match. The issue is that `message` includes PID/TID/task_id prefix, which is noise for the frontend. But this is a cosmetic issue, not a functional one.

### Revised Assessment
Bug 2 is **cosmetic, not functional**. The regex works but produces noisy messages. Downgrade to P2.

### Optional Enhancement
Strip the PID/TID/task_id prefix from the message:
```python
# After regex match, clean up the message
message = re.sub(r'^PID:\d+ TID:\d+ \[.*?\]\s*', '', message)
```

---

## Bug 3: Double websocket.accept()

### Current Flow
```
websocket_logs:
  await websocket.accept()          # line 181 — accept #1
  ... auth ...
  await log_manager.connect(websocket)
    → await websocket.accept()      # line 46 — accept #2 (BUG)
```

### Fix
Remove `await websocket.accept()` from `LogConnectionManager.connect()`. The endpoint already handles accept before auth. `connect()` should only append to `active_connections` and start the monitor task.

```python
async def connect(self, websocket: WebSocket):
    self.active_connections.append(websocket)
    if self.log_task is None or self.log_task.done():
        self.stop_flag = False
        self.log_task = asyncio.create_task(self.monitor_log_file())
```

### Risk
Low. The accept is already done at the endpoint level. No other callers of `connect()` exist.

---

## Bug 4: Relative LOGGING_LOCATION

### Current
```python
# config.py:68
LOGGING_LOCATION: str = "./data/bonita.log"
```

Celery workers and uvicorn may have different CWDs.

### Fix
In `init_log_config()`, resolve to absolute path:
```python
def init_log_config():
    log_path = os.path.abspath(settings.LOGGING_LOCATION)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    # ... use log_path for RotatingFileHandler
```

And update `settings.LOGGING_LOCATION` so the WebSocket monitor also uses the resolved path:
```python
settings.LOGGING_LOCATION = log_path
```

### Alternative
Resolve in Settings `model_post_init`, but that runs at import time and `os.makedirs` at import is risky. Better to resolve at `init_log_config()` time (startup).

### Risk
Low. `os.path.abspath` uses CWD at call time, which is the process CWD — correct for both uvicorn and Celery.
