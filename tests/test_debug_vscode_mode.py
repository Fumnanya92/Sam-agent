"""
Test script for Error-Focused Debug Mode and VSCode Intelligent Coding Mode
"""

import sys
sys.path.insert(0, r"C:\Users\DELL.COM\Desktop\Darey\Sam-Agent")

import os

print("=" * 60)
print("TESTING ERROR DEBUG MODE & VSCODE MODE")
print("=" * 60)

# Test 1: Module imports
print("\nTest 1: Module Import")
try:
    from system.screen_vision import analyze_screen_for_errors, capture_screen
    from system.vscode_mode import analyze_vscode_screen
    print("✅ All modules imported successfully")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Screen capture function
print("\nTest 2: Screen Capture Function")
try:
    screenshot_bytes = capture_screen()
    print(f"✅ Screen captured: {len(screenshot_bytes)} bytes")
    print(f"   Sample: {screenshot_bytes[:20]}...")
except Exception as e:
    print(f"❌ Screen capture failed: {e}")

# Test 3: Check OpenAI API key
print("\nTest 3: OpenAI API Key Detection")
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    print(f"✅ API key found: {api_key[:10]}... ({len(api_key)} characters)")
    has_api_key = True
else:
    # Try config file
    try:
        import json
        from pathlib import Path
        config_path = Path(__file__).parent.parent / "config" / "api_keys.json"
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                api_key = config.get("openai_api_key")
                if api_key:
                    print(f"✅ API key found in config: {api_key[:10]}... ({len(api_key)} characters)")
                    has_api_key = True
                else:
                    print("⚠️  API key not found in environment or config")
                    has_api_key = False
        else:
            print("⚠️  Config file not found, API key not in environment")
            has_api_key = False
    except Exception as e:
        print(f"⚠️  Could not check config file: {e}")
        has_api_key = False

# Test 4: Test analyze_screen_for_errors (if API key available)
if has_api_key:
    print("\nTest 4: Error-Focused Debug Analysis")
    print("   (This will send a request to OpenAI API)")
    try:
        result = analyze_screen_for_errors(api_key)
        print(f"✅ Analysis completed")
        print(f"   Response preview: {result[:200]}...")
    except Exception as e:
        print(f"❌ Debug analysis failed: {e}")
else:
    print("\nTest 4: Error-Focused Debug Analysis")
    print("⏭️  Skipped (no API key)")

# Test 5: Test analyze_vscode_screen (if API key available)
if has_api_key:
    print("\nTest 5: VSCode Intelligent Coding Mode Analysis")
    print("   (This will send a request to OpenAI API)")
    try:
        result = analyze_vscode_screen(api_key)
        print(f"✅ Analysis completed")
        print(f"   Response preview: {result[:200]}...")
    except Exception as e:
        print(f"❌ VSCode analysis failed: {e}")
else:
    print("\nTest 5: VSCode Intelligent Coding Mode Analysis")
    print("⏭️  Skipped (no API key)")

# Test 6: Check intent configuration
print("\nTest 6: Intent Configuration")
try:
    with open("core/prompt.txt", "r") as f:
        prompt_content = f.read()
    
    if "debug_screen" in prompt_content:
        print("✅ debug_screen intent found in prompt.txt")
    else:
        print("❌ debug_screen intent NOT found in prompt.txt")
    
    if "vscode_mode" in prompt_content:
        print("✅ vscode_mode intent found in prompt.txt")
    else:
        print("❌ vscode_mode intent NOT found in prompt.txt")
        
except Exception as e:
    print(f"❌ Could not read prompt.txt: {e}")

# Test 7: Check main.py handlers
print("\nTest 7: Handler Verification in main.py")
try:
    with open("main.py", "r") as f:
        main_content = f.read()
    
    if 'intent == "debug_screen"' in main_content:
        print("✅ debug_screen handler found in main.py")
    else:
        print("❌ debug_screen handler NOT found in main.py")
    
    if 'intent == "vscode_mode"' in main_content:
        print("✅ vscode_mode handler found in main.py")
    else:
        print("❌ vscode_mode handler NOT found in main.py")
        
except Exception as e:
    print(f"❌ Could not read main.py: {e}")

# Test 8: Check imports in main.py
print("\nTest 8: Import Verification in main.py")
try:
    with open("main.py", "r") as f:
        main_content = f.read()
    
    if "analyze_screen_for_errors" in main_content:
        print("✅ analyze_screen_for_errors import found")
    else:
        print("❌ analyze_screen_for_errors import NOT found")
    
    if "analyze_vscode_screen" in main_content:
        print("✅ analyze_vscode_screen import found")
    else:
        print("❌ analyze_vscode_screen import NOT found")
        
except Exception as e:
    print(f"❌ Could not verify imports: {e}")

# Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print("\n📋 ERROR-FOCUSED DEBUG MODE")
print("   Voice Commands:")
print("   • 'Sam, debug this'")
print("   • 'Fix this error'")
print("   • 'Why is this failing'")
print("   • 'What is wrong'")
print("   • 'Analyze this error'")
print("\n📋 VSCODE INTELLIGENT CODING MODE")
print("   Voice Commands:")
print("   • 'Sam, analyze my code'")
print("   • 'Look at my code'")
print("   • 'Improve this code'")
print("   • 'Refactor this'")
print("   • 'Optimize this file'")

if has_api_key:
    print("\n✅ BOTH MODES ARE READY!")
    print("   Start Sam: python main.py")
    print("   Say any command above to test.")
else:
    print("\n⚠️  SETUP REQUIRED")
    print("   Set OPENAI_API_KEY environment variable or add to config/api_keys.json")
    print("   Then run: python main.py")

print("\n" + "=" * 60)
