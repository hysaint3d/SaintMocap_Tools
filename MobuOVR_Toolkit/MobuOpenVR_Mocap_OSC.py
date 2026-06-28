# -*- coding: utf-8 -*-
"""
MobuOpenVR_Mocap_OSC.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Virtual Capture Receiver & Driver for MotionBuilder via OSC.
Listens to OVR_OSC_Streamer coordinates, initializes HIK skeletons,
and binds Control Rigs with dynamic T-Pose offsets.

由小聖腦絲與 Antigravity 協作完成
https://www.facebook.com/hysaint3d.mocap
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from pyfbsdk import *
from pyfbsdk_additions import *
import sys
import os
import socket
import struct
import math

# ── Bone tables (from MobuCharacter_Toolkit.py) ───────────────────────────────
BONE_POS = {
    "Hips":(0,96,0),"Spine":(0,104,0),"Chest":(0,116,0),"UpperChest":(0,126,0),
    "Neck":(0,140,0),"Head":(0,150,0),
    "LeftShoulder":(7,137,0),"LeftUpperArm":(18,137,0),"LeftLowerArm":(42,137,0),"LeftHand":(64,137,0),
    "RightShoulder":(-7,137,0),"RightUpperArm":(-18,137,0),"RightLowerArm":(-42,137,0),"RightHand":(-64,137,0),
    "LeftUpperLeg":(9,96,0),"LeftLowerLeg":(9,52,0),"LeftFoot":(9,8,0),"LeftToes":(9,0,8),
    "RightUpperLeg":(-9,96,0),"RightLowerLeg":(-9,52,0),"RightFoot":(-9,8,0),"RightToes":(-9,0,8),
}

HIERARCHY = {
    "Hips":None,"Spine":"Hips","Chest":"Spine","UpperChest":"Chest","Neck":"UpperChest","Head":"Neck",
    "LeftShoulder":"UpperChest","LeftUpperArm":"LeftShoulder","LeftLowerArm":"LeftUpperArm","LeftHand":"LeftLowerArm",
    "RightShoulder":"UpperChest","RightUpperArm":"RightShoulder","RightLowerArm":"RightUpperArm","RightHand":"RightLowerArm",
    "LeftUpperLeg":"Hips","LeftLowerLeg":"LeftUpperLeg","LeftFoot":"LeftLowerLeg","LeftToes":"LeftFoot",
    "RightUpperLeg":"Hips","RightLowerLeg":"RightUpperLeg","RightFoot":"RightLowerLeg","RightToes":"RightFoot",
}

HIK_LINK = {
    "Hips":"HipsLink","Spine":"SpineLink","Chest":"Spine1Link","UpperChest":"Spine2Link",
    "Neck":"NeckLink","Head":"HeadLink",
    "LeftShoulder":"LeftShoulderLink","LeftUpperArm":"LeftArmLink","LeftLowerArm":"LeftForeArmLink","LeftHand":"LeftHandLink",
    "RightShoulder":"RightShoulderLink","RightUpperArm":"RightArmLink","RightLowerArm":"RightForeArmLink","RightHand":"RightHandLink",
    "LeftUpperLeg":"LeftUpLegLink","LeftLowerLeg":"LeftLegLink","LeftFoot":"LeftFootLink","LeftToes":"LeftToeBaseLink",
    "RightUpperLeg":"RightUpLegLink","RightLowerLeg":"RightLegLink","RightFoot":"RightFootLink","RightToes":"RightToeBaseLink",
}

BONE_NAMES = {
    "Hips": "Hips",
    "Spine": "Spine",
    "Chest": "Spine1",
    "UpperChest": "Spine2",
    "Neck": "Neck",
    "Head": "Head",
    "LeftShoulder": "LeftShoulder",
    "LeftUpperArm": "LeftArm",
    "LeftLowerArm": "LeftForeArm",
    "LeftHand": "LeftHand",
    "RightShoulder": "RightShoulder",
    "RightUpperArm": "RightArm",
    "RightLowerArm": "RightForeArm",
    "RightHand": "RightHand",
    "LeftUpperLeg": "LeftUpLeg",
    "LeftLowerLeg": "LeftLeg",
    "LeftFoot": "LeftFoot",
    "LeftToes": "LeftToeBase",
    "RightUpperLeg": "RightUpLeg",
    "RightLowerLeg": "RightLeg",
    "RightFoot": "RightFoot",
    "RightToes": "RightToeBase",
}

EFFECTORS = [
    ("Hips", "Hips"),
    ("Head", "Head"),
    ("Chest", "Chest"),
    ("Left Hand", "LeftWrist"),
    ("Right Hand", "RightWrist"),
    ("Left Foot", "LeftAnkle"),
    ("Right Foot", "RightAnkle"),
]

# ── State ─────────────────────────────────────────────────────────────────────
if hasattr(sys, 'mobu_openvr_mocap_osc_idle_func') and sys.mobu_openvr_mocap_osc_idle_func:
    try: FBSystem().OnUIIdle.Remove(sys.mobu_openvr_mocap_osc_idle_func)
    except: pass
    
if hasattr(sys, 'mobu_openvr_mocap_osc_state') and sys.mobu_openvr_mocap_osc_state:
    _s = sys.mobu_openvr_mocap_osc_state.get('osc_socket')
    if _s:
        try: _s.close()
        except: pass

if not hasattr(sys, 'mobu_openvr_mocap_osc_state'):
    sys.mobu_openvr_mocap_osc_state = {
        'osc_socket': None,
        'osc_listening': False,
    }
g_state = sys.mobu_openvr_mocap_osc_state

if not hasattr(sys, 'mobu_openvr_mocap_osc_ver'): sys.mobu_openvr_mocap_osc_ver = 0
sys.mobu_openvr_mocap_osc_ver += 1
g_current_ver = sys.mobu_openvr_mocap_osc_ver

g_ui = {}

# ── Custom OSC Decoder ────────────────────────────────────────────────────────
def _osc_parse(data):
    """Parses binary OSC packets without external dependencies."""
    try:
        addr_end = data.find(b'\x00')
        if addr_end == -1: return None, []
        address = data[:addr_end].decode('utf-8')

        type_start = (addr_end + 4) & ~0x03
        if type_start >= len(data) or data[type_start] != ord(','):
            return address, []

        type_end = data.find(b'\x00', type_start)
        if type_end == -1: return address, []
        type_tags = data[type_start+1:type_end].decode('utf-8')

        arg_start = (type_end + 4) & ~0x03
        args = []
        offset = arg_start
        for tag in type_tags:
            if offset >= len(data): break
            if tag == 'f':
                args.append(struct.unpack('>f', data[offset:offset+4])[0]); offset += 4
            elif tag == 'i':
                args.append(struct.unpack('>i', data[offset:offset+4])[0]); offset += 4
            elif tag == 's':
                s_end = data.find(b'\x00', offset)
                if s_end == -1: break
                args.append(data[offset:s_end].decode('utf-8'))
                offset = (s_end + 4) & ~0x03
        return address, args
    except:
        return None, []

# ── Dynamic OSC Data Nulls ────────────────────────────────────────────────────
def find_model_by_name(name):
    if not name:
        return None
    for comp in FBSystem().Scene.Components:
        if isinstance(comp, FBModel):
            if comp.LongName == name or comp.Name == name:
                return comp
    return None

def find_osc_marker(marker_name):
    for comp in FBSystem().Scene.Components:
        if isinstance(comp, FBModel):
            if comp.LongName == marker_name or comp.Name == marker_name:
                return comp
    return None

def get_or_create_osc_marker(marker_name):
    existing = find_osc_marker(marker_name)
    if existing:
        return existing
        
    marker = FBModelMarker(marker_name)
    marker.Show = True
    marker.Size = 200.0
    look_prop = marker.PropertyList.Find('LookUI')
    if look_prop:
        look_prop.Data = 1  # Hard Cross
        
    # Set color based on effector name
    if "LeftHand" in marker_name or "LeftWrist" in marker_name:
        marker.Color = FBColor(0.0, 0.4, 1.0) # Sleek blue
    elif "RightHand" in marker_name or "RightWrist" in marker_name:
        marker.Color = FBColor(0.0, 1.0, 0.4) # Sleek green
        
    return marker

def set_or_create_user_prop(model, prop_name, value):
    prop = model.PropertyList.Find(prop_name)
    if not prop:
        prop = model.PropertyCreate(prop_name, FBPropertyType.kFBPT_double, 'Number', True, True, None)
        if prop:
            prop.SetAnimated(True)
    if prop:
        try: prop.Data = float(value)
        except: pass

# ── OSC Receiver Listener ─────────────────────────────────────────────────────
def poll_osc_packets():
    sock = g_state.get('osc_socket')
    if not sock: return
    
    ns = g_ui["edit_ns"].Text.strip()
    if ns and not ns.endswith(":"): ns += ":"
    
    # Process up to 200 packets per frame to avoid lag
    packets = 0
    while packets < 200:
        try:
            data, _ = sock.recvfrom(65536)
            address, args = _osc_parse(data)
            if not address:
                packets += 1
                continue
                
            if address.startswith("/ovr/pose/") and len(args) == 6:
                effector_name = address.replace("/ovr/pose/", "")
                
                # Add to received_effectors set
                if 'received_effectors' not in g_state:
                    g_state['received_effectors'] = set()
                g_state['received_effectors'].add(effector_name)
                
                marker_name = f"{ns}OVR_Data_{effector_name}"
                marker = find_osc_marker(marker_name)
                
                if marker:
                    tx, ty, tz, rx, ry, rz = args
                    marker.SetVector(FBVector3d(tx, ty, tz), FBModelTransformationType.kModelTranslation, True)
                    marker.SetVector(FBVector3d(rx, ry, rz), FBModelTransformationType.kModelRotation, True)
                
            elif address.startswith("/ovr/controller/") and len(args) == 5:
                effector_name = address.replace("/ovr/controller/", "")
                
                # Add to received_effectors set
                if 'received_effectors' not in g_state:
                    g_state['received_effectors'] = set()
                g_state['received_effectors'].add(effector_name)
                
                marker_name = f"{ns}OVR_Data_{effector_name}"
                marker = find_osc_marker(marker_name)
                
                if marker:
                    trigger, grip, joy_x, joy_y, buttons = args
                    set_or_create_user_prop(marker, "Ctrl_Trigger", trigger)
                    set_or_create_user_prop(marker, "Ctrl_Grip", grip)
                    set_or_create_user_prop(marker, "Ctrl_JoystickX", joy_x)
                    set_or_create_user_prop(marker, "Ctrl_JoystickY", joy_y)
                    set_or_create_user_prop(marker, "Ctrl_Buttons", buttons)
                
            packets += 1
        except BlockingIOError:
            break
        except socket.error as e:
            if e.errno == 10035: break # WSAEWOULDBLOCK
            break
        except:
            break

def do_create_tracker_markers():
    ns = g_ui["edit_ns"].Text.strip()
    if ns and not ns.endswith(":"): ns += ":"
    
    received = g_state.get('received_effectors', set())
    if not received:
        _update_status("No active OSC data received yet. Cannot create trackers.")
        return
        
    created_count = 0
    for _, name_id in EFFECTORS:
        if name_id in received:
            marker_name = f"{ns}OVR_Data_{name_id}"
            marker = get_or_create_osc_marker(marker_name)
            if marker:
                created_count += 1
    _update_status(f"Created {created_count} tracker markers.")

# ── Pairing and Scale Functions ───────────────────────────────────────────────
def get_tracker_pos(part_name):
    """Retrieves world position of the paired tracker for the given body part."""
    cb_t = g_ui.get(f'cb_tracker_{part_name}')
    if not cb_t or cb_t.ItemIndex < 0:
        return None
    tracker_name = cb_t.Items[cb_t.ItemIndex]
    if not tracker_name or tracker_name == "None":
        return None
    model = find_model_by_name(tracker_name)
    if not model:
        return None
    pos = FBVector3d()
    model.GetVector(pos, FBModelTransformationType.kModelTranslation, True)
    return pos

def populate_pairing_dropdowns():
    """Scans the scene for tracker markers and effectors, and updates dropdown items."""
    trackers = ["None"]
    effectors = ["None"]
    
    for comp in FBSystem().Scene.Components:
        if isinstance(comp, FBModel):
            name = comp.Name
            # Trackers (usually starting with OVR_Data_ or OVR_ or custom marker)
            if "OVR_Data_" in name or name.startswith("OVR_") or isinstance(comp, FBModelMarker):
                if name not in trackers:
                    trackers.append(name)
            
            # Effectors/Auxiliaries
            name_lower = name.lower()
            if "effector" in name_lower or "aux" in name_lower or "wrist" in name_lower or "ankle" in name_lower:
                if name not in effectors:
                    effectors.append(name)
                    
    for part, _ in EFFECTORS:
        cb_t = g_ui.get(f'cb_tracker_{part}')
        cb_e = g_ui.get(f'cb_effector_{part}')
        
        if cb_t:
            current = cb_t.Items[cb_t.ItemIndex] if cb_t.ItemIndex >= 0 else "None"
            cb_t.Items.removeAll()
            for t in trackers:
                cb_t.Items.append(t)
            if current in trackers:
                cb_t.ItemIndex = trackers.index(current)
            else:
                cb_t.ItemIndex = 0
                
        if cb_e:
            current = cb_e.Items[cb_e.ItemIndex] if cb_e.ItemIndex >= 0 else "None"
            cb_e.Items.removeAll()
            for e in effectors:
                cb_e.Items.append(e)
            if current in effectors:
                cb_e.ItemIndex = effectors.index(current)
            else:
                cb_e.ItemIndex = 0

def auto_map_pairings():
    """Automatically maps trackers and effectors based on name keywords."""
    populate_pairing_dropdowns()
    
    ns = g_ui["edit_ns"].Text.strip()
    if ns and not ns.endswith(":"): ns += ":"
    
    for part, suffix in EFFECTORS:
        cb_t = g_ui.get(f'cb_tracker_{part}')
        cb_e = g_ui.get(f'cb_effector_{part}')
        
        if cb_t:
            matched_idx = 0
            for idx, item in enumerate(cb_t.Items):
                if suffix.lower() in item.lower() or part.replace(" ", "").lower() in item.lower():
                    matched_idx = idx
                    break
            cb_t.ItemIndex = matched_idx
            
        if cb_e:
            matched_idx = 0
            for idx, item in enumerate(cb_e.Items):
                item_no_ns = item[len(ns):] if item.startswith(ns) else item
                if suffix.lower() in item_no_ns.lower() or part.replace(" ", "").lower() in item_no_ns.lower():
                    matched_idx = idx
                    break
            cb_e.ItemIndex = matched_idx

def do_bind_paired():
    """Binds all configured pairings using Relation Constraints and Offset Nulls."""
    ns = g_ui["edit_ns"].Text.strip()
    if ns and not ns.endswith(":"): ns += ":"
    
    do_unbind_all()
    
    con = get_or_create_mocap_relation_constraint()
    bound_count = 0
    
    for part, _ in EFFECTORS:
        cb_t = g_ui.get(f'cb_tracker_{part}')
        cb_e = g_ui.get(f'cb_effector_{part}')
        
        if not cb_t or not cb_e:
            continue
            
        src_name = cb_t.Items[cb_t.ItemIndex] if cb_t.ItemIndex >= 0 else "None"
        tgt_name = cb_e.Items[cb_e.ItemIndex] if cb_e.ItemIndex >= 0 else "None"
        
        if src_name == "None" or tgt_name == "None":
            continue
            
        src_model = find_model_by_name(src_name)
        tgt_model = find_model_by_name(tgt_name)
        
        if not src_model or not tgt_model:
            continue
            
        # Create offset null
        offset_name = f"Offset_{src_model.Name}_{tgt_model.Name}"
        offset_null = FBModelNull(offset_name)
        offset_null.Show = True
        offset_null.Size = 10.0
        
        # Position offset null
        t_vec = FBVector3d()
        r_vec = FBVector3d()
        tgt_model.GetVector(t_vec, FBModelTransformationType.kModelTranslation, True)
        tgt_model.GetVector(r_vec, FBModelTransformationType.kModelRotation, True)
        
        offset_null.SetVector(t_vec, FBModelTransformationType.kModelTranslation, True)
        offset_null.SetVector(r_vec, FBModelTransformationType.kModelRotation, True)
        
        # Parent to tracker
        offset_null.Parent = src_model
        FBSystem().Scene.Evaluate()
        
        src_box = con.SetAsSource(offset_null)
        trgt_box = con.ConstrainObject(tgt_model)
        
        src_box.UseGlobalTransforms = True
        trgt_box.UseGlobalTransforms = True
        
        box_y_offset = len(con.Boxes) * 60
        con.SetBoxPosition(src_box, 50, box_y_offset)
        con.SetBoxPosition(trgt_box, 400, box_y_offset)
        
        src_out = src_box.AnimationNodeOutGet()
        trgt_in = trgt_box.AnimationNodeInGet()
        
        def find_node(parent, name):
            if not parent: return None
            for n in parent.Nodes:
                if n.Name.lower() == name.lower(): return n
            return None
            
        connected = 0
        for node_name in ('Translation', 'Rotation'):
            src_n = find_node(src_out, node_name)
            trgt_n = find_node(trgt_in, node_name)
            if src_n and trgt_n:
                try:
                    FBConnect(src_n, trgt_n)
                    connected += 1
                except: pass
        
        if connected >= 2:
            bound_count += 1
            
    con.Active = True
    FBSystem().Scene.Evaluate()
    _update_status(f"Bound {bound_count} pairs successfully.")
    FBMessageBox("Binding Complete", f"Successfully bound {bound_count} pair(s)!", "OK")

# ── Character Skeleton & Control Rig Init ─────────────────────────────────────
def do_generate_skeleton():
    ns = g_ui["edit_ns"].Text.strip()
    if ns and not ns.endswith(":"): ns += ":"
    
    # Calculate scale factors dynamically from T-Pose trackers
    scale_leg = 1.0
    scale_spine = 1.0
    scale_l_arm = 1.0
    scale_r_arm = 1.0
    
    use_tpose_scale = g_ui.get("chk_tpose_scale") and g_ui["chk_tpose_scale"].State == 1
    
    if use_tpose_scale:
        pos_hips = get_tracker_pos("Hips")
        pos_head = get_tracker_pos("Head")
        pos_chest = get_tracker_pos("Chest")
        pos_lhand = get_tracker_pos("Left Hand")
        pos_rhand = get_tracker_pos("Right Hand")
        
        print("[OVR OSC] Calculating bone scale proportions from tracker T-pose...")
        
        if pos_hips:
            scale_leg = pos_hips[1] / 96.0
            print(f"  Hips Height Y: {pos_hips[1]:.2f}cm (Scale: {scale_leg:.3f})")
            
        if pos_head and pos_hips:
            scale_spine = (pos_head[1] - pos_hips[1]) / 54.0
            print(f"  Head to Hips Y delta: {pos_head[1] - pos_hips[1]:.2f}cm (Scale: {scale_spine:.3f})")
        else:
            scale_spine = scale_leg
            
        ref_x = 0.0
        if pos_chest:
            ref_x = pos_chest[0]
        elif pos_hips:
            ref_x = pos_hips[0]
            
        if pos_lhand:
            scale_l_arm = abs(pos_lhand[0] - ref_x) / 64.0
            print(f"  Left Hand X delta: {abs(pos_lhand[0] - ref_x):.2f}cm (Scale: {scale_l_arm:.3f})")
        else:
            scale_l_arm = scale_leg
            
        if pos_rhand:
            scale_r_arm = abs(pos_rhand[0] - ref_x) / 64.0
            print(f"  Right Hand X delta: {abs(pos_rhand[0] - ref_x):.2f}cm (Scale: {scale_r_arm:.3f})")
        else:
            scale_r_arm = scale_leg
            
        # Update height field
        estimated_height = 96.0 * scale_leg + 74.0 * scale_spine
        g_ui["edit_height"].Text = f"{estimated_height:.1f}"
        _update_status(f"Scaled from T-Pose: Leg={scale_leg:.2f}, Spine={scale_spine:.2f}")
    else:
        try: scale = float(g_ui["edit_height"].Text.strip()) / 170.0
        except: scale = 1.0
        scale_leg = scale
        scale_spine = scale
        scale_l_arm = scale
        scale_r_arm = scale
        print(f"[OVR OSC] Generating skeleton with uniform height scale: {scale:.3f}")

    char_name = ns + "OVR_Tracked_Character"
    
    # 1. 精確清理舊角色 (LongName 比對)
    for c in list(FBSystem().Scene.Characters):
        n = getattr(c, 'LongName', None) or c.Name
        if n == char_name:
            try: c.SetCharacterizeOn(False); c.FBDelete()
            except: pass

    # 精確清理舊骨架
    root_name   = ns + "Reference"
    all_expected = set([root_name] + [ns + BONE_NAMES[k] for k in BONE_NAMES])
    for comp in list(FBSystem().Scene.Components):
        try:
            if not isinstance(comp, FBModel): continue
            n = getattr(comp, 'LongName', None) or comp.Name
            if n in all_expected:
                comp.FBDelete()
        except: pass

    FBSystem().Scene.Evaluate()

    # 2. 建立 Reference 根節點
    root = FBModelSkeleton(root_name)
    root.LongName = root_name
    root.SetVector(FBVector3d(0, 0, 0), FBModelTransformationType.kModelTranslation, True)
    root.Show = True

    # 3. 建立骨骼並套用動態縮放
    models = {}
    for key, pos in BONE_POS.items():
        bone_name = ns + BONE_NAMES[key]
        m = FBModelSkeleton(bone_name)
        m.LongName = bone_name
        m.Show = True
        
        x, y, z = pos
        
        # Apply structured scaling based on body region
        if key == "Hips":
            y_val = y * scale_leg
            x_val = x
            z_val = z
        elif key in ["Spine", "Chest", "UpperChest", "Neck", "Head"]:
            y_val = 96.0 * scale_leg + (y - 96.0) * scale_spine
            x_val = x
            z_val = z
        elif "Left" in key and ("Shoulder" in key or "Arm" in key or "Hand" in key):
            y_val = 96.0 * scale_leg + (y - 96.0) * scale_spine
            x_val = x * scale_l_arm
            z_val = z
        elif "Right" in key and ("Shoulder" in key or "Arm" in key or "Hand" in key):
            y_val = 96.0 * scale_leg + (y - 96.0) * scale_spine
            x_val = x * scale_r_arm
            z_val = z
        elif "Left" in key and ("Leg" in key or "Foot" in key or "Toes" in key):
            y_val = y * scale_leg
            x_val = x * scale_leg
            z_val = z * scale_leg
        elif "Right" in key and ("Leg" in key or "Foot" in key or "Toes" in key):
            y_val = y * scale_leg
            x_val = x * scale_leg
            z_val = z * scale_leg
        else:
            y_val = y * scale_leg
            x_val = x * scale_leg
            z_val = z * scale_leg
            
        m.SetVector(FBVector3d(x_val, y_val, z_val),
                    FBModelTransformationType.kModelTranslation, True)
        models[key] = m

    # 4. 建立父子階層
    for key, parent_key in HIERARCHY.items():
        if key not in models: continue
        models[key].Parent = root if parent_key is None else models.get(parent_key, root)

    # 5. 旋轉歸零
    for m in models.values():
        m.SetVector(FBVector3d(0, 0, 0), FBModelTransformationType.kModelRotation, False)
    root.SetVector(FBVector3d(0, 0, 0), FBModelTransformationType.kModelRotation, False)

    FBSystem().Scene.Evaluate()

    # 6. 建立 HIK FBCharacter 並映射骨骼
    char = FBCharacter(char_name)
    char.SetCharacterizeOn(False)
    
    for key, prop_name in HIK_LINK.items():
        if key not in models: continue
        model = models[key]
        prop  = char.PropertyList.Find(prop_name)
        if prop:
            prop.removeAll()
            try:    prop.append(model)
            except: prop.insert(model)
        else:
            base = prop_name.replace("Link", "")
            for p in char.PropertyList:
                if p.Name.endswith("Link") and base in p.Name:
                    p.removeAll()
                    try:    p.append(model)
                    except: p.insert(model)
                    break

    # Spine fallback
    if "Spine" not in models and "Chest" in models:
        prop = char.PropertyList.Find("SpineLink")
        if prop:
            prop.removeAll()
            try:    prop.append(models["Chest"])
            except: prop.insert(models["Chest"])

    # 7. 映射根節點
    ref_prop = char.PropertyList.Find("ReferenceLink")
    if ref_prop is None:
        for p in char.PropertyList:
            if "Reference" in p.Name:
                ref_prop = p; break
    if ref_prop is not None:
        ref_prop.removeAll()
        try: ref_prop.append(root)
        except:
            try: ref_prop.insert(root)
            except: pass

    FBSystem().Scene.Evaluate()
    ok = char.SetCharacterizeOn(True)
    FBSystem().Scene.Evaluate()

    if ok:
        _update_status("Skeleton generated & characterized!")
    else:
        err = char.GetCharacterizeError()
        msg = f"Characterization failed:\n{err}"
        print(f"[OVR OSC Tool] {msg}")
        _update_status("Characterization failed! See console.")
        FBMessageBox("Characterization Error", msg, "OK")

# ── Dynamic Alignment & Constraints ───────────────────────────────────────────
def get_or_create_mocap_relation_constraint():
    ns = g_ui["edit_ns"].Text.strip()
    if ns and not ns.endswith(":"): ns += ":"
    
    constraint_name = f"{ns}OSC_Mocap_Bindings"
    
    # Check if it already exists
    for con in FBSystem().Scene.Constraints:
        if isinstance(con, FBConstraintRelation) and (con.Name == constraint_name or con.LongName == constraint_name):
            return con
            
    # Create new one
    con = FBConstraintRelation(constraint_name)
    con.Active = True
    return con

def clean_specific_binding(src_name, tgt_name):
    offset_name = f"Offset_{src_name}_{tgt_name}"
    
    # Delete offset null
    for comp in list(FBSystem().Scene.Components):
        if isinstance(comp, FBModel) and (comp.Name == offset_name or comp.Name.endswith(offset_name)):
            comp.FBDelete()
            
    # Find the consolidated Relation Constraint and delete specific boxes representing the source/target
    ns = g_ui["edit_ns"].Text.strip()
    if ns and not ns.endswith(":"): ns += ":"
    constraint_name = f"{ns}OSC_Mocap_Bindings"
    
    con = None
    for c in FBSystem().Scene.Constraints:
        if isinstance(c, FBConstraintRelation) and (c.Name == constraint_name or c.LongName == constraint_name):
            con = c
            break
            
    if con:
        # Loop backwards to safely remove boxes
        for i in range(len(con.Boxes) - 1, -1, -1):
            box = con.Boxes[i]
            if (box.Name == offset_name or box.Name == tgt_name or 
                box.Name.endswith(offset_name) or box.Name.endswith(tgt_name)):
                try:
                    box.FBDelete()
                except:
                    pass
            
    FBSystem().Scene.Evaluate()

def do_bind_selected():
    selected = FBModelList()
    FBGetSelectedModels(selected, None, True, True)
    if len(selected) != 2:
        FBMessageBox("Selection Error", "Please select exactly 2 objects:\n1. The Tracker (first)\n2. The Control Rig effector (second)", "OK")
        return
        
    src_model = selected[0]
    tgt_model = selected[1]
    
    clean_specific_binding(src_model.Name, tgt_model.Name)
    
    # Create offset null
    offset_name = f"Offset_{src_model.Name}_{tgt_model.Name}"
    offset_null = FBModelNull(offset_name)
    offset_null.Show = True
    offset_null.Size = 10.0
    
    # Position offset null
    t_vec = FBVector3d()
    r_vec = FBVector3d()
    tgt_model.GetVector(t_vec, FBModelTransformationType.kModelTranslation, True)
    tgt_model.GetVector(r_vec, FBModelTransformationType.kModelRotation, True)
    
    offset_null.SetVector(t_vec, FBModelTransformationType.kModelTranslation, True)
    offset_null.SetVector(r_vec, FBModelTransformationType.kModelRotation, True)
    
    # Parent offset null
    offset_null.Parent = src_model
    FBSystem().Scene.Evaluate()
    
    con = get_or_create_mocap_relation_constraint()
    
    src_box = con.SetAsSource(offset_null)
    trgt_box = con.ConstrainObject(tgt_model)
    
    src_box.UseGlobalTransforms = True
    trgt_box.UseGlobalTransforms = True
    
    box_y_offset = len(con.Boxes) * 60
    con.SetBoxPosition(src_box, 50, box_y_offset)
    con.SetBoxPosition(trgt_box, 400, box_y_offset)
    
    src_out = src_box.AnimationNodeOutGet()
    trgt_in = trgt_box.AnimationNodeInGet()
    
    def find_node(parent, name):
        if not parent: return None
        for n in parent.Nodes:
            if n.Name.lower() == name.lower(): return n
        return None
        
    connected = 0
    for node_name in ('Translation', 'Rotation'):
        src_n = find_node(src_out, node_name)
        trgt_n = find_node(trgt_in, node_name)
        if src_n and trgt_n:
            try:
                FBConnect(src_n, trgt_n)
                connected += 1
            except: pass
            
    con.Active = True
    FBSystem().Scene.Evaluate()
    
    if connected >= 2:
        _update_status(f"Bound '{src_model.Name}' to '{tgt_model.Name}' successfully.")
        FBMessageBox("Binding Complete", f"Successfully bound '{src_model.Name}' to '{tgt_model.Name}'!", "OK")
    else:
        _update_status(f"Failed to connect constraint channels.")

def do_unbind_all():
    ns = g_ui["edit_ns"].Text.strip()
    if ns and not ns.endswith(":"): ns += ":"
    constraint_name = f"{ns}OSC_Mocap_Bindings"
    
    constraint_count = 0
    offset_count = 0
    
    for con in list(FBSystem().Scene.Constraints):
        if (con.Name == constraint_name or con.LongName == constraint_name or 
            con.Name.endswith("OSC_Mocap_Bindings") or con.Name.startswith("Relation_")):
            con.Active = False
            con.FBDelete()
            constraint_count += 1
            
    for comp in list(FBSystem().Scene.Components):
        if isinstance(comp, FBModel) and (comp.Name.startswith("Offset_") or "Offset_" in comp.Name):
            comp.FBDelete()
            offset_count += 1
            
    FBSystem().Scene.Evaluate()
    _update_status(f"Cleaned {constraint_count} constraints and {offset_count} offsets.")

# ── OSC Connect & Listeners ───────────────────────────────────────────────────
def update_mocap_markers_list():
    if 'edit_markers_list' not in g_ui:
        return
        
    if not hasattr(update_mocap_markers_list, 'counter'):
        update_mocap_markers_list.counter = 0
    update_mocap_markers_list.counter += 1
    if update_mocap_markers_list.counter % 15 != 0:
        return
        
    ns = g_ui["edit_ns"].Text.strip()
    if ns and not ns.endswith(":"): ns += ":"
    
    markers_info = []
    for _, name_id in EFFECTORS:
        marker_name = f"{ns}OVR_Data_{name_id}"
        found = None
        for comp in FBSystem().Scene.Components:
            if isinstance(comp, FBModelMarker):
                if comp.LongName == marker_name or comp.Name == marker_name:
                    found = comp
                    break
        if found:
            t = FBVector3d()
            found.GetVector(t, FBModelTransformationType.kModelTranslation, True)
            markers_info.append(f"• {found.Name}:  Pos({t[0]:.1f}, {t[1]:.1f}, {t[2]:.1f})")
            
    if not markers_info:
        if g_state.get('osc_listening'):
            g_ui['edit_markers_list'].Text = "OSC Receiver active. Waiting for tracking data..."
        else:
            g_ui['edit_markers_list'].Text = "OSC Receiver disconnected."
    else:
        g_ui['edit_markers_list'].Text = "Active Tracking Markers in Scene:\n\n" + "\n".join(markers_info)

def OnUIIdle(c, e):
    if sys.mobu_openvr_mocap_osc_ver != g_current_ver:
        try: FBSystem().OnUIIdle.Remove(OnUIIdle)
        except: pass
        return
        
    poll_osc_packets()
    update_mocap_markers_list()

def _connect_osc():
    try:
        port = int(g_ui['edit_osc_port'].Text)
    except:
        port = 9007
        
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("0.0.0.0", port))
        s.setblocking(False)
        g_state['osc_socket'] = s
        g_state['osc_listening'] = True
        g_state['received_effectors'] = set()
        
        # Register idle loop
        FBSystem().OnUIIdle.Remove(OnUIIdle)
        FBSystem().OnUIIdle.Add(OnUIIdle)
        sys.mobu_openvr_mocap_osc_idle_func = OnUIIdle
        
        g_ui['btn_osc_connect'].Caption = 'Disconnect OSC Receiver'
        _update_status(f"OSC listening on port {port}...")
    except Exception as ex:
        FBMessageBox('OSC Bind Error', f'Cannot bind UDP port {port}:\n{ex}', 'OK')

def _disconnect_osc():
    s = g_state.get('osc_socket')
    if s:
        try: s.close()
        except: pass
    g_state['osc_socket'] = None
    g_state['osc_listening'] = False
    if 'received_effectors' in g_state:
        g_state['received_effectors'].clear()
    g_ui['btn_osc_connect'].Caption = 'Connect OSC Receiver'
    
    ns = g_ui["edit_ns"].Text.strip()
    if ns and not ns.endswith(":"): ns += ":"
    
    for _, effector_name in EFFECTORS:
        null_name = f"{ns}OVR_Data_{effector_name}"
        for comp in list(FBSystem().Scene.Components):
            if isinstance(comp, FBModel) and (comp.LongName == null_name or comp.Name == null_name):
                comp.FBDelete()
                
    _update_status("OSC Receiver Disconnected.")

def OnOSCConnectClick(c, e):
    if g_state['osc_listening']: _disconnect_osc()
    else: _connect_osc()

def _update_status(msg):
    if 'lbl_status' in g_ui:
        g_ui['lbl_status'].Caption = str(msg)
    if 'lbl_status_init' in g_ui:
        g_ui['lbl_status_init'].Caption = str(msg)

# ── UI Construction ───────────────────────────────────────────────────────────
def PopulateTool(tool):
    tool.StartSizeX = 480
    tool.StartSizeY = 825

    # Tabs
    x = FBAddRegionParam(0, FBAttachType.kFBAttachLeft,   "")
    y = FBAddRegionParam(0, FBAttachType.kFBAttachTop,    "")
    w = FBAddRegionParam(0, FBAttachType.kFBAttachRight,  "")
    h = FBAddRegionParam(25, FBAttachType.kFBAttachNone, "")
    tool.AddRegion("tabs", "tabs", x, y, w, h)
    
    x = FBAddRegionParam(0, FBAttachType.kFBAttachLeft,   "")
    y = FBAddRegionParam(0, FBAttachType.kFBAttachBottom, "tabs")
    w = FBAddRegionParam(0, FBAttachType.kFBAttachRight,  "")
    h = FBAddRegionParam(0, FBAttachType.kFBAttachBottom, "")
    tool.AddRegion("main","main", x, y, w, h)
    
    tabs = FBTabPanel()
    tabs.Items.append("Mocap Receiver")
    tabs.Items.append("Character Init & Calibrate")
    tool.SetControl("tabs", tabs)
    
    lay_mocap = FBVBoxLayout()
    lay_init = FBVBoxLayout()
    
    def on_tab_change(control, event):
        if control.ItemIndex == 0:
            tool.SetControl("main", lay_mocap)
        else:
            tool.SetControl("main", lay_init)
            populate_pairing_dropdowns()
            
    tabs.OnChange.Add(on_tab_change)
    tool.SetControl("main", lay_mocap)
 
    # ── TAB 1: MOCAP & CALIBRATION ───────────────────────────────────────────
    hdr1 = FBLabel(); hdr1.Caption = "=== OSC UDP MOVEMENT RECEIVER ==="
    hdr1.Justify = FBTextJustify.kFBTextJustifyCenter
    lay_mocap.Add(hdr1, 25)
    
    # Port configuration
    lyt_port = FBHBoxLayout()
    lbl_port = FBLabel(); lbl_port.Caption = "UDP Receive Port:"
    g_ui['edit_osc_port'] = FBEdit(); g_ui['edit_osc_port'].Text = "9007"
    lyt_port.Add(lbl_port, 110)
    lyt_port.Add(g_ui['edit_osc_port'], 170)
    lay_mocap.Add(lyt_port, 25)
    
    # Connect button
    g_ui['btn_osc_connect'] = FBButton()
    g_ui['btn_osc_connect'].Caption = 'Connect OSC Receiver'
    g_ui['btn_osc_connect'].OnClick.Add(OnOSCConnectClick)
    lay_mocap.Add(g_ui['btn_osc_connect'], 30)
    
    # Create Tracker Markers button
    g_ui['btn_create_trackers'] = FBButton()
    g_ui['btn_create_trackers'].Caption = 'Create Tracker Markers'
    g_ui['btn_create_trackers'].OnClick.Add(lambda c,e: do_create_tracker_markers())
    lay_mocap.Add(g_ui['btn_create_trackers'], 30)
    
    hdr_markers = FBLabel(); hdr_markers.Caption = "=== RECEIVED TRACKING MARKERS ==="
    hdr_markers.Justify = FBTextJustify.kFBTextJustifyCenter
    lay_mocap.Add(hdr_markers, 25)
    
    g_ui['edit_markers_list'] = FBEdit()
    g_ui['edit_markers_list'].ReadOnly = True
    g_ui['edit_markers_list'].MultiLine = True
    g_ui['edit_markers_list'].Text = "OSC Receiver disconnected."
    lay_mocap.Add(g_ui['edit_markers_list'], 180)
        
    # Status Label
    g_ui['lbl_status'] = FBLabel(); g_ui['lbl_status'].Caption = "Ready."
    lay_mocap.Add(g_ui['lbl_status'], 25)
 
    # ── TAB 2: CHARACTER INIT ─────────────────────────────────────────────────
    hdr_init = FBLabel(); hdr_init.Caption = "=== GENERATE HIK SKELETON ==="
    hdr_init.Justify = FBTextJustify.kFBTextJustifyCenter
    lay_init.Add(hdr_init, 25)
    
    lyt_ns = FBHBoxLayout()
    lbl_ns = FBLabel(); lbl_ns.Caption = "Namespace:"
    g_ui["edit_ns"] = FBEdit(); g_ui["edit_ns"].Text = "A"
    lyt_ns.Add(lbl_ns, 90)
    lyt_ns.Add(g_ui["edit_ns"], 170)
    lay_init.Add(lyt_ns, 30)
    
    lyt_h = FBHBoxLayout()
    lbl_h = FBLabel(); lbl_h.Caption = "Height (cm):"
    g_ui["edit_height"] = FBEdit(); g_ui["edit_height"].Text = "170"
    lyt_h.Add(lbl_h, 90)
    lyt_h.Add(g_ui["edit_height"], 170)
    lay_init.Add(lyt_h, 30)
    
    # Checkbox to trigger auto-scaling from physical T-Pose
    lyt_scale_opts = FBHBoxLayout()
    g_ui["chk_tpose_scale"] = FBButton()
    g_ui["chk_tpose_scale"].Style = FBButtonStyle.kFBCheckbox
    g_ui["chk_tpose_scale"].Caption = "Auto-Scale from T-Pose Trackers"
    g_ui["chk_tpose_scale"].State = 0
    lyt_scale_opts.Add(g_ui["chk_tpose_scale"], 260)
    lay_init.Add(lyt_scale_opts, 25)
    
    btn_gen = FBButton(); btn_gen.Caption = "1. Generate Character Skeleton"
    btn_gen.OnClick.Add(lambda c,e: do_generate_skeleton())
    lay_init.Add(btn_gen, 35)
    
    hdr_pairing = FBLabel(); hdr_pairing.Caption = "=== TRACKER & EFFECTOR PAIRINGS ==="
    hdr_pairing.Justify = FBTextJustify.kFBTextJustifyCenter
    lay_init.Add(hdr_pairing, 25)
    
    # Headers for pairing grid
    lyt_grid_hdr = FBHBoxLayout()
    lbl_hdr_part = FBLabel(); lbl_hdr_part.Caption = "Body Part"
    lbl_hdr_tracker = FBLabel(); lbl_hdr_tracker.Caption = "OSC Tracker Source"
    lbl_hdr_effector = FBLabel(); lbl_hdr_effector.Caption = "Target Effector/Aux"
    lyt_grid_hdr.Add(lbl_hdr_part, 110)
    lyt_grid_hdr.Add(lbl_hdr_tracker, 160)
    lyt_grid_hdr.Add(lbl_hdr_effector, 160)
    lay_init.Add(lyt_grid_hdr, 20)
    
    # Pairing selection rows
    for part, _ in EFFECTORS:
        lyt_row = FBHBoxLayout()
        
        lbl_part = FBLabel(); lbl_part.Caption = part + ":"
        cb_t = FBList(); cb_t.Style = FBListStyle.kFBDropDownList
        cb_t.Items.append("None")
        cb_t.ItemIndex = 0
        
        cb_e = FBList(); cb_e.Style = FBListStyle.kFBDropDownList
        cb_e.Items.append("None")
        cb_e.ItemIndex = 0
        
        g_ui[f'cb_tracker_{part}'] = cb_t
        g_ui[f'cb_effector_{part}'] = cb_e
        
        lyt_row.Add(lbl_part, 110)
        lyt_row.Add(cb_t, 160)
        lyt_row.Add(cb_e, 160)
        lay_init.Add(lyt_row, 25)
        
    # Utility Buttons for Pairing Management
    lyt_pair_btns = FBHBoxLayout()
    btn_refresh_pairings = FBButton(); btn_refresh_pairings.Caption = "Refresh Scene Lists"
    btn_refresh_pairings.OnClick.Add(lambda c,e: populate_pairing_dropdowns())
    
    btn_auto_pair = FBButton(); btn_auto_pair.Caption = "Auto-Map by Name"
    btn_auto_pair.OnClick.Add(lambda c,e: auto_map_pairings())
    
    lyt_pair_btns.Add(btn_refresh_pairings, 215)
    lyt_pair_btns.Add(btn_auto_pair, 215)
    lay_init.Add(lyt_pair_btns, 30)
    
    # Binding Controls
    lyt_bind_btns = FBHBoxLayout()
    btn_bind_paired = FBButton(); btn_bind_paired.Caption = "Bind Paired Trackers"
    btn_bind_paired.OnClick.Add(lambda c,e: do_bind_paired())
    
    btn_unbind = FBButton(); btn_unbind.Caption = "Unbind & Clean All"
    btn_unbind.OnClick.Add(lambda c,e: do_unbind_all())
    
    lyt_bind_btns.Add(btn_bind_paired, 215)
    lyt_bind_btns.Add(btn_unbind, 215)
    lay_init.Add(lyt_bind_btns, 35)
    
    g_ui['lbl_status_init'] = FBLabel(); g_ui['lbl_status_init'].Caption = "Ready."
    lay_init.Add(g_ui['lbl_status_init'], 25)
    
    # Help text
    help_box = FBEdit()
    help_box.ReadOnly = True
    help_box.MultiLine = True
    help_box.Text = (
        "使用指南 / Workflow:\n"
        "1. 在 [Mocap Receiver] 點擊 Connect 啟動接收，待數據傳入後點擊 [Create Tracker Markers]。\n"
        "2. 在下方列表選擇配對對象，或直接點擊 [Auto-Map by Name] 自動媒合定位器與效果器。\n"
        "3. 若要啟用自適應人體比例生成，請勾選 [Auto-Scale from T-Pose Trackers]，然後點擊 [1. Generate Character Skeleton] 生成骨架（會依 T-Pose 自動拉伸關節長度）。\n"
        "4. 點擊 [Bind Paired Trackers] 一鍵完成所有配對綁定，並套用 Offset。如需重設請按 [Unbind & Clean All]。"
    )
    lay_init.Add(help_box, 130)

def CreateTool():
    tool = FBCreateUniqueTool("Saint's OpenVR MoCap (OSC)")
    if tool:
        PopulateTool(tool)
        ShowTool(tool)
    else:
        print("[OVR OSC Tool] Error creating MobuOpenVR Mocap OSC Tool.")

CreateTool()
