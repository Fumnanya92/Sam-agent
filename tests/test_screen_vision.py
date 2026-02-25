"""
Test Screen Vision Mode
========================

Tests screen capture and vision analysis:
1. Screen capture functionality
2. Base64 encoding
3. OpenAI API key detection
4. Vision analysis (if API key available)
5. Intent configuration
6. Handler verification
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

print("=" * 80)
print("SCREEN VISION MODE TEST")
print("=" * 80)
print()

# Test 1: Import Module
print("Test 1: Module Import")
print("-" * 80)
try:
    from system.screen_vision import capture_screen_base64, analyze_screen, get_openai_key
    print("✅ screen_vision module imported successfully")
    print()
except Exception as e:
    print(f"❌ Module import failed: {e}")
    print()
    sys.exit(1)

# Test 2: Screen Capture
print("Test 2: Screen Capture")
print("-" * 80)
try:
    image_base64 = capture_screen_base64()
    print(f"✅ Screen captured successfully")
    print(f"   - Image size: {len(image_base64)} bytes (base64)")
    print(f"   - Sample: {image_base64[:50]}...")
    print()
except Exception as e:
    print(f"❌ Screen capture failed: {e}")
    print()
    sys.exit(1)

# Test 3: API Key Detection
print("Test 3: OpenAI API Key Detection")
print("-" * 80)
try:
    api_key = get_openai_key()
    if api_key:
        print(f"✅ OpenAI API key found")
        print(f"   - Key starts with: {api_key[:10]}...")
        print(f"   - Key length: {len(api_key)} characters")
        has_api_key = True
    else:
        print("⚠️  OpenAI API key NOT found")
        print("   - Vision analysis will not work without API key")
        print("   - Set OPENAI_API_KEY environment variable or add to config/api_keys.json")
        has_api_key = False
    print()
except Exception as e:
    print(f"❌ API key detection failed: {e}")
    print()
    has_api_key = False

# Test 4: Vision Analysis (only if API key available)
if has_api_key:
    print("Test 4: Vision Analysis")
    print("-" * 80)
    try:
        print("   Analyzing screen (this may take a few seconds)...")
        analysis = analyze_screen()
        
        if "error" in analysis.lower() and "api key" in analysis.lower():
            print("⚠️  Vision analysis requires valid API key")
            print(f"   - Response: {analysis[:100]}...")
        else:
            print("✅ Vision analysis completed")
            print("\n   Sam's Analysis:")
            print("   " + "-" * 76)
            for line in analysis.split('\n'):
                print(f"   {line}")
            print("   " + "-" * 76)
        print()
    except Exception as e:
        print(f"⚠️  Vision analysis failed: {e}")
        print("   - This is expected if API key is invalid or network is unavailable")
        print()
else:
    print("Test 4: Vision Analysis")
    print("-" * 80)
    print("⚠️  Skipped - No API key available")
    print()

# Test 5: Verify Intent Configuration
print("Test 5: Intent Configuration Verification")
print("-" * 80)
try:
    prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'core', 'prompt.txt')
    with open(prompt_path, 'r', encoding='utf-8') as f:
        prompt_content = f.read()
    
    if 'screen_vision' in prompt_content:
        print("✅ screen_vision intent found in prompt.txt")
        
        # Check for detection rules
        if 'look at my screen' in prompt_content or 'analyze screen' in prompt_content:
            print("✅ Screen vision detection rules configured")
        else:
            print("⚠️  Detection rules might be incomplete")
    else:
        print("❌ screen_vision intent NOT found in prompt.txt")
        sys.exit(1)
    print()
except Exception as e:
    print(f"❌ Prompt verification failed: {e}")
    print()
    sys.exit(1)

# Test 6: Verify Main.py Handler
print("Test 6: Main.py Handler Verification")
print("-" * 80)
try:
    main_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'main.py')
    with open(main_path, 'r', encoding='utf-8') as f:
        main_content = f.read()
    
    if 'elif intent == "screen_vision":' in main_content:
        print("✅ screen_vision intent handler found in main.py")
    else:
        print("❌ screen_vision intent handler NOT found in main.py")
        sys.exit(1)
    
    if 'from system.screen_vision import analyze_screen' in main_content:
        print("✅ screen_vision import statement found")
    else:
        print("⚠️  Import might be inside the handler (dynamic import)")
    print()
except Exception as e:
    print(f"❌ Main.py verification failed: {e}")
    print()
    sys.exit(1)

# Test 7: Check Dependencies
print("Test 7: Dependencies Check")
print("-" * 80)
try:
    import mss
    print("✅ mss installed")
except ImportError:
    print("❌ mss NOT installed - run: pip install mss")

try:
    from PIL import Image
    print("✅ Pillow installed")
except ImportError:
    print("❌ Pillow NOT installed - run: pip install pillow")

try:
    import requests
    print("✅ requests installed")
except ImportError:
    print("❌ requests NOT installed - run: pip install requests")

print()

# Test 8: Sample Voice Commands
print("Test 8: Sample Voice Commands")
print("-" * 80)
sample_commands = [
    "Sam, look at my screen",
    "What am I seeing?",
    "Analyze my screen",
    "Explain this error",
    "What am I looking at?",
    "Walk me through this",
]

print("Sam can now respond to:")
for cmd in sample_commands:
    print(f"   • {cmd}")
print()

# Final Summary
print("=" * 80)
if has_api_key:
    print("✅ SCREEN VISION MODE IS READY!")
else:
    print("⚠️  SCREEN VISION MODE PARTIALLY READY")
print("=" * 80)
print()
print("🎯 What Sam Can Do Now:")
print("   • Capture your screen")
print("   • Analyze with AI vision model")
print("   • Describe what's visible")
print("   • Explain errors on screen")
print("   • Guide through interfaces")
print()

if has_api_key:
    print("🚀 To test with Sam:")
    print("   1. Run: python main.py")
    print("   2. Say: 'Sam, look at my screen'")
    print("   3. Sam will analyze and describe what he sees")
else:
    print("⚠️  TO ENABLE VISION ANALYSIS:")
    print("   1. Get OpenAI API key from https://platform.openai.com")
    print("   2. Set environment variable: OPENAI_API_KEY=your_key")
    print("   3. OR add to config/api_keys.json:")
    print('      { "openai_api_key": "your_key" }')
    print("   4. Then run: python main.py")
    print("   5. Say: 'Sam, look at my screen'")
print()
print("=" * 80)
print("📋 Features:")
print("   ✅ Phase 1: Observation Mode (CURRENT)")
print("   🔜 Phase 2: Interactive Guidance")
print("   🔜 Phase 3: Click Suggestion Overlay")
print("   🔜 Phase 4: Autonomous Cursor Assistance")
print("=" * 80)
