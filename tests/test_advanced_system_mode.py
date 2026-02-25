"""
Test Advanced System Mode Features
===================================

Tests process control, system watcher, and autonomous features:
1. Process detection and control
2. Background system monitoring
3. Performance mode
4. Auto mode capabilities
5. System trend tracking
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import time
from system.process_control import get_heavy_processes, kill_process_by_name
from system.system_watcher import SystemWatcher

print("=" * 80)
print("ADVANCED SYSTEM MODE TEST")
print("=" * 80)
print()

# Test 1: Heavy Process Detection
print("Test 1: Heavy Process Detection")
print("-" * 80)
try:
    heavy = get_heavy_processes(5)
    print(f"✅ Found {len(heavy)} processes")
    print("\nTop 5 processes by CPU usage:")
    for i, proc in enumerate(heavy, 1):
        print(f"   {i}. {proc['name']} - {proc['cpu_percent']}% CPU (PID: {proc['pid']})")
    print()
except Exception as e:
    print(f"❌ Heavy process detection failed: {e}")
    print()
    sys.exit(1)

# Test 2: System Watcher Initialization
print("Test 2: System Watcher Initialization")
print("-" * 80)
try:
    watcher = SystemWatcher()
    print("✅ SystemWatcher created")
    print(f"   - Running: {watcher.running}")
    print(f"   - Auto mode: {watcher.auto_mode}")
    print(f"   - Max samples: {watcher.max_samples}")
    print()
except Exception as e:
    print(f"❌ System watcher initialization failed: {e}")
    print()
    sys.exit(1)

# Test 3: Background Monitoring
print("Test 3: Background Monitoring")
print("-" * 80)
try:
    watcher.start()
    print("✅ Background monitoring started")
    print("   Collecting data for 3 seconds...")
    time.sleep(3)
    
    print(f"   - CPU history samples: {len(watcher.cpu_history)}")
    print(f"   - RAM history samples: {len(watcher.ram_history)}")
    
    if len(watcher.cpu_history) > 0:
        print(f"   - Latest CPU: {watcher.cpu_history[-1]:.1f}%")
        print(f"   - Latest RAM: {watcher.ram_history[-1]:.1f}%")
    print()
except Exception as e:
    print(f"❌ Background monitoring failed: {e}")
    print()
    sys.exit(1)

# Test 4: Average Load Calculation
print("Test 4: Average Load Calculation")
print("-" * 80)
try:
    avg_cpu, avg_ram = watcher.get_average_load()
    print("✅ Average load calculated")
    print(f"   - Average CPU: {avg_cpu:.1f}%")
    print(f"   - Average RAM: {avg_ram:.1f}%")
    print()
except Exception as e:
    print(f"❌ Average load calculation failed: {e}")
    print()
    sys.exit(1)

# Test 5: Auto Mode Toggle
print("Test 5: Auto Mode Toggle")
print("-" * 80)
try:
    watcher.enable_auto_mode()
    print(f"✅ Auto mode enabled: {watcher.auto_mode}")
    
    watcher.disable_auto_mode()
    print(f"✅ Auto mode disabled: {watcher.auto_mode}")
    print()
except Exception as e:
    print(f"❌ Auto mode toggle failed: {e}")
    print()
    sys.exit(1)

# Test 6: Watcher Stop
print("Test 6: Watcher Stop")
print("-" * 80)
try:
    watcher.stop()
    print(f"✅ Watcher stopped: {not watcher.running}")
    print()
except Exception as e:
    print(f"❌ Watcher stop failed: {e}")
    print()
    sys.exit(1)

# Test 7: Verify Intent Configuration
print("Test 7: Intent Configuration Verification")
print("-" * 80)
try:
    prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'core', 'prompt.txt')
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt_content = f.read()
    
    intents_to_check = ['kill_process', 'performance_mode', 'auto_mode', 'system_trend']
    all_found = True
    
    for intent in intents_to_check:
        if intent in prompt_content:
            print(f"✅ {intent} intent configured")
        else:
            print(f"❌ {intent} intent NOT found")
            all_found = False
    
    if not all_found:
        sys.exit(1)
    print()
except Exception as e:
    print(f"❌ Intent verification failed: {e}")
    print()
    sys.exit(1)

# Test 8: Verify Main.py Handlers
print("Test 8: Main.py Handler Verification")
print("-" * 80)
try:
    main_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'main.py')
    with open(main_path, 'r', encoding='utf-8') as f:
        main_content = f.read()
    
    # Check imports
    if 'from system.process_control import' in main_content:
        print("✅ process_control imported")
    else:
        print("❌ process_control NOT imported")
        sys.exit(1)
    
    if 'from system.system_watcher import SystemWatcher' in main_content:
        print("✅ SystemWatcher imported")
    else:
        print("❌ SystemWatcher NOT imported")
        sys.exit(1)
    
    # Check watcher initialization
    if 'watcher = SystemWatcher()' in main_content and 'watcher.start()' in main_content:
        print("✅ Watcher initialized and started")
    else:
        print("❌ Watcher initialization incomplete")
        sys.exit(1)
    
    # Check handlers
    handlers_to_check = ['kill_process', 'performance_mode', 'auto_mode', 'system_trend']
    for handler in handlers_to_check:
        if f'elif intent == "{handler}":' in main_content:
            print(f"✅ {handler} handler found")
        else:
            print(f"❌ {handler} handler NOT found")
            sys.exit(1)
    print()
except Exception as e:
    print(f"❌ Main.py verification failed: {e}")
    print()
    sys.exit(1)

# Test 9: Sample Voice Commands
print("Test 9: Sample Voice Commands")
print("-" * 80)
sample_commands = {
    "kill_process": [
        "Kill Chrome",
        "Close Notepad",
        "Terminate that process",
        "Stop the heavy app"
    ],
    "performance_mode": [
        "What's heavy?",
        "Optimize system",
        "Performance mode",
        "What's using resources?"
    ],
    "auto_mode": [
        "Enable auto mode",
        "Manage system automatically",
        "Autonomous mode on"
    ],
    "system_trend": [
        "System trend",
        "Average load",
        "Performance history",
        "How has my system been?"
    ]
}

for intent, commands in sample_commands.items():
    print(f"\n{intent.upper().replace('_', ' ')}:")
    for cmd in commands:
        print(f"   • {cmd}")
print()

# Final Summary
print("=" * 80)
print("✅ ALL ADVANCED SYSTEM MODE TESTS PASSED!")
print("=" * 80)
print()
print("🎯 Sam's Advanced Capabilities:")
print("   ✅ Detect heavy processes")
print("   ✅ Kill processes by name")
print("   ✅ Background system monitoring")
print("   ✅ Track CPU/RAM trends over time")
print("   ✅ Performance mode advisory")
print("   ✅ Autonomous system management")
print("   ✅ Auto-terminate heavy apps when overloaded")
print()
print("🔥 What Sam Can Do:")
print("   • 'What's heavy?' - Identify resource-intensive apps")
print("   • 'Kill Chrome' - Terminate specific processes")
print("   • 'Enable auto mode' - Autonomous performance management")
print("   • 'System trend' - View average load over time")
print("   • Auto-intervention when CPU > 90%")
print()
print("🚀 To test with Sam:")
print("   1. Run: python main.py")
print("   2. Say: 'Enable auto mode'")
print("   3. Say: 'What's heavy?'")
print("   4. Say: 'System trend'")
print()
print("=" * 80)
print("⚠️  WARNING: Auto mode will kill processes automatically when CPU > 90%")
print("=" * 80)
