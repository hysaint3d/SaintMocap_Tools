# -*- coding: utf-8 -*-
"""
MobuTwistBone_Calculator.py  ── v5 (Template Integration + Auto-Axis)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
新功能 (v5):
  1. 整合 JSON 骨架模板 (Templates/) — Skeleton 下拉選單動態載入，
     支援任何角色規格 (UE, AccuRig, VRoid, ARP, MMD, Rigify...)。
  2. 智慧骨骼軸向自動偵測 (Auto Detect Axis) —
     透過分析驅動骨骼的子關節局部位置向量，自動判斷扭轉軸。
  3. 模糊配對演算法 — 自動從場景中匹配 Twist Bones，免除硬編碼。
  4. 保留舊版 TWIST_RULES 作為無模板環境的備援回退機制。

由小聖腦絲與 Antigravity 協作完成
https://www.facebook.com/hysaint3d.mocap
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from pyfbsdk import *
from pyfbsdk_additions import *
import os
import json

g_ui = {}
g_template_map = {}   # display_name -> filename
g_template_path = {}  # display_name -> full path

# ── Fallback legacy rules (hardcoded) ────────────────────────────────────────
# Used when no template files are found or user selects a legacy preset.
# Format: (driver_keyword, [twist_keywords_ALL_must_match])
TWIST_RULES = {
    "UE_HAND": [
        ("hand_l",     ["lowerarm", "twist", "_l"]),
        ("hand_r",     ["lowerarm", "twist", "_r"]),
        ("lowerarm_l", ["upperarm", "twist", "_l"]),
        ("lowerarm_r", ["upperarm", "twist", "_r"]),
        ("calf_l",     ["thigh",    "twist", "_l"]),
        ("calf_r",     ["thigh",    "twist", "_r"]),
        ("foot_l",     ["calf",     "twist", "_l"]),
        ("foot_r",     ["calf",     "twist", "_r"]),
    ],
    "UE_FOREARM": [
        ("lowerarm_l", ["lowerarm", "twist", "_l"]),
        ("lowerarm_r", ["lowerarm", "twist", "_r"]),
        ("lowerarm_l", ["upperarm", "twist", "_l"]),
        ("lowerarm_r", ["upperarm", "twist", "_r"]),
        ("calf_l",     ["thigh",    "twist", "_l"]),
        ("calf_r",     ["thigh",    "twist", "_r"]),
        ("foot_l",     ["calf",     "twist", "_l"]),
        ("foot_r",     ["calf",     "twist", "_r"]),
    ],
    "AccuRig_HAND": [
        ("l_hand",     ["l_", "forearm",  "twist"]),
        ("r_hand",     [" r_", "forearm",  "twist"]),
        ("l_forearm",  ["l_", "upperarm", "twist"]),
        ("r_forearm",  ["r_", "upperarm", "twist"]),
        ("l_calf",     ["l_", "thigh",    "twist"]),
        ("r_calf",     ["r_", "thigh",    "twist"]),
        ("l_foot",     ["l_", "calf",     "twist"]),
        ("r_foot",     ["r_", "calf",     "twist"]),
    ],
    "AccuRig_FOREARM": [
        ("l_forearm",  ["l_", "forearm",  "twist"]),
        ("r_forearm",  ["r_", "forearm",  "twist"]),
        ("l_forearm",  ["l_", "upperarm", "twist"]),
        ("r_forearm",  ["r_", "upperarm", "twist"]),
        ("l_calf",     ["l_", "thigh",    "twist"]),
        ("r_calf",     ["r_", "thigh",    "twist"]),
        ("l_foot",     ["l_", "calf",     "twist"]),
        ("r_foot",     ["r_", "calf",     "twist"]),
    ],
}

# HIK slot -> (segment_label, side)  for template-driven twist search
# We only care about the 4 limb segments that have twist bones.
HIK_TWIST_SLOTS = {
    # Forearm twists: driven by HAND or FOREARM, target segment = lowerarm
    "LeftForeArmLink":  ("forearm",  "left"),
    "RightForeArmLink": ("forearm",  "right"),
    "LeftHandLink":     ("forearm",  "left"),   # Hand-mode driver
    "RightHandLink":    ("forearm",  "right"),
    # Upperarm twists: driven by FOREARM, target segment = upperarm
    "LeftArmLink":      ("upperarm", "left"),
    "RightArmLink":     ("upperarm", "right"),
    # Thigh twists: driven by CALF, target = thigh
    "LeftUpLegLink":    ("thigh",    "left"),
    "RightUpLegLink":   ("thigh",    "right"),
    "LeftLegLink":      ("thigh",    "left"),   # Calf-mode driver
    "RightLegLink":     ("thigh",    "right"),
    # Calf twists: driven by FOOT, target = calf
    "LeftLegLink2":     ("calf",     "left"),
    "RightLegLink2":    ("calf",     "right"),
    "LeftFootLink":     ("calf",     "left"),
    "RightFootLink":    ("calf",     "right"),
}

# Twist bone detection keywords
TWIST_KEYWORDS = ["twist", "tw", "roll"]

# ── Path helpers ──────────────────────────────────────────────────────────────
def get_script_dir():
    """ Robustly get the script directory, handling MoBu's __file__ issues. """
    try:
        import inspect
        script_path = inspect.getfile(inspect.currentframe())
        if os.path.isfile(script_path):
            return os.path.dirname(os.path.abspath(script_path))
    except Exception:
        pass
    if "__file__" in globals() and os.path.isfile(str(__file__)):
        return os.path.dirname(os.path.abspath(__file__))
    # Last-resort fallback to current working directory
    return os.getcwd()

def get_template_dir():
    base = get_script_dir()
    for cand in ["Templates", "templates", "Template", "template"]:
        p = os.path.join(base, cand)
        if os.path.isdir(p):
            return p
    return base

# ── UI helpers ────────────────────────────────────────────────────────────────
def status(msg):
    try:
        g_ui["lbl_status"].Caption = msg
    except:
        pass

def make_spacer():
    lbl = FBLabel()
    lbl.Caption = ""
    return lbl

def hdr(text):
    lbl = FBLabel()
    lbl.Caption = "-- {} --".format(text)
    lbl.Justify = FBTextJustify.kFBTextJustifyCenter
    return lbl

def show_welcome():
    msg = ("Saint's Twistbone_tool  v5\n"
           "由小聖腦絲與 Antigravity 協作完成\n"
           "https://www.facebook.com/hysaint3d.mocap")
    FBMessageBox("Welcome", msg, "OK")

# ── Character / Namespace helpers ─────────────────────────────────────────────
def get_character_ns(char):
    if not char:
        return None
    valid_ids = []
    for name in ["kFBHipsNodeId", "kFBReferenceNodeId", "kFBHeadNodeId",
                 "kFBLeftHandNodeId", "kFBRightHandNodeId", "kFBPelvisId"]:
        if hasattr(FBBodyNodeId, name):
            valid_ids.append(getattr(FBBodyNodeId, name))
    for node_id in valid_ids:
        try:
            model = char.GetCharacterModel(node_id)
            if model:
                long_name = model.LongName
                if ":" in long_name:
                    return long_name.rsplit(":", 1)[0] + ":"
        except:
            pass
    return ""

def check_active_character():
    char = FBApplication().CurrentCharacter
    if not char:
        FBMessageBox("No Active Character",
                     "Please select an active HIK Character in the Character Controls first.", "OK")
        status("Error: No active character.")
        return None
    return char

def get_ns():
    raw = g_ui["edit_ns"].Text.strip()
    if raw and not raw.endswith(":"):
        raw += ":"
    return raw

# ── Template loading ──────────────────────────────────────────────────────────
LEGACY_ITEMS = [
    "[ Legacy ] Unreal Engine (UE4/UE5)",
    "[ Legacy ] AccuRig / CC4",
]

def refresh_templates():
    """
    Scan Templates/ directory and populate Skeleton dropdown.
    Template entries appear first (sorted), followed by legacy presets.
    """
    global g_template_map, g_template_path
    g_template_map = {}
    g_template_path = {}
    lst = g_ui.get("list_type")
    if lst is None:
        return
    lst.Items.removeAll()

    t_dir = get_template_dir()
    found = []
    if os.path.isdir(t_dir):
        for f in sorted(os.listdir(t_dir)):
            if not f.endswith(".json"):
                continue
            full = os.path.join(t_dir, f)
            d_name = f.replace(".json", "")
            try:
                with open(full, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
                    if "DisplayName" in data:
                        d_name = data["DisplayName"]
            except:
                pass
            found.append((d_name, f, full))

    for d_name, f, full in found:
        g_template_map[d_name] = f
        g_template_path[d_name] = full
        lst.Items.append(d_name)

    # Append legacy fallback presets
    for leg in LEGACY_ITEMS:
        lst.Items.append(leg)

    if lst.Items:
        lst.ItemIndex = 0

# ── Auto-detect bone axis ─────────────────────────────────────────────────────
def detect_bone_axis(bone):
    """
    Detect the primary roll/twist axis of a bone by examining the
    local translation of its first non-twist child.
    Returns "X", "Y", or "Z".  Falls back to "X" if detection fails.
    """
    if bone is None:
        return "X"
    try:
        children = bone.Children
        child = None
        for i in range(len(children)):
            c = children[i]
            if c is None:
                continue
            n = c.Name.lower()
            if any(kw in n for kw in TWIST_KEYWORDS):
                continue   # skip twist branches
            child = c
            break

        if child is None:
            return "X"

        trans = FBVector3d()
        child.GetVector(trans, FBModelTransformationType.kModelTranslation, False)
        ax, ay, az = abs(trans[0]), abs(trans[1]), abs(trans[2])
        if ay >= ax and ay >= az:
            return "Y"
        if az >= ax and az >= ay:
            return "Z"
        return "X"
    except Exception as e:
        print("[AutoAxis] detect_bone_axis error: {}".format(e))
        return "X"

def get_axis(driver_bone=None):
    """
    Return axis string "X"/"Y"/"Z" based on UI selection.
    If the user picked "Auto" (index 0), detect from the given driver_bone.
    """
    axes = ["X", "Y", "Z"]
    idx = g_ui["list_axis"].ItemIndex
    if idx == 0:  # Auto
        return detect_bone_axis(driver_bone) if driver_bone else "X"
    return axes[idx - 1] if 1 <= idx <= 3 else "X"

def get_base_weight():
    try:
        v = float(g_ui["edit_weight"].Text.strip())
        return max(0.01, min(1.0, v))
    except:
        return 0.5

# ── Skeleton scanning ─────────────────────────────────────────────────────────
def scan_skeletons():
    result = []
    for comp in FBSystem().Scene.Components:
        try:
            if isinstance(comp, FBModelSkeleton):
                result.append(comp)
        except:
            pass
    return result

def find_driver(skeletons, keyword, ns):
    kw = keyword.lower()
    for bone in skeletons:
        try:
            long_name = bone.LongName
            if ns and not long_name.lower().startswith(ns.lower()):
                continue
            short = bone.Name.lower()
            if kw in short and not any(tk in short for tk in TWIST_KEYWORDS):
                return bone
        except:
            pass
    return None

def find_twists(skeletons, driver, keywords, ns):
    result = []
    for bone in skeletons:
        try:
            if bone == driver:
                continue
            long_name = bone.LongName
            if ns and not long_name.lower().startswith(ns.lower()):
                continue
            short = bone.Name.lower()
            if all(kw in short for kw in keywords):
                result.append(bone)
        except:
            pass
    result.sort(key=lambda b: b.Name)
    return result

# ── Template-driven fuzzy pair resolver ───────────────────────────────────────
def _norm(s):
    """Normalize bone name for comparison: lowercase, collapse separators."""
    return s.lower().replace("_", "").replace("-", "").replace(".", "").replace(" ", "")

def _side_marker(bone_name):
    """
    Detect the side marker of a bone name and return a canonical tuple:
    (side, side_variants_list)
    side = "left" | "right" | None
    side_variants = list of lowercase strings that identify this side.
    """
    n = bone_name.lower()
    # Common left/right suffixes and prefixes
    left_hints  = ["_l", "_left", " l", ".l", "left_", "l_", " left", "lft"]
    right_hints = ["_r", "_right", " r", ".r", "right_", "r_", " right", "rgt"]
    for h in left_hints:
        if h in n:
            return "left", left_hints
    for h in right_hints:
        if h in n:
            return "right", right_hints
    return None, []

def find_twist_bones_for_segment(skeletons, driver_bone, segment_keywords, ns):
    """
    Fuzzy-search for twist bones in the scene that:
      1. Belong to the correct namespace (ns).
      2. Contain at least one twist keyword.
      3. Contain at least one segment keyword (from segment_keywords list).
      4. Are on the same side as driver_bone.
    Returns list sorted by name.
    """
    driver_side, _ = _side_marker(driver_bone.Name)
    result = []
    for bone in skeletons:
        try:
            if bone == driver_bone:
                continue
            long_name = bone.LongName
            if ns and not long_name.lower().startswith(ns.lower()):
                continue
            n = bone.Name.lower()
            # Must contain a twist keyword
            if not any(tk in n for tk in TWIST_KEYWORDS):
                continue
            # Must contain at least one segment keyword
            if not any(sk in n for sk in segment_keywords):
                continue
            # Must match driver side
            bone_side, _ = _side_marker(bone.Name)
            if driver_side and bone_side and bone_side != driver_side:
                continue
            result.append(bone)
        except:
            pass
    result.sort(key=lambda b: b.Name)
    return result


def get_twist_pairs_from_template(template_path, skeletons, hand_mode, ns):
    """
    Load a JSON template and resolve (driver_bone, [twist_bones], segment_label) tuples.

    Template-driven logic:
    - For forearm twists:
        hand_mode=True  → driver = Hand bone (LeftHandLink / RightHandLink)
        hand_mode=False → driver = ForeArm bone (LeftForeArmLink / RightForeArmLink)
      Target segment keywords: names containing any part of the ForeArm bone name
      (minus side marker) + "twist" / "tw" / "roll".
    - For upperarm twists:
        driver = ForeArm bone
        Target segment: UpperArm.
    - For thigh twists:
        driver = Calf bone (LeftLegLink / RightLegLink)
        Target segment: Thigh.
    - For calf twists:
        driver = Foot bone (LeftFootLink / RightFootLink)
        Target segment: Calf.

    Returns list of (driver_bone, twist_bones_list, segment_label).
    """
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            bmap = json.load(f)
    except Exception as e:
        print("[TwistTemplate] Failed to load '{}': {}".format(template_path, e))
        return []

    def get_bone_name(slot):
        val = bmap.get(slot)
        if val is None:
            return None
        if isinstance(val, dict):
            return val.get("Name", None)
        return str(val)

    def find_driver_from_name(bone_name):
        if not bone_name:
            return None
        n = bone_name.lower()
        for bone in skeletons:
            try:
                long_name = bone.LongName
                if ns and not long_name.lower().startswith(ns.lower()):
                    continue
                if bone.Name.lower() == n:
                    return bone
            except:
                pass
        return None

    def extract_segment_keywords(bone_name):
        """
        Extract the core 'body segment' keywords from a bone name,
        stripping side markers (_l/_r/L_/R_/etc.) and common prefixes.
        Returns list of lowercase keyword fragments (≥4 chars) to search for.
        """
        if not bone_name:
            return []
        n = bone_name.lower()
        # Strip known side markers
        for tok in ["_l_", "_r_", "_l", "_r", "l_", "r_",
                    "left", "right", "lft", "rgt", " l ", " r "]:
            n = n.replace(tok, "_")
        # Strip known prefixes/suffixes (CC_Base_, CC_G_, etc.)
        for prefix in ["cc_base_", "cc_g_", "cc_", "rl_", "bip01 ", "bip001 "]:
            if n.startswith(prefix):
                n = n[len(prefix):]
        # Split by separators and keep meaningful tokens
        parts = [p for p in n.replace("-", "_").replace(".", "_").split("_") if len(p) >= 3]
        return parts

    pairs = []
    processed_pairs = set()  # avoid duplicates

    for side, forearm_slot, hand_slot, upperarm_slot, calf_slot, thigh_slot, foot_slot in [
        ("left",
         "LeftForeArmLink", "LeftHandLink", "LeftArmLink",
         "LeftLegLink", "LeftUpLegLink", "LeftFootLink"),
        ("right",
         "RightForeArmLink", "RightHandLink", "RightArmLink",
         "RightLegLink", "RightUpLegLink", "RightFootLink"),
    ]:
        forearm_name   = get_bone_name(forearm_slot)
        hand_name      = get_bone_name(hand_slot)
        upperarm_name  = get_bone_name(upperarm_slot)
        calf_name      = get_bone_name(calf_slot)
        thigh_name     = get_bone_name(thigh_slot)
        foot_name      = get_bone_name(foot_slot)

        forearm_bone   = find_driver_from_name(forearm_name)
        hand_bone      = find_driver_from_name(hand_name)
        upperarm_bone  = find_driver_from_name(upperarm_name)
        calf_bone      = find_driver_from_name(calf_name)
        thigh_bone     = find_driver_from_name(thigh_name)
        foot_bone      = find_driver_from_name(foot_name)

        # ── Forearm twists ───────────────────────────────────────────────────
        forearm_driver = hand_bone if hand_mode else forearm_bone
        if forearm_driver and forearm_bone:
            seg_kws = extract_segment_keywords(forearm_name)
            key = ("forearm", side)
            if key not in processed_pairs:
                twists = find_twist_bones_for_segment(skeletons, forearm_bone, seg_kws, ns)
                if twists:
                    pairs.append((forearm_driver, twists, "ForeArm-{}".format(side)))
                    processed_pairs.add(key)
                    print("[Template] ForeArm ({}) driver='{}' twist_kws={} → {} twist(s)".format(
                        side, forearm_driver.Name, seg_kws, len(twists)))

        # ── Upperarm twists ──────────────────────────────────────────────────
        if forearm_bone and upperarm_bone:
            seg_kws = extract_segment_keywords(upperarm_name)
            key = ("upperarm", side)
            if key not in processed_pairs:
                twists = find_twist_bones_for_segment(skeletons, upperarm_bone, seg_kws, ns)
                if twists:
                    pairs.append((forearm_bone, twists, "UpperArm-{}".format(side)))
                    processed_pairs.add(key)
                    print("[Template] UpperArm ({}) driver='{}' twist_kws={} → {} twist(s)".format(
                        side, forearm_bone.Name, seg_kws, len(twists)))

        # ── Thigh twists ─────────────────────────────────────────────────────
        if calf_bone and thigh_bone:
            seg_kws = extract_segment_keywords(thigh_name)
            key = ("thigh", side)
            if key not in processed_pairs:
                twists = find_twist_bones_for_segment(skeletons, thigh_bone, seg_kws, ns)
                if twists:
                    pairs.append((calf_bone, twists, "Thigh-{}".format(side)))
                    processed_pairs.add(key)
                    print("[Template] Thigh ({}) driver='{}' twist_kws={} → {} twist(s)".format(
                        side, calf_bone.Name, seg_kws, len(twists)))

        # ── Calf twists ──────────────────────────────────────────────────────
        if foot_bone and calf_bone:
            seg_kws = extract_segment_keywords(calf_name)
            key = ("calf", side)
            if key not in processed_pairs:
                twists = find_twist_bones_for_segment(skeletons, calf_bone, seg_kws, ns)
                if twists:
                    pairs.append((foot_bone, twists, "Calf-{}".format(side)))
                    processed_pairs.add(key)
                    print("[Template] Calf ({}) driver='{}' twist_kws={} → {} twist(s)".format(
                        side, foot_bone.Name, seg_kws, len(twists)))

    return pairs

# ── Animation node helpers ────────────────────────────────────────────────────
def find_anim_node(anim_node, name):
    if anim_node is None:
        return None
    try:
        node_list = anim_node.Nodes
        for i in range(len(node_list)):
            n = node_list[i]
            if n.Name == name:
                return n
    except Exception as e:
        print("[find_anim_node] {}: {}".format(name, e))
    return None

def list_anim_nodes(anim_node):
    if anim_node is None:
        return []
    try:
        return [anim_node.Nodes[i].Name for i in range(len(anim_node.Nodes))]
    except:
        return ["(error listing nodes)"]

def set_local_transform(box):
    try:
        box.UseGlobalTransforms = False
        return True
    except Exception as e:
        print("[Twist] WARN: UseGlobalTransforms failed on '{}': {}".format(box.Name, e))
        return False

def get_rot_node_name(box_node_get_fn):
    for name in ("Lcl Rotation", "Rotation"):
        n = find_anim_node(box_node_get_fn(), name)
        if n is not None:
            return n, name
    return None, None

# ── Weight null helper ────────────────────────────────────────────────────────
CONSTRAINT_NAME    = "REL_TwistBones"
WEIGHT_NULL_PREFIX = "_TwistW_"

def make_weight_null(weight, label):
    null_name = "{}{}".format(WEIGHT_NULL_PREFIX, label)
    for comp in list(FBSystem().Scene.Components):
        try:
            if isinstance(comp, FBModelNull) and comp.Name == null_name:
                comp.FBDelete()
        except:
            pass
    null = FBModelNull(null_name)
    null.Show = False
    null.Visibility = False
    null.SystemObject = True
    try:
        null.Translation = FBVector3d(weight, 0.0, 0.0)
    except:
        pass
    return null

def set_box_pos(con, box, x, y):
    if con is None or box is None:
        return
    try:
        con.SetBoxPosition(box, int(x), int(y))
    except Exception as e:
        print("[Twist] SetBoxPosition failed: {}".format(e))

# ── Constraint builder ────────────────────────────────────────────────────────
def add_driver_to_constraint(con, driver, twist_bones, axis, y_start, base_weight=0.5):
    """
    Build the relation-constraint graph for one driver → N twist bones.
    axis: "X" | "Y" | "Z"
    """
    if not driver or not twist_bones:
        return 0

    num_twists = len(twist_bones)

    src_box = con.SetAsSource(driver)
    FBSystem().Scene.Evaluate()
    if src_box is None:
        print("[Twist] SetAsSource None: {}".format(driver.Name))
        return 0

    set_local_transform(src_box)
    FBSystem().Scene.Evaluate()

    src_rot, rot_name = get_rot_node_name(src_box.AnimationNodeOutGet)
    if src_rot is None:
        print("[Twist] Rotation node not found on {}. Nodes: {}".format(
            driver.Name, list_anim_nodes(src_box.AnimationNodeOutGet())))
        return 0
    print("[Twist] src '{}' axis='{}' using node '{}'".format(driver.Name, axis, rot_name))

    set_box_pos(con, src_box, 100, y_start + 50)

    v2n = con.CreateFunctionBox("Converters", "Vector to Number")
    FBSystem().Scene.Evaluate()
    if v2n is None:
        print("[Twist] 'Vector to Number' creation failed")
        return 0

    v2n_in     = find_anim_node(v2n.AnimationNodeInGet(),  "V")
    v2n_out_ax = find_anim_node(v2n.AnimationNodeOutGet(), axis)

    if v2n_in is None or v2n_out_ax is None:
        print("[Twist] V2N nodes missing (axis={}). In:{} Out:{}".format(
            axis,
            list_anim_nodes(v2n.AnimationNodeInGet()),
            list_anim_nodes(v2n.AnimationNodeOutGet())))
        return 0

    FBConnect(src_rot, v2n_in)
    set_box_pos(con, v2n, 450, y_start + 50)

    connected = 0
    for i, twist in enumerate(twist_bones):
        step_weight = ((i + 1) / float(num_twists)) * base_weight
        y_twist = y_start + i * 200

        dst_box = con.ConstrainObject(twist)
        FBSystem().Scene.Evaluate()
        if dst_box is None:
            print("[Twist] ConstrainObject None: {}".format(twist.Name))
            continue

        set_local_transform(dst_box)
        FBSystem().Scene.Evaluate()

        dst_rot, dst_rot_name = get_rot_node_name(dst_box.AnimationNodeInGet)
        if dst_rot is None:
            print("[Twist] Rotation node not found on {}".format(twist.Name))
            continue

        set_box_pos(con, dst_box, 1500, y_twist + 50)

        # Weight null
        label = "{}_{}" .format(driver.Name[:8], i)
        weight_null = make_weight_null(step_weight, label)
        weight_scalar = None

        if weight_null is not None:
            w_src = con.SetAsSource(weight_null)
            FBSystem().Scene.Evaluate()
            if w_src is not None:
                set_box_pos(con, w_src, 100, y_twist + 100)
                w_trans = (find_anim_node(w_src.AnimationNodeOutGet(), "Translation") or
                           find_anim_node(w_src.AnimationNodeOutGet(), "Lcl Translation"))
                if w_trans is not None:
                    wv2n = con.CreateFunctionBox("Converters", "Vector to Number")
                    FBSystem().Scene.Evaluate()
                    if wv2n is not None:
                        set_box_pos(con, wv2n, 450, y_twist + 100)
                        wv2n_in = find_anim_node(wv2n.AnimationNodeInGet(), "V")
                        wv2n_x  = find_anim_node(wv2n.AnimationNodeOutGet(), "X")
                        if wv2n_in and wv2n_x:
                            FBConnect(w_trans, wv2n_in)
                            weight_scalar = wv2n_x

        mult_node = None
        if weight_scalar is not None:
            for mult_name in ("Multiply (a x b)", "Multiply (a*b)"):
                mult = con.CreateFunctionBox("Number", mult_name)
                FBSystem().Scene.Evaluate()
                if mult is not None:
                    set_box_pos(con, mult, 800, y_twist + 50)
                    m_a   = find_anim_node(mult.AnimationNodeInGet(),  "a")
                    m_b   = find_anim_node(mult.AnimationNodeInGet(),  "b")
                    m_out = find_anim_node(mult.AnimationNodeOutGet(), "Result")
                    if m_a and m_b and m_out:
                        FBConnect(v2n_out_ax,   m_a)
                        FBConnect(weight_scalar, m_b)
                        mult_node = m_out
                        break

        n2v_source = mult_node if mult_node is not None else v2n_out_ax
        weight_tag = "w={:.2f}".format(step_weight) if mult_node else "no-weight"

        n2v = con.CreateFunctionBox("Converters", "Number to Vector")
        FBSystem().Scene.Evaluate()
        if n2v is None:
            print("[Twist] 'Number to Vector' creation failed")
            continue

        set_box_pos(con, n2v, 1150, y_twist + 50)

        n2v_in_ax = find_anim_node(n2v.AnimationNodeInGet(),  axis)
        n2v_out   = find_anim_node(n2v.AnimationNodeOutGet(), "Result")

        if n2v_in_ax is None or n2v_out is None:
            print("[Twist] N2V nodes missing. in:{} out:{}".format(
                list_anim_nodes(n2v.AnimationNodeInGet()),
                list_anim_nodes(n2v.AnimationNodeOutGet())))
            continue

        FBConnect(n2v_source, n2v_in_ax)
        FBConnect(n2v_out, dst_rot)
        connected += 1
        print("[Twist] {} →{}({})→ {}".format(driver.Name, axis, weight_tag, twist.Name))

    return connected

# ── Resolve pairs from current UI selection ───────────────────────────────────
def resolve_pairs(skeletons, ns):
    """
    Returns list of (driver_bone, twist_bones, segment_label) depending on
    whether a JSON template or a legacy preset is active.
    """
    idx = g_ui["list_type"].ItemIndex
    if idx < 0:
        return []
    item_name = g_ui["list_type"].Items[idx]
    hand_mode = g_ui["chk_hand_driver"].State == 1

    # ── JSON template mode ────────────────────────────────────────────────────
    if item_name in g_template_path:
        t_path = g_template_path[item_name]
        return get_twist_pairs_from_template(t_path, skeletons, hand_mode, ns)

    # ── Legacy fallback mode ───────────────────────────────────────────────────
    if "Unreal Engine" in item_name:
        rule_key = "UE_HAND" if hand_mode else "UE_FOREARM"
    else:
        rule_key = "AccuRig_HAND" if hand_mode else "AccuRig_FOREARM"

    rules = TWIST_RULES[rule_key]
    pairs = []
    for driver_kw, twist_kws in rules:
        driver = find_driver(skeletons, driver_kw, ns)
        if not driver:
            continue
        twists = find_twists(skeletons, driver, twist_kws, ns)
        if twists:
            pairs.append((driver, twists, driver_kw))
    return pairs

# ── Namespace auto-detect ─────────────────────────────────────────────────────
def OnAutoNS(control, event):
    char = FBApplication().CurrentCharacter
    if char:
        ns = get_character_ns(char)
        if ns is not None:
            g_ui["edit_ns"].Text = ns.rstrip(":")
            status("NS from HIK: '{}'".format(ns))
            return
    models = FBModelList()
    FBGetSelectedModels(models)
    if models:
        try:
            long_name = models[0].LongName
            if ":" in long_name:
                ns = long_name.rsplit(":", 1)[0]
                g_ui["edit_ns"].Text = ns
                status("NS from Selection: '{}'".format(ns))
                return
        except:
            pass
    status("No namespace detected.")

# ── Step 1: Dry-run ───────────────────────────────────────────────────────────
def OnDryRun(control, event):
    char = check_active_character()
    if not char:
        return

    ns_resolved = get_character_ns(char)
    if ns_resolved is not None:
        g_ui["edit_ns"].Text = ns_resolved.rstrip(":")

    ns        = get_ns()
    skeletons = scan_skeletons()

    if not skeletons:
        status("No skeleton found!")
        FBMessageBox("Not Found", "No FBModelSkeleton in scene.", "OK")
        return

    print("\n" + "="*60)
    print("Twist Dry-Run | NS='{}'".format(ns or "(none)"))
    print("="*60)
    print("\n[All FBModelSkeleton bones in scene]")
    for b in sorted(skeletons, key=lambda x: x.Name):
        print("  {}".format(b.Name))
    print()

    pairs = resolve_pairs(skeletons, ns)
    found = 0
    for driver, twist_bones, label in pairs:
        auto_axis = get_axis(driver)
        for t in twist_bones:
            print("  [OK] {} --[{}]--> {} (axis={})".format(
                driver.Name, label, t.Name, auto_axis))
            found += 1

    print("\n" + "="*60)
    print("Total pairs matched: {}".format(found))
    print("(Help > Python > Script to see output)")

    status("Dry-run: {} pairs. See Python Console.".format(found))
    FBMessageBox("Dry-Run",
        "Found {} twist pair(s).\n\nSee Python Console for full bone list "
        "and match results.".format(found), "OK")

# ── Step 2: Build ─────────────────────────────────────────────────────────────
def OnBuild(control, event):
    char = check_active_character()
    if not char:
        return

    ns_resolved = get_character_ns(char)
    if ns_resolved is not None:
        g_ui["edit_ns"].Text = ns_resolved.rstrip(":")

    ns          = get_ns()
    base_weight = get_base_weight()
    skeletons   = scan_skeletons()

    if not skeletons:
        status("No skeleton found!")
        FBMessageBox("Error", "No skeleton in scene.", "OK")
        return

    # ── Remove existing constraint + weight nulls ─────────────────────────────
    for comp in list(FBSystem().Scene.Constraints):
        try:
            if comp.Name == CONSTRAINT_NAME:
                comp.FBDelete()
        except:
            pass
    for comp in list(FBSystem().Scene.Components):
        try:
            if isinstance(comp, FBModelNull) and comp.Name.startswith(WEIGHT_NULL_PREFIX):
                comp.FBDelete()
        except:
            pass
    FBSystem().Scene.Evaluate()

    # ── Create constraint ─────────────────────────────────────────────────────
    con = FBConstraintRelation(CONSTRAINT_NAME)
    if con is None:
        FBMessageBox("Error", "FBConstraintRelation() returned None.", "OK")
        return
    con.Active = False
    FBSystem().Scene.Evaluate()

    pairs = resolve_pairs(skeletons, ns)

    total_twists  = 0
    total_drivers = 0
    y_start       = 100

    for driver, twist_bones, label in pairs:
        # Per-driver axis detection (if Auto mode)
        axis = get_axis(driver)
        n = add_driver_to_constraint(con, driver, twist_bones, axis, y_start, base_weight)
        if n > 0:
            total_drivers += 1
            total_twists  += n
            y_start += max(1, len(twist_bones)) * 200 + 100

    FBSystem().Scene.Evaluate()

    if total_twists > 0:
        con.Active = True
        FBSystem().Scene.Evaluate()
        msg = ("1 constraint  |  {} drivers  |  {} twist joints\n"
               "Base weight: {}").format(total_drivers, total_twists, base_weight)
        status("{} drivers, {} twists | weight={}".format(
            total_drivers, total_twists, base_weight))
        FBMessageBox("Done", msg, "OK")
    else:
        con.FBDelete()
        status("No pairs found.")
        FBMessageBox("No Results", "No pairs found.\nRun Dry-Run first.", "OK")

# ── Remove ────────────────────────────────────────────────────────────────────
def OnRemove(control, event):
    n = 0
    for comp in list(FBSystem().Scene.Constraints):
        try:
            if comp.Name == CONSTRAINT_NAME:
                comp.FBDelete(); n += 1
        except:
            pass
    for comp in list(FBSystem().Scene.Components):
        try:
            if isinstance(comp, FBModelNull) and comp.Name.startswith(WEIGHT_NULL_PREFIX):
                comp.FBDelete(); n += 1
        except:
            pass
    FBSystem().Scene.Evaluate()
    status("Removed {} object(s).".format(n))
    FBMessageBox("Done", "Removed {}.".format(n), "OK")

# ── UI ────────────────────────────────────────────────────────────────────────
def PopulateTool(tool):
    tool.StartSizeX = 320
    tool.StartSizeY = 460

    x = FBAddRegionParam(0,  FBAttachType.kFBAttachLeft,   "")
    y = FBAddRegionParam(0,  FBAttachType.kFBAttachTop,    "")
    w = FBAddRegionParam(0,  FBAttachType.kFBAttachRight,  "")
    h = FBAddRegionParam(0,  FBAttachType.kFBAttachBottom, "")
    tool.AddRegion("main", "main", x, y, w, h)

    lay = FBVBoxLayout()
    tool.SetControl("main", lay)

    # Title
    lay.Add(hdr("Saint's Twistbone_tool  v5"), 25)

    # ── Skeleton type (dynamic template list) ─────────────────────────────────
    r1 = FBHBoxLayout()
    lbl1 = FBLabel(); lbl1.Caption = "Skeleton:"
    g_ui["list_type"] = FBList()
    r1.Add(lbl1, 68); r1.Add(g_ui["list_type"], 215)
    lay.Add(r1, 28)

    # Note: refresh_templates() will populate list_type immediately after UI setup.

    # Driver mode
    g_ui["chk_hand_driver"] = FBButton()
    g_ui["chk_hand_driver"].Style   = FBButtonStyle.kFBCheckbox
    g_ui["chk_hand_driver"].Caption = "Forearm Twist driven by Hand/Wrist"
    g_ui["chk_hand_driver"].State   = 1
    lay.Add(g_ui["chk_hand_driver"], 25)

    note_drv = FBLabel()
    note_drv.Caption = "  OFF = Forearm bone as driver (traditional)"
    note_drv.Justify = FBTextJustify.kFBTextJustifyLeft
    lay.Add(note_drv, 18)

    # ── Twist Axis selector (Auto + X/Y/Z) ───────────────────────────────────
    r_ax = FBHBoxLayout()
    lbl_ax = FBLabel(); lbl_ax.Caption = "Twist Axis:"
    g_ui["list_axis"] = FBList()
    g_ui["list_axis"].Items.append("Auto (detect from bone direction)")
    g_ui["list_axis"].Items.append("X  (forearm roll - UE/AccuRig default)")
    g_ui["list_axis"].Items.append("Y")
    g_ui["list_axis"].Items.append("Z")
    g_ui["list_axis"].ItemIndex = 0   # Default: Auto
    r_ax.Add(lbl_ax, 68); r_ax.Add(g_ui["list_axis"], 215)
    lay.Add(r_ax, 28)

    # ── Base weight ───────────────────────────────────────────────────────────
    r_wt = FBHBoxLayout()
    lbl_wt = FBLabel(); lbl_wt.Caption = "Base Weight:"
    g_ui["edit_weight"] = FBEdit(); g_ui["edit_weight"].Text = "0.5"
    note_wt = FBLabel(); note_wt.Caption = "(0.01 - 1.0)"
    r_wt.Add(lbl_wt, 68); r_wt.Add(g_ui["edit_weight"], 80); r_wt.Add(note_wt, 100)
    lay.Add(r_wt, 26)

    # ── Namespace ─────────────────────────────────────────────────────────────
    r2 = FBHBoxLayout()
    lbl2 = FBLabel(); lbl2.Caption = "Namespace:"
    g_ui["edit_ns"] = FBEdit(); g_ui["edit_ns"].Text = ""
    btn_ns = FBButton(); btn_ns.Caption = "Auto"
    btn_ns.OnClick.Add(OnAutoNS)
    r2.Add(lbl2, 68); r2.Add(g_ui["edit_ns"], 118); r2.Add(btn_ns, 60)
    lay.Add(r2, 28)

    lay.Add(make_spacer(), 8)

    # Step 1
    b1 = FBButton()
    b1.Caption = "Auto-Detect Twistbone"
    b1.OnClick.Add(OnDryRun)
    lay.Add(b1, 36)

    lay.Add(make_spacer(), 5)

    # Step 2
    b2 = FBButton()
    b2.Caption = "Build Twist constraint"
    b2.OnClick.Add(OnBuild)
    lay.Add(b2, 36)

    lay.Add(make_spacer(), 5)

    # Remove
    b3 = FBButton()
    b3.Caption = "Remove All Twist Constraints"
    b3.OnClick.Add(OnRemove)
    lay.Add(b3, 32)

    lay.Add(make_spacer(), 8)

    # Status
    g_ui["lbl_status"] = FBLabel()
    g_ui["lbl_status"].Caption = "Ready."
    g_ui["lbl_status"].Justify = FBTextJustify.kFBTextJustifyCenter
    lay.Add(g_ui["lbl_status"], 22)

    # Populate template list now that list_type widget exists
    refresh_templates()


def CreateTool():
    tool = FBCreateUniqueTool("Saint's Twistbone_tool")
    if tool:
        PopulateTool(tool)
        ShowTool(tool)
        show_welcome()
    else:
        print("[TwistCalc] FBCreateUniqueTool returned None.")

CreateTool()
