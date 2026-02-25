import sys
sys.path.insert(0, '.')
from automation.chrome_debug import evaluate_js
import json

print("\n=== FINDING UNREAD TAB AND INDICATORS ===\n")

# Check for Unread tab/button
unread_tab_js = """
(() => {
    // Look for the Unread tab/button
    const bodyText = document.body.innerText;
    const hasUnreadInBody = bodyText.includes('Unread');
    
    // Try to find the Unread filter button
    const buttons = document.querySelectorAll('button, [role="tab"], [role="button"]');
    let unreadButton = null;
    
    for (let btn of buttons) {
        const text = btn.innerText || btn.textContent || '';
        if (text.includes('Unread') || text.includes('unread')) {
            unreadButton = {
                text: text.trim().slice(0, 50),
                ariaLabel: btn.getAttribute('aria-label'),
                role: btn.getAttribute('role')
            };
            break;
        }
    }
    
    // Look for any elements with unread counts in visible chats
    const pane = document.querySelector('#pane-side');
    let chatsWithBadges = [];
    
    if (pane) {
        const rows = pane.querySelectorAll('[role="row"]');
        for (let i = 0; i < rows.length; i++) {
            const row = rows[i];
            
            // Look for badge indicators - green dots, numbers, or bold text
            const boldElements = row.querySelectorAll('[style*="font-weight: 700"], [style*="font-weight:700"], strong, b');
            const greenDots = row.querySelectorAll('[fill="#00a884"], [fill="#25d366"]');  // WhatsApp green colors
            
            // Look for any small number badges
            const spans = row.querySelectorAll('span');
            let badgeNumber = null;
            for (let span of spans) {
                // Check if span has a background (badges usually have colored backgrounds)
                const style = window.getComputedStyle(span);
                const bgColor = style.backgroundColor;
                const text = span.innerText.trim();
                
                // If it's a small number with a colored background, it's likely a badge
                if (/^\\d+$/.test(text) && parseInt(text) > 0 && parseInt(text) < 100) {
                    if (bgColor && bgColor !== 'rgba(0, 0, 0, 0)' && bgColor !== 'transparent') {
                        badgeNumber = text;
                        break;
                    }
                }
            }
            
            if (boldElements.length > 0 || greenDots.length > 0 || badgeNumber) {
                const nameEl = row.querySelector('span[dir="auto"]');
                chatsWithBadges.push({
                    index: i,
                    name: nameEl ? nameEl.innerText : 'Unknown',
                    hasBoldText: boldElements.length > 0,
                    hasGreenDot: greenDots.length > 0,
                    badgeNumber: badgeNumber
                });
            }
            
            if (chatsWithBadges.length >= 10) break;  // Limit to first 10 with indicators
        }
    }
    
    return {
        hasUnreadInBody: hasUnreadInBody,
        unreadButton: unreadButton,
        chatsWithIndicators: chatsWithBadges
    };
})()
"""

result = evaluate_js(unread_tab_js)

if result:
    print(json.dumps(result, indent=2))
else:
    print("Failed to find unread indicators")