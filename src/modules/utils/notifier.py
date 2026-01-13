import platform
import subprocess
from PyQt6.QtWidgets import QApplication
from .common import debug_log

class SystemNotifier:
    @staticmethod
    def notify(title, message, icon="dialog-information"):
        system = platform.system()
        try:
            if system == "Linux":
                cmd = ['notify-send', '-a', 'CineBridge Pro', '-i', icon, title, message]
                if icon == "dialog-error": cmd.extend(['-u', 'critical'])
                subprocess.Popen(cmd)
                try:
                    sound_id = "message" if icon == "dialog-information" else "dialog-error"
                    subprocess.Popen(['canberra-gtk-play', '-i', sound_id], stderr=subprocess.DEVNULL)
                except: 
                    if icon != "dialog-information": QApplication.beep()
            elif system == "Darwin":
                script = f'display notification "{message}" with title "{title}"'
                script += ' sound name "Basso"' if icon == "dialog-error" else ' sound name "Glass"'
                subprocess.run(["osascript", "-e", script])
            elif system == "Windows":
                ps_script = f"""
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;
                $template_type = [Windows.UI.Notifications.ToastTemplateType]::ToastText02;
                $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template_type);
                $xml = $template.GetXml();
                $text = $template.GetElementsByTagName("text");
                $text[0].AppendChild($template.CreateTextNode("{title}")) > $null;
                $text[1].AppendChild($template.CreateTextNode("{message}")) > $null;
                $toast = [Windows.UI.Notifications.ToastNotification]::new($template);
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("CineBridge Pro").Show($toast);
                """
                subprocess.Popen(["powershell", "-Command", ps_script], creationflags=subprocess.CREATE_NO_WINDOW)
            if system != "Linux": QApplication.beep()
        except Exception as e: debug_log(f"Notification failed: {e}")
