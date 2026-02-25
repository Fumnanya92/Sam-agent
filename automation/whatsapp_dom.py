from automation.chrome_debug import evaluate_js


def get_latest_message_from_open_chat():
    """Extract latest message from currently opened chat. Returns structured dict or None."""
    extract_js = r"""
    (() => {
        const main = document.querySelector('#main');
        if (!main) return null;

        // WhatsApp uses [data-pre-plain-text] for messages
        const messages = main.querySelectorAll('[data-pre-plain-text]');
        if (!messages.length) return null;

        const last = messages[messages.length - 1];

        // Get metadata (contains timestamp and sender for incoming)
        const metadata = last.getAttribute('data-pre-plain-text') || '';
        
        // Extract text - get textContent but remove the timestamp at the end
        let text = last.textContent || '';
        // Remove trailing timestamp (format: "9:33 AM" or "9:33 PM")
        text = text.replace(/\d{1,2}:\d{2}\s[AP]M$/, '').trim();
        
        // Determine direction: incoming messages have sender name after ] in metadata
        // Format: "[time, date] Sender: " for incoming, "[time, date] " for outgoing
        const isIncoming = /\]\s+[^:]+:\s*$/.test(metadata);
        const direction = isIncoming ? 'incoming' : 'outgoing';
        
        // Extract sender from metadata if incoming
        let sender = null;
        if (isIncoming) {
            const match = metadata.match(/\]\s*(.+?):\s*$/);
            if (match) sender = match[1].trim();
        }

        // Detect media types
        const hasImage = last.querySelector('img[src*="blob:"]');
        const hasAudio = last.querySelector('[data-testid="audio-play"]');
        const hasVideo = last.querySelector('video');
        const hasDocument = last.querySelector('[data-icon="document"]');

        let messageType = "text";
        if (!text) {
            if (hasImage) messageType = "image";
            else if (hasAudio) messageType = "audio";
            else if (hasVideo) messageType = "video";
            else if (hasDocument) messageType = "document";
            else messageType = "unknown";
        }

        return {
            text: text || null,
            type: messageType,
            direction: direction,
            sender: sender,
            metadata: metadata
        };
    })()
    """

    return evaluate_js(extract_js)


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


# NOTE: send_message_in_open_chat function has been removed
# as part of the transition to draft & confirm system for safety.
