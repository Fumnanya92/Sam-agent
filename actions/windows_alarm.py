"""
Windows native alarm system integration for Sam.

Uses Windows Alarms & Clock app to set real system alarms.
"""
import subprocess
import winreg
from datetime import datetime, timedelta
from log.logger import get_logger

logger = get_logger("WINDOWS_ALARM")


def set_windows_alarm(alarm_time: datetime, label: str = "Sam Alarm") -> tuple[bool, str]:
    """
    Set an alarm using Windows Task Scheduler.
    
    Creates a scheduled task that will fire at the alarm time with:
    - Windows toast notification
    - Alarm sound
    - TTS announcement
    
    Args:
        alarm_time: When the alarm should fire
        label: Description for the alarm
    
    Returns:
        (success: bool, message: str)
    """
    try:
        # Create the alarm via Task Scheduler (automated approach)
        success, message = _create_scheduled_alarm(alarm_time, label)
        
        if success:
            logger.info(f"Windows alarm created successfully for {alarm_time.strftime('%I:%M %p')}")
            return True, f"Alarm set for {alarm_time.strftime('%I:%M %p')}"
        else:
            logger.error(f"Failed to create alarm: {message}")
            return False, message
            
    except Exception as e:
        logger.error(f"Failed to set Windows alarm: {e}", exc_info=True)
        return False, f"Couldn't set Windows alarm: {e}"


def _open_alarms_app(alarm_time: datetime, label: str) -> bool:
    """
    Open Windows Alarms & Clock app.
    
    Note: The ms-clock: protocol doesn't support pre-filling alarm time,
    so we just open the app to the alarms page.
    """
    try:
        # Open Windows Alarms & Clock app to Alarms page
        subprocess.run(
            ['explorer', 'ms-clock:'],
            shell=True,
            check=False
        )
        logger.info(f"Opened Windows Alarms app for user to set {alarm_time.strftime('%H:%M')}")
        return True
    except Exception as e:
        logger.warning(f"Failed to open Alarms app: {e}")
        return False


def _create_scheduled_alarm(alarm_time: datetime, label: str) -> tuple[bool, str]:
    """
    Create a Windows Task Scheduler task that will fire at the alarm time.
    
    This creates a real system-level alarm that will trigger even if Sam isn't running.
    """
    try:
        # Task name (unique per alarm)
        task_name = f"SamAlarm_{alarm_time.strftime('%Y%m%d_%H%M')}"
        
        # Create notification script that will run at alarm time
        notification_script = _create_alarm_notification_script(label, alarm_time)
        
        # Build schtasks command to create the scheduled task
        # Format time for schtasks: HH:MM
        alarm_time_str = alarm_time.strftime('%H:%M')
        alarm_date_str = alarm_time.strftime('%m/%d/%Y')
        
        # Create the task using schtasks.exe
        create_cmd = [
            'schtasks', '/Create',
            '/TN', task_name,
            '/TR', f'powershell.exe -WindowStyle Hidden -File "{notification_script}"',
            '/SC', 'ONCE',
            '/ST', alarm_time_str,
            '/SD', alarm_date_str,
            '/F'  # Force create (overwrite if exists)
        ]
        
        result = subprocess.run(
            create_cmd,
            capture_output=True,
            text=True,
            shell=True,
            check=False
        )
        
        if result.returncode == 0:
            logger.info(f"Created Windows scheduled alarm task: {task_name} for {alarm_time_str}")
            return True, f"Alarm scheduled via Windows Task Scheduler for {alarm_time.strftime('%I:%M %p')}"
        else:
            logger.error(f"Task creation failed: {result.stderr}")
            return False, f"Couldn't create alarm task: {result.stderr}"
            
    except Exception as e:
        logger.error(f"Failed to create scheduled alarm: {e}", exc_info=True)
        return False, f"Alarm scheduling failed: {e}"


def _create_alarm_notification_script(label: str, alarm_time: datetime) -> str:
    """
    Create a PowerShell script that shows a Windows notification and plays alarm sound.
    Returns the path to the script file.
    """
    import tempfile
    import os
    
    script_dir = os.path.join(tempfile.gettempdir(), 'SamAlarms')
    os.makedirs(script_dir, exist_ok=True)
    
    script_path = os.path.join(script_dir, f'alarm_{alarm_time.strftime("%Y%m%d_%H%M")}.ps1')
    
    # PowerShell script to show notification and play sound
    script_content = f'''# Sam Alarm Notification
$title = "⏰ Alarm: {label}"
$message = "Alarm set for {alarm_time.strftime('%I:%M %p')} is going off!"

# Show Windows notification
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

$template = @"
<toast>
    <visual>
        <binding template="ToastText02">
            <text id="1">$title</text>
            <text id="2">$message</text>
        </binding>
    </visual>
    <audio src="ms-winsoundevent:Notification.Looping.Alarm" loop="true" />
</toast>
"@

$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Sam Alarm").Show($toast)

# Also play system alarm sound
Add-Type -AssemblyName System.Speech
$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer
$speak.Speak("Alarm: {label}")

# Keep notification visible for 30 seconds
Start-Sleep -Seconds 30
'''
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    logger.info(f"Created alarm notification script: {script_path}")
    return script_path


def list_windows_alarms() -> list[dict]:
    """
    List all Sam-created Windows alarms (scheduled tasks).
    
    Returns list of dicts with task info.
    """
    try:
        result = subprocess.run(
            ['schtasks', '/Query', '/FO', 'CSV', '/NH'],
            capture_output=True,
            text=True,
            shell=True,
            check=False
        )
        
        alarms = []
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if 'SamAlarm_' in line:
                    parts = line.replace('"', '').split(',')
                    if len(parts) >= 3:
                        alarms.append({
                            'name': parts[0].strip(),
                            'next_run': parts[1].strip(),
                            'status': parts[2].strip()
                        })
        
        logger.info(f"Found {len(alarms)} scheduled Sam alarms")
        return alarms
        
    except Exception as e:
        logger.error(f"Failed to list alarms: {e}")
        return []


def cancel_windows_alarm(task_name: str) -> tuple[bool, str]:
    """
    Cancel a Windows scheduled alarm by task name.
    """
    try:
        result = subprocess.run(
            ['schtasks', '/Delete', '/TN', task_name, '/F'],
            capture_output=True,
            text=True,
            shell=True,
            check=False
        )
        
        if result.returncode == 0:
            logger.info(f"Cancelled Windows alarm: {task_name}")
            return True, f"Alarm cancelled"
        else:
            return False, f"Couldn't cancel alarm: {result.stderr}"
            
    except Exception as e:
        logger.error(f"Failed to cancel alarm: {e}")
        return False, str(e)
