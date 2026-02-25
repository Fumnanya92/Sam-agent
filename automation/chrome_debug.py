import requests
import json
import time
from websocket import create_connection
import uuid
import subprocess
import os
import psutil

DEBUG_PORT = 9222


def is_chrome_debug_running():
    """Check if Chrome is running with remote debugging enabled."""
    try:
        response = requests.get(f"http://localhost:{DEBUG_PORT}/json", timeout=2)
        return response.status_code == 200
    except:
        return False


def find_chrome_executable():
    """Find Chrome executable on Windows."""
    possible_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Users\{}\AppData\Local\Google\Chrome\Application\chrome.exe".format(os.getenv('USERNAME', '')),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None


def launch_chrome_debug():
    """Launch Chrome with remote debugging if not already running."""
    if is_chrome_debug_running():
        print("[INFO] Chrome debug session already active. Reusing existing instance.")
        return True
    
    print("[INFO] Chrome debug not detected. Launching Chrome...")
    
    chrome_exe = find_chrome_executable()
    if not chrome_exe:
        print("[ERROR] Chrome executable not found!")
        return False
    
    # Kill any existing Chrome processes first (clean slate)
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                proc.kill()
        time.sleep(2)  # Wait for processes to close
    except:
        pass
    
    # Launch Chrome with debug flags
    debug_dir = r"C:\chrome-debug-profile"
    try:
        subprocess.Popen([
            chrome_exe,
            f"--remote-debugging-port={DEBUG_PORT}",
            "--remote-allow-origins=*",
            f"--user-data-dir={debug_dir}",
            "https://web.whatsapp.com"
        ], 
        creationflags=subprocess.CREATE_NO_WINDOW  # Hide window creation
        )
        
        # Wait and verify Chrome started successfully
        for attempt in range(10):
            time.sleep(1)
            if is_chrome_debug_running():
                print("[SUCCESS] Chrome launched successfully with debug enabled!")
                return True
        
        print("[ERROR] Chrome launched but debug connection failed.")
        return False
        
    except Exception as e:
        print(f"[ERROR] Failed to launch Chrome: {e}")
        return False


def ensure_chrome_debug():
    """Ensure Chrome is running with debug support. Launch if needed."""
    return launch_chrome_debug()


def get_whatsapp_tab():
    # Ensure Chrome is running with debug support
    if not ensure_chrome_debug():
        return None
    
    try:
        tabs = requests.get(f"http://localhost:{DEBUG_PORT}/json").json()
        for tab in tabs:
            if "web.whatsapp.com" in tab.get("url", ""):
                return tab
        return None
    except Exception:
        return None


def evaluate_js(expression):
    """Evaluate JavaScript in the WhatsApp Web tab"""
    tab = get_whatsapp_tab()
    if not tab:
        return None

    try:
        ws = create_connection(tab["webSocketDebuggerUrl"], enable_multithread=True)
        request_id = int(uuid.uuid4().int % 100000)
        payload = {
            "id": request_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "returnByValue": True
            }
        }
        ws.send(json.dumps(payload))
        while True:
            result = json.loads(ws.recv())
            if result.get("id") == request_id:
                break
        ws.close()
        result_obj = result.get("result", {}).get("result", {})
        if "value" in result_obj:
            return result_obj["value"]
        elif result_obj.get("type") == "string":
            return result_obj.get("value")
        else:
            return None
    except Exception as e:
        print(f"[DEBUG] Error evaluating JS: {e}")
        return None


def get_active_tab():
    """Detect which tab is currently active in WhatsApp"""
    
    detect_tabs_js = """
    (() => {
        // Find all tabs in the chat list header
        const tabs = document.querySelectorAll('[role="tab"]');
        let tabInfo = [];
        
        tabs.forEach(tab => {
            const text = (tab.innerText || '').trim();
            const isSelected = tab.getAttribute('aria-selected') === 'true';
            const hasNumber = /\\d+/.test(text);
            
            tabInfo.push({
                text: text,
                isSelected: isSelected,
                hasNumberBadge: hasNumberBadge
            });
        });
        
        return tabInfo;
    })()
    """
    
    return evaluate_js(detect_tabs_js) or []


def switch_to_unread_tab():
    """Switch to the Unread tab to filter only unread messages"""
    
    switch_js = """
    (() => {
        const tabs = document.querySelectorAll('[role="tab"]');
        let unreadTab = null;

        // Find the tab that contains "Unread" or has an unread count badge
        for (let tab of tabs) {
            const text = (tab.innerText || '').toLowerCase().trim();
            const ariaLabel = (tab.getAttribute('aria-label') || '').toLowerCase();
            
            // Look for "unread" in text or aria-label, and ensure it has a number
            const hasUnreadKeyword = text.includes('unread') || ariaLabel.includes('unread');
            const hasNumber = /\\d+/.test(tab.innerText || '');
            
            // Exclude archived tab
            const isArchived = text.includes('archived') || ariaLabel.includes('archived');

            if ((hasUnreadKeyword || hasNumber) && !isArchived) {
                // Prefer tab with "unread" in the name
                if (hasUnreadKeyword) {
                    unreadTab = tab;
                    break;
                } else if (!unreadTab && hasNumber) {
                    // Fallback: use tab with number if "unread" keyword not found
                    unreadTab = tab;
                }
            }
        }

        if (unreadTab) {
            const isAlreadySelected = unreadTab.getAttribute('aria-selected') === 'true';

            if (!isAlreadySelected) {
                unreadTab.click();
                return { switched: true, alreadyActive: false };
            }

            return { switched: true, alreadyActive: true };
        }

        // If no unread tab found, we're probably already viewing all or there are no unreads
        return { switched: false };
    })()
    """
    return evaluate_js(switch_js)



def get_unread_messages():
    """Get all unread WhatsApp messages with sender names AND message content"""
    
    # Step 1: Switch to unread tab (detects dynamically, no hardcoded names)
    switch_result = switch_to_unread_tab()
    
    if not switch_result or not switch_result.get('switched'):
        return []
    
    # Wait for DOM if we just switched
    if not switch_result.get('alreadyActive'):
        time.sleep(1)
    
    # Step 2: Extract chat names AND message previews from unread chats
    extract_js = r"""
    (() => {
        const pane = document.querySelector('#pane-side');
        if (!pane) return [];

        const rows = pane.querySelectorAll('[role="row"]');
        let results = [];

        rows.forEach(row => {
            // Get contact name using span[title]
            const nameEl = row.querySelector('span[title]');
            const name = nameEl ? nameEl.title.trim() : null;
            
            if (!name) return;
            
            // Get message preview - look for the message text content
            let messagePreview = null;
            
            // Strategy 1: Look for span elements that might contain message text
            const textElements = row.querySelectorAll('span');
            for (let span of textElements) {
                const text = span.innerText?.trim();
                // Skip if it's the contact name, timestamp, date, or unread count
                if (text && 
                    text !== name && 
                    !/^\d{1,2}:\d{2}/.test(text) && // Skip timestamps like "10:30"
                    !/^\d{1,2}\/\d{1,2}\/\d{4}/.test(text) && // Skip dates like "1/21/2026"
                    !/^\d+$/.test(text) && // Skip unread counts like "3"
                    text.length > 3 && // Must be meaningful length
                    text.length < 200) { // But not too long
                    messagePreview = text;
                    break;
                }
            }
            
            // Strategy 2: If no message found, try looking for div elements
            if (!messagePreview) {
                const divElements = row.querySelectorAll('div');
                for (let div of divElements) {
                    const text = div.innerText?.trim();
                    if (text && 
                        text !== name && 
                        !/^\d{1,2}:\d{2}/.test(text) &&
                        !/^\d{1,2}\/\d{1,2}\/\d{4}/.test(text) && // Skip dates like "1/21/2026"
                        !/^\d+$/.test(text) &&
                        text.length > 3 &&
                        text.length < 200) {
                        messagePreview = text;
                        break;
                    }
                }
            }
            
            results.push({ 
                name: name,
                message: messagePreview || "Media or no preview available"
            });
        });

        return results;
    })()
    """
    
    return evaluate_js(extract_js) or []


# --- Phase 4D: Fuzzy Chat Matching ---

def switch_to_all_tab():
    """Switch to the 'All' tab (first tab, not archived, not unread)"""
    switch_js = """
    (() => {
        const tabs = document.querySelectorAll('[role="tab"]');
        let allTab = null;
        for (let tab of tabs) {
            const text = (tab.innerText || '').trim();
            const hasNumber = /\\d+/.test(text);
            const isArchived = text.toLowerCase().includes("archived");
            if (!hasNumber && !isArchived) {
                allTab = tab;
                break;
            }
        }
        if (allTab) {
            const isAlreadySelected = allTab.getAttribute('aria-selected') === 'true';
            if (!isAlreadySelected) {
                allTab.click();
                return { switched: true, alreadyActive: false };
            }
            return { switched: true, alreadyActive: true };
        }
        return { switched: false };
    })()
    """
    return evaluate_js(switch_js)

def get_all_chat_names():
    """Extract all visible chat names from the All tab."""
    # Always switch to All tab first
    switch_result = switch_to_all_tab()
    if not switch_result or not switch_result.get('switched'):
        return []
    if not switch_result.get('alreadyActive'):
        time.sleep(1)
    extract_js = """
    (() => {
        const pane = document.querySelector('#pane-side');
        if (!pane) return [];
        const rows = pane.querySelectorAll('[role="row"]');
        let results = [];
        rows.forEach(row => {
            // Use span[title] - WhatsApp stores full name in title attribute
            const nameEl = row.querySelector('span[title]');
            if (nameEl && nameEl.title) {
                const name = nameEl.title.trim();
                if (name) {
                    results.push(name);
                }
            }
        });
        return results;
    })()
    """
    return evaluate_js(extract_js) or []

# Fuzzy matching engine
try:
    from rapidfuzz import fuzz, process
except ImportError:
    fuzz = None
    process = None

def find_best_chat_match(query, chat_list, threshold=65):
    """Find best fuzzy match for chat name (case-normalized)."""
    if not chat_list or not fuzz or not process:
        return None, []
    query = query.strip().lower()
    normalized = [c.lower() for c in chat_list]
    matches = process.extract(
        query,
        normalized,
        scorer=fuzz.WRatio,
        limit=5
    )
    strong = [m for m in matches if m[1] >= threshold]
    if not strong:
        return None, matches
    matches_sorted = sorted(matches, key=lambda x: x[1], reverse=True)
    best_index = matches_sorted[0][2]
    best_name = chat_list[best_index]
    if len(strong) == 1:
        return best_name, matches
    if strong[0][1] - strong[1][1] > 15:
        return best_name, matches
    return None, matches

def open_chat_by_name(chat_name):
    """Click chat row by matching name (handles emojis and partial matches)."""
    import json
    safe_name = json.dumps(chat_name)
    open_js = f"""
    (() => {{
        const target = {safe_name};
        const rows = document.querySelectorAll('#pane-side [role="row"]');
        
        for (let row of rows) {{
            // Use span[title] for reliable chat name matching
            const nameEl = row.querySelector('span[title]');
            if (!nameEl) continue;
            
            const name = nameEl.title.trim();
            
            // Check for exact match
            if (name === target) {{
                row.click();
                return true;
            }}
            
            // Check if name starts with target (handles emojis at end like "Sugar❤️")
            if (name.startsWith(target)) {{
                row.click();
                return true;
            }}
            
            // Check if target is contained in name (case-insensitive)
            if (name.toLowerCase().includes(target.toLowerCase())) {{
                row.click();
                return true;
            }}
        }}
        
        return false;
    }})()
    """
    return evaluate_js(open_js)