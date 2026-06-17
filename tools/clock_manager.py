import os
import time
import logging
import subprocess
from datetime import datetime, timedelta
from typing import Dict, Any, List
from tools.base import BaseTool

logger = logging.getLogger("jarvis.tools.clock_manager")

# Global memory storage for active timers and alarms
_active_alerts: List[Dict[str, Any]] = []

def get_fired_alerts() -> List[Dict[str, Any]]:
    """
    Checks for any alerts that have reached their target time.
    Returns the list of newly fired alerts and removes them or marks them.
    """
    now = time.time()
    fired = []
    global _active_alerts
    
    still_active = []
    for alert in _active_alerts:
        if now >= alert["target_time"]:
            fired.append({
                "id": alert["id"],
                "type": alert["type"],
                "label": alert["label"]
            })
            logger.info(f"Alert fired: {alert['type']} - {alert['label']}")
        else:
            still_active.append(alert)
            
    _active_alerts = still_active
    return fired

def get_active_alerts() -> List[Dict[str, Any]]:
    """
    Returns the list of all currently active/pending alerts.
    """
    return _active_alerts

def cancel_alert(alert_id: str) -> bool:
    """
    Cancels/removes an active alert by its ID.
    Returns True if found and removed, False otherwise.
    """
    global _active_alerts
    initial_len = len(_active_alerts)
    _active_alerts = [alert for alert in _active_alerts if alert["id"] != alert_id]
    return len(_active_alerts) < initial_len

def automate_timer_gui(duration: int, label: str):
    """
    Automates the Windows Clock app GUI to set a timer.
    """
    import ctypes
    import time
    import subprocess
    
    # 1. Wait a bit for the clock app to open and stabilize
    time.sleep(2.0)
    
    # 2. Find the Clock window
    hwnd = ctypes.windll.user32.FindWindowW("ApplicationFrameWindow", "Clock")
    if not hwnd:
        hwnd = ctypes.windll.user32.FindWindowW(None, "Clock")
        
    if not hwnd:
        logger.warning("GUI Automation: Clock window not found.")
        return False
        
    # 3. Bring the window to the foreground
    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    time.sleep(0.1)
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    
    # 4. Format hours, minutes, seconds
    mins, secs = divmod(duration, 60)
    hours, mins = divmod(mins, 60)
    
    # 5. Prepare PowerShell keystrokes command
    safe_label = label.replace("'", "''")
    ps_cmd = (
        f"$wshell = New-Object -ComObject Wscript.Shell; "
        f"$wshell.SendKeys('^n'); "
        f"Start-Sleep -Milliseconds 600; "
        f"$wshell.SendKeys('{hours}'); "
        f"Start-Sleep -Milliseconds 100; "
        f"$wshell.SendKeys('{{TAB}}'); "
        f"Start-Sleep -Milliseconds 100; "
        f"$wshell.SendKeys('{mins}'); "
        f"Start-Sleep -Milliseconds 100; "
        f"$wshell.SendKeys('{{TAB}}'); "
        f"Start-Sleep -Milliseconds 100; "
        f"$wshell.SendKeys('{secs}'); "
        f"Start-Sleep -Milliseconds 100; "
        f"$wshell.SendKeys('{{TAB}}'); "
        f"Start-Sleep -Milliseconds 100; "
        f"$wshell.SendKeys('{safe_label}'); "
        f"Start-Sleep -Milliseconds 100; "
        f"$wshell.SendKeys('{{ENTER}}');"
    )
    
    try:
        subprocess.Popen(["powershell", "-Command", ps_cmd], shell=False)
        logger.info(f"GUI Automation: Sent keystrokes to create timer '{label}' of {duration}s.")
        return True
    except Exception as e:
        logger.error(f"GUI Automation: Failed to send keystrokes: {e}")
        return False

def automate_alarm_gui(time_str: str, label: str):
    """
    Automates the Windows Clock app GUI to set an alarm.
    """
    import ctypes
    import time
    import subprocess
    from datetime import datetime
    
    # Try parsing time_str to extract hours, minutes, and am/pm
    hours, minutes, ampm = None, None, None
    
    formats_12h = [("%I:%M %p", True), ("%I:%M%p", True), ("%I:%M", False), ("%H:%M", False)]
    for fmt, is_12h in formats_12h:
        try:
            parsed = datetime.strptime(time_str.strip(), fmt)
            hours = parsed.hour
            minutes = parsed.minute
            if is_12h:
                ampm = "a" if parsed.hour < 12 else "p"
            break
        except ValueError:
            continue
            
    if hours is None:
        logger.warning(f"GUI Automation: Could not parse time '{time_str}' for alarm GUI automation.")
        return False
        
    # 1. Wait a bit for the clock app to open and stabilize
    time.sleep(2.0)
    
    # 2. Find the Clock window
    hwnd = ctypes.windll.user32.FindWindowW("ApplicationFrameWindow", "Clock")
    if not hwnd:
        hwnd = ctypes.windll.user32.FindWindowW(None, "Clock")
        
    if not hwnd:
        logger.warning("GUI Automation: Clock window not found.")
        return False
        
    # 3. Bring the window to the foreground
    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    time.sleep(0.1)
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    
    display_hour = hours
    if ampm:
        display_hour = hours % 12
        if display_hour == 0:
            display_hour = 12
            
    safe_label = label.replace("'", "''")
    
    # Construct SendKeys sequence
    keys_seq = [
        f"$wshell.SendKeys('{display_hour}');",
        "Start-Sleep -Milliseconds 100;",
        "$wshell.SendKeys('{TAB}');",
        "Start-Sleep -Milliseconds 100;",
        f"$wshell.SendKeys('{minutes:02d}');",
        "Start-Sleep -Milliseconds 100;",
        "$wshell.SendKeys('{TAB}');",
        "Start-Sleep -Milliseconds 100;"
    ]
    
    if ampm:
        keys_seq.extend([
            f"$wshell.SendKeys('{ampm}');",
            "Start-Sleep -Milliseconds 100;",
            "$wshell.SendKeys('{TAB}');",
            "Start-Sleep -Milliseconds 100;"
        ])
        
    keys_seq.extend([
        f"$wshell.SendKeys('{safe_label}');",
        "Start-Sleep -Milliseconds 100;",
        "$wshell.SendKeys('{ENTER}');"
    ])
    
    keys_str = " ".join(keys_seq)
    
    ps_cmd = (
        f"$wshell = New-Object -ComObject Wscript.Shell; "
        f"$wshell.SendKeys('^n'); "
        f"Start-Sleep -Milliseconds 600; "
        f"{keys_str}"
    )
    
    try:
        subprocess.Popen(["powershell", "-Command", ps_cmd], shell=False)
        logger.info(f"GUI Automation: Sent keystrokes to create alarm '{label}' at {time_str}.")
        return True
    except Exception as e:
        logger.error(f"GUI Automation: Failed to send keystrokes: {e}")
        return False

class ClockManagerTool(BaseTool):
    """
    Launches the Windows Clock app or manages local timers and alarms inside J.A.R.V.I.S.
    """
    @property
    def name(self) -> str:
        return "clock_app"

    @property
    def description(self) -> str:
        return (
            "Launches the Windows system Clock app or schedules local alarms and timers in J.A.R.V.I.S. "
            "Actions:\n"
            "- 'open': Opens the Windows Clock app (default).\n"
            "- 'set_timer': Sets a timer for a duration in seconds.\n"
            "- 'set_alarm': Sets an alarm for a specific time (format: HH:MM or HH:MM AM/PM)."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["open", "set_timer", "set_alarm"],
                    "description": "The clock action to execute. Defaults to 'open' if not provided."
                },
                "duration": {
                    "type": "integer",
                    "description": "Duration in seconds (required only when action is 'set_timer')."
                },
                "time_str": {
                    "type": "string",
                    "description": "Time string (e.g., '15:30' or '03:30 PM') (required only when action is 'set_alarm')."
                },
                "label": {
                    "type": "string",
                    "description": "Optional custom label/name for the alarm or timer (e.g., 'Take out garbage')."
                }
            },
            "required": [],
            "additionalProperties": False
        }

    async def run(self, **kwargs) -> str:
        action = kwargs.get("action", "open")
        duration = kwargs.get("duration", 0)
        time_str = kwargs.get("time_str", "")
        label = kwargs.get("label", "Alert")

        # 1. Action: Open system Clock app
        if action == "open":
            try:
                # ms-clock protocol is the standard handler for Alarms & Clock on Windows
                logger.info("Launching Windows Clock app via ms-clock URI")
                import os
                if hasattr(os, "startfile"):
                    os.startfile("ms-clock:")
                else:
                    subprocess.Popen(["explorer.exe", "ms-clock:"], shell=False)
                return "Successfully opened the Windows Clock application."
            except Exception as e:
                return f"Failed to open Clock app: {e}"

        # 2. Action: Set local timer
        elif action == "set_timer":
            if not duration or duration <= 0:
                return "Error: Please specify a valid duration in seconds greater than 0."
            
            target = time.time() + duration
            alert_id = f"timer_{int(target)}"
            
            alert = {
                "id": alert_id,
                "type": "Timer",
                "target_time": target,
                "label": label
            }
            _active_alerts.append(alert)
            
            # Launch the PC Clock app timer tab so user can see it
            try:
                import os
                if hasattr(os, "startfile"):
                    os.startfile("ms-clock:timer")
                else:
                    subprocess.Popen(["explorer.exe", "ms-clock:timer"], shell=False)
                
                # Run GUI automation in a background thread to set the timer in the app
                import threading
                threading.Thread(target=automate_timer_gui, args=(duration, label), daemon=True).start()
            except Exception as launch_err:
                logger.warning(f"Failed to open/automate PC clock timer: {launch_err}")

            # Format friendly message
            mins, secs = divmod(duration, 60)
            dur_msg = f"{mins}m {secs}s" if mins else f"{secs}s"
            return f"Timer '{label}' set successfully for {dur_msg} from now."

        # 3. Action: Set local alarm
        elif action == "set_alarm":
            if not time_str:
                return "Error: Please specify a time string for the alarm."
            
            try:
                now_dt = datetime.now()
                target_time = None
                
                # Try parsing formats
                formats = ["%H:%M", "%I:%M %p", "%I:%M%p"]
                parsed_time = None
                for fmt in formats:
                    try:
                        parsed_time = datetime.strptime(time_str.strip(), fmt)
                        break
                    except ValueError:
                        continue
                
                if not parsed_time:
                    return f"Error: Unable to parse time '{time_str}'. Please use HH:MM (24h) or HH:MM AM/PM formats."
                
                # Build target datetime today
                target_dt = now_dt.replace(hour=parsed_time.hour, minute=parsed_time.minute, second=0, microsecond=0)
                
                # If target time has already passed today, set it for tomorrow
                if target_dt <= now_dt:
                    target_dt += timedelta(days=1)
                
                epoch_target = target_dt.timestamp()
                alert_id = f"alarm_{int(epoch_target)}"
                
                alert = {
                    "id": alert_id,
                    "type": "Alarm",
                    "target_time": epoch_target,
                    "label": label
                }
                _active_alerts.append(alert)
                
                # Launch the PC Clock app alarm tab so user can see it
                try:
                    import os
                    if hasattr(os, "startfile"):
                        os.startfile("ms-clock:alarm")
                    else:
                        subprocess.Popen(["explorer.exe", "ms-clock:alarm"], shell=False)
                    
                    # Run GUI automation in a background thread to set the alarm in the app
                    import threading
                    threading.Thread(target=automate_alarm_gui, args=(time_str, label), daemon=True).start()
                except Exception as launch_err:
                    logger.warning(f"Failed to open/automate PC clock alarm: {launch_err}")

                time_formatted = target_dt.strftime("%I:%M %p (%A)")
                return f"Alarm '{label}' set successfully for {time_formatted}."
            except Exception as e:
                return f"Error setting alarm: {str(e)}"

        else:
            return f"Error: Unsupported action '{action}'."
