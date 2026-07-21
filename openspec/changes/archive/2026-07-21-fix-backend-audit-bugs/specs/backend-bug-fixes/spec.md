# Spec: Backend Audit Bug Fixes

## ADDED Requirements

### Requirement: R1: destpath None Guard

Transfer logic MUST safely handle records where `destpath` is None (new records never previously transferred).

#### Scenario: New record transfer without crash
- GIVEN a record with `destpath = None` (first-time transfer)
- WHEN `celery_transfer_group` processes this record and the new destpath differs
- THEN the code MUST NOT call `os.path.exists(None)`
- AND the record proceeds to update `destpath` without error

#### Scenario: Existing record with different destpath
- GIVEN a record with `destpath = "/old/path.mp4"`
- WHEN transfer produces a new destpath `/new/path.mp4`
- THEN the old file at `/old/path.mp4` MUST be deleted if it exists

### Requirement: R2: Log Message Cleanup

WebSocket log entries MUST strip PID/TID/task_id prefix from message field to improve readability.

#### Scenario: Celery task log message
- GIVEN a log line `[2026-07-21 16:38:41] INFO in celery.app.trace: PID:1234 TID:5678 [abc123] Task started`
- WHEN the WebSocket log monitor parses this line
- THEN the message field MUST be `Task started` (without PID/TID/task_id prefix)
- AND timestamp, level, module MUST be extracted correctly

#### Scenario: Non-matching log line
- GIVEN a log line that does not match the LOGGING_FORMAT pattern
- WHEN the WebSocket log monitor parses this line
- THEN the line MUST be skipped gracefully without exception

### Requirement: R3: Single WebSocket Accept

WebSocket connections MUST be accepted exactly once, at the endpoint level before authentication.

#### Scenario: WebSocket connection lifecycle
- GIVEN a client connects to `/api/v1/ws/logs`
- WHEN the endpoint accepts the connection and authenticates via first message
- THEN `websocket.accept()` MUST be called exactly once
- AND `LogConnectionManager.connect()` MUST NOT call `accept()` again
- AND the connection MUST be added to active_connections and monitor task started

### Requirement: R4: Absolute Log Path

Log file path MUST be resolved to an absolute path at startup to ensure consistency across processes.

#### Scenario: Different CWD between uvicorn and Celery
- GIVEN `LOGGING_LOCATION` is configured as `./data/bonita.log`
- WHEN `init_log_config()` runs in either uvicorn or Celery worker
- THEN the path MUST be resolved to an absolute path via `os.path.abspath()`
- AND the parent directory MUST be created if missing
- AND `settings.LOGGING_LOCATION` MUST be updated to the resolved absolute path
- AND both processes MUST write to the same file
