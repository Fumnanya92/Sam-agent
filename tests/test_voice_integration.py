"""
Quick test to verify WhatsApp AI integration in main.py
Tests intent recognition and module imports
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_imports():
    """Test that all WhatsApp modules can be imported"""
    print("\n" + "="*70)
    print("WHATSAPP AI INTEGRATION TEST")
    print("="*70)
    
    print("\n[PHASE 1] Testing Module Imports")
    print("-" * 70)
    
    try:
        from automation.whatsapp_ai_engine import WhatsAppAIEngine
        print("[OK] WhatsAppAIEngine imported")
    except Exception as e:
        print(f"[FAIL] WhatsAppAIEngine import failed: {e}")
        return False
    
    try:
        from automation.whatsapp_assistant import WhatsAppAssistant
        print("[OK] WhatsAppAssistant imported")
    except Exception as e:
        print(f"[FAIL] WhatsAppAssistant import failed: {e}")
        return False
    
    try:
        from automation.chrome_debug import get_all_chat_names, find_best_chat_match, open_chat_by_name
        print("[OK] Chrome debug functions imported")
    except Exception as e:
        print(f"[FAIL] Chrome debug import failed: {e}")
        return False
    
    print("\n[PHASE 2] Testing Initialization")
    print("-" * 70)
    
    try:
        engine = WhatsAppAIEngine()
        print(f"[OK] Engine initialized with mode: {engine.reply_mode}")
    except Exception as e:
        print(f"[FAIL] Engine initialization failed: {e}")
        return False
    
    try:
        assistant = WhatsAppAssistant()
        print(f"[OK] Assistant initialized")
    except Exception as e:
        print(f"[FAIL] Assistant initialization failed: {e}")
        return False
    
    print("\n[PHASE 3] Testing LLM Prompt Update")
    print("-" * 70)
    
    try:
        with open("core/prompt.txt", "r") as f:
            prompt = f.read()
        
        required_intents = [
            "whatsapp_summary",
            "open_whatsapp_chat", 
            "read_whatsapp",
            "reply_whatsapp",
            "confirm_send"
        ]
        
        for intent in required_intents:
            if intent in prompt:
                print(f"[OK] Intent '{intent}' found in prompt")
            else:
                print(f"[FAIL] Intent '{intent}' missing from prompt")
                return False
    except Exception as e:
        print(f"[FAIL] Prompt check failed: {e}")
        return False
    
    print("\n[PHASE 4] Testing Main.py Integration")
    print("-" * 70)
    
    try:
        with open("main.py", "r") as f:
            main_code = f.read()
        
        required_imports = [
            "from automation.whatsapp_ai_engine import WhatsAppAIEngine",
            "from automation.whatsapp_assistant import WhatsAppAssistant",
            "whatsapp_engine = WhatsAppAIEngine()",
            "whatsapp_assistant = WhatsAppAssistant()"
        ]
        
        for import_line in required_imports:
            if import_line in main_code:
                print(f"[OK] Found: {import_line[:50]}...")
            else:
                print(f"[FAIL] Missing: {import_line}")
                return False
        
        # Check intent handlers
        intent_handlers = [
            'elif intent == "whatsapp_summary"',
            'elif intent == "open_whatsapp_chat"',
            'elif intent == "read_whatsapp"',
            'elif intent == "reply_whatsapp"',
            'elif intent == "confirm_send"'
        ]
        
        for handler in intent_handlers:
            if handler in main_code:
                print(f"[OK] Handler found: {handler}")
            else:
                print(f"[FAIL] Handler missing: {handler}")
                return False
                
    except Exception as e:
        print(f"[FAIL] Main.py check failed: {e}")
        return False
    
    print("\n" + "="*70)
    print("[SUCCESS] WhatsApp AI is fully wired to Sam!")
    print("="*70)
    print("\nVoice commands now supported:")
    print("  - 'Sam, check WhatsApp' -> Lists unread messages")
    print("  - 'Sam, open Ella' -> Opens chat with Ella")
    print("  - 'Sam, read WhatsApp' -> Reads latest message")
    print("  - 'Sam, reply to this' -> AI generates and sends reply")
    print("  - 'Yes, send it' -> Confirms sensitive message")
    print("="*70 + "\n")
    
    return True


if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
