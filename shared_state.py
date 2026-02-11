import threading

# Global state to prevent Sam from hearing himself
is_sam_speaking = threading.Event()
