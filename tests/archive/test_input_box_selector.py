"""
Test to find the correct input box selector in WhatsApp Web
"""

import sys
import os
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from automation.chrome_debug import evaluate_js, get_all_chat_names, find_best_chat_match, open_chat_by_name

def test_input_selectors():
    print("\n" + "="*70)
    print("Testing WhatsApp Input Box Selectors")
    print("="*70)
    
    # First, open a chat
    print("\n[1/2] Opening Sugar chat...")
    all_chats = get_all_chat_names()
    if not all_chats:
        print("ERROR: No chats found")
        return None
    
    best_match, _ = find_best_chat_match("Sugar", all_chats)
    if not best_match:
        print("ERROR: Could not find Sugar")
        return None
    
    open_result = open_chat_by_name(best_match)
    print(f"Chat opened: {open_result}")
    
    print("Waiting for chat to load...")
    time.sleep(3)
    
    print("\n[2/2] Testing selectors...")
    
    test_js = """
    (() => {
        const main = document.querySelector('#main');
        if (!main) return { error: 'main_not_found' };
        
        // Test various selectors
        const results = {};
        
        results.contenteditable_textbox = !!main.querySelector('[contenteditable="true"][role="textbox"]');
        results.contenteditable_only = !!main.querySelector('[contenteditable="true"]');
        results.role_textbox_only = !!main.querySelector('[role="textbox"]');
        results.data_tab = !!main.querySelector('[data-tab]');
        
        // Get all contenteditable elements
        const allContentEditable = main.querySelectorAll('[contenteditable="true"]');
        results.contenteditable_count = allContentEditable.length;
        
        // Get the footer (where input usually is)
        const footer = main.querySelector('footer');
        results.footer_exists = !!footer;
        
        if (footer) {
            results.footer_contenteditable = !!footer.querySelector('[contenteditable="true"]');
            results.footer_textbox = !!footer.querySelector('[role="textbox"]');
            
            // Try to get the actual input
            const input = footer.querySelector('[contenteditable="true"]');
            if (input) {
                results.input_classes = input.className;
                results.input_data_tab = input.getAttribute('data-tab');
                results.input_role = input.getAttribute('role');
            }
        }
        
        // Check if chat is actually open
        const header = main.querySelector('header');
        results.header_exists = !!header;
        
        return results;
    })()
    """
    
    result = evaluate_js(test_js)
    
    print("\n[RESULTS]")
    import json
    print(json.dumps(result, indent=2))
    print("\n" + "="*70 + "\n")
    
    return result


if __name__ == "__main__":
    test_input_selectors()
