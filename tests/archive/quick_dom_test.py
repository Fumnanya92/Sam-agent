import sys
sys.path.insert(0, '.')
from automation.chrome_debug import evaluate_js
import json

print("\n=== WHATSAPP UNREAD MESSAGES TEST ===\n")

# Count rows
row_count = evaluate_js('document.querySelectorAll("#pane-side [role=row]").length')
print(f"Total chat rows found: {row_count}\n")

if row_count and int(row_count) > 0:
    # Get unread messages
    result = evaluate_js("""
(() => {
    const paneContainer = document.querySelector('#pane-side');
    if (!paneContainer) return [];
    
    const chatRows = paneContainer.querySelectorAll('[role="row"]');
    let results = [];

    chatRows.forEach(row => {
        const nameEl = row.querySelector('span[dir="auto"]');
        const name = nameEl ? nameEl.innerText : null;
        
        let unreadCount = null;
        
        // Method 1: aria-label
        const ariaElements = row.querySelectorAll('[aria-label]');
        for (let el of ariaElements) {
            const label = el.getAttribute('aria-label');
            if (label && label.toLowerCase().includes('unread')) {
                const match = label.match(/(\\d+)/);
                if (match) {
                    unreadCount = match[1];
                    break;
                }
            }
        }
        
        // Method 2: badge spans
        if (!unreadCount) {
            const spans = row.querySelectorAll('span');
            for (let span of spans) {
                const text = span.innerText.trim();
                if (/^\\d+$/.test(text) && parseInt(text) > 0 && parseInt(text) < 1000) {
                    if (span.innerText.length < 5) {
                        unreadCount = text;
                        break;
                    }
                }
            }
        }
        
        if (name && unreadCount) {
            results.push({ name: name, unread: unreadCount });
        }
    });

    return results;
})()
""")
    
    if result:
        print(f"Unread messages detected: {len(result)}\n")
        print(json.dumps(result, indent=2))
    else:
        print("No unread messages found (or detection method needs adjustment)")
else:
    print("ERROR: No chat rows found - WhatsApp may not be loaded")