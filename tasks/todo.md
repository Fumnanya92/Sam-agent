# Code Quality Fixes - Phase 1

## Tasks
- [x] Fix 1: memory/memory_manager.py - asyncio.get_event_loop() -> get_running_loop()
- [x] Fix 2: daemon/main.py - store and cancel bridge task
- [x] Fix 3: config/loader.py - use config() instead of load_config()
- [x] Verify with import test
- [x] Commit changes

## Status
DONE - All three code quality fixes completed and committed.

## Changes Summary

### Fix 1: memory/memory_manager.py
- Replaced deprecated `asyncio.get_event_loop()` with `asyncio.get_running_loop()`
- Removed unreachable `else` branch with `run_until_complete()` (would deadlock in running loop)
- Now uses `loop.create_task(_write())` for fire-and-forget execution
- Simplified error handling with cleaner try/except block

### Fix 2: daemon/main.py
- Added global variable `_bridge_task` to track the bridge chat queue task
- Modified `_run_ai_loop_headless()` to store the task handle: `_bridge_task = asyncio.create_task(_bridge_chat_queue())`
- Updated lifespan shutdown logic to cancel the bridge task before cancelling the ai_loop task
- Ensures proper cleanup of all background tasks on shutdown

### Fix 3: config/loader.py
- Changed `get()` function to call cached `config()` instead of `load_config()`
- Eliminates redundant disk reads on every call
- Improves performance for repeated config access
- Maintains same API and return values

## Verification
- Import test: All imports successful ✓
- Commit: 98c284c created successfully ✓
- Git log: Commit appears in history ✓
