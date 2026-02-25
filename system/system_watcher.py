import psutil
import time
import threading

class SystemWatcher:
    def __init__(self):
        self.running = False
        self.cpu_history = []
        self.ram_history = []
        self.max_samples = 120  # 2 minutes if 1 sec interval
        self.auto_mode = False

    def start(self):
        if self.running:
            return

        self.running = True
        thread = threading.Thread(target=self._loop, daemon=True)
        thread.start()

    def stop(self):
        self.running = False

    def enable_auto_mode(self):
        self.auto_mode = True

    def disable_auto_mode(self):
        self.auto_mode = False

    def _loop(self):
        while self.running:
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent

            self.cpu_history.append(cpu)
            self.ram_history.append(ram)

            if len(self.cpu_history) > self.max_samples:
                self.cpu_history.pop(0)
            if len(self.ram_history) > self.max_samples:
                self.ram_history.pop(0)

            # AUTO intervention
            if self.auto_mode:
                self._auto_logic(cpu, ram)

    def _auto_logic(self, cpu, ram):
        if cpu > 90:
            from system.process_control import get_heavy_processes, kill_process_by_name
            heavy = get_heavy_processes(1)
            if heavy:
                name = heavy[0]['name']
                if name.lower() not in ["system", "idle", "system idle process"]:
                    kill_process_by_name(name)
                    print(f"[AUTO MODE] Terminated {name}")

    def get_average_load(self):
        if not self.cpu_history:
            return 0, 0
        return (
            sum(self.cpu_history) / len(self.cpu_history),
            sum(self.ram_history) / len(self.ram_history)
        )
