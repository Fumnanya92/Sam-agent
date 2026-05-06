"""
tests/test_whatsapp_capability.py

Capability smoke-test for WhatsApp read flow.

This test validates that:
  1. The Chrome debug session is reachable (Sam browser profile is running)
  2. A WhatsApp Web tab exists and is on web.whatsapp.com
  3. The WhatsApp DOM can be queried (document.readyState == "complete")
  4. The unread-message extraction JS returns a list (may be empty — that's fine)

It does NOT require actual unread messages. It only validates the plumbing.

Marks the whatsapp_summary capability as working/broken in the registry on pass/fail.
"""

import pytest


def _chrome_available() -> bool:
    try:
        from automation.chrome_debug import is_chrome_debug_running
        return is_chrome_debug_running()
    except Exception:
        return False


@pytest.mark.skipif(not _chrome_available(), reason="Chrome debug session not running — start Sam browser profile first")
class TestWhatsAppCapability:

    def test_whatsapp_tab_exists(self):
        from automation.chrome_debug import get_whatsapp_tab
        tab = get_whatsapp_tab()
        assert tab is not None, (
            "No WhatsApp Web tab found in Chrome. "
            "Run scripts/bootstrap_sam_browser.py once to set up the persistent profile."
        )

    def test_dom_ready(self):
        from automation.chrome_debug import evaluate_js
        ready = evaluate_js("document.readyState")
        assert ready == "complete", f"WhatsApp Web DOM not ready: readyState={ready!r}"

    def test_unread_extraction_returns_list(self):
        from automation.chrome_debug import get_unread_messages
        result = get_unread_messages()
        assert isinstance(result, list), f"get_unread_messages() returned {type(result)}, expected list"

    def test_latest_message_extraction(self):
        """Open the first unread chat (if any) and verify message extraction works."""
        from automation.chrome_debug import get_unread_messages, open_chat_by_name
        from automation.whatsapp_dom import get_latest_message_from_open_chat
        unreads = get_unread_messages()
        if not unreads:
            pytest.skip("No unread messages — skipping message read test")
        name = unreads[0].get("name")
        assert name, "First unread item has no name"
        opened = open_chat_by_name(name)
        assert opened, f"Could not open chat with '{name}'"
        msg = get_latest_message_from_open_chat()
        assert msg is not None, f"get_latest_message_from_open_chat() returned None for '{name}'"
        assert "direction" in msg
