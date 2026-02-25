from automation.chrome_debug import evaluate_js

# Simple test first
print("Testing basic JS evaluation:")
basic_test = evaluate_js("document.title")
print(f"Page title: {basic_test}")

if basic_test:
    print("\nTesting chat detection:")
    
    # Simple chat count test
    chat_count = evaluate_js("document.querySelectorAll('[data-testid=\"cell-frame-container\"]').length")
    print(f"Number of chats found: {chat_count}")
    
    if chat_count and int(chat_count) > 0:
        print("\nLooking for unread indicators...")
        
        # Look for any elements containing numbers
        unread_test = evaluate_js("""
        (() => {
            const chats = document.querySelectorAll('[data-testid="cell-frame-container"]');
            let results = [];
            
            for (let i = 0; i < Math.min(5, chats.length); i++) {
                const chat = chats[i];
                const nameEl = chat.querySelector('span[dir="auto"]');
                const name = nameEl ? nameEl.innerText : 'Unknown';
                
                // Look for any span with just numbers
                const allSpans = chat.querySelectorAll('span');
                let unreadCount = null;
                
                for (let span of allSpans) {
                    const text = span.innerText.trim();
                    if (/^\\d+$/.test(text) && parseInt(text) > 0 && parseInt(text) < 100) {
                        unreadCount = text;
                        break;
                    }
                }
                
                if (unreadCount) {
                    results.push({name: name, unread: unreadCount});
                }
            }
            
            return results;
        })()
        """)
        
        print(f"Unread messages found: {unread_test}")
else:
    print("Chrome debug connection failed - checking connection...")
    from automation.chrome_controller import ensure_chrome_running
    ensure_chrome_running()
    print("Chrome restarted - try running the test again")