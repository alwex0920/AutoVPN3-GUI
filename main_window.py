import sys
import os
import subprocess
from fetcher import Fetcher
from ping_tester import PingWorker
from openvpn_launcher import OpenVPNLauncher
import platform
import shutil
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QTextEdit, QProgressBar, QComboBox, QLabel,
                             QFileDialog, QMessageBox, QApplication, QSystemTrayIcon,
                             QMenu)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import QDialog, QFormLayout, QComboBox, QLineEdit, QCheckBox, QDialogButtonBox

class ConnectionOptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Параметры подключения")
        layout = QFormLayout(self)
        
        self.proto_combo = QComboBox()
        self.proto_combo.addItems(["tcp", "udp"])
        layout.addRow("Протокол:", self.proto_combo)
        
        self.port_edit = QLineEdit("443")
        layout.addRow("Порт:", self.port_edit)
        
        self.auth_check = QCheckBox("Требуется авторизация")
        layout.addRow(self.auth_check)
        
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("логин")
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("пароль")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Логин:", self.username_edit)
        layout.addRow("Пароль:", self.password_edit)
        
        # изначально скрываем поля авторизации
        self.username_edit.setVisible(False)
        self.password_edit.setVisible(False)
        self.auth_check.toggled.connect(lambda checked: self.username_edit.setVisible(checked) or self.password_edit.setVisible(checked))
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)
    
    def get_options(self):
        return {
            'proto': self.proto_combo.currentText(),
            'port': self.port_edit.text(),
            'auth': self.auth_check.isChecked(),
            'username': self.username_edit.text(),
            'password': self.password_edit.text()
        }

OS = platform.system()  # 'Linux', 'Windows', 'Darwin'

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Autovpn3 GUI")
        self.resize(1000, 700)
        self.setWindowIcon(QIcon("resources/icon.png"))

        self.servers = []           # список серверов (словарей)
        self.ping_workers = []   # список активных воркеров
        self.ping_values = []       # параллельный список пингов
        self.active_launcher = None # текущий запущенный OpenVPN
        self.tray_icon = None

        # Создаём центральный виджет
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Панель управления
        control_panel = QHBoxLayout()
        self.country_combo = QComboBox()
        self.country_combo.addItems(["Все", "JP", "US", "DE", "RU", "NL", "FR", "GB", "CA"])
        self.load_btn = QPushButton("Загрузить список (через прокси)")
        self.load_file_btn = QPushButton("Загрузить из файла")
        self.best_btn = QPushButton("Подключиться к лучшему")
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        control_panel.addWidget(QLabel("Страна:"))
        control_panel.addWidget(self.country_combo)
        control_panel.addWidget(self.load_btn)
        control_panel.addWidget(self.load_file_btn)
        control_panel.addWidget(self.best_btn)
        control_panel.addWidget(self.progress)
        layout.addLayout(control_panel)

        # Таблица
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["IP", "Страна", "Пинг (мс)", "Подключиться", "Удалить"])
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(4, 80)
        layout.addWidget(self.table)

        # Лог
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(QLabel("Лог OpenVPN:"))
        layout.addWidget(self.log_text)

        # Строка состояния
        self.statusBar().showMessage("Готов")

        # Подключаем сигналы
        self.load_btn.clicked.connect(self.load_servers)
        self.load_file_btn.clicked.connect(self.load_from_file)
        self.best_btn.clicked.connect(self.connect_to_best)

        # Настройка трея
        self.setup_tray()

        # Таймер для чтения вывода OpenVPN
        self.vpn_output_timer = QTimer()
        self.vpn_output_timer.timeout.connect(self.read_vpn_output)
        self.vpn_output_timer.setInterval(100)

    # ---------- Трей ----------
    def setup_tray(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon(self)
            self.tray_icon.setIcon(QIcon("resources/icon.png"))
            self.tray_icon.setToolTip("Autovpn3 GUI")
            menu = QMenu()
            show_action = QAction("Показать", self)
            quit_action = QAction("Выйти", self)
            show_action.triggered.connect(self.show_window)
            quit_action.triggered.connect(self.exit_app)
            menu.addAction(show_action)
            menu.addAction(quit_action)
            self.tray_icon.setContextMenu(menu)
            self.tray_icon.show()
        else:
            print("Трей не поддерживается")

    def closeEvent(self, event):
        # При закрытии окна прячем в трей, а не закрываем
        if self.tray_icon and self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            self.tray_icon.showMessage("Autovpn3 GUI",
                                       "Приложение свёрнуто в трей",
                                       QSystemTrayIcon.MessageIcon.Information, 2000)
        else:
            self.exit_app()

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def exit_app(self):
        # Останавливаем OpenVPN, если запущен
        if self.active_launcher:
            self.active_launcher.stop()
        # Завершаем все пинг-воркеры
        for w in self.ping_workers:
            w.quit()
            w.wait()
        QApplication.quit()

    # ---------- Загрузка серверов ----------
    def load_servers(self):
        self.log_text.clear()
        self.statusBar().showMessage("Загрузка списка через прокси...")
        self.load_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)

        # Запускаем поток загрузки
        self.fetcher_thread = QThread()
        self.fetcher_worker = FetcherWorker(use_proxy=True)
        self.fetcher_worker.moveToThread(self.fetcher_thread)
        self.fetcher_thread.started.connect(self.fetcher_worker.run)
        self.fetcher_worker.finished.connect(self.on_servers_loaded)
        self.fetcher_worker.finished.connect(self.fetcher_thread.quit)
        self.fetcher_worker.error.connect(self.on_load_error)
        self.fetcher_worker.error.connect(self.fetcher_thread.quit)
        self.fetcher_thread.start()

    def load_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите файл списка", "", "Text files (*.txt);;All files (*.*)")
        if not file_path:
            return
        self.log_text.clear()
        self.statusBar().showMessage(f"Загрузка из файла {file_path}...")
        self.load_file_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)

        fetcher = Fetcher()
        try:
            servers = fetcher.from_file(file_path)
            self.process_servers(servers)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось прочитать файл:\n{e}")
        finally:
            self.load_file_btn.setEnabled(True)
            self.progress.setVisible(False)

    def on_servers_loaded(self, servers):
        self.process_servers(servers)
        self.load_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.statusBar().showMessage(f"Загружено серверов: {len(servers)}", 5000)

    def on_load_error(self, error_msg):
        QMessageBox.critical(self, "Ошибка загрузки", error_msg)
        self.load_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.statusBar().showMessage("Ошибка загрузки", 5000)

    def process_servers(self, servers):
        # Фильтр по стране
        country = self.country_combo.currentText()
        if country != "Все":
            servers = [s for s in servers if s['country'] == country]
        if not servers:
            QMessageBox.warning(self, "Нет серверов", "Для выбранной страны серверов не найдено")
            return
        self.servers = servers[:60]  # берём первые 60
        self.ping_values = [None] * len(self.servers)

        # Отображаем таблицу
        self.table.setRowCount(len(self.servers))
        for i, srv in enumerate(self.servers):
            self.table.setItem(i, 0, QTableWidgetItem(srv['ip']))
            self.table.setItem(i, 1, QTableWidgetItem(srv['country']))
            self.table.setItem(i, 2, QTableWidgetItem("--"))
            # Кнопки "Подключиться" и "Удалить" будут добавлены через setCellWidget позже
        self.add_action_buttons()

        # Запускаем пинг-тестирование для всех серверов
        self.ping_index = 0
        self.ping_total = len(self.servers)
        self.progress.setVisible(True)
        self.progress.setMaximum(self.ping_total)
        self.progress.setValue(0)
        self.start_next_ping()

    def add_action_buttons(self):
        for i in range(self.table.rowCount()):
            # Кнопка "Подключиться"
            btn_connect = QPushButton("Подключиться")
            btn_connect.clicked.connect(lambda checked, idx=i: self.connect_to_server(idx))
            self.table.setCellWidget(i, 3, btn_connect)
            # Кнопка "Удалить"
            btn_delete = QPushButton("Удалить")
            btn_delete.clicked.connect(lambda checked, idx=i: self.delete_server(idx))
            self.table.setCellWidget(i, 4, btn_delete)

    def start_next_ping(self):
        if self.ping_index >= self.ping_total:
            self.progress.setVisible(False)
            self.statusBar().showMessage("Пинг-тестирование завершено", 3000)
            return
        ip = self.servers[self.ping_index]['ip']
        worker = PingWorker(self.ping_index, ip)
        self.ping_workers.append(worker)   # сохраняем ссылку
        worker.finished.connect(self.on_ping_finished)
        worker.start()

    def on_ping_finished(self, index, ping_ms):
        self.ping_values[index] = ping_ms
        self.table.setItem(index, 2, QTableWidgetItem(f"{ping_ms:.1f}" if ping_ms < 9999 else "❌"))
        self.ping_index += 1
        self.progress.setValue(self.ping_index)
        # Удаляем воркер из списка после завершения
        for w in self.ping_workers:
            if w.index == index:
                w.finished.disconnect()
                w.quit()
                w.wait()
                self.ping_workers.remove(w)
                break
        self.start_next_ping()

    # ---------- Управление серверами ----------
    def delete_server(self, index):
        # Удаляем сервер из списка и из таблицы
        self.servers.pop(index)
        self.ping_values.pop(index)
        self.table.removeRow(index)
        # Переназначаем кнопки для последующих строк
        for i in range(index, self.table.rowCount()):
            # нужно обновить lambda для новых индексов
            btn_connect = self.table.cellWidget(i, 3)
            btn_connect.clicked.disconnect()
            btn_connect.clicked.connect(lambda checked, idx=i: self.connect_to_server(idx))
            btn_delete = self.table.cellWidget(i, 4)
            btn_delete.clicked.disconnect()
            btn_delete.clicked.connect(lambda checked, idx=i: self.delete_server(idx))

    def is_tool_available(self, tool):
        return shutil.which(tool) is not None

    def connect_to_server(self, index):
        srv = self.servers[index]
        config_b64 = srv['base64_config']
        
        # Очищаем лог перед новым подключением
        self.log_text.clear()
        
        # Проверка наличия OpenVPN (только для Windows)
        if OS == 'Windows' and not self.is_tool_available('openvpn'):
            QMessageBox.critical(self, "Ошибка", "OpenVPN не найден. Установите OpenVPN и добавьте в PATH.")
            return
        
        # Показываем диалог с настройками подключения
        dialog = ConnectionOptionsDialog(self)
        if not dialog.exec():
            return  # пользователь отменил
        
        opts = dialog.get_options()
        username = opts['username'] if opts['auth'] else None
        password = opts['password'] if opts['auth'] else None
        proto = opts['proto']
        port = opts['port']
        
        # Запускаем OpenVPN с полученными параметрами
        self.statusBar().showMessage(f"Подключение к {srv['ip']}:{port} ({proto})...")
        self.active_launcher = OpenVPNLauncher(
            config_b64, username, password,
            proto=proto, port=port
        )
        self.process = self.active_launcher.start()
        self.vpn_output_timer.start()
        self.add_disconnect_button()

    def connect_to_best(self):
        if not self.ping_values:
            QMessageBox.warning(self, "Нет данных", "Сначала загрузите серверы.")
            return
        best_idx = -1
        best_ping = 9999
        for i, p in enumerate(self.ping_values):
            if p is not None and p < best_ping:
                best_ping = p
                best_idx = i
        if best_idx == -1:
            QMessageBox.warning(self, "Нет доступных серверов", "Не удалось найти сервер с рабочим пингом.")
        else:
            self.connect_to_server(best_idx)

    def add_disconnect_button(self):
        # Безопасно удаляем старую кнопку, если она существует
        if hasattr(self, 'disconnect_btn') and self.disconnect_btn is not None:
            try:
                self.disconnect_btn.deleteLater()
            except RuntimeError:
                pass
            self.disconnect_btn = None
        self.disconnect_btn = QPushButton("Отключиться от VPN")
        self.disconnect_btn.clicked.connect(self.disconnect_vpn)
        self.statusBar().addPermanentWidget(self.disconnect_btn)

    def disconnect_vpn(self):
        if self.active_launcher:
            self.active_launcher.stop()
            self.active_launcher = None
        self.vpn_output_timer.stop()
        self.statusBar().showMessage("VPN отключён")
        if hasattr(self, 'disconnect_btn') and self.disconnect_btn is not None:
            try:
                self.disconnect_btn.deleteLater()
            except RuntimeError:
                pass
            self.disconnect_btn = None
        self.log_text.append("VPN остановлен пользователем.")

    def read_vpn_output(self):
        if self.process is None:
            return
        # Проверяем, завершился ли процесс
        poll = self.process.poll()
        if poll is not None:
            print(f"[VPN] Процесс OpenVPN завершился с кодом {poll}")
            self.vpn_output_timer.stop()
            if hasattr(self, 'disconnect_btn'):
                self.disconnect_btn.deleteLater()
            # Дополнительно: выводим остатки из буфера
            self._read_all_pipes()
            return
        # Читаем без блокировки
        self._read_all_pipes()

    def _read_all_pipes(self):
        import select
        # Читаем stdout
        if select.select([self.process.stdout], [], [], 0)[0]:
            line = self.process.stdout.readline()
            if line:
                self.log_text.append(line.strip())
                print(f"[VPN stdout] {line.strip()}")
        # Читаем stderr
        if select.select([self.process.stderr], [], [], 0)[0]:
            line = self.process.stderr.readline()
            if line:
                self.log_text.append("[STDERR] " + line.strip())
                print(f"[VPN stderr] {line.strip()}")

    # ---------- Дополнительно: автозапуск ----------
    def enable_autostart(self):
        # Реализуем создание .desktop файла в Linux
        autostart_dir = os.path.expanduser("~/.config/autostart")
        os.makedirs(autostart_dir, exist_ok=True)
        desktop_file = os.path.join(autostart_dir, "vpn-gate-gui.desktop")
        with open(desktop_file, 'w') as f:
            f.write("[Desktop Entry]\n")
            f.write("Type=Application\n")
            f.write(f"Name=Autovpn3 GUI\n")
            f.write(f"Exec={sys.executable} {os.path.abspath(sys.argv[0])}\n")
            f.write("Hidden=false\n")
            f.write("NoDisplay=false\n")
            f.write("X-GNOME-Autostart-enabled=true\n")
        QMessageBox.information(self, "Автозапуск", "Автозапуск включён (создан .desktop файл)")

# ---------- Вспомогательный класс для потока загрузки ----------
class FetcherWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, use_proxy=True):
        super().__init__()
        self.use_proxy = use_proxy

    def run(self):
        try:
            fetcher = Fetcher(proxy_url="https://alwex-vpn.vercel.app/proxy?url=")
            # Используем URL VPN Gate
            url = "https://www.vpngate.net/api/iphone/"
            servers = fetcher.from_url(url, use_proxy=self.use_proxy, timeout=60)
            self.finished.emit(servers)
        except Exception as e:
            self.error.emit(str(e))