import time as _time
from automation.chrome_debug import evaluate_js


def get_latest_message_from_open_chat(max_retries: int = 3):
    """Extract latest message from currently opened chat with retry + selector fallbacks.

    Tries three extraction strategies in order:
      1. data-pre-plain-text attribute (original WhatsApp DOM attribute)
      2. aria-label on focusable message rows (accessibility-tree approach)
      3. Raw textContent scan of the conversation area
    """
    extract_js = r"""
    (() => {
        const main = document.querySelector('#main');
        if (!main) return null;

        function stripTimestamp(t) {
            return (t || '').replace(/\s*\d{1,2}:\d{2}(\s[AP]M)?\s*$/, '').trim();
        }

        // ── Strategy 1: data-pre-plain-text (classic WhatsApp attribute) ──
        const byAttr = main.querySelectorAll('[data-pre-plain-text]');
        if (byAttr.length) {
            const last = byAttr[byAttr.length - 1];
            const metadata = last.getAttribute('data-pre-plain-text') || '';
            let text = stripTimestamp(last.textContent || '');
            const isIncoming = /\]\s+[^:]+:\s*$/.test(metadata);
            let sender = null;
            if (isIncoming) {
                const m = metadata.match(/\]\s*(.+?):\s*$/);
                if (m) sender = m[1].trim();
            }
            const hasImage    = last.querySelector('img[src*="blob:"]');
            const hasAudio    = last.querySelector('[aria-label*="audio" i], [data-testid="audio-play"]');
            const hasVideo    = last.querySelector('video');
            const hasDocument = last.querySelector('[data-icon="document"], [aria-label*="document" i]');
            let type = "text";
            if (!text) {
                if (hasImage) type = "image";
                else if (hasAudio) type = "audio";
                else if (hasVideo) type = "video";
                else if (hasDocument) type = "document";
                else type = "unknown";
            }
            return { text: text || null, type, direction: isIncoming ? 'incoming' : 'outgoing', sender, metadata };
        }

        // ── Strategy 2: aria-label on message rows ──
        const msgRows = main.querySelectorAll('[role="row"], [data-id]');
        if (msgRows.length) {
            const last = msgRows[msgRows.length - 1];
            const lbl = (last.getAttribute('aria-label') || '').trim();
            if (lbl && lbl.length > 1) {
                const text = stripTimestamp(lbl);
                return { text: text || null, type: "text", direction: "incoming", sender: null, metadata: "" };
            }
        }

        // ── Strategy 3: raw textContent of the conversation area ──
        const convArea = main.querySelector('[role="application"], [data-testid="conversation-panel-body"]') || main;
        const rawText = stripTimestamp((convArea.innerText || '').trim().split('\n').filter(Boolean).pop() || '');
        if (rawText) {
            return { text: rawText, type: "text", direction: "incoming", sender: null, metadata: "" };
        }

        return null;
    })()
    """

    for attempt in range(max_retries):
        result = evaluate_js(extract_js)
        if result:
            return result
        if attempt < max_retries - 1:
            _time.sleep(1.0)
    return None


def get_current_chat_name():
    """Get the name of the currently open chat from the header with retry logic."""
    import time

    # A more robust JS probe that tries several header selectors and the
    # selected row in the side pane as fallbacks. Returns the first non-empty
    # trimmed string it finds, or null.
    get_name_js = """
    (() => {
        function probeHeaderName() {
            const main = document.querySelector('#main') || document;
            const header = main.querySelector('header') || document.querySelector('header');
            if (!header) return null;

            const candidates = [
                '[data-testid="conversation-info-header-chat-title"]',
                'div[data-testid="conversation-info-header-chat-title"]',
                'span[dir="auto"][title]',
                'div[role="heading"] span',
                'span[dir="auto"]'
            ];

            for (const sel of candidates) {
                try {
                    const el = header.querySelector(sel);
                    if (el && el.innerText && el.innerText.trim()) return el.innerText.trim();
                } catch (e) { /* ignore selector errors */ }
            }

            // Last resort: take the first non-empty line of header text
            const txt = header.innerText || '';
            if (txt) {
                const firstLine = txt.split('\n')[0].trim();
                if (firstLine) return firstLine;
            }
            return null;
        }

        function probeSelectedRow() {
            try {
                const sel = document.querySelector('#pane-side [aria-selected="true"]') || document.querySelector('#pane-side [role="row"].selected');
                if (!sel) {
                    // Fallback: there may be a visually selected row without aria-selected
                    const rows = document.querySelectorAll('#pane-side [role="row"]');
                    for (const r of rows) {
                        if (r.getAttribute('aria-selected') === 'true' || r.className.includes('selected')) return r;
                    }
                    return null;
                }
                const nameEl = sel.querySelector('span[dir="auto"]') || sel.querySelector('div') || sel.querySelector('span');
                if (nameEl && nameEl.innerText && nameEl.innerText.trim()) return nameEl.innerText.trim();
            } catch (e) { /* ignore DOM issues */ }
            return null;
        }

        return probeHeaderName() || probeSelectedRow() || null;
    })()
    """

    # Retry longer to account for loading delays when opening a chat
    for attempt in range(8):
        result = evaluate_js(get_name_js)
        if result:
            return result
        # exponential-ish backoff short sleep
        time.sleep(0.25 if attempt < 2 else 0.5)

    return None


def send_message_in_open_chat(message: str) -> bool:
    """
    Type and send a message in the currently open WhatsApp chat.
    Uses JS to insert text into the input box and dispatch an Enter key event.
    Returns True if the send succeeded, False otherwise.
    """
    if not message or not message.strip():
        return False

    # Escape the message for safe JS string injection
    safe_msg = message.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

    send_js = f"""
    (() => {{
        const main = document.querySelector('#main');
        if (!main) return false;

        // Find the message input box — try multiple selectors
        const selectors = [
            'div[data-tab="10"][contenteditable="true"]',
            'div[contenteditable="true"][data-testid="conversation-compose-box-input"]',
            'footer div[contenteditable="true"]',
            'div[role="textbox"]'
        ];

        let input = null;
        for (const sel of selectors) {{
            input = main.querySelector(sel);
            if (input) break;
        }}
        if (!input) return false;

        // Focus and insert text using execCommand so WhatsApp's React state tracks it
        input.focus();
        document.execCommand('insertText', false, `{safe_msg}`);

        // Brief wait then send Enter key via KeyboardEvent
        setTimeout(() => {{
            const enterEvent = new KeyboardEvent('keydown', {{
                bubbles: true, cancelable: true, keyCode: 13, which: 13, key: 'Enter'
            }});
            input.dispatchEvent(enterEvent);
        }}, 150);

        return true;
    }})()
    """

    result = evaluate_js(send_js)
    if not result:
        return False
    # Give WhatsApp a moment to process the send
    _time.sleep(0.5)
    return True
