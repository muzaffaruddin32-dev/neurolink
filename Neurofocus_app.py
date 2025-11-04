
# neurofocus_app.py — web-compatible version
import streamlit as st
import pandas as pd
import numpy as np
import time
from collections import deque
import random

# ===============================
# CONFIGURATION
# ===============================
SAMPLE_INTERVAL = 0.5  # seconds
SMOOTH_WINDOW = 8      # samples (~2 sec)
THRESH_HIGH = 70
THRESH_MED = 40

# ===============================
# HELPER FUNCTIONS
# ===============================
def generate_demo_data():
    """Generate realistic demo data for attention/stress monitoring"""
    # Create a more realistic pattern with occasional spikes
    base_value = random.gauss(60, 5)
    
    # Add some time-based variation
    time_factor = time.time() % 30  # 30-second cycle
    if time_factor < 10:
        # First 10 seconds: relatively stable
        variation = random.gauss(0, 3)
    elif time_factor < 20:
        # Next 10 seconds: more variation
        variation = random.gauss(0, 8)
    else:
        # Last 10 seconds: occasional spikes
        if random.random() < 0.3:  # 30% chance of spike
            variation = random.gauss(0, 15)
        else:
            variation = random.gauss(0, 5)
    
    value = base_value + variation
    return int(max(0, min(100, value)))

# ===============================
# STREAMLIT UI
# ===============================
st.set_page_config(layout="wide", page_title="NeuroFocus")
st.title("🧠 NeuroFocus — Attention / Stress Monitor")

# Sidebar Settings
with st.sidebar:
    st.subheader("⚙️ Settings")
    sample_interval = st.number_input("Sample interval (s)", value=SAMPLE_INTERVAL, min_value=0.1, step=0.1)
    smooth_w = st.slider("Smoothing window (samples)", 1, 30, SMOOTH_WINDOW)
    th_high = st.slider("Green threshold (>=)", 50, 100, THRESH_HIGH)
    th_med = st.slider("Yellow threshold (< and >=)", 0, 99, THRESH_MED)
    st.write("Green ≥", th_high)
    st.write("Yellow ≥", th_med, "and <", th_high)
    st.write("Red <", th_med)
    
    st.subheader("ℹ️ About")
    st.info("This is a web-compatible demo version of NeuroFocus. It simulates attention/stress monitoring without requiring hardware.")

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

# Initialize buffers
if "values" not in st.session_state:
    st.session_state.values = deque(maxlen=400)
if "last_update" not in st.session_state:
    st.session_state.last_update = 0

# ===============================
# START BUTTON
# ===============================
if start:
    st.session_state.values.clear()
    st.session_state.running = True
    st.session_state.last_update = time.time()
    st.success("✅ Monitoring started")
    st.rerun()

# ===============================
# STOP BUTTON
# ===============================
if stop:
    st.session_state.running = False
    st.success("🛑 Monitoring stopped.")
    st.rerun()

# ===============================
# MONITORING LOOP (AUTO-REFRESH)
# ===============================
if st.session_state.running:
    current_time = time.time()
    
    # Check if enough time has passed since last update
    if current_time - st.session_state.last_update >= sample_interval:
        # Generate demo data
        val = generate_demo_data()
        st.session_state.values.append(val)
        st.session_state.last_update = current_time
        
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
        
        # Auto-refresh
        time.sleep(0.1)
        st.rerun()
    else:
        # If not enough time has passed, just wait a bit and rerun
        time.sleep(0.1)
        st.rerun()
else:
    # Display a message when not running
    if not st.session_state.values:
        chart_placeholder.info("Click 'Start Monitoring' to begin")
    else:
        # Keep showing the last data even when stopped
        data = pd.DataFrame({"value": list(st.session_state.values)})
        chart_placeholder.line_chart(data)
        
        if st.session_state.values:
            window = list(st.session_state.values)[-smooth_w:]
            smooth = int(np.mean(window)) if window else st.session_state.values[-1]
            metric_placeholder.metric("Last Value", smooth)
            
            # Determine stress level
            if smooth >= th_high:
                status_placeholder.success("🟢 Relaxed (Green)")
            elif smooth >= th_med:
                status_placeholder.warning("🟡 Mild (Yellow)")
            else:
                status_placeholder.error("🔴 High Stress (Red)")
