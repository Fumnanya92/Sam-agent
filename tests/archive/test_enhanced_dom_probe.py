from automation.chrome_debug import evaluate_js

# Enhanced DOM exploration to find unread indicators
js = """
(() => {
    const chats = document.querySelectorAll('[data-testid="cell-frame-container"]');
    let results = [];

    chats.forEach((chat, index) => {
        if (index < 10) { // Only check first 10 chats for debugging
            const nameEl = chat.querySelector('span[dir="auto"]');
            const name = nameEl?.innerText || 'Unknown';
            
            // Try multiple badge selectors
            const badge1 = chat.querySelector('[data-testid="icon-unread-count"]');
            const badge2 = chat.querySelector('[aria-label*="unread"]');
            const badge3 = chat.querySelector('span[aria-label]');
            const badge4 = chat.querySelector('[data-testid*="unread"]');
            const badge5 = chat.querySelector('span[title*="unread"]');
            
            // Look for any span with numbers that could be unread count
            const spans = chat.querySelectorAll('span');
            let numberSpan = null;
            spans.forEach(span => {
                const text = span.innerText;
                if (text && /^\d+$/.test(text) && parseInt(text) > 0 && parseInt(text) < 1000) {
                    numberSpan = span;
                }
            });
            
            const unread = badge1?.innerText || badge2?.innerText || badge3?.innerText || 
                          badge4?.innerText || badge5?.innerText || numberSpan?.innerText || null;
            
            results.push({
                name: name,
                unread: unread,
                hasAnyBadge: !!(badge1 || badge2 || badge3 || badge4 || badge5 || numberSpan),
                chatHTML: chat.innerHTML.slice(0, 500)  // First 500 chars of HTML for debugging
            });
        }
    });

    return results;
})()
"""

print("Enhanced DOM Probe Results:")
result = evaluate_js(js)
if result:
    for chat in result:
        print(f"Name: {chat['name']}")
        print(f"Unread: {chat['unread']}")
        print(f"Has Badge: {chat['hasAnyBadge']}")
        print("---")
else:
    print("No results returned")