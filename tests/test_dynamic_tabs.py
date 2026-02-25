import sys
sys.path.insert(0, '.')
from automation.chrome_debug import get_active_tab, switch_to_unread_tab, get_unread_messages
import json

print("\n=== Dynamic Tab Detection Test ===\n")

# Test 1: Detect all tabs and current active one
print("1. Detecting available tabs:")
tabs = get_active_tab()
if tabs:
    for tab in tabs:
        status = "✓ ACTIVE" if tab['isSelected'] else ""
        badge = f" (has badge: {tab['hasNumberBadge']})" if tab['hasNumberBadge'] else ""
        print(f"   - {tab['text']:<30} {status}{badge}")
else:
    print("   No tabs detected")

print("\n2. Switching to unread tab (dynamic detection):")
switch_result = switch_to_unread_tab()
print(f"   {json.dumps(switch_result, indent=2)}")

print("\n3. Getting unread messages:")
unreads = get_unread_messages()
if unreads:
    print(f"   Found {len(unreads)} unread chats:")
    for i, chat in enumerate(unreads[:10], 1):
        print(f"   {i}. {chat['name']}")
    if len(unreads) > 10:
        print(f"   ... and {len(unreads) - 10} more")
else:
    print("   No unread messages")

print("\n✅ Dynamic tab detection complete!")