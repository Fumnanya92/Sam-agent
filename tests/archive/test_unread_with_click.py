import sys
sys.path.insert(0, '.')
from automation.chrome_debug import evaluate_js
import json
import time

print("\n=== Testing Unread Tab Click + Detection ===\n")

# Step 1: Click the Unread tab
click_unread_js = """
(() => {
    // Find the Unread tab button
    const buttons = document.querySelectorAll('button, [role="tab"]');
    let unreadButton = null;
    
    for (let btn of buttons) {
        const text = (btn.innerText || btn.textContent || '').trim();
        if (text.startsWith('Unread')) {
            unreadButton = btn;
            break;
        }
    }
    
    if (unreadButton) {
        unreadButton.click();
        return {success: true, text: unreadButton.innerText};
    }
    
    return {success: false, error: 'Unread tab not found'};
})()
"""

print("1. Clicking Unread tab...")
click_result = evaluate_js(click_unread_js)
print(f"   Result: {json.dumps(click_result, indent=2)}")

if click_result and click_result.get('success'):
    print("\n2. Waiting for tab to load...")
    time.sleep(1)  # Give WhatsApp time to filter
    
    print("\n3. Detecting unread messages...")
    
    # Step 2: Get unread messages
    detect_js = """
    (() => {
        const paneContainer = document.querySelector('#pane-side');
        if (!paneContainer) return [];
        
        const chatRows = paneContainer.querySelectorAll('[role="row"]');
        let results = [];

        chatRows.forEach(row => {
            const nameEl = row.querySelector('span[dir="auto"]');
            const name = nameEl ? nameEl.innerText : null;
            
            if (!name) return;
            
            // Find unread badge
            const spans = row.querySelectorAll('span');
            let unreadCount = null;
            
            for (let span of spans) {
                const style = window.getComputedStyle(span);
                const bgColor = style.backgroundColor;
                const text = span.innerText.trim();
                
                if (/^\\d+$/.test(text) && parseInt(text) > 0 && parseInt(text) < 1000) {
                    if (bgColor && bgColor !== 'rgba(0, 0, 0, 0)' && bgColor !== 'transparent') {
                        unreadCount = text;
                        break;
                    }
                }
            }
            
            if (unreadCount) {
                results.push({ name: name, unread: unreadCount });
            }
        });

        return results;
    })()
    """
    
    unread_messages = evaluate_js(detect_js)
    
    if unread_messages:
        print(f"   Found {len(unread_messages)} chats with unread messages:\n")
        print(json.dumps(unread_messages, indent=2))
    else:
        print("   No unread messages found")
else:
    print("\n   ERROR: Could not click Unread tab")