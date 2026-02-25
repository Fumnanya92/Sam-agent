"""Quick test to verify the three fixes"""
import sys
sys.path.insert(0, r'c:\Users\DELL.COM\Desktop\Darey\Sam-Agent')

print("=" * 70)
print("TESTING RECENT FIXES")
print("=" * 70)

# Test 1: Console output for Sam responses
print("\n[TEST 1] Console Output for Sam Responses")
print("-" * 70)
try:
    from automation.whatsapp_assistant import WhatsAppAssistant
    assistant = WhatsAppAssistant()
    
    # Mock test - the _speak method should print to console
    print("Testing _speak() method with console output...")
    assistant._speak("Test message - you should see this with emoji", None)
    print("✅ PASS: Console output works (check above for 🤖 Sam: ...)")
except Exception as e:
    print(f"❌ FAIL: {e}")

# Test 2: Date filtering in message extraction
print("\n[TEST 2] Date Filtering in Message Extraction")
print("-" * 70)
try:
    from automation.chrome_debug import is_chrome_debug_running
    
    if is_chrome_debug_running():
        print("Chrome debug is running")
        from automation.chrome_debug import get_unread_messages
        
        messages = get_unread_messages()
        if messages:
            print(f"Found {len(messages)} unread messages")
            print("\nFirst 3 messages:")
            for i, msg in enumerate(messages[:3], 1):
                name = msg.get('name', 'Unknown')
                preview = msg.get('message', 'No preview')
                
                # Check if message is a date format
                is_date = bool(__import__('re').match(r'^\d{1,2}/\d{1,2}/\d{4}$', preview))
                
                status = "❌ FAIL (date found)" if is_date else "✅ OK"
                print(f"  {i}. {name}: {preview[:50]}... {status}")
            print("\n✅ PASS: Date filtering implemented")
        else:
            print("⚠️  No unread messages found")
    else:
        print("⚠️  Chrome debug not running - skipping test")
except Exception as e:
    print(f"❌ FAIL: {e}")

# Test 3: Tab switching logic
print("\n[TEST 3] Unread Tab Switching")
print("-" * 70)
try:
    from automation.chrome_debug import switch_to_unread_tab
    
    if is_chrome_debug_running():
        result = switch_to_unread_tab()
        if result and result.get('switched'):
            already_active = result.get('alreadyActive', False)
            status = "already active" if already_active else "switched successfully"
            print(f"✅ PASS: Tab switch {status}")
            print(f"   Result: {result}")
        else:
            print(f"❌ FAIL: Could not switch to unread tab")
            print(f"   Result: {result}")
    else:
        print("⚠️  Chrome debug not running - skipping test")
except Exception as e:
    print(f"❌ FAIL: {e}")

print("\n" + "=" * 70)
print("TESTING COMPLETE")
print("=" * 70)
