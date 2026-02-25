"""
Check what buttons exist after opening chat and entering text
"""

import sys
import os
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from automation.chrome_debug import evaluate_js, get_all_chat_names, find_best_chat_match, open_chat_by_name

print("Opening Sugar...")
all_chats = get_all_chat_names()
best_match, _ = find_best_chat_match("Sugar", all_chats)
open_chat_by_name(best_match)

print("Waiting 3 seconds...")
time.sleep(3)

print("\nChecking for buttons BEFORE entering text...")
check_before_js = """
(() => {
    const result = {};
    
    // Check for send button
    result.send_testid = !!document.querySelector('[data-testid="send"]');
    result.send_aria = !!document.querySelector('[aria-label="Send"]');
    
    // Count all buttons
    const allButtons = document.querySelectorAll('button');
    result.total_buttons = allButtons.length;
    
    // Get footer buttons
    const footer = document.querySelector('footer');
    result.footer_exists = !!footer;
    if (footer) {
        const footerButtons = footer.querySelectorAll('button');
        result.footer_buttons = footerButtons.length;
    }
    
    return result;
})()
"""

before_result = evaluate_js(check_before_js)
print(before_result)

print("\nNow entering text...")
enter_text_js = """
(() => {
    const allContentEditable = document.querySelectorAll('[contenteditable="true"]');
    if (allContentEditable.length === 0) return { error: 'no_input' };
    
    const input = allContentEditable[allContentEditable.length - 1];
    input.focus();
    input.innerText = 'Test message';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    
    return { text_entered: true };
})()
"""

text_result = evaluate_js(enter_text_js)
print(text_result)

print("\nWaiting 1 second for button to appear...")
time.sleep(1)

print("\nChecking for buttons AFTER entering text...")
check_after_js = """
(() => {
    const result = {};
    
    // Check for send button
    result.send_testid = !!document.querySelector('[data-testid="send"]');
    result.send_aria = !!document.querySelector('[aria-label="Send"]');
    
    // Count all buttons
    const allButtons = document.querySelectorAll('button');
    result.total_buttons = allButtons.length;
    
    // Get footer buttons
    const footer = document.querySelector('footer');
    if (footer) {
        const footerButtons = footer.querySelectorAll('button');
        result.footer_buttons = footerButtons.length;
        
        // Get details about footer buttons
        const buttonInfo = [];
        for (let i = 0; i < Math.min(footerButtons.length, 5); i++) {
            const btn = footerButtons[i];
            buttonInfo.push({
                aria_label: btn.getAttribute('aria-label'),
                title: btn.getAttribute('title'),
                data_testid: btn.getAttribute('data-testid'),
                has_svg: !!btn.querySelector('svg')
            });
        }
        result.button_details = buttonInfo;
    }
    
    return result;
})()
"""

after_result = evaluate_js(check_after_js)
import json
print(json.dumps(after_result, indent=2))

print("\n✓ Check complete")
