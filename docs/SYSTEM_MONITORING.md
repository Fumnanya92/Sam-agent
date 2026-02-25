# System Monitoring Mode

## Overview

Sam can now monitor and report on system performance including CPU, RAM, disk usage, battery status, internet connectivity, and top processes.

## Features

### 1. **CPU Monitoring**
- Real-time CPU usage percentage
- Updated with 1-second interval for accuracy

### 2. **Memory (RAM) Monitoring**
- Current RAM usage percentage
- Used RAM in GB
- Total available RAM in GB

### 3. **Disk Monitoring**
- Disk usage percentage
- Used disk space in GB
- Total disk capacity in GB

### 4. **Battery Status** (if available)
- Battery percentage
- Charging status (plugged in / running on battery)
- Returns `null` for desktop computers without battery

### 5. **Internet Connectivity**
- Checks connection to Google DNS (8.8.8.8)
- Reports online/offline status
- 2-second timeout for quick response

### 6. **Process Monitoring**
- Lists top 3 CPU-intensive processes
- Shows process name and CPU usage
- Filters out system idle processes

## Voice Commands

Sam responds to natural language queries about system status:

```
"What's my CPU usage?"
"How's my system doing?"
"Check system status"
"Am I online?"
"What's my RAM usage?"
"How much battery do I have?"
"Check disk space"
"System performance"
"What's draining my machine?"
```

## Example Interaction

**You**: "How's my system doing?"

**Sam**: 
```
Sir,

CPU usage is 38 percent.
RAM usage is 79.4 percent. 6.29 gigabytes of 7.92 gigabytes.
Disk usage is 76.6 percent. 364.86 gigabytes of 476.37 gigabytes.

Internet connection is active.

Top processes:
Chrome at 15.2 percent.
Python at 8.5 percent.
```

## Technical Details

### Dependencies
- **psutil** - Cross-platform library for system monitoring

Install with:
```bash
pip install psutil
```

### Module Structure

```
system/
├── __init__.py
└── system_monitor.py    # Core monitoring functions
```

### Functions

#### `get_cpu_usage()`
Returns current CPU usage as a percentage (float).

#### `get_ram_usage()`
Returns dictionary:
```python
{
    "percent": float,      # Usage percentage
    "used_gb": float,     # Used RAM in GB
    "total_gb": float     # Total RAM in GB
}
```

#### `get_disk_usage()`
Returns dictionary:
```python
{
    "percent": float,      # Usage percentage
    "used_gb": float,     # Used space in GB
    "total_gb": float     # Total capacity in GB
}
```

#### `get_battery_status()`
Returns dictionary or None:
```python
{
    "percent": float,      # Battery percentage
    "plugged": bool       # True if charging
}
```

#### `get_top_process()`
Returns list of top 3 processes:
```python
[
    {
        "pid": int,           # Process ID
        "name": str,          # Process name
        "cpu_percent": float  # CPU usage
    },
    ...
]
```

#### `is_online()`
Returns boolean indicating internet connectivity.

#### `get_system_report()`
Returns complete system report with all metrics.

## Implementation

### 1. Core Module
[system/system_monitor.py](../system/system_monitor.py) contains all monitoring functions.

### 2. Intent Handler
[main.py](../main.py) includes the `system_status` intent handler that:
1. Calls `get_system_report()`
2. Formats the data into natural language
3. Speaks the report using TTS
4. Logs to UI

### 3. Intent Configuration
[core/prompt.txt](../core/prompt.txt) includes:
- `system_status` in the intent list
- Detection rules for system-related queries
- No parameters required

## Testing

### Unit Test
[tests/test_system_mode.py](../tests/test_system_mode.py) - Basic system report generation

Run with:
```bash
python tests/test_system_mode.py
```

### Integration Test
[tests/test_system_integration.py](../tests/test_system_integration.py) - Complete integration test

Run with:
```bash
python tests/test_system_integration.py
```

Tests include:
1. System report generation
2. Intent configuration verification
3. Main.py handler verification
4. Sample voice commands
5. Expected response format

## Platform Support

### Windows
- ✅ CPU usage
- ✅ RAM usage
- ✅ Disk usage
- ✅ Battery (laptops)
- ✅ Internet connectivity
- ✅ Process monitoring

### Linux
- ✅ CPU usage
- ✅ RAM usage
- ✅ Disk usage
- ✅ Battery (laptops)
- ✅ Internet connectivity
- ✅ Process monitoring

### macOS
- ✅ CPU usage
- ✅ RAM usage
- ✅ Disk usage
- ✅ Battery (laptops)
- ✅ Internet connectivity
- ✅ Process monitoring

## Use Cases

### 1. Performance Monitoring
Check if system resources are being overused before starting resource-intensive tasks.

### 2. Troubleshooting
Identify which processes are consuming CPU when system feels slow.

### 3. Battery Management
Check battery status before unplugging laptop.

### 4. Disk Space Management
Monitor disk space to avoid running out of storage.

### 5. Connectivity Verification
Verify internet connection before attempting network operations.

## Future Enhancements

### Potential Features
- 🔄 **Continuous Monitoring** - Alert when resources exceed thresholds
- 🔋 **Power Management** - Auto enable battery saver mode
- 🧠 **Adaptive Performance** - Auto close heavy apps when resources low
- 🔧 **Self-Healing** - Restart broken services automatically
- 📊 **Historical Tracking** - Track system performance over time
- ⚠️ **Proactive Alerts** - "Sir, RAM is at 95%, recommend closing some apps"

### Advanced Capabilities
- Network bandwidth monitoring
- GPU usage tracking
- Temperature monitoring
- Fan speed control
- Process kill/restart commands
- System optimization suggestions

## Troubleshooting

### psutil Not Found
```bash
pip install psutil
```

### Permission Errors
Some operations may require elevated privileges. Run as administrator on Windows or use `sudo` on Linux/macOS.

### Battery Returns None
This is normal for desktop computers without batteries.

### Internet Always Shows Offline
Check firewall settings - connection to 8.8.8.8 port 53 must be allowed.

## Architecture

```
Voice Input: "How's my system?"
      ↓
Intent Detection (LLM)
      ↓
Intent: system_status
      ↓
main.py handler
      ↓
get_system_report()
      ↓
psutil queries
      ↓
Format message
      ↓
TTS Output (Edge TTS)
```

## Summary

System Monitoring Mode gives Sam awareness of machine health and performance. This is the foundation for more advanced features like adaptive performance management, power optimization, and self-healing capabilities.

Sam can now answer:
- ✅ "How's my system doing?"
- ✅ "What's using my CPU?"
- ✅ "Do I have enough disk space?"
- ✅ "Am I online?"
- ✅ "How's my battery?"

**Status**: ✅ Fully implemented and tested
**Dependencies**: psutil 7.2.2+
**Platform**: Cross-platform (Windows, Linux, macOS)

---

**This is the beginning of machine awareness for Sam.**
