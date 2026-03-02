# Fix One-Time Reminder Deletion Bug

## Problem
The AI cannot properly delete one-time reminders because:
1. No function exists for the AI to delete one-time reminders specifically
2. The keyword-based handling in `command_handlers.py` is broken (doesn't match singular forms)
3. The AI responds saying it deleted the reminder, but actually doesn't

## Solution
Add proper AI functions for reminder deletion and remove the broken keyword handling.

## Tasks

### 1. Add new functions to registry
- [x] `delete_one_time_reminder` - Delete a specific one-time reminder by schedule ID
- [x] `delete_all_one_time_reminders` - Delete all one-time reminders for user
- [x] `delete_all_daily_reminders` - Delete all daily reminders for user  
- [x] `delete_all_reminders` - Delete all reminders for user

### 2. Add handlers in executor.py
- [x] `_handle_delete_one_time_reminder` - Handler for delete_one_time_reminder
- [x] `_handle_delete_all_one_time_reminders` - Handler for delete_all_one_time_reminders
- [x] `_handle_delete_all_daily_reminders` - Handler for delete_all_daily_reminders
- [x] `_handle_delete_all_reminders` - Handler for delete_all_reminders

### 3. Remove keyword-based handling
- [x] Remove deletion patterns from `handle_schedule_deletion_commands` in `command_handlers.py`
- [x] Removed the entire `handle_schedule_deletion_commands` function

### 4. Add examples in definitions.py
- [x] Add examples for the new deletion functions in CONTEXT_EXAMPLES

### 5. Test
- [ ] Run existing tests to ensure no regressions
- [ ] Create test for new functions
