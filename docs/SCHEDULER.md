# Scheduler API Documentation

This document describes the public API for all schedule-related operations in Kurs Bot.

## Overview

The scheduler module provides a unified public API through `src/scheduler/api.py`. All schedule operations should use this facade rather than importing internal implementation modules.

## Public API

### Import Pattern
```python
from src.scheduler import api as scheduler_api
```

### Core Functions

#### `create_daily_schedule(user_id, lesson_id, time_str, **kwargs)`
Creates a daily recurring schedule for lesson delivery.

**Parameters:**
- `user_id` (int): The user ID
- `lesson_id` (int): Starting lesson ID
- `time_str` (str): Time in "HH:MM" format (local to user's timezone)
- `session` (Session, optional): Database session

**Returns:** `Schedule` object

**Example:**
```python
schedule = scheduler_api.create_daily_schedule(
    user_id=123,
    lesson_id=1,
    time_str="07:30",
    session=db_session
)
```

#### `update_daily_schedule(schedule_id, time_str, **kwargs)`
Updates an existing daily schedule with a new time.

**Parameters:**
- `schedule_id` (int): The schedule ID to update
- `time_str` (str): New time in "HH:MM" format
- `session` (Session, optional): Database session

**Returns:** `Schedule` object

#### `create_one_time_schedule(user_id, run_at, message, **kwargs)`
Creates a one-time reminder schedule.

**Parameters:**
- `user_id` (int): The user ID
- `run_at` (datetime): When to send the reminder (UTC)
- `message` (str): The reminder message
- `session` (Session, optional): Database session

**Returns:** `Schedule` object

**Example:**
```python
from datetime import datetime, timedelta

schedule = scheduler_api.create_one_time_schedule(
    user_id=123,
    run_at=datetime.utcnow() + timedelta(hours=2),
    message="Remember to practice today's lesson",
    session=db_session
)
```

#### `deactivate_schedule(schedule_id)`
Deactivates a single schedule.

**Parameters:**
- `schedule_id` (int): The schedule ID to deactivate

**Returns:** `bool` - True if deactivated, False if not found

#### `deactivate_user_schedules(user_id, **kwargs)`
Deactivates all schedules for a user.

**Parameters:**
- `user_id` (int): The user ID
- `schedule_type` (str, optional): Filter by type ('daily', 'one_time', etc.)
- `session` (Session, optional): Database session

**Returns:** `int` - Number of schedules deactivated

#### `get_user_schedules(user_id, **kwargs)`
Retrieves all schedules for a user.

**Parameters:**
- `user_id` (int): The user ID
- `active_only` (bool, optional): Only return active schedules (default: False)
- `session` (Session, optional): Database session

**Returns:** `List[Schedule]`

#### `find_active_daily_schedule(user_id, **kwargs)`
Finds the active daily schedule for a user.

**Parameters:**
- `user_id` (int): The user ID
- `session` (Session, optional): Database session

**Returns:** `Schedule` or `None`

#### `execute_scheduled_task(schedule_id, simulate=False, session=None)`
Executes a scheduled task (used for testing/debugging).

**Parameters:**
- `schedule_id` (int): The schedule ID to execute
- `simulate` (bool): If True, simulates without sending actual messages
- `session` (Session, optional): Database session

**Returns:** `dict` with execution results


## Internal Modules (Do Not Import Directly)

The following modules are internal implementation details and should not be imported directly:

- `src.scheduler.manager` - Database operations
- `src.scheduler.operations` - Core operations
- `src.scheduler.time_utils` - Time parsing utilities
- `src.scheduler.core` - SchedulerService implementation
- `src.scheduler.jobs` - Job management

**Always use the public API (`src.scheduler.api`) instead.**

## Common Patterns

### Checking for Existing Schedule
```python
existing = scheduler_api.find_active_daily_schedule(user_id, session=session)
if existing:
    # Update existing
    scheduler_api.update_daily_schedule(existing.id, new_time, session=session)
else:
    # Create new
    scheduler_api.create_daily_schedule(user_id, lesson_id, time_str, session=session)
```

### Deactivating All User Schedules
```python
count = scheduler_api.deactivate_user_schedules(user_id, session=session)
print(f"Deactivated {count} schedules")
```

### Getting Schedule Status
```python
schedules = scheduler_api.get_user_schedules(user_id, active_only=True, session=session)
for schedule in schedules:
    print(f"Schedule {schedule.id}: {schedule.schedule_type} at {schedule.next_send_time}")
```

## Error Handling

All API functions handle common errors gracefully:

- **Invalid time format**: Returns `None` or raises `ValueError` with clear message
- **User not found**: Returns `None` or empty list
- **Database errors**: Logged and re-raised as appropriate exceptions

## Testing

Run scheduler-specific tests:
```bash
pytest tests/ -k schedule -v
```

Key test files:
- `tests/unit/scheduler/test_scheduler_manager.py`
- `tests/unit/scheduler/test_scheduler_service.py`
- `tests/unit/scheduler/test_timezones.py`
