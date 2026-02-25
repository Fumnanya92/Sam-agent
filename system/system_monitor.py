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
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            processes.append(proc.info)
        except:
            continue

    processes = sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)
    return processes[:3]


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
