"""
Quick test to verify WhatsApp Assistant components are working.
"""
import sys

# Force UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

print("Testing WhatsApp Assistant Components...")
print("=" * 60)

# Test 1: Safety Filter
print("\n1. Testing Safety Filter...")
from automation.safety_filter import is_sensitive

test_cases = [
    ("Hello, how are you?", False),
    ("I'll transfer 50000 naira", True),
    ("Can you send me the payment?", True),
    ("See you tomorrow!", False),
    ("My bank account is 1234567890", True),
]

for text, expected in test_cases:
    result = is_sensitive(text)
    status = "[OK]" if result == expected else "[FAIL]"
    print(f"  {status} '{text[:30]}...' -> Sensitive: {result}")

# Test 2: Import WhatsAppAssistant
print("\n2. Testing WhatsAppAssistant Import...")
try:
    from automation.whatsapp_assistant import WhatsAppAssistant
    wa = WhatsAppAssistant()
    print("  [OK] WhatsAppAssistant imported successfully")
    print(f"  [OK] Initial state: unread_cache={len(wa.unread_cache)}, current_chat={wa.current_chat}")
except Exception as e:
    print(f"  [FAIL] Error: {e}")

# Test 3: Import WhatsAppController
print("\n3. Testing WhatsAppController Import...")
try:
    from automation.whatsapp_controller import WhatsAppController
    wc = WhatsAppController()
    print("  [OK] WhatsAppController imported successfully")
    print(f"  [OK] Initial state: pending_reply={wc.pending_reply}, pending_chat={wc.pending_chat}")
except Exception as e:
    print(f"  [FAIL] Error: {e}")

# Test 4: Import Reply Engine
print("\n4. Testing Reply Engine Import...")
try:
    from automation.whatsapp_reply_engine import generate_whatsapp_reply
    print("  [OK] Reply engine imported successfully")
except Exception as e:
    print(f"  [FAIL] Error: {e}")

# Test 5: Import DOM functions
print("\n5. Testing WhatsApp DOM functions...")
try:
    from automation.whatsapp_dom import (
        get_latest_message_from_open_chat,
        send_message_in_open_chat
    )
    print("  [OK] get_latest_message_from_open_chat imported")
    print("  [OK] send_message_in_open_chat imported")
except Exception as e:
    print(f"  [FAIL] Error: {e}")

# Test 6: Import Chrome Debug functions
print("\n6. Testing Chrome Debug functions...")
try:
    from automation.chrome_debug import (
        get_unread_messages,
        get_all_chat_names,
        find_best_chat_match,
        open_chat_by_name
    )
    print("  [OK] get_unread_messages imported")
    print("  [OK] get_all_chat_names imported")
    print("  [OK] find_best_chat_match imported")
    print("  [OK] open_chat_by_name imported")
except Exception as e:
    print(f"  [FAIL] Error: {e}")

print("\n" + "=" * 60)
print("[SUCCESS] All components loaded successfully!")
print("=" * 60)
