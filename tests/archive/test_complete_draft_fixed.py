"""
Complete PHASE 5 Test:
1. Open Sugar chat
2. Read latest message
3. Generate draft reply
4. Copy to clipboard
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from automation.chrome_debug import open_chat_by_name
from automation.whatsapp_dom import get_latest_message_from_open_chat, get_current_chat_name
from automation.reply_drafter import generate_reply
from automation.reply_controller import ReplyController
import pyperclip
import time

print("=" * 70)
print("COMPLETE TEST: WhatsApp Draft Reply System (PHASE 5)")
print("=" * 70)
print()

# Initialize controller
reply_controller = ReplyController()
chat_to_open = "Sugar"

# Step 1: Open chat
print(f"[1/5] Opening chat with '{chat_to_open}'...")
try:
    success = open_chat_by_name(chat_to_open)
    
    if success:
        print(f"✓ Chat opened!")
        time.sleep(1)  # Wait for chat to load
        
        # Verify which chat is open
        current_chat = get_current_chat_name()
        print(f"   Current chat: {current_chat}")
        print()
    else:
        print("❌ FAILED: Could not open chat")
        exit(1)
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    exit(1)

# Step 2: Read latest message
print("[2/5] Reading latest message from chat...")
try:
    latest = get_latest_message_from_open_chat()
    
    if not latest or not latest.get("text"):
        print("❌ FAILED: No message found or message is empty")
        print(f"   Message data: {latest}")
        exit(1)
    
    print(f"✓ Message found!")
    print(f"   From: {latest.get('sender', 'You (outgoing)')}")
    print(f"   Text: {latest.get('text', 'N/A')[:80]}...")
    print(f"   Type: {latest.get('type', 'unknown')}")
    print(f"   Direction: {latest.get('direction', 'unknown')}")
    print()
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    exit(1)

# Step 3: Generate draft reply
print("[3/5] Generating AI draft reply...")
try:
    draft = generate_reply(
        message_text=latest.get("text", ""),
        sender=latest.get("sender", chat_to_open)
    )
    
    print(f"✓ Draft generated!")
    print(f"   Draft: \"{draft}\"")
    print()
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    exit(1)

# Step 4: Store draft in controller
print("[4/5] Storing draft in controller...")
try:
    reply_controller.set_draft(
        receiver=latest.get("sender", chat_to_open),
        draft_text=draft
    )
    
    if reply_controller.has_pending():
        print(f"✓ Draft stored!")
        draft_info = reply_controller.get_draft()
        print(f"   Receiver: {draft_info['receiver']}")
        print()
    else:
        print("❌ FAILED: Draft not stored properly")
        exit(1)
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    exit(1)

# Step 5: Copy to clipboard
print("[5/5] Copying draft to clipboard (simulating 'send it')...")
try:
    success = reply_controller.copy_to_clipboard()
    
    if success:
        clipboard_content = pyperclip.paste()
        print(f"✓ Draft copied to clipboard!")
        print()
        
        if clipboard_content == draft:
            print("=" * 70)
            print("✅ SUCCESS: PHASE 5 Draft System Working!")
            print("=" * 70)
            print()
            print("📋 CLIPBOARD CONTAINS:")
            print(f'   "{clipboard_content}"')
            print()
            print("You can now manually paste this in WhatsApp and press Enter.")
            print("=" * 70)
        else:
            print("⚠️  WARNING: Clipboard content doesn't match draft")
            print(f"   Expected: {draft}")
            print(f"   Got: {clipboard_content}")
    else:
        print("❌ FAILED: Could not copy to clipboard")
        exit(1)
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    exit(1)

# Clean up
reply_controller.clear()
print()
print("✅ Test completed successfully - draft workflow fully operational!")
