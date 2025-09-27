import sys, time, threading, os
from datetime import datetime, timedelta
from PySide6.QtWidgets import (QApplication, QLabel, QPushButton, QVBoxLayout, 
                               QWidget, QSlider, QProgressBar, QFrame)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont
from pynput import keyboard, mouse
import screen_brightness_control as sbc
from plyer import notification
import cv2
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# ---------------- Data Logging ----------------
if not os.path.exists("data"):
    os.makedirs("data")

def log_activity(minutes):
    today = datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.join("data", f"{today}.txt")
    with open(file_path, "a") as f:
        f.write(f"{minutes}\n")

def get_weekly_data():
    today = datetime.now()
    weekly_data = {}
    for i in range(7):
        day = today - timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        file_path = os.path.join("data", f"{day_str}.txt")
        total_minutes = 0
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                total_minutes = sum([int(line.strip()) for line in f.readlines()])
        weekly_data[day_str] = total_minutes
    return weekly_data

def plot_weekly_graph():
    data = get_weekly_data()
    days = list(data.keys())[::-1]  # oldest first
    minutes = list(data.values())[::-1]
    plt.figure(figsize=(8,4))
    plt.bar(days, minutes, color='skyblue')
    plt.title("Weekly Screen Activity (minutes)")
    plt.ylabel("Minutes")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

# ---------------- Activity Monitor ----------------
class ActivityMonitor:
    def __init__(self):
        self.last_activity = time.time()
    
    def _on_input(self, *args):
        self.last_activity = time.time()
    
    def start(self):
        t1 = threading.Thread(target=self._keyboard_listener, daemon=True)
        t2 = threading.Thread(target=self._mouse_listener, daemon=True)
        t1.start()
        t2.start()
    
    def _keyboard_listener(self):
        with keyboard.Listener(on_press=self._on_input) as listener:
            listener.join()
    
    def _mouse_listener(self):
        with mouse.Listener(on_click=self._on_input) as listener:
            listener.join()
    
    def get_idle_time(self):
        return time.time() - self.last_activity

# ---------------- Notifications ----------------
def send_notification(message="Time for a 5-min break!"):
    notification.notify(title="EyeGuard Reminder 👀", message=message, timeout=5)

# ---------------- Brightness Utils ----------------
def get_brightness():
    try:
        return sbc.get_brightness(display=0)
    except:
        return None

# ---------------- Optional Eye Detection ----------------
class EyeHeuristic:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
    
    def check_eyes(self):
        ret, frame = self.cap.read()
        if not ret:
            return False
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        upper = gray[0:h//2, :]
        mean_intensity = upper.mean()
        return mean_intensity < 50

    def release(self):
        self.cap.release()

# ---------------- Main GUI ----------------
class EyeGuardApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EyeGuard - Eye Strain Monitor")
        self.resize(450, 450)
        self.setStyleSheet("background-color: #f0f4f8;")  # light background

        # ---------------- Fonts ----------------
        self.title_font = QFont("Arial", 14, QFont.Bold)
        self.label_font = QFont("Arial", 12)
        self.button_font = QFont("Arial", 11, QFont.Bold)

        # ---------------- Labels ----------------
        self.status_label = QLabel("Status: Idle")
        self.status_label.setFont(self.title_font)
        self.status_label.setStyleSheet("color: #2c3e50;")
        self.brightness_label = QLabel("Brightness: Checking...")
        self.brightness_label.setFont(self.label_font)
        self.break_label = QLabel("Next break in: 30:00")
        self.break_label.setFont(self.label_font)

        # ---------------- Buttons ----------------
        self.start_btn = QPushButton("Start Monitoring")
        self.start_btn.setFont(self.button_font)
        self.start_btn.setStyleSheet("background-color: #3498db; color: white; padding: 8px; border-radius: 5px;")
        self.start_btn.clicked.connect(self.start_monitoring)

        self.graph_btn = QPushButton("Show Weekly Activity")
        self.graph_btn.setFont(self.button_font)
        self.graph_btn.setStyleSheet("background-color: #e67e22; color: white; padding: 8px; border-radius: 5px;")
        self.graph_btn.clicked.connect(plot_weekly_graph)

        # ---------------- Slider ----------------
        self.slider_label = QLabel("Break interval: 30 min")
        self.slider_label.setFont(self.label_font)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(1)
        self.slider.setMaximum(120)
        self.slider.setValue(30)
        self.slider.valueChanged.connect(self.change_interval)
        self.slider.setStyleSheet("""
            QSlider::handle:horizontal { background: #3498db; border-radius: 7px; }
            QSlider::groove:horizontal { height: 8px; background: #bdc3c7; border-radius: 4px; }
        """)

        # ---------------- Progress Bar ----------------
        self.progress = QProgressBar()
        self.progress.setMaximum(self.slider.value() * 60)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #bdc3c7; border-radius: 8px; background: #ecf0f1;
            }
            QProgressBar::chunk {
                background-color: #2ecc71; border-radius: 8px;
            }
        """)

        # ---------------- Embedded Chart ----------------
        self.figure = Figure(figsize=(4,2))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("Today's Activity (minutes)")
        self.ax.set_ylabel("Minutes")
        self.ax.set_ylim(0, 60)
        self.ax.set_xticks(range(24))
        self.ax.set_xticklabels([f"{i}h" for i in range(24)])
        self.bar_container = self.ax.bar(range(24), [0]*24, color='skyblue')

        # ---------------- Layout ----------------
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)

        # Status Frame
        frame_status = QFrame()
        frame_status.setStyleSheet("background-color: #dff9fb; border-radius: 8px; padding: 10px;")
        frame_layout = QVBoxLayout()
        frame_layout.addWidget(self.status_label)
        frame_layout.addWidget(self.brightness_label)
        frame_layout.addWidget(self.break_label)
        frame_status.setLayout(frame_layout)

        main_layout.addWidget(frame_status)
        main_layout.addWidget(self.progress)
        main_layout.addWidget(self.start_btn)
        main_layout.addWidget(self.slider_label)
        main_layout.addWidget(self.slider)
        main_layout.addWidget(self.canvas)
        main_layout.addWidget(self.graph_btn)
        main_layout.addStretch()
        self.setLayout(main_layout)

        # ---------------- Activity Monitor ----------------
        self.monitor = ActivityMonitor()
        self.monitor.start()

        # ---------------- Timer ----------------
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_gui)

        # Timer variables
        self.break_interval_minutes = 30
        self.remaining_seconds = self.break_interval_minutes * 60
        self.elapsed_seconds_for_log = 0

        # Optional eye heuristic
        self.eye_check = EyeHeuristic()

    def start_monitoring(self):
        self.timer.start(1000)  # update every second
        self.status_label.setText("Status: Monitoring Started")
        self.start_btn.setEnabled(False)

    def change_interval(self):
        self.break_interval_minutes = self.slider.value()
        self.slider_label.setText(f"Break interval: {self.break_interval_minutes} min")
        self.remaining_seconds = self.break_interval_minutes * 60
        self.progress.setMaximum(self.remaining_seconds)
        self.progress.setValue(0)

    def update_chart(self):
        today = datetime.now().strftime("%Y-%m-%d")
        file_path = os.path.join("data", f"{today}.txt")
        hourly_data = [0]*24
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                lines = [int(x.strip()) for x in f.readlines()]
                for i, val in enumerate(lines):
                    hour = i % 24
                    hourly_data[hour] += val

        colors = ['#2ecc71' if h>0 else '#bdc3c7' for h in hourly_data]
        for rect, h, c in zip(self.bar_container, hourly_data, colors):
            rect.set_height(h)
            rect.set_color(c)
        self.canvas.draw()

    def update_gui(self):
        # Update brightness
        brightness = get_brightness()
        if brightness:
            self.brightness_label.setText(f"Brightness: {brightness[0]}%")

        # Update countdown
        mins = self.remaining_seconds // 60
        secs = self.remaining_seconds % 60
        self.break_label.setText(f"Next break in: {mins:02d}:{secs:02d}")

        # Update progress bar
        self.progress.setValue(self.break_interval_minutes*60 - self.remaining_seconds)
        self.remaining_seconds -= 1

        # Log activity per minute
        self.elapsed_seconds_for_log += 1
        if self.elapsed_seconds_for_log >= 60:
            idle_time = self.monitor.get_idle_time()
            if idle_time < 60:
                log_activity(1)
            self.elapsed_seconds_for_log = 0

        # Check break notification
        idle_time = self.monitor.get_idle_time()
        if self.remaining_seconds <= 0 and idle_time < self.break_interval_minutes*60:
            eyes_closed = self.eye_check.check_eyes()
            if eyes_closed:
                send_notification("Take a break! Your eyes may be strained 👀")
            else:
                send_notification("Take a short break 👀")
            self.remaining_seconds = self.break_interval_minutes * 60
            self.progress.setMaximum(self.remaining_seconds)
            self.progress.setValue(0)

        # Update embedded chart
        self.update_chart()

    def closeEvent(self, event):
        self.eye_check.release()
        event.accept()

# ---------------- Run App ----------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EyeGuardApp()
    window.show()
    sys.exit(app.exec())
