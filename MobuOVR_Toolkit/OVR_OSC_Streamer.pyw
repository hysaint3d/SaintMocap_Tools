# -*- coding: utf-8 -*-
"""
OVR_OSC_Streamer.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Standalone SteamVR (OpenVR) Tracker Streamer.
Reads tracking device poses and streams them via OSC UDP to MotionBuilder.

Requirements:
  pip install openvr

由小聖腦絲與 Antigravity 協作完成
https://www.facebook.com/hysaint3d.mocap
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import sys
import os
import time
import math
import socket
import struct
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox

# ── OpenVR Check & Import ─────────────────────────────────────────────────────
OVR_AVAILABLE = False
try:
    import openvr
    OVR_AVAILABLE = True
except ImportError:
    pass

EFFECTORS = [
    "Hips",
    "Head",
    "Chest",
    "Left Hand",
    "Right Hand",
    "Left Foot",
    "Right Foot"
]

# ── Custom OSC Encoder ────────────────────────────────────────────────────────
def pack_osc_message(address, types, values):
    """Packs OSC message into binary format without external libraries."""
    addr_bytes = address.encode('utf-8')
    addr_padded = addr_bytes + b'\x00' * (4 - (len(addr_bytes) % 4))
    
    type_bytes = (',' + types).encode('utf-8')
    type_padded = type_bytes + b'\x00' * (4 - (len(type_bytes) % 4))
    
    args_bytes = b''
    for t, val in zip(types, values):
        if t == 'f':
            args_bytes += struct.pack('>f', float(val))
        elif t == 'i':
            args_bytes += struct.pack('>i', int(val))
        elif t == 's':
            s_bytes = val.encode('utf-8')
            args_bytes += s_bytes + b'\x00' * (4 - (len(s_bytes) % 4))
            
    return addr_padded + type_padded + args_bytes

def _mat34_to_pose(mat):
    """Extract (tx, ty, tz, rx, ry, rz) in cm/deg from OpenVR HmdMatrix34_t."""
    m = mat.m
    tx = m[0][3] * 100.0
    ty = m[1][3] * 100.0
    tz = m[2][3] * 100.0
    
    # Euler from rotation matrix (ZXY decomposition)
    sy = math.sqrt(m[0][0]**2 + m[1][0]**2)
    if sy > 1e-6:
        rx = math.degrees(math.atan2( m[2][1], m[2][2]))
        ry = math.degrees(math.atan2(-m[2][0], sy))
        rz = math.degrees(math.atan2( m[1][0], m[0][0]))
    else:
        rx = math.degrees(math.atan2(-m[1][2], m[1][1]))
        ry = math.degrees(math.atan2(-m[2][0], sy))
        rz = 0.0
    return tx, ty, tz, rx, ry, rz

def get_device_class_name(vr_system, device_index):
    """Returns the string name of the OpenVR tracked device class."""
    if not OVR_AVAILABLE or not vr_system:
        return "Unknown"
    try:
        cls = vr_system.getTrackedDeviceClass(device_index)
        if cls == openvr.TrackedDeviceClass_Invalid:
            return "Invalid"
        elif cls == openvr.TrackedDeviceClass_HMD:
            return "HMD"
        elif cls == openvr.TrackedDeviceClass_Controller:
            return "Controller"
        elif cls == openvr.TrackedDeviceClass_GenericTracker:
            return "Tracker"
        elif cls == openvr.TrackedDeviceClass_TrackingReference:
            return "BaseStation"
        elif cls == openvr.TrackedDeviceClass_DisplayRedirect:
            return "DisplayRedirect"
        else:
            return f"Unknown ({cls})"
    except Exception:
        return "Unknown"

# ── Streamer Application GUI ──────────────────────────────────────────────────
class OVRStreamerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Saint's OpenVR OSC Streamer")
        self.geometry("400x780")
        self.resizable(False, True)
        
        # State
        self.vr_system = None
        self.is_connected = False
        self.is_streaming = False
        self.streaming_thread = None
        
        # Config Variables
        self.ip_var = tk.StringVar(value="127.0.0.1")
        self.port_var = tk.StringVar(value="9007")
        self.fps_var = tk.StringVar(value="90")
        
        # Mapping Variables (Effector -> Combobox mapping)
        self.comboboxes = {}
        self.mapping_vars = {}
        for eff in EFFECTORS:
            self.mapping_vars[eff] = tk.StringVar(value="None")
            
        # Thread-safe Log Queue
        self.log_queue = queue.Queue()
        
        self.create_widgets()
        
        self.after(100, self.process_log_queue)
        
        self.log("Saint's OpenVR OSC Streamer started.")
        if OVR_AVAILABLE:
            self.log("OpenVR module loaded successfully.")
        else:
            self.log("Warning: OpenVR module is not installed.")
        
        # Check OpenVR installation
        if not OVR_AVAILABLE:
            messagebox.showerror(
                "Dependency Error", 
                "The 'openvr' Python module is not installed.\n\n"
                "Please open your Command Prompt and run:\n"
                "pip install openvr\n\n"
                "Then restart this application."
            )
            self.destroy()
            sys.exit()

    def log(self, message):
        """Thread-safe logging helper."""
        timestamp = time.strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}\n")

    def process_log_queue(self):
        """Reads logs from queue and updates Tkinter Text widget safely."""
        try:
            while True:
                msg = self.log_queue.get_nowait()
                if hasattr(self, 'log_txt') and self.log_txt.winfo_exists():
                    self.log_txt.config(state="normal")
                    self.log_txt.insert(tk.END, msg)
                    self.log_txt.see(tk.END)
                    
                    # Limit lines to 100
                    total_lines = int(self.log_txt.index('end-1c').split('.')[0])
                    if total_lines > 100:
                        self.log_txt.delete('1.0', f'{total_lines - 100}.0')
                        
                    self.log_txt.config(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self.process_log_queue)

    def create_widgets(self):
        style = ttk.Style()
        style.theme_use('vista')
        
        # Network Config Frame
        net_frame = ttk.LabelFrame(self, text=" Network Config ", padding=10)
        net_frame.pack(fill="x", padx=15, pady=10)
        
        ttk.Label(net_frame, text="Target IP:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(net_frame, textvariable=self.ip_var, width=15).grid(row=0, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Label(net_frame, text="Port:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(net_frame, textvariable=self.port_var, width=10).grid(row=1, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Label(net_frame, text="Target FPS:").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Entry(net_frame, textvariable=self.fps_var, width=8).grid(row=2, column=1, sticky="w", padx=5, pady=2)
        
        # SteamVR Connect Frame
        vr_frame = ttk.LabelFrame(self, text=" SteamVR Control ", padding=10)
        vr_frame.pack(fill="x", padx=15, pady=5)
        
        self.btn_connect = ttk.Button(vr_frame, text="Connect SteamVR", command=self.toggle_vr_connection)
        self.btn_connect.pack(fill="x", pady=5)
        
        self.lbl_status = ttk.Label(vr_frame, text="Status: Disconnected", foreground="red", font=("Consolas", 10, "bold"))
        self.lbl_status.pack(pady=2)
        
        # Control Buttons at bottom
        self.btn_stream = ttk.Button(self, text="Start Streaming", command=self.toggle_streaming, state="disabled")
        self.btn_stream.pack(side="bottom", fill="x", padx=15, pady=10)

        self.btn_refresh = ttk.Button(self, text="Refresh Tracked Devices", command=self.refresh_devices, state="disabled")
        self.btn_refresh.pack(side="bottom", fill="x", padx=15, pady=5)

        # Mapping Config Frame
        map_frame = ttk.LabelFrame(self, text=" Tracker Assignment Mapping ", padding=10)
        map_frame.pack(fill="both", expand=True, padx=15, pady=5)
        
        # Log Monitor Frame
        log_frame = ttk.LabelFrame(map_frame, text=" Log Monitor ", padding=5)
        log_frame.pack(side="bottom", fill="x", pady=5)
        
        self.log_txt = tk.Text(log_frame, height=5, wrap="word", state="disabled", font=("Consolas", 9))
        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_txt.yview)
        self.log_txt.configure(yscrollcommand=log_scrollbar.set)
        self.log_txt.pack(side="left", fill="both", expand=True)
        log_scrollbar.pack(side="right", fill="y")
        
        # Scrollable area in mapping frame
        canvas = tk.Canvas(map_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(map_frame, orient="vertical", command=canvas.yview)
        scroll_content = ttk.Frame(canvas)
        
        scroll_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Populate mapping rows
        for eff in EFFECTORS:
            row = ttk.Frame(scroll_content)
            row.pack(fill="x", pady=4, anchor="w")
            
            lbl = ttk.Label(row, text=eff + ":", width=12, anchor="w")
            lbl.pack(side="left")
            
            cb = ttk.Combobox(row, textvariable=self.mapping_vars[eff], width=25, state="readonly")
            cb['values'] = ("None",)
            cb.pack(side="left", padx=5)
            self.comboboxes[eff] = cb

    def toggle_vr_connection(self):
        if not self.is_connected:
            try:
                self.log("Connecting to SteamVR...")
                self.vr_system = openvr.init(openvr.VRApplication_Background)
                self.is_connected = True
                self.btn_connect.config(text="Disconnect SteamVR")
                self.lbl_status.config(text="Status: SteamVR Connected", foreground="green")
                self.btn_refresh.config(state="normal")
                self.btn_stream.config(state="normal")
                self.refresh_devices()
                self.log("SteamVR connection established.")
            except Exception as e:
                self.log(f"SteamVR connection failed: {e}")
                messagebox.showerror("Connection Error", f"Failed to connect to SteamVR:\n{e}\n\nMake sure SteamVR is running.")
        else:
            self.log("Disconnecting from SteamVR...")
            self.stop_streaming_if_running()
            openvr.shutdown()
            self.vr_system = None
            self.is_connected = False
            self.btn_connect.config(text="Connect SteamVR")
            self.lbl_status.config(text="Status: Disconnected", foreground="red")
            self.btn_refresh.config(state="disabled")
            self.btn_stream.config(state="disabled")
            self.clear_device_dropdowns()
            self.log("Disconnected from SteamVR.")

    def stop_streaming_if_running(self):
        if self.is_streaming:
            self.is_streaming = False
            if self.streaming_thread:
                self.streaming_thread.join(timeout=1.0)
            self.btn_stream.config(text="Start Streaming")

    def toggle_streaming(self):
        if not self.is_streaming:
            self.is_streaming = True
            self.btn_stream.config(text="Stop Streaming")
            # Disable dropdowns while streaming to prevent live mapping changes from glitching
            for cb in self.comboboxes.values():
                cb.config(state="disabled")
            
            target_ip = self.ip_var.get()
            target_port = self.port_var.get()
            fps = self.fps_var.get()
            self.log(f"Starting OSC stream to {target_ip}:{target_port} at {fps} FPS...")
            
            self.streaming_thread = threading.Thread(target=self.stream_loop, daemon=True)
            self.streaming_thread.start()
        else:
            self.is_streaming = False
            self.btn_stream.config(text="Start Streaming")
            for cb in self.comboboxes.values():
                cb.config(state="readonly")
            self.log("OSC Streaming stopped.")

    def get_active_devices(self):
        if not self.vr_system:
            return []
            
        devices = []
        poses = (openvr.TrackedDevicePose_t * openvr.k_unMaxTrackedDeviceCount)()
        self.vr_system.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseStanding, 0, poses)
        
        for i in range(openvr.k_unMaxTrackedDeviceCount):
            try:
                pose = poses[i]
                if pose.bPoseIsValid:
                    cls_name = get_device_class_name(self.vr_system, i)
                    try:
                        serial = self.vr_system.getStringTrackedDeviceProperty(i, openvr.Prop_SerialNumber_String)
                    except Exception:
                        serial = "UnknownSerial"
                    devices.append(f"OVR_Device_{i} ({cls_name} - {serial})")
            except Exception as e:
                print(f"[OVR OSC Streamer] Error querying device {i}: {e}")
        return devices

    def refresh_devices(self):
        self.log("Refreshing tracked devices...")
        devices = self.get_active_devices()
        self.log(f"Found {len(devices)} active device(s):")
        for dev in devices:
            self.log(f"  - {dev}")
            
        dropdown_options = ["None"] + devices
        
        for eff, cb in self.comboboxes.items():
            current_val = self.mapping_vars[eff].get()
            cb['values'] = dropdown_options
            
            # If previous selection is still valid, keep it; otherwise default to None
            if current_val in dropdown_options:
                self.mapping_vars[eff].set(current_val)
            else:
                self.mapping_vars[eff].set("None")

    def clear_device_dropdowns(self):
        for eff, cb in self.comboboxes.items():
            cb['values'] = ("None",)
            self.mapping_vars[eff].set("None")

    def stream_loop(self):
        # Establish Socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        target_ip = self.ip_var.get()
        try:
            target_port = int(self.port_var.get())
            fps = max(1, int(self.fps_var.get()))
        except:
            target_port = 9007
            fps = 90
            
        delay = 1.0 / fps
        flip = [1, 1, -1, 1, -1, -1] # Default flip
        
        poses = (openvr.TrackedDevicePose_t * openvr.k_unMaxTrackedDeviceCount)()
        
        last_log_time = time.time()
        
        while self.is_streaming and self.is_connected:
            loop_start = time.time()
            
            # Fetch poses
            self.vr_system.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseStanding, 0, poses)
            
            active_info = []
            
            # Map mappings
            for eff in EFFECTORS:
                mapping_str = self.mapping_vars[eff].get()
                if mapping_str == "None" or not mapping_str.startswith("OVR_Device_"):
                    continue
                    
                # Extract device index
                try:
                    idx = int(mapping_str.split(" ")[0].replace("OVR_Device_", ""))
                except:
                    continue
                    
                pose = poses[idx]
                if pose.bPoseIsValid:
                    rtx, rty, rtz, rrx, rry, rrz = _mat34_to_pose(pose.mDeviceToAbsoluteTracking)
                    # Apply axes flip
                    tx = rtx * flip[0]
                    ty = rty * flip[1]
                    tz = rtz * flip[2]
                    rx = rrx * flip[3]
                    ry = rry * flip[4]
                    rz = rrz * flip[5]
                    
                    # Pack and send OSC message
                    # Address example: /ovr/pose/LeftWrist (mapping Left Hand to LeftWrist)
                    osc_eff_name = eff.replace(" ", "")
                    # Special rename for Wrist and Ankle to match Control Rig naming conventions
                    if osc_eff_name == "LeftHand": osc_eff_name = "LeftWrist"
                    elif osc_eff_name == "RightHand": osc_eff_name = "RightWrist"
                    elif osc_eff_name == "LeftFoot": osc_eff_name = "LeftAnkle"
                    elif osc_eff_name == "RightFoot": osc_eff_name = "RightAnkle"
                    
                    address = f"/ovr/pose/{osc_eff_name}"
                    packet = pack_osc_message(address, "ffffff", [tx, ty, tz, rx, ry, rz])
                    sock.sendto(packet, (target_ip, target_port))
                    
                    # Store tracker summary for periodic log
                    active_info.append(f"{osc_eff_name}: ({tx:.1f}, {ty:.1f}, {tz:.1f})")
                    
                    # Read and stream controller buttons & analog axes for digital puppetry
                    res, cstate = self.vr_system.getControllerState(idx)
                    if res:
                        # Axis 0: Joystick/Trackpad X and Y
                        # Axis 1: Trigger (typically index finger, 0.0 to 1.0)
                        # Axis 2: Grip (typically middle/fist, 0.0 to 1.0)
                        joy_x = cstate.rAxis[0].x
                        joy_y = cstate.rAxis[0].y
                        trigger = cstate.rAxis[1].x
                        grip = cstate.rAxis[2].x
                        buttons = cstate.ulButtonPressed
                        
                        ctrl_address = f"/ovr/controller/{osc_eff_name}"
                        ctrl_packet = pack_osc_message(ctrl_address, "ffffi", [trigger, grip, joy_x, joy_y, buttons])
                        sock.sendto(ctrl_packet, (target_ip, target_port))
                        
            # Periodic logging
            current_time = time.time()
            if current_time - last_log_time >= 1.0:
                if active_info:
                    summary = f"Streaming {len(active_info)} effectors. Examples: " + ", ".join(active_info[:2])
                    if len(active_info) > 2:
                        summary += f" (+{len(active_info) - 2} more)"
                    self.log(summary)
                else:
                    self.log("Streaming: No valid mapped trackers active.")
                last_log_time = current_time
                
            # Dynamic throttle
            elapsed = time.time() - loop_start
            sleep_time = max(0.001, delay - elapsed)
            time.sleep(sleep_time)
            
        sock.close()

if __name__ == "__main__":
    app = OVRStreamerApp()
    app.mainloop()
