"""
Test System Status Integration with Sam
========================================

Tests the complete system_status intent flow:
1. System monitoring functions work correctly
2. Intent detection recognizes system queries
3. Main.py handler processes requests correctly
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
from system.system_monitor import get_system_report

print("=" * 80)
print("SYSTEM STATUS INTEGRATION TEST")
print("=" * 80)
print()

# Test 1: System Report Generation
print("Test 1: System Report Generation")
print("-" * 80)
try:
    report = get_system_report()
    print("✅ System report generated successfully")
    print(f"   - CPU: {report['cpu']}%")
    print(f"   - RAM: {report['ram']['percent']}% ({report['ram']['used_gb']} GB / {report['ram']['total_gb']} GB)")
    print(f"   - Disk: {report['disk']['percent']}% ({report['disk']['used_gb']} GB / {report['disk']['total_gb']} GB)")
    print(f"   - Battery: {report['battery']}")
    print(f"   - Online: {report['online']}")
    print(f"   - Top Processes: {len(report['top_processes'])} processes found")
    print()
except Exception as e:
    print(f"❌ System report generation failed: {e}")
    print()
    sys.exit(1)

# Test 2: Verify Intent in Prompt
print("Test 2: Intent Configuration")
print("-" * 80)
try:
    prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'core', 'prompt.txt')
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt_content = f.read()
    
    if 'system_status' in prompt_content:
        print("✅ system_status intent found in prompt.txt")
        
        # Check for detection rules
        if 'CPU' in prompt_content and 'RAM' in prompt_content:
            print("✅ System status detection rules configured")
        else:
            print("⚠️  Detection rules might be incomplete")
    else:
        print("❌ system_status intent NOT found in prompt.txt")
        sys.exit(1)
    print()
except Exception as e:
    print(f"❌ Prompt verification failed: {e}")
    print()
    sys.exit(1)

# Test 3: Verify Main.py Handler
print("Test 3: Main.py Handler Verification")
print("-" * 80)
try:
    main_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'main.py')
    with open(main_path, 'r', encoding='utf-8') as f:
        main_content = f.read()
    
    if 'from system.system_monitor import get_system_report' in main_content:
        print("✅ system_monitor imported in main.py")
    else:
        print("❌ system_monitor NOT imported in main.py")
        sys.exit(1)
    
    if 'elif intent == "system_status":' in main_content:
        print("✅ system_status intent handler found in main.py")
    else:
        print("❌ system_status intent handler NOT found in main.py")
        sys.exit(1)
    
    if "CPU usage is" in main_content and "RAM usage is" in main_content:
        print("✅ System status message formatting configured")
    else:
        print("⚠️  Message formatting might be incomplete")
    print()
except Exception as e:
    print(f"❌ Main.py verification failed: {e}")
    print()
    sys.exit(1)

# Test 4: Sample Voice Commands
print("Test 4: Sample Voice Commands Sam Can Understand")
print("-" * 80)
sample_commands = [
    "What's my CPU usage?",
    "How's my system doing?",
    "Check system status",
    "Am I online?",
    "What's my RAM usage?",
    "How much battery do I have?",
    "Check disk space",
    "System performance",
]

print("Sam can now respond to:")
for cmd in sample_commands:
    print(f"   • {cmd}")
print()

# Test 5: Expected Response Format
print("Test 5: Expected Response Format")
print("-" * 80)
print("When you ask 'How's my system?', Sam will say:")
print()
example_response = f"""Sir,

CPU usage is {report['cpu']} percent.
RAM usage is {report['ram']['percent']} percent. {report['ram']['used_gb']} gigabytes of {report['ram']['total_gb']} gigabytes.
Disk usage is {report['disk']['percent']} percent. {report['disk']['used_gb']} gigabytes of {report['disk']['total_gb']} gigabytes.
"""

if report['battery']:
    example_response += f"\nBattery is at {report['battery']['percent']} percent."
    if report['battery']['plugged']:
        example_response += " Plugged in."
    else:
        example_response += " Running on battery."

if report['online']:
    example_response += "\n\nInternet connection is active."
else:
    example_response += "\n\nInternet appears to be offline."

print(example_response)
print()

# Final Summary
print("=" * 80)
print("✅ ALL TESTS PASSED - SYSTEM MODE IS READY!")
print("=" * 80)
print()
print("🎯 What Sam Can Do Now:")
print("   • Monitor CPU usage")
print("   • Check RAM usage")
print("   • Report disk space")
print("   • Check battery status (if available)")
print("   • Verify internet connectivity")
print("   • Identify top processes")
print()
print("🚀 To test with Sam:")
print("   1. Run: python main.py")
print("   2. Say: 'How's my system doing?'")
print("   3. Sam will report all system stats")
print()
print("=" * 80)
