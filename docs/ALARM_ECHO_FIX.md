# Sam Alarm & Echo Fix - Summary

## Issues Fixed

### 1. **Echo/Feedback Loop (Sam Listening to Himself)**

**Problem:** Sam's TTS output was being captured by the microphone as user input, causing him to respond to his own speech.

**Root Cause:** Race condition where speech recognition wasn't immediately suppressed when Sam started speaking.

**Solution:** 
- Modified [speech_client.html](speech_client.html) to:
  1. Set `suppressed` mode BEFORE pausing recognition
  2. Check suppression status BEFORE processing any transcript
  3. Added console logging to track suppressed transcripts

**Changes Made:**
- [speech_client.html](speech_client.html#L86-L91): Moved `setMode('suppressed')` before `pauseRecognition()`
- [speech_client.html](speech_client.html#L175-L182): Added early suppression check with logging

---

### 2. **Wrong Alarm System (Using Reminders Instead of Windows Alarms)**

**Problem:** When user said "set alarm for 2:30", Sam used his internal reminder system (just plays a sound) instead of Windows' native Alarms & Clock app.

**Root Cause:** No integration with Windows alarm system; all timed alerts used ReminderEngine.

**Solution:**
1. Created new Windows alarm integration module
2. Added new `set_alarm` intent separate from `set_reminder`
3. Updated prompt to distinguish between alarms and reminders

**Changes Made:**

#### New Files:
- [actions/windows_alarm.py](actions/windows_alarm.py) - Complete Windows alarm integration:
  - `set_windows_alarm()` - Creates scheduled tasks via Windows Task Scheduler
  - `list_windows_alarms()` - Lists all Sam-created alarms
  - `cancel_windows_alarm()` - Cancels scheduled alarms
  - Creates PowerShell notification scripts with Windows toast notifications and alarm sounds

#### Modified Files:
- [intents/handlers.py](intents/handlers.py#L6):
  - Added `timedelta` import
  - Added `_handle_set_alarm()` function (calls Windows Task Scheduler)
  - Modified `_handle_set_reminder()` to only handle internal reminders
  - Added alarm handler to intent router

- [core/prompt.txt](core/prompt.txt):
  - Added `set_alarm` to intents list
  - Split alarm/reminder rules:
    - "set alarm for [time]" → `set_alarm` (Windows system)
    - "remind me at [time]" → `set_reminder` (internal)
    - "remind me in [duration]" → `set_reminder` (internal)

---

## How It Works Now

### Alarms (Windows System-Level)
```
User: "Set alarm for 7:30 AM"
Sam: Detects set_alarm intent
     → Creates Windows Task Scheduler task
     → Task triggers at 7:30 AM with:
        - Windows toast notification
        - Looping alarm sound
        - TTS announcement
     → Works even if Sam isn't running
```

### Reminders (Sam Internal)
```
User: "Remind me in 15 minutes to call John"
Sam: Detects set_reminder intent
     → Adds to ReminderEngine
     → Fires after 15 minutes (only if Sam is running)
     → Plays reminder sound + speaks
```

---

## Testing Instructions

### Test 1: Echo Fix
1. Restart Sam
2. Say "Hey Sam, what time is it?"
3. **Expected:** Sam responds with time, does NOT process his own speech
4. **Check logs:** Should see `[SUPPRESSED]` entries for Sam's voice (in browser console)

### Test 2: Windows Alarm
1. Say "Hey Sam, set alarm for [2 minutes from now]"
2. **Expected:** 
   - Sam says "Alarm set in Windows for [time]"
   - Check Task Scheduler: `Win + R` → `taskschd.msc`
   - Look for task named `SamAlarm_YYYYMMDD_HHMM`
3. Wait for alarm time
4. **Expected:** Windows notification appears with alarm sound

### Test 3: Internal Reminder
1. Say "Hey Sam, remind me in 1 minute to test"
2. **Expected:** Sam says "Reminder set..."
3. Wait 1 minute
4. **Expected:** Sam speaks "Reminder: test" (no Windows notification)

### Test 4: Verify No Cross-Contamination
1. Set multiple alarms and reminders
2. List reminders: "Hey Sam, list reminders"
3. **Expected:** Only internal reminders listed (not Windows alarms)

---

## Technical Details

### Windows Task Scheduler Integration
- Tasks created with name pattern: `SamAlarm_YYYYMMDD_HHMM`
- Each alarm gets a dedicated PowerShell script in: `%TEMP%\SamAlarms\`
- Scripts use Windows Toast Notifications API
- Alarm sound: `ms-winsoundevent:Notification.Looping.Alarm`

### Echo Prevention Mechanism
1. Before Sam speaks: Send `sam_speaking` command via WebSocket
2. HTML client: Set mode to `suppressed`, stop recognition
3. Recognition stopped: Microphone disabled
4. After Sam speaks: Send `sam_done` command
5. HTML client: Resume recognition, set mode to `active`

**Critical timing:**
- Mode must be set BEFORE stopping recognition
- Transcript check must happen BEFORE UI updates

---

## Potential Issues & Solutions

### Issue: Alarm doesn't fire
- **Check:** Task Scheduler permissions
- **Solution:** Run PowerShell as admin if needed

### Issue: Still hearing echo
- **Check:** Browser console for `[SUPPRESSED]` logs
- **Solution:** 
  - Clear browser cache
  - Hard refresh (Ctrl+F5)
  - Check WebSocket latency

### Issue: "Can't parse time"
- **Formats supported:** 
  - "2:30 PM" (12-hour)
  - "14:30" (24-hour)
  - "2:30" (assumes 24-hour if no AM/PM)
- **Solution:** Use clearer time format

---

## Files Modified/Created

### Created:
- `actions/windows_alarm.py` - Windows alarm system integration

### Modified:
- `speech_client.html` - Echo prevention fixes
- `intents/handlers.py` - Added set_alarm handler, fixed imports
- `core/prompt.txt` - Separated alarm/reminder intent rules

---

## Next Steps (Optional Improvements)

1. **Fallback for Task Scheduler Failures:**
   - If Task Scheduler fails, fall back to opening Windows Alarms app

2. **Alarm Management UI:**
   - "Cancel my 7:30 alarm" functionality
   - "List all my alarms" (including Windows alarms)

3. **Recurring Alarms:**
   - Support "set alarm for 7 AM every weekday"

4. **Volume Control:**
   - Let user specify alarm volume

---

## Logs to Monitor

After restart, check:
- `log/sam_main_*.log` - Main execution log
- `log/sam_errors_*.log` - Error tracking
- Browser Console - WebSocket traffic and suppression logs
- Task Scheduler History - Alarm execution logs

```bash
# View recent logs
Get-Content log\sam_main_*.log -Tail 50

# Check for echo issues
Select-String -Path log\sam_main_*.log -Pattern "Final transcript"

# List Sam alarm tasks
schtasks /Query /FO LIST | Select-String -Pattern "SamAlarm"
```

---

## Summary

✅ **Fixed:** Sam no longer listens to himself  
✅ **Fixed:** Alarms now use Windows system (persistent)  
✅ **Added:** Proper distinction between alarms and reminders  
✅ **Added:** Windows Task Scheduler integration  

**Before:** "Set alarm" → Internal reminder (stops when Sam closes)  
**After:** "Set alarm" → Windows scheduled task (system-level persistence)
