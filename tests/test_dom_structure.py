from automation.chrome_debug import evaluate_js
import json

print("=== WhatsApp DOM Structure Analysis ===\n")

# 1. Check common container selectors
print("1. Testing common container selectors:")
selectors_to_test = [
    '[data-testid="cell-frame-container"]',
    '[data-testid="chat"]',
    '[role="listitem"]',
    '[role="row"]',
    '._2nY6U',  # Common WhatsApp class for chat list item
    '.zoWT4',   # Another common class
    '[data-id]',  # Many WhatsApp elements have data-id
]

for selector in selectors_to_test:
    count = evaluate_js(f'document.querySelectorAll("{selector}").length')
    print(f"   {selector}: {count} elements")

# 2. Get all testid attributes to learn what's available
print("\n2. Finding all data-testid values:")
testids = evaluate_js("""
Array.from(document.querySelectorAll('[data-testid]'))
    .slice(0, 50)
    .map(el => el.getAttribute('data-testid'))
    .filter((v, i, a) => a.indexOf(v) === i)
    .sort()
""")
if testids:
    print(f"   Found {len(testids)} unique test IDs (first 50):")
    for tid in testids[:20]:
        print(f"     - {tid}")

# 3. Check for the unread count in the title/header
print("\n3. Checking unread count indicators:")
title = evaluate_js("document.title")
print(f"   Page title: {title}")

# 4. Look for the actual chat list structure
print("\n4. Analyzing chat list structure:")
structure = evaluate_js("""
(() => {
    // Try multiple possible chat list selectors
    const possibleSelectors = [
        '[data-testid="chat-list"]',
        '#pane-side',
        '[role="grid"]',
        '._aigv._aigw',  // Common WhatsApp wrapper
    ];
    
    for (let selector of possibleSelectors) {
        const container = document.querySelector(selector);
        if (container) {
            const children = container.children;
            return {
                selector: selector,
                found: true,
                childCount: children.length,
                firstChildTag: children[0] ? children[0].tagName : null,
                firstChildClasses: children[0] ? children[0].className : null,
                firstChildTestId: children[0] ? children[0].getAttribute('data-testid') : null
            };
        }
    }
    return {found: false};
})()
""")
print(f"   {json.dumps(structure, indent=2)}")

# 5. Get a sample of actual chat HTML
print("\n5. Sample chat HTML structure:")
sample_html = evaluate_js("""
(() => {
    const grid = document.querySelector('[role="grid"]');
    if (grid) {
        const rows = grid.querySelectorAll('[role="row"]');
        if (rows.length > 0) {
            // Get first row's outer HTML (truncated)
            return rows[0].outerHTML.slice(0, 1000);
        }
    }
    return 'Chat grid not found';
})()
""")
print(f"   {sample_html[:500] if sample_html else 'No sample available'}...")