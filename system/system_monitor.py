import psutil
import socket
from datetime import datetime


def get_cpu_usage():
    return psutil.cpu_percent(interval=1)


def get_ram_usage():
    memory = psutil.virtual_memory()
    return {
        "percent": memory.percent,
        "used_gb": round(memory.used / (1024 ** 3), 2),
        "total_gb": round(memory.total / (1024 ** 3), 2)
    }


def get_disk_usage():
    disk = psutil.disk_usage('/')
    return {
        "percent": disk.percent,
        "used_gb": round(disk.used / (1024 ** 3), 2),
        "total_gb": round(disk.total / (1024 ** 3), 2)
    }


def get_battery_status():
    battery = psutil.sensors_battery()
    if battery:
        return {
            "percent": battery.percent,
            "plugged": battery.power_plugged
        }
    return None


def get_top_process():
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_percent']):
        try:
            info = proc.info
            if info['name'] and info['memory_percent'] and info['memory_percent'] > 0:
                processes.append(info)
        except:
            continue

    processes = sorted(processes, key=lambda x: x.get('memory_percent', 0), reverse=True)
    # Return as cpu_percent key so handler at handlers.py line 788 still works
    return [{'name': p['name'], 'cpu_percent': round(p['memory_percent'], 1)}
            for p in processes[:3]]


def is_online():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return True
    except:
        return False


def get_system_report():
    return {
        "time": datetime.now().strftime("%H:%M:%S"),
        "cpu": get_cpu_usage(),
        "ram": get_ram_usage(),
        "disk": get_disk_usage(),
        "battery": get_battery_status(),
        "online": is_online(),
        "top_processes": get_top_process()
    }
