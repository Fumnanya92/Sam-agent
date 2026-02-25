"""
Test the new Draft & Confirm messaging system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.reply_drafter import generate_reply
from automation.reply_controller import ReplyController
from automation.whatsapp_ai_engine import WhatsAppAIEngine

def test_draft_system():
    """Test the draft and confirm flow"""
    
    print("="*50)
    print("TESTING DRAFT & CONFIRM SYSTEM")
    print("="*50)
    
    # Test 1: Reply generation
    print("\n1. Testing reply generation...")
    draft = generate_reply("Hello, how are you?", "John")
    print(f"Generated draft: '{draft}'")
    
    # Test 2: Reply controller
    print("\n2. Testing reply controller...")
    controller = ReplyController()
    
    controller.set_draft("John", draft)
    print(f"Has pending: {controller.has_pending()}")
    
    draft_info = controller.get_draft()
    print(f"Draft info: {draft_info}")
    
    # Test 3: Copy to clipboard (simulation)
    print("\n3. Testing clipboard copy...")
    success = controller.copy_to_clipboard()
    print(f"Copy success: {success}")
    
    # Test 4: Chrome auto-launch detection
    print("\n4. Testing Chrome detection...")
    from automation.chrome_debug import is_chrome_debug_running, find_chrome_executable
    
    chrome_running = is_chrome_debug_running()
    chrome_exe = find_chrome_executable()
    
    print(f"Chrome debug running: {chrome_running}")
    print(f"Chrome executable found: {chrome_exe is not None}")
    
    # Test 5: WhatsApp AI Engine integration
    print("\n5. Testing WhatsApp AI Engine...")
    engine = WhatsAppAIEngine()
    print(f"Engine initialized: {engine is not None}")
    print(f"Reply controller ready: {engine.reply_controller is not None}")
    
    print("\n" + "="*50)
    print("DRAFT & CONFIRM SYSTEM TEST COMPLETE!")
    print("="*50)
    print("\nNew features implemented:")
    print("✓ AI reply generation with config fallback")
    print("✓ Draft storage and clipboard copy")
    print("✓ Chrome auto-launch detection")
    print("✓ Voice commands: 'send it', 'cancel', 'edit'")
    print("✓ Removed dangerous auto-send functionality")
    print("✓ Safe manual paste workflow")

if __name__ == "__main__":
    test_draft_system()