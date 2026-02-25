"""
Test to find correct header selector for chat name
"""

import sys
import os
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from automation.chrome_debug import evaluate_js, get_all_chat_names, find_best_chat_match, open_chat_by_name

print("Opening Sugar chat...")
all_chats = get_all_chat_names()
best_match, _ = find_best_chat_match("Sugar", all_chats)
open_chat_by_name(best_match)

print("Waiting 3 seconds...")
time.sleep(3)

print("\nTrying different header selectors...")
test_js = """
(() => {
    const result = {};
    
    // Check if main exists
    const main = document.querySelector('#main');
    result.main_exists = !!main;
    
    if (!main) return result;
    
    // Try different header selectors
    const header = main.querySelector('header');
    result.header_exists = !!header;
    
    if (header) {
        // Try various span selectors
        const span1 = header.querySelector('span[dir="auto"]');
        const span2 = header.querySelector('span[title]');
        const allSpans = header.querySelectorAll('span');
        
        result.span_dir_auto = span1 ? span1.innerText : null;
        result.span_title = span2 ? span2.innerText : null;
        result.span_title_attr = span2 ? span2.getAttribute('title') : null;
        result.total_spans = allSpans.length;
        
        // Get first few spans' text
        const spanTexts = [];
        for (let i = 0; i < Math.min(allSpans.length, 5); i++) {
            const text = allSpans[i].innerText.trim();
            if (text) spanTexts.push(text);
        }
        result.span_texts = spanTexts;
    }
    
    return result;
})()
"""

result = evaluate_js(test_js)

import json
print(json.dumps(result, indent=2))
