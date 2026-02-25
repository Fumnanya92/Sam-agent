from automation.chrome_debug import get_unread_messages
import json

# Get all unread messages (automatically clicks Unread tab)
result = get_unread_messages()

if result:
    print(json.dumps(result, indent=2))
else:
    print("No unread messages found")