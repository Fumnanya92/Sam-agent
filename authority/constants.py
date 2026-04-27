"""
Authority level requirements and action category definitions.
Ported from Jarvis src/roles/authority.ts
"""

ACTION_CATEGORIES = [
    "read_data", "write_data", "delete_data",
    "send_message", "send_email",
    "execute_command", "install_software",
    "make_payment", "modify_settings",
    "spawn_agent", "terminate_agent",
    "access_browser", "control_app",
]

# Minimum authority level required per action category (scale 1-10)
AUTHORITY_REQUIREMENTS: dict[str, int] = {
    "read_data":        1,
    "write_data":       3,
    "send_message":     3,
    "execute_command":  5,
    "access_browser":   5,
    "control_app":      5,
    "spawn_agent":      1,
    "send_email":       7,
    "install_software": 7,
    "make_payment":     9,
    "modify_settings":  9,
    "delete_data":      9,
    "terminate_agent":  9,
}


def describe_level(level: int) -> str:
    if level <= 2:
        return "Read-only: can read data, nothing else."
    if level <= 4:
        return "Read/write: can read, write data and send messages."
    if level <= 6:
        return "Command execution: can execute commands, control apps, access browser."
    if level <= 8:
        return "Agent management: can spawn agents, send emails, install software."
    return "Full access: payments, settings, delete data, terminate agents."
