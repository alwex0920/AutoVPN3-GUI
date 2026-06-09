import subprocess
import re
import platform
from PyQt6.QtCore import QThread, pyqtSignal

class PingWorker(QThread):
    finished = pyqtSignal(int, float)

    def __init__(self, index, ip, count=1):
        super().__init__()
        self.index = index
        self.ip = ip
        self.count = count
        self.os = platform.system()

    def run(self):
        ping = 9999.0
        try:
            if self.os == 'Windows':
                cmd = ['ping', '-n', str(self.count), '-w', '1000', self.ip]
                out = subprocess.check_output(cmd, universal_newlines=True, timeout=5, encoding='cp866')
                print(f"[DEBUG] Windows ping {self.ip}:\n{out[:500]}")
                m = re.search(r'время[= ](\d+)мс', out, re.IGNORECASE)
                if not m:
                    m = re.search(r'time[= ](\d+)ms', out, re.IGNORECASE)
                if m:
                    ping = float(m.group(1))
            else:
                # Linux: используем fping без -q, чтобы получить полный вывод
                proc = subprocess.run(['fping', '-c', str(self.count), self.ip],
                                      capture_output=True, text=True, timeout=5)
                stdout = proc.stdout.strip()
                stderr = proc.stderr.strip()
                print(f"[DEBUG] fping {self.ip} -> stdout: {stdout}")
                print(f"[DEBUG] fping {self.ip} -> stderr: {stderr}")
                output = stdout if stdout else stderr
                if output:
                    # Паттерн 1: (214 avg, 0% loss)
                    m = re.search(r'\((\d+(?:\.\d+)?)\s*avg', output)
                    if not m:
                        # Паттерн 2: min/avg/max = 1.2/3.4/5.6
                        m = re.search(r'min/avg/max = [\d.]+/([\d.]+)/[\d.]+', output)
                    if not m:
                        # Паттерн 3: последнее число перед ms
                        numbers = re.findall(r'(\d+(?:\.\d+)?)\s*ms', output)
                        if numbers:
                            ping = float(numbers[-1])
                    else:
                        ping = float(m.group(1))
                else:
                    print(f"[WARN] Нет вывода от fping для {self.ip}")
        except subprocess.TimeoutExpired:
            print(f"[WARN] Таймаут пинга для {self.ip}")
        except Exception as e:
            print(f"[ERROR] Ping failed for {self.ip}: {e}")
        print(f"[DEBUG] Итоговый пинг для {self.ip}: {ping}")
        self.finished.emit(self.index, ping)