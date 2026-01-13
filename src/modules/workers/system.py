import os
import time
import glob
import platform
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

class SystemMonitor(QThread):
    stats_signal = pyqtSignal(dict)
    def run(self):
        while True:
            stats = {'cpu_load': 0, 'cpu_temp': 0, 'gpu_load': 0, 'gpu_temp': 0, 'has_gpu': False, 'gpu_vendor': ''}
            if PSUTIL_AVAILABLE:
                try: 
                    stats['cpu_load'] = int(psutil.cpu_percent(interval=None))
                    if hasattr(psutil, "sensors_temperatures"):
                        t = psutil.sensors_temperatures()
                        if 'coretemp' in t: stats['cpu_temp'] = int(t['coretemp'][0].current)
                        elif 'cpu_thermal' in t: stats['cpu_temp'] = int(t['cpu_thermal'][0].current)
                except: pass
            
            # 1. NVIDIA
            try:
                res = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,temperature.gpu', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=1)
                if res.returncode == 0:
                    p = res.stdout.strip().split(',')
                    if len(p) >= 2: stats['gpu_load'] = int(p[0].strip()); stats['gpu_temp'] = int(p[1].strip()); stats['has_gpu'] = True; stats['gpu_vendor'] = 'NVIDIA'
            except: pass

            # 2. AMD Linux
            if not stats['has_gpu'] and platform.system() == "Linux":
                try:
                    for card in glob.glob('/sys/class/drm/card*/device'):
                        busy = os.path.join(card, 'gpu_busy_percent')
                        if os.path.exists(busy):
                            with open(busy, 'r') as f: stats['gpu_load'] = int(f.read().strip())
                            stats['has_gpu'] = True; stats['gpu_vendor'] = 'AMD'
                            tf = glob.glob(os.path.join(card, 'hwmon/hwmon*/temp1_input'))
                            if tf:
                                with open(tf[0], 'r') as f: stats['gpu_temp'] = int(int(f.read().strip()) / 1000)
                            break
                except: pass

            # 3. Windows AMD/Intel
            if not stats['has_gpu'] and platform.system() == "Windows":
                try:
                    v_res = subprocess.run(['wmic', 'path', 'Win32_VideoController', 'get', 'Name'], capture_output=True, text=True, timeout=1)
                    v_out = v_res.stdout.upper()
                    vendor = 'AMD' if "AMD" in v_out else 'Intel' if "INTEL" in v_out else 'GPU'
                    ps = r"(Get-Counter '\GPU Engine(*)\Utilization Percentage' -ErrorAction SilentlyContinue).CounterSamples | Measure-Object -Property CookedValue -Max | Select-Object -ExpandProperty Maximum"
                    l_res = subprocess.run(['powershell', '-Command', ps], capture_output=True, text=True, timeout=1)
                    if l_res.returncode == 0 and l_res.stdout.strip():
                        stats['gpu_load'] = int(float(l_res.stdout.strip())); stats['has_gpu'] = True; stats['gpu_vendor'] = vendor
                except: pass

            self.stats_signal.emit(stats); time.sleep(2)
