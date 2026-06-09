import subprocess
import tempfile
import base64
import os
import re
import platform

class OpenVPNLauncher:
    def __init__(self, config_base64, username=None, password=None, proto='tcp', port='443'):
        self.config_base64 = config_base64
        self.username = username
        self.password = password
        self.proto = proto   # 'tcp' или 'udp'
        self.port = port
        self.process = None
        self.config_path = None
        self.os = platform.system()

    def start(self):
        print("[OpenVPNLauncher] Декодируем конфигурацию...")
        try:
            config_data = base64.b64decode(self.config_base64).decode('utf-8')
            # Заменяем строку proto (ищем "proto tcp" или "proto udp")
            config_data = re.sub(r'^proto\s+\w+', f'proto {self.proto}', config_data, flags=re.MULTILINE)
            # Заменяем порт в строке remote (ищем "remote IP порт")
            config_data = re.sub(r'^remote\s+(\S+)\s+\d+', f'remote \\1 {self.port}', config_data, flags=re.MULTILINE)
            print("[OpenVPNLauncher] Конфигурация успешно декодирована.")
        except Exception as e:
            print(f"[OpenVPNLauncher] Ошибка декодирования base64: {e}")
            return None

        if self.username and self.password:
            config_data += f"\nauth-user-pass\n{self.username}\n{self.password}\n"
            print("[OpenVPNLauncher] Добавлены данные авторизации.")

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ovpn', delete=False) as f:
                f.write(config_data)
                self.config_path = f.name
            print(f"[OpenVPNLauncher] Временный конфиг создан: {self.config_path}")
        except Exception as e:
            print(f"[OpenVPNLauncher] Ошибка создания временного файла: {e}")
            return None

        if self.os == 'Windows':
            cmd = ['openvpn', '--config', self.config_path]
        else:
            cmd = ['pkexec', 'openvpn', '--config', self.config_path]
        print(f"[OpenVPNLauncher] Запуск команды: {' '.join(cmd)}")

        try:
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            print(f"[OpenVPNLauncher] Процесс запущен (PID: {self.process.pid})")
            return self.process
        except Exception as e:
            print(f"[OpenVPNLauncher] Ошибка запуска: {e}")
            return None

    def stop(self):
        if self.process:
            print("[OpenVPNLauncher] Останавливаем процесс OpenVPN...")
            if self.os == 'Windows':
                self.process.terminate()
                self.process.wait(timeout=3)
            else:
                # Linux: используем pkexec для отправки сигнала
                subprocess.run(['pkexec', 'kill', '-TERM', str(self.process.pid)], capture_output=True)
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            if self.config_path and os.path.exists(self.config_path):
                os.unlink(self.config_path)
                print(f"[OpenVPNLauncher] Удалён временный файл: {self.config_path}")