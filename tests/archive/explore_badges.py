import sys
sys.path.insert(0, '.')
from automation.chrome_debug import evaluate_js
import json

print("\n=== EXPLORING UNREAD BADGE STRUCTURE ===\n")

# Get detailed info about first 10 chats
explore_js = """
(() => {
    const paneContainer = document.querySelector('#pane-side');
    if (!paneContainer) return {error: 'No pane-side found'};
    
    const chatRows = paneContainer.querySelectorAll('[role="row"]');
    let results = [];

    for (let i = 0; i < Math.min(10, chatRows.length); i++) {
        const row = chatRows[i];
        const nameEl = row.querySelector('span[dir="auto"]');
        const name = nameEl ? nameEl.innerText : 'Unknown';
        
        // Get all spans in this row
        const allSpans = row.querySelectorAll('span');
        let spanTexts = [];
        allSpans.forEach(span => {
            const text = span.innerText.trim();
            if (text && text.length < 50) {  // Only short texts
                spanTexts.push(text);
            }
        });
        
        // Get aria-labels
        const ariaLabels = [];
        const ariaElements = row.querySelectorAll('[aria-label]');
        ariaElements.forEach(el => {
            ariaLabels.push(el.getAttribute('aria-label'));
        });
        
        // Check for common badge classes
        const hasGreenDot = !!row.querySelector('[data-icon="unread"]');
        const hasNotifBadge = !!row.querySelector('[data-icon="badge-unread"]');
        
        results.push({
            index: i,
            name: name,
            hasGreenUnreadIcon: hasGreenDot,
            hasUnreadBadge: hasNotifBadge,
            spanTexts: spanTexts.slice(0, 10),
            ariaLabels: ariaLabels.slice(0, 5),
            outerHTMLSnippet: row.outerHTML.slice(0, 500)
        });
    }

    return results;
})()
"""

result = evaluate_js(explore_js)

if result:
    for chat in result:
        print(f"Chat #{chat['index']}: {chat['name']}")
        print(f"  Green dot: {chat['hasGreenUnreadIcon']}, Badge: {chat['hasUnreadBadge']}")
        print(f"  Span texts: {chat['spanTexts'][:5]}")
        print(f"  Aria labels: {chat['ariaLabels'][:3]}")
        print("---\n")
else:
    print("Failed to explore chat structure")