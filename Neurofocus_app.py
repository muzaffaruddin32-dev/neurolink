# neurofocus_app.py
import streamlit as st
import pandas as pd
import numpy as np
import time
import threading
import serial
import serial.tools.list_ports
from collections import deque
import random

# CONFIG
ARDUINO_BAUD = 115200
SAMPLE_INTERVAL = 0.25 # seconds
SMOOTH_WINDOW = 8 # samples (about 2 seconds at 4Hz)
THRESH_HIGH = 70 # above => green (relaxed)
THRESH_MED = 40 # between med & high => yellow
# below THRESH_MED => red (high stress)

# Helpers
def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if 'Arduino' in p.description or 'USB Serial' in p.description or 'CH340' in p.description:
            return p.device
    return None

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
        except Exception as e:
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
                        # scale 0-1023 to 0-100
                        scaled = int(100.0 * (raw / 1023.0))
                        self.out_list.append(scaled)
                    except:
                        pass
            except Exception as e:
                # attempt reconnect
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
        except Exception as e:
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

# Streamlit UI
st.set_page_config(layout="wide", page_title="NeuroFocus")
st.title("NeuroFocus — Attention / Stress Monitor")

# sidebar controls
with st.sidebar:
    st.subheader("Settings")
    demo_mode = st.checkbox("Use Demo Mode (no hardware)", value=True)
    sample_interval = st.number_input("Sample interval (s)", value=SAMPLE_INTERVAL, min_value=0.1, step=0.1)
    smooth_w = st.slider("Smoothing window (samples)", 1, 30, SMOOTH_WINDOW)
    th_high = st.slider("Green threshold (>=)", 50, 100, THRESH_HIGH)
    th_med = st.slider("Yellow threshold (< and >=)", 0, 99, THRESH_MED)
    st.write("Green >= ", th_high)
    st.write("Yellow >= ", th_med, " and < ", th_high)
    st.write("Red < ", th_med)

# main
col1, col2 = st.columns([3,1])
with col1:
    chart = st.line_chart(pd.DataFrame({'value':[0]}))
    cur_metric = st.metric("Current value", 0)
with col2:
    st.write("Controls")
    start = st.button("Start Monitoring")
    stop_btn = st.button("Stop Monitoring")
    arduino_port_input = st.text_input("Arduino port (leave blank to auto-find)")
    st.write("Detected port:", arduino_port_input or find_arduino_port())

# data buffer
if 'values' not in st.session_state:
    st.session_state['values'] = deque(maxlen=400)
if 'reader' not in st.session_state:
    st.session_state['reader'] = None
if 'writer' not in st.session_state:
    st.session_state['writer'] = None

# start/stop logic
if start:
    st.session_state['values'].clear()
    # setup serial reader if not demo
    if not demo_mode:
        port = arduino_port_input.strip() or find_arduino_port()
        if not port:
            st.error("No Arduino port found. Use demo mode or enter port.")
        else:
            st.success(f"Starting serial reader on {port}")
            st.session_state['serial_queue'] = []
            reader = SerialReader(port, ARDUINO_BAUD, st.session_state['serial_queue'])
            reader.start()
            st.session_state['reader'] = reader
            st.session_state['writer'] = ArduinoWriter(port, ARDUINO_BAUD)
    # run monitoring loop
    stop_flag = False
    demo_gen = None
    if demo_mode:
        demo_gen = (int(max(0, min(100, random.gauss(60,8)))) for _ in range(1000000))
    try:
        while True:
            if stop_btn:
                break
            if demo_mode:
                val = next(demo_gen)
            else:
                q = st.session_state.get('serial_queue', [])
                if q:
                    val = q.pop(0)
                else:
                    # fallback to demo if no data
                    val = int(max(0, min(100, random.gauss(60,8))))

            st.session_state['values'].append(val)
            # smoothing
            window = list(st.session_state['values'])[-smooth_w:]
            smooth = int(np.mean(window)) if window else val
            chart.add_rows(pd.DataFrame({'value':[smooth]}))
            cur_metric.metric("Current value", smooth)

            # decide level using thresholds
            if smooth >= th_high:
                level = 0 # green
                st.success("Relaxed (Green)")
            elif smooth >= th_med:
                level = 1 # yellow
                st.warning("Mild (Yellow)")
            else:
                level = 2 # red
                st.error("High stress (Red)")

            # send to Arduino
            if st.session_state.get('writer') is not None:
                st.session_state['writer'].send(f"SET:{level}")

            time.sleep(sample_interval)
    except Exception as e:
        st.error(f"Stopped due to error: {e}")

# stop threads if stop pressed
if stop_btn and st.session_state.get('reader') is not None:
    st.session_state['reader'].stop()
    st.session_state['reader'] = None
    st.success("Stopped serial reader")
