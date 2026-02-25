"""
Direct manual test: Open Sugar and send message with longer wait and more detailed logging
"""

import sys
import os
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from automation.chrome_debug import evaluate_js, get_all_chat_names, find_best_chat_match, open_chat_by_name

print("\n" + "="*70)
print("MANUAL MESSAGE SEND TEST")
print("="*70)

# Step 1: Open Sugar
print("\n[1/4] Opening Sugar chat...")
all_chats = get_all_chat_names()
best_match, _ = find_best_chat_match("Sugar", all_chats)
print(f"Best match: {best_match}")

open_result = open_chat_by_name(best_match)
print(f"Chat opened: {open_result}")

# Step 2: Wait longer
print("\n[2/4] Waiting 5 seconds for chat to fully load...")
time.sleep(5)

# Step 3: Check what elements exist
print("\n[3/4] Checking DOM structure...")
check_js = """
(() => {
    const main = document.querySelector('#main');
    if (!main) return { error: 'no_main' };
    
    const footer = main.querySelector('footer');
    const header = main.querySelector('header');
    
    const result = {
        main: !!main,
        header: !!header,
        footer: !!footer
    };
    
    if (footer) {
        const allDivs = footer.querySelectorAll('div');
        result.footer_div_count = allDivs.length;
        
        const contentEditable = footer.querySelector('[contenteditable="true"]');
        result.footer_has_contenteditable = !!contentEditable;
        
        // Try alternative selector (maybe it's a paragraph or span)
        const allContentEditable = document.querySelectorAll('[contenteditable="true"]');
        result.all_contenteditable_count = allContentEditable.length;
        
        // Check for input wrapper divs
        const inputWrapper = footer.querySelector('[data-tab="10"]');
        result.has_input_wrapper_tab10 = !!inputWrapper;
    }
    
    return result;
})()
"""

dom_check = evaluate_js(check_js)
import json
print(json.dumps(dom_check, indent=2))

# Step 4: Try to send with alternative method
print("\n[4/4] Attempting to send message...")
send_js = """
(() => {
    // Try to find input in any way possible
    const inputs = document.querySelectorAll('[contenteditable="true"]');
    console.log('Found contenteditable elements:', inputs.length);
    
    if (inputs.length === 0) {
        return { error: 'no_input_found', tried: 'all_contenteditable' };
    }
    
    // Use the last one (usually the message input)
    const input = inputs[inputs.length - 1];
    input.focus();
    input.innerText = 'hello sugar, how are you. are you awake';
   
    // Dispatch events
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    
    // Find send button
    const sendButtons = document.querySelectorAll('[data-testid="send"]');
    console.log('Found send buttons:', sendButtons.length);
    
    if (sendButtons.length > 0) {
        sendButtons[0].click();
        return { success: true };
    }
    
    return { error: 'no_send_button' };
})()
"""

send_result = evaluate_js(send_js)
print("Send result:", json.dumps(send_result, indent=2))

print("\n" + "="*70 + "\n")
