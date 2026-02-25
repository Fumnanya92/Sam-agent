import requests
import json
import time
from websocket import create_connection

DEBUG_PORT = 9222


def get_whatsapp_tab():
    try:
        tabs = requests.get(f"http://localhost:{DEBUG_PORT}/json").json()
        for tab in tabs:
            if "web.whatsapp.com" in tab.get("url", ""):
                return tab
        return None
    except Exception:
        return None


def evaluate_whatsapp_state():
    tab = get_whatsapp_tab()
    if not tab:
        print("[DEBUG] WhatsApp tab not found.")
        return "NOT_OPEN"

    try:
        ws_url = tab["webSocketDebuggerUrl"]
        print(f"[DEBUG] Connecting to WebSocket: {ws_url}")
        ws = create_connection(ws_url, enable_multithread=True)

        def eval_js(expression):
            payload = {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expression}
            }
            ws.send(json.dumps(payload))
            while True:
                result = json.loads(ws.recv())
                if result.get("id") == 1:
                    break
            return result.get("result", {}).get("result", {}).get("value")

        # More robust checks: combine selector presence and body-text heuristics
        checks_js = """
        (function(){
            const bodyText = document.body ? document.body.innerText || '' : '';
            const checks = {
                hostname: location.hostname,
                navigatorOnline: navigator.onLine,
                qrCanvas: !!document.querySelector('canvas[aria-label="Scan me!"]'),
                introAny: !!document.querySelector('[data-testid^="intro"]'),
                chatList: !!document.querySelector('[data-testid="chat-list"]'),
                roleGrid: !!document.querySelector('[role="grid"]'),
                hasSearchText: bodyText.indexOf('Search or start new chat') !== -1,
                hasTypeAMessage: bodyText.indexOf('Type a message') !== -1,
                bodySnippet: bodyText.slice(0,2000)
            };
            return JSON.stringify(checks);
        })()
        """

        checks_json = eval_js(checks_js)
        try:
            checks = json.loads(checks_json)
        except Exception:
            print(f"[DEBUG] Failed to parse checks_json: {checks_json}")
            ws.close()
            return "UNKNOWN"

        print(f"[DEBUG] DOM checks: {checks}")

        if checks.get('qrCanvas') or checks.get('introAny') or checks.get('hasSearchText') and not checks.get('chatList'):
            ws.close()
            return "QR_REQUIRED" if checks.get('qrCanvas') else "LOADING"

        if not checks.get('navigatorOnline'):
            ws.close()
            return "OFFLINE"

        if checks.get('chatList') or checks.get('roleGrid') or checks.get('hasTypeAMessage'):
            ws.close()
            return "CONNECTED"

        ws.close()
        print("[DEBUG] Unknown state after checks.")
        return "UNKNOWN"

    except Exception as e:
        print(f"[DEBUG] Exception in evaluate_whatsapp_state: {e}")
        return "OFFLINE"
