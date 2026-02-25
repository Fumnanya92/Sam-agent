# Advanced System Mode - Complete Guide

## Overview

Advanced System Mode gives Sam **autonomous control** over system performance with real-time monitoring, process management, and intelligent intervention capabilities.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              ADVANCED SYSTEM MODE                    │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐│
│  │   Process    │  │   System     │  │   Auto    ││
│  │   Control    │  │   Watcher    │  │   Mode    ││
│  └──────────────┘  └──────────────┘  └───────────┘│
│         │                 │                 │       │
│         ├─ Heavy Detection│                 │       │
│         ├─ Process Kill   ├─ Background     │       │
│         └─ Performance    │   Monitoring    │       │
│           Advisory        ├─ Trend Tracking │       │
│                          └─ History         │       │
│                                    │        │       │
│                          ┌─────────▼────────▼─────┐ │
│                          │  Autonomous Control    │ │
│                          │  CPU > 90% → Auto Kill │ │
│                          └────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

## Features

### 1. **Process Control** (`system/process_control.py`)

#### Heavy Process Detection
Identifies resource-intensive applications in real-time.

```python
from system.process_control import get_heavy_processes

# Get top 5 CPU-intensive processes
heavy = get_heavy_processes(5)
# Returns: [{'pid': int, 'name': str, 'cpu_percent': float}, ...]
```

#### Process Termination
Kill processes by name with fuzzy matching.

```python
from system.process_control import kill_process_by_name

# Kill all processes matching "chrome"
killed = kill_process_by_name("chrome")
# Returns: ['chrome.exe', 'chrome.exe'] (all killed instances)
```

**Safety Features:**
- Requires explicit process name
- Returns list of killed processes
- Handles access denied gracefully
- Won't crash if process already terminated

### 2. **System Watcher** (`system/system_watcher.py`)

Background daemon that continuously monitors system performance.

#### Key Features:
- **Continuous Monitoring**: Samples every 1 second
- **History Tracking**: Stores last 120 samples (2 minutes)
- **Trend Analysis**: Calculate average CPU/RAM usage
- **Auto Mode**: Autonomous intervention when overloaded

#### Usage:

```python
from system.system_watcher import SystemWatcher

# Initialize and start
watcher = SystemWatcher()
watcher.start()

# Enable autonomous mode
watcher.enable_auto_mode()

# Get average load
avg_cpu, avg_ram = watcher.get_average_load()

# Stop monitoring
watcher.stop()
```

#### Auto Mode Logic:
- Monitors CPU and RAM continuously
- When CPU > 90%: Automatically kills heaviest process
- Excludes system processes from termination
- Logs all auto-interventions

### 3. **Performance Mode**

Analyzes current system load and identifies bottlenecks.

**Sam's Response:**
```
"Sir, the heaviest process is Chrome using 45.2 percent CPU.
Next is Python at 12.8 percent."
```

### 4. **Autonomous Mode**

Sam manages system performance automatically without user intervention.

**Capabilities:**
- Real-time overload detection
- Automatic process termination
- Intelligent process selection (ignores system processes)
- Continuous background monitoring

**When Active:**
- Monitors every second
- CPU > 90% → Auto-kills heaviest app
- Logs all interventions
- Prevents system crashes

## Voice Commands

### Process Management

| Command | Intent | Action |
|---------|--------|--------|
| "Kill Chrome" | kill_process | Terminates Chrome |
| "Close Notepad" | kill_process | Closes Notepad |
| "Terminate that process" | kill_process | Asks for process name |
| "Stop the heavy app" | kill_process | Asks for process name |

### Performance Analysis

| Command | Intent | Action |
|---------|--------|--------|
| "What's heavy?" | performance_mode | Lists heavy processes |
| "Optimize system" | performance_mode | Analyzes performance |
| "Performance mode" | performance_mode | Shows bottlenecks |
| "What's using resources?" | performance_mode | Identifies heavy apps |

### Autonomous Control

| Command | Intent | Action |
|---------|--------|--------|
| "Enable auto mode" | auto_mode | Activates autonomous management |
| "Manage system automatically" | auto_mode | Starts auto-intervention |
| "Autonomous mode on" | auto_mode | Enables background control |

### Trend Analysis

| Command | Intent | Action |
|---------|--------|--------|
| "System trend" | system_trend | Shows average load |
| "Average load" | system_trend | Reports CPU/RAM trends |
| "Performance history" | system_trend | Historical performance |
| "How has my system been?" | system_trend | Trend summary |

## Complete Interaction Examples

### Example 1: Identify and Kill Heavy Process

**You:** "What's heavy?"

**Sam:** "Sir, the heaviest process is Chrome using 65.3 percent CPU. Next is Spotify at 15.2 percent."

**You:** "Kill Chrome"

**Sam:** "Sir, I have terminated chrome.exe, chrome.exe, chrome.exe." *(all instances)*

### Example 2: Enable Autonomous Mode

**You:** "Enable auto mode"

**Sam:** "Sir, autonomous performance mode enabled. I will monitor and manage system load automatically."

*(Later, when CPU spikes to 92%)*

**Console:** `[AUTO MODE] Terminated chrome.exe`

### Example 3: Check System Trends

**You:** "System trend"

**Sam:** "Sir, average CPU load is 38.5 percent and RAM usage is 72.3 percent over the past monitoring period."

### Example 4: Performance Advisory

**You:** "How's my system doing?"

**Sam:** *(system_status)* "Sir, CPU usage is 85 percent. RAM usage is 78.4 percent..."

**You:** "What's draining it?"

**Sam:** *(performance_mode)* "Sir, the heaviest process is OBS using 42.7 percent CPU."

## Implementation Details

### Files Created

1. **system/process_control.py**
   - `get_heavy_processes(limit=5)` - Detect heavy processes
   - `kill_process_by_name(name)` - Terminate processes

2. **system/system_watcher.py**
   - `SystemWatcher` class - Background monitoring daemon
   - Auto-intervention logic
   - Trend tracking

### Files Modified

1. **main.py**
   - Added imports for process control and watcher
   - Initialized SystemWatcher on startup
   - Added 4 new intent handlers:
     - `kill_process` - Process termination
     - `performance_mode` - Heavy process advisory
     - `auto_mode` - Autonomous management
     - `system_trend` - Trend reporting

2. **core/prompt.txt**
   - Added 4 new intents
   - Added parameter rules
   - Added detection rules for system management

### Configuration

#### System Watcher Parameters

```python
class SystemWatcher:
    max_samples = 120      # 2 minutes of history (1 sample/sec)
    auto_threshold = 90    # CPU % that triggers auto-kill
```

#### Customize Auto Mode Threshold

Edit `system/system_watcher.py`:

```python
def _auto_logic(self, cpu, ram):
    if cpu > 85:  # Lower threshold (default: 90)
        # ... auto intervention logic
```

## Safety Considerations

### ⚠️ Auto Mode Warnings

**Auto mode will automatically kill processes!**

- CPU > 90% triggers auto-termination
- Heaviest process is always targeted
- System processes are excluded
- No user confirmation required

**Recommended Usage:**
- Test in safe environment first
- Monitor console logs for interventions
- Disable if unwanted terminations occur
- Use performance_mode first to identify issues

### Process Kill Safety

- Requires explicit process name
- Partial name matching (e.g., "chrome" matches "chrome.exe")
- Handles permission errors gracefully
- Won't crash if process doesn't exist
- Returns list of actually killed processes

### Protected Processes

Auto mode excludes:
- `System`
- `System Idle Process`
- `Idle`
- Kernel processes

## Testing

### Unit Tests

```bash
# Test all advanced system mode features
python tests/test_advanced_system_mode.py
```

**Tests Include:**
1. Heavy process detection
2. System watcher initialization
3. Background monitoring
4. Average load calculation
5. Auto mode toggle
6. Intent configuration
7. Handler verification
8. Sample commands

### Manual Testing

```bash
# Start Sam
python main.py

# Test commands
"What's heavy?"               # Should list top processes
"System trend"                # Should show average load
"Enable auto mode"            # Should confirm activation
"Kill notepad"                # Should terminate notepad
```

## Performance Impact

### System Watcher Overhead
- **CPU**: < 0.1% (1 sample per second)
- **Memory**: ~1-2 MB (120 samples stored)
- **Thread**: Single background daemon thread

### Process Detection
- **Time**: ~50-100ms to scan all processes
- **Impact**: Minimal (runs on-demand)

### Auto Mode
- **Continuous**: Always running when enabled
- **Intervention**: <100ms to kill process
- **Logging**: Console output for debugging

## Troubleshooting

### "Process not found"
- Process may have already closed
- Check exact process name in Task Manager
- Try partial name (e.g., "chrome" instead of "chrome.exe")

### "Access Denied"
- Some processes require administrator privileges
- Run Sam as administrator on Windows
- System processes cannot be killed

### Auto Mode Not Triggering
- CPU must exceed 90% threshold
- Check with "system trend" if monitoring is working
- Verify watcher is started (should be automatic)

### Watcher Not Starting
- Check console for errors
- Restart Sam completely
- Verify psutil is installed

## Future Enhancements

### Planned Features
- 🔋 **Power Mode** - Battery-aware performance
- 🌡️ **Temperature Monitoring** - Thermal throttling detection
- 📊 **Performance Graphs** - Visual trend display
- 🎯 **Smart Targeting** - Learn which apps to kill
- ⏰ **Scheduled Optimization** - Periodic cleanup
- 💾 **Memory Pressure** - RAM-based intervention
- 🔔 **Proactive Alerts** - Warn before overload

### Advanced Capabilities
- Process priority adjustment
- CPU affinity management
- Network bandwidth control
- Disk I/O monitoring
- GPU usage tracking
- Container/VM management

## Technical Reference

### Dependencies
- **psutil**: Cross-platform system monitoring
- **threading**: Background daemon execution
- **time**: Sleep intervals for monitoring

### Platform Support

| Feature | Windows | Linux | macOS |
|---------|---------|-------|-------|
| Process Detection | ✅ | ✅ | ✅ |
| Process Kill | ✅ | ✅ | ✅ |
| CPU Monitoring | ✅ | ✅ | ✅ |
| RAM Monitoring | ✅ | ✅ | ✅ |
| Auto Mode | ✅ | ✅ | ✅ |

### API Reference

#### `get_heavy_processes(limit=5)`
Returns top CPU-intensive processes.

**Returns:** `List[Dict[str, Any]]`
```python
[
    {'pid': 1234, 'name': 'chrome.exe', 'cpu_percent': 45.2},
    ...
]
```

#### `kill_process_by_name(name)`
Terminates all processes matching name.

**Parameters:**
- `name` (str): Process name (partial match)

**Returns:** `List[str]` - Names of killed processes

#### `SystemWatcher.start()`
Starts background monitoring.

#### `SystemWatcher.enable_auto_mode()`
Activates autonomous intervention.

#### `SystemWatcher.get_average_load()`
Returns average CPU and RAM usage.

**Returns:** `Tuple[float, float]` - (avg_cpu, avg_ram)

## Summary

Advanced System Mode transforms Sam from a passive assistant into an **active system guardian** with:

✅ **Real-time monitoring** - Continuous background tracking
✅ **Process control** - Kill heavy apps on command
✅ **Autonomous management** - Auto-intervention when overloaded
✅ **Trend analysis** - Historical performance insights
✅ **Performance advisory** - Identify bottlenecks instantly

**This is Sam's first step toward true machine intelligence.**

---

**Status**: ✅ Fully implemented and tested
**Risk Level**: ⚠️ Medium (auto mode kills processes)
**Dependencies**: psutil
**Platform**: Cross-platform

**⚠️ USE AUTO MODE WITH CAUTION - It will terminate processes automatically!**
