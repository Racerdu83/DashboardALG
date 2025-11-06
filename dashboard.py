import sys
import os
import psutil
import wmi
import platform
import subprocess
import threading
import requests
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar,
    QPushButton, QGridLayout, QHBoxLayout, QComboBox, QSystemTrayIcon, QStyle
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont

# NVIDIA
try:
    import pynvml
    pynvml.nvmlInit()
    NVIDIA_AVAILABLE = True
except:
    NVIDIA_AVAILABLE = False

import winshell
from win32com.client import Dispatch

# --------------------------
APP_VERSION = "1.0.0"
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/Racerdu83/DashboardALG/main/version.txt"
GITHUB_EXE_URL = "https://github.com/Racerdu83/DashboardALG/releases/download/ALGApps/DashboardMonitor.exe"

# --------------------------
def check_update():
    try:
        r = requests.get(GITHUB_VERSION_URL, timeout=5)
        latest_version = r.text.strip()
        if latest_version != APP_VERSION:
            return latest_version
    except Exception as e:
        print("Impossible de vérifier la version :", e)
    return None

def download_update():
    try:
        r = requests.get(GITHUB_EXE_URL, stream=True)
        exe_path = os.path.join(os.getenv('TEMP'), "DashboardMonitor_new.exe")
        with open(exe_path, "wb") as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)
        return exe_path
    except Exception as e:
        print("Erreur téléchargement :", e)
        return None

def run_update(exe_path):
    subprocess.Popen([exe_path])
    sys.exit()

# --------------------------
class Dashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dashboard Monitor")
        self.setGeometry(100, 100, 400, 500)
        self.setStyleSheet("background-color: #1e1e1e; color: white;")
        self.wmi_obj = wmi.WMI()
        self.ping_result = "N/A"

        self.title_font = QFont("Segoe UI", 11, QFont.Weight.Bold)
        self.label_font = QFont("Segoe UI", 10)

        main_layout = QVBoxLayout()

        # ======== Barre de boutons du haut ========
        btn_layout = QHBoxLayout()

        # Bouton épingler
        self.pin_button = QPushButton("📌 Épingler")
        self.pin_button.setCheckable(True)
        self.pin_button.clicked.connect(self.toggle_pin)
        btn_layout.addWidget(self.pin_button)

        # Bouton autostart
        self.autostart_checkbox = QPushButton("⚙️ Autostart")
        self.autostart_checkbox.setCheckable(True)
        self.autostart_checkbox.setChecked(self.is_autostart_enabled())
        self.autostart_checkbox.clicked.connect(self.toggle_autostart)
        btn_layout.addWidget(self.autostart_checkbox)

        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # ======== Grid des stats ========
        self.grid = QGridLayout()
        self.grid.setSpacing(10)

        # CPU
        self.cpu_label = QLabel("CPU : 0%")
        self.cpu_label.setFont(self.title_font)
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setTextVisible(True)
        self.cpu_bar.setStyleSheet(self.bar_style())
        self.grid.addWidget(self.cpu_label, 0, 0, 1, 2)
        self.grid.addWidget(self.cpu_bar, 1, 0, 1, 2)

        # RAM
        self.ram_label = QLabel("RAM : 0%")
        self.ram_label.setFont(self.title_font)
        self.ram_bar = QProgressBar()
        self.ram_bar.setStyleSheet(self.bar_style())
        self.grid.addWidget(self.ram_label, 2, 0, 1, 2)
        self.grid.addWidget(self.ram_bar, 3, 0, 1, 2)

        # GPU
        self.gpu_label = QLabel("GPU : N/A")
        self.gpu_label.setFont(self.title_font)
        self.gpu_bar = QProgressBar()
        self.gpu_bar.setStyleSheet(self.bar_style())
        self.grid.addWidget(self.gpu_label, 4, 0, 1, 2)

        # Sélecteur GPU
        self.gpu_combo = QComboBox()
        self.gpu_combo.setFont(self.label_font)
        self.grid.addWidget(QLabel("Sélection GPU :"), 5, 0)
        self.grid.addWidget(self.gpu_combo, 5, 1)
        self.detect_gpus()

        # Disques
        self.disk_labels = []
        self.disk_bars = []
        self.disk_start_row = 6
        main_layout.addLayout(self.grid)

        # Réseau
        self.net_label = QLabel("Réseau : ↑ 0 KB/s | ↓ 0 KB/s | Ping N/A")
        self.net_label.setFont(self.title_font)
        main_layout.addWidget(self.net_label)

        self.setLayout(main_layout)

        # Tray icon pour notifications
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QApplication.style().standardIcon(QStyle.SP_ComputerIcon))
        self.tray_icon.show()

        # Timer
        self.last_net = psutil.net_io_counters()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(1000)

        # Thread ping
        self.ping_thread = threading.Thread(target=self.update_ping, daemon=True)
        self.ping_thread.start()

    # ============================
    # 🔧 AUTOSTART FUNCTIONS
    # ============================
    def get_startup_path(self):
        return os.path.join(os.getenv("APPDATA"), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    def get_shortcut_path(self):
        exe_path = sys.executable
        name = os.path.basename(exe_path).replace(".exe","")
        return os.path.join(self.get_startup_path(), f"{name}.lnk")
    def is_autostart_enabled(self):
        return os.path.exists(self.get_shortcut_path())
    def toggle_autostart(self):
        shortcut_path = self.get_shortcut_path()
        exe_path = sys.executable
        try:
            if self.autostart_checkbox.isChecked():
                shell = Dispatch('WScript.Shell')
                shortcut = shell.CreateShortCut(shortcut_path)
                shortcut.Targetpath = exe_path
                shortcut.WorkingDirectory = os.path.dirname(exe_path)
                shortcut.IconLocation = exe_path
                shortcut.save()
                self.autostart_checkbox.setText("⚙️ Autostart ✅")
                self.show_notification("Autostart activé", "L’application démarrera avec Windows")
            else:
                if os.path.exists(shortcut_path):
                    os.remove(shortcut_path)
                self.autostart_checkbox.setText("⚙️ Autostart")
                self.show_notification("Autostart désactivé", "L’application ne démarrera plus automatiquement")
        except Exception as e:
            print("Erreur autostart :", e)
            self.autostart_checkbox.setChecked(False)
            self.show_notification("Erreur", str(e))

    def show_notification(self, title, message):
        self.tray_icon.showMessage(title, message, QSystemTrayIcon.Information, 4000)

    # ============================
    # UI functions
    # ============================
    def bar_style(self):
        return """
            QProgressBar {
                border: 2px solid #555;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #00ccff;
                width: 10px;
                margin: 1px;
            }
        """
    def toggle_pin(self):
        if self.pin_button.isChecked():
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.show()
            self.pin_button.setText("📌 Épinglé")
        else:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
            self.show()
            self.pin_button.setText("📌 Épingler")
    def detect_gpus(self):
        self.gpu_list = []
        try:
            if NVIDIA_AVAILABLE:
                count = pynvml.nvmlDeviceGetCount()
                for i in range(count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    name = pynvml.nvmlDeviceGetName(handle).decode()
                    self.gpu_combo.addItem(f"{i}: {name}")
                    self.gpu_list.append(handle)
            cpu_name = self.wmi_obj.Win32_Processor()[0].Name
            self.gpu_combo.addItem(f"CPU intégré : {cpu_name}")
            self.gpu_list.append("CPU")
        except:
            self.gpu_combo.addItem("Aucune GPU détectée")

    def update_stats(self):
        # CPU
        cpu = int(psutil.cpu_percent())
        cpu_temp, gpu_temp = self.get_temps()
        self.cpu_bar.setValue(cpu)
        self.cpu_label.setText(f"CPU : {cpu}% | {cpu_temp}")
        self.cpu_bar.setStyleSheet(self.dynamic_color(cpu))
        # RAM
        ram = psutil.virtual_memory()
        ram_percent = int(ram.percent)
        self.ram_bar.setValue(ram_percent)
        self.ram_label.setText(f"RAM : {ram.used//(1024**3)}Go / {ram.total//(1024**3)}Go ({ram_percent}%)")
        self.ram_bar.setStyleSheet(self.dynamic_color(ram_percent))
        # GPU
        gpu_percent = 0
        gpu_info = "GPU : "
        try:
            selected_index = self.gpu_combo.currentIndex()
            gpu_item = self.gpu_list[selected_index]
            if gpu_item == "CPU":
                gpu_info += "CPU intégré"
                gpu_percent = 0
            elif NVIDIA_AVAILABLE:
                handle = gpu_item
                name = pynvml.nvmlDeviceGetName(handle).decode()
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpu_percent = int(pynvml.nvmlDeviceGetUtilizationRates(handle).gpu)
                gpu_info += f"{name} | {gpu_percent}% | {mem.used//1024**2}Mo/{mem.total//1024**2}Mo"
            else:
                gpu_info += "N/A"
                gpu_percent = 0
        except:
            gpu_info += "Erreur"
            gpu_percent = 0
        if gpu_temp != "N/A":
            gpu_info += f" | {gpu_temp}"
        self.gpu_label.setText(gpu_info)
        self.gpu_bar.setValue(gpu_percent)
        self.gpu_bar.setFormat(f"{gpu_percent}%" if gpu_percent else "N/A")
        self.gpu_bar.setStyleSheet(self.dynamic_color(gpu_percent))
        # Disques
        partitions = psutil.disk_partitions()
        current_disks = [p.device for p in partitions]
        for idx in reversed(range(len(self.disk_labels))):
            lbl = self.disk_labels[idx]
            if lbl.text().split(":")[0] not in current_disks:
                self.grid.removeWidget(lbl)
                lbl.deleteLater()
                bar = self.disk_bars[idx]
                self.grid.removeWidget(bar)
                bar.deleteLater()
                self.disk_labels.pop(idx)
                self.disk_bars.pop(idx)
        for p in partitions:
            if p.device not in [lbl.text().split(":")[0] for lbl in self.disk_labels]:
                lbl = QLabel(f"{p.device}")
                lbl.setFont(self.label_font)
                bar = QProgressBar()
                bar.setStyleSheet(self.dynamic_color(0))
                bar.setFormat("0%")
                self.grid.addWidget(lbl, self.disk_start_row + len(self.disk_labels), 0)
                self.grid.addWidget(bar, self.disk_start_row + len(self.disk_bars), 1)
                self.disk_labels.append(lbl)
                self.disk_bars.append(bar)
        for idx, p in enumerate(partitions):
            try:
                usage = psutil.disk_usage(p.mountpoint)
                percent = int(usage.percent)
                self.disk_bars[idx].setValue(percent)
                self.disk_bars[idx].setFormat(f"{percent}%")
                self.disk_labels[idx].setText(f"{p.device} : {usage.used//(1024**3)}Go / {usage.total//(1024**3)}Go")
                self.disk_bars[idx].setStyleSheet(self.dynamic_color(percent))
            except (PermissionError, FileNotFoundError):
                self.disk_labels[idx].setText(f"{p.device} : accès/refusé")
                self.disk_bars[idx].setValue(0)
        # Réseau
        net = psutil.net_io_counters()
        sent = (net.bytes_sent - self.last_net.bytes_sent)/1024
        recv = (net.bytes_recv - self.last_net.bytes_recv)/1024
        self.last_net = net
        self.net_label.setText(f"Réseau : ↑ {sent:.1f} KB/s | ↓ {recv:.1f} KB/s | Ping {self.ping_result}")

    def dynamic_color(self, value):
        if value < 50:
            color = "#00ccff"
        elif value < 75:
            color = "#ffff33"
        else:
            color = "#ff3333"
        return f"""
            QProgressBar {{
                border: 2px solid #555;
                border-radius: 5px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                width: 10px;
                margin: 1px;
            }}
        """

    def get_temps(self):
        cpu_temp = "N/A"
        gpu_temp = "N/A"
        try:
            temps = self.wmi_obj.MSAcpi_ThermalZoneTemperature()
            if temps:
                t_values = [(t.CurrentTemperature / 10.0) - 273.15 for t in temps]
                cpu_temp = f"{int(max(t_values))}°C"
        except:
            pass
        return cpu_temp, gpu_temp

    def update_ping(self):
        import time, re
        while True:
            try:
                output = subprocess.check_output(
                    ["ping", "-4", "-n", "1", "8.8.8.8"],
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                m = re.search(r"(\d+)ms", output)
                self.ping_result = m.group(1) + "ms" if m else "N/A"
            except:
                self.ping_result = "N/A"
            time.sleep(2)

# --------------------------
if __name__ == "__main__":
    # Vérifier mise à jour
    latest = check_update()
    if latest:
        exe = download_update()
        if exe:
            run_update(exe)

    app = QApplication(sys.argv)
    dash = Dashboard()
    dash.show()
    sys.exit(app.exec())
