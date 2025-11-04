import streamlit as st
import pandas as pd
import numpy as np
import time
import threading
import serial
import serial.tools.list_ports
from collections import deque
import random

# ===============================
# CONFIGURATION
# ===============================
ARDUINO_BAUD = 115200
SAMPLE_INTERVAL = 0.25 # seconds
SMOOTH_WINDOW = 8 # samples (~2 sec)
THRESH_HIGH = 70
THRESH_MED = 40

# ===============================
# HELPER FUNCTIONS
# ===============================
def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if 'Arduino' in p.description or 'USB Serial' in p.description or 'CH340' in p.description:
            return p.device
    return None

# ===============================
# SERIAL COMMUNICATION CLASSES
# ===============================
class SerialReader(threading.Thread):
    def __init__(self, port, baud, out_list):
        super().__init__(daemon=True)
        self.port = port
        self.baud = baud
        self.out_list = out_list
        self._stop = False
        self.ser = None
        self.connect()

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            time.sleep(1)
        except Exception:
            self.ser = None

    def run(self):
        while not self._stop:
            if self.ser is None:
                self.connect()
                time.sleep(1)
                continue
            try:
                line = self.ser.readline().decode(errors='ignore').strip()
                if line.startswith("PULSE_RAW:"):
                    try:
                        raw = int(line.split(":")[1])
                        scaled = int(100.0 * (raw / 1023.0))
                        self.out_list.append(scaled)
                    except:
                        pass
            except Exception:
                try:
                    self.ser.close()
                except:
                    pass
                self.ser = None
        if self.ser:
            try:
                self.ser.close()
            except:
                pass

    def stop(self):
        self._stop = True

class ArduinoWriter:
    def __init__(self, port, baud):
        self.port = port
        self.baud = baud
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            time.sleep(1)
        except Exception:
            self.ser = None

    def send(self, cmd):
        if self.ser:
            try:
                self.ser.write((cmd + '\n').encode())
            except:
                try:
                    self.ser.close()
                except:
                    pass
                self.ser = None

# ===============================
# STREAMLIT UI
# ===============================
st.set_page_config(layout="wide", page_title="NeuroFocus")
st.title("🧠 NeuroFocus — Attention / Stress Monitor")

# Sidebar Settings
with st.sidebar:
    st.subheader("⚙️ Settings")
    demo_mode = st.checkbox("Use Demo Mode (no hardware)", value=True)
    sample_interval = st.number_input("Sample interval (s)", value=SAMPLE_INTERVAL, min_value=0.1, step=0.1)
    smooth_w = st.slider("Smoothing window (samples)", 1, 30, SMOOTH_WINDOW)
    th_high = st.slider("Green threshold (≥)", 50, 100, THRESH_HIGH)
    th_med = st.slider("Yellow threshold (< and ≥)", 0, 99, THRESH_MED)
    st.write("Green ≥", th_high)
    st.write("Yellow ≥", th_med, "and <", th_high)
    st.write("Red <", th_med)

# Main layout
col1, col2 = st.columns([3, 1])
with col1:
    chart_placeholder = st.empty()
    metric_placeholder = st.empty()
    status_placeholder = st.empty()
with col2:
    st.write("### Controls")
    if "running" not in st.session_state:
        st.session_state.running = False

    start = st.button("▶️ Start Monitoring", disabled=st.session_state.running)
    stop = st.button("⏹️ Stop Monitoring", disabled=not st.session_state.running)

    arduino_port_input = st.text_input("Arduino port (leave blank to auto-find)")
    detected_port = arduino_port_input or find_arduino_port()
    st.write("Detected port:", detected_port or "None")

# Initialize buffers
if "values" not in st.session_state:
    st.session_state.values = deque(maxlen=400)
if "serial_queue" not in st.session_state:
    st.session_state.serial_queue = []
if "reader" not in st.session_state:
    st.session_state.reader = None
if "writer" not in st.session_state:
    st.session_state.writer = None

# ===============================
# START BUTTON
# ===============================
if start:
    st.session_state.values.clear()
    st.session_state.running = True

    # Setup hardware
    if not demo_mode:
        port = detected_port
        if not port:
            st.error("❌ No Arduino port found. Enable demo mode or specify manually.")
            st.session_state.running = False
        else:
            st.success(f"✅ Connected to {port}")
            reader = SerialReader(port, ARDUINO_BAUD, st.session_state.serial_queue)
            reader.start()
            st.session_state.reader = reader
            st.session_state.writer = ArduinoWriter(port, ARDUINO_BAUD)

    st.experimental_rerun()

# ===============================
# STOP BUTTON
# ===============================
if stop:
    st.session_state.running = False
    if st.session_state.reader:
        st.session_state.reader.stop()
        st.session_state.reader = None
    st.success("🛑 Monitoring stopped.")
    st.experimental_rerun()

# ===============================
# MONITORING LOOP
# ===============================
if st.session_state.running:
    # Simulate or read data
    if demo_mode:
        val = int(max(0, min(100, random.gauss(60, 8))))
    else:
        q = st.session_state.serial_queue
        if q:
            val = q.pop(0)
        else:
            val = int(max(0, min(100, random.gauss(60, 8))))

    st.session_state.values.append(val)

    # Smooth data
    window = list(st.session_state.values)[-smooth_w:]
    smooth = int(np.mean(window)) if window else val

    # Update visuals
    data = pd.DataFrame({"value": list(st.session_state.values)})
    chart_placeholder.line_chart(data)
    metric_placeholder.metric("Current Value", smooth)

    # Determine stress level
    if smooth >= th_high:
        level = 0
        status_placeholder.success("🟢 Relaxed (Green)")
    elif smooth >= th_med:
        level = 1
        status_placeholder.warning("🟡 Mild (Yellow)")
    else:
        level = 2
        status_placeholder.error("🔴 High Stress (Red)")

    # Send to Arduino
    if st.session_state.writer is not None:
        st.session_state.writer.send(f"SET:{level}")

    # Wait and rerun
    time.sleep(sample_interval)
    st.experimental_rerun()
