# -*- coding: utf-8 -*-
"""
MobuCharacter_DisplayFix.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
一鍵修正場景中骨骼 (Skeleton) 與空物件 (Null) 的顯示尺寸，並提供場景清理、顯示模式設定與透明度修正功能。
Fix skeleton and null display sizes in one click, clean up the scene, and adjust display settings.

Workflow / 功能介紹：
  1. Display Size Fix (骨骼顯示尺寸修正): 
     Set all Skeleton and Null display sizes to a target value (default 1.0) 
     to solve the oversized bone issues when exporting FBX from Blender to MotionBuilder.
     一鍵將 Skeleton / Null 的 Display Size 設為指定值（預設 1.0），
     專門解決 Blender 匯出 FBX 至 MotionBuilder 後骨骼顯示尺寸過大（通常為 100）的問題。

  2. Select Oversized & Dry-Run (選取大尺寸骨骼與預覽): 
     Automatically select all oversized objects in the scene and print a dry-run report in the Python console.
     自動選取場景中所有尺寸不符的骨骼，並在控制台輸出 Dry-Run 報表。

  3. Scene Clean-up & Utilities (場景清理與工具頁): 
     - Quickly delete all custom lights and cameras in the scene, while safely retaining the system's Producer cameras.
       提供一鍵清除場景內所有自訂燈光 (Lights) 與攝影機 (Cameras) 的捷徑，並自動保留 MotionBuilder 內建的 Producer 系統攝影機。
     - Set all models to Texture + Shader display mode.
       一鍵將所有模型的顯示設定為貼圖與著色器模式 (Texture + Shader)。
     - Enable Transparency (Accurate): Replace current shaders on models with a Lighted shader configured for Accurate Transparency.
       一鍵將模型的 Shader 替換為 Lighted Shader，並將透明度運算模式設為精確透明度 (Accurate Transparency)。

由小聖腦絲與 Antigravity 協作完成
https://www.facebook.com/hysaint3d.mocap
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from pyfbsdk import *
from pyfbsdk_additions import *

g_ui = {}

# ── Helpers ───────────────────────────────────────────────────────────────────
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

def get_target_size():
    try:
        v = float(g_ui["edit_size"].Text.strip())
        return max(0.001, v)
    except:
        return 1.0

# ── Core logic ────────────────────────────────────────────────────────────────
def scan_and_fix():
    target = get_target_size()
    fix_sk  = g_ui["chk_skeleton"].State == 1
    fix_null = g_ui["chk_null"].State == 1
    sel_only = g_ui["chk_sel"].State == 1

    targets = []
    skipped = []

    for comp in FBSystem().Scene.Components:
        try:
            is_sk   = isinstance(comp, FBModelSkeleton)
            is_null = isinstance(comp, FBModelNull)

            if not ((fix_sk and is_sk) or (fix_null and is_null)):
                continue
            if sel_only and not comp.Selected:
                continue

            current_size = comp.Size
            if abs(current_size - target) > 0.0001:
                targets.append((comp, current_size))
            else:
                skipped.append(comp)
        except:
            pass

    # Apply
    fixed = 0
    for comp, _ in targets:
        try:
            comp.Size = target
            fixed += 1
        except:
            print("[DisplayFix] Failed to set size on: {}".format(comp.LongName))

    FBSystem().Scene.Evaluate()

    print("[DisplayFix] Fixed {} object(s) → size = {}".format(fixed, target))
    status("Fixed {} object(s) → size = {}".format(fixed, target))

    if fixed > 0:
        FBMessageBox("Done",
                     "Set Display Size = {} on {} object(s).".format(target, fixed), "OK")
    else:
        FBMessageBox("Nothing to fix",
                     "All selected objects are already at size {}.".format(target), "OK")


# ── Button callbacks ──────────────────────────────────────────────────────────
def OnFix(control, event):
    scan_and_fix()

def OnSelectAll(control, event):
    """Select all oversized skeletons/nulls in scene and print Dry-Run info."""
    target  = get_target_size()
    fix_sk   = g_ui["chk_skeleton"].State == 1
    fix_null = g_ui["chk_null"].State == 1

    targets = []
    skipped = []

    for comp in FBSystem().Scene.Components:
        try:
            is_sk   = isinstance(comp, FBModelSkeleton)
            is_null = isinstance(comp, FBModelNull)
            if not ((fix_sk and is_sk) or (fix_null and is_null)):
                continue

            current_size = comp.Size
            if abs(current_size - target) > 0.0001:
                targets.append((comp, current_size))
            else:
                skipped.append(comp)
        except:
            pass

    # Select them
    for comp, _ in targets:
        try:
            comp.Selected = True
        except:
            pass

    FBSystem().Scene.Evaluate()

    # Dry-Run Console output
    print("\n" + "="*55)
    print("Display Size Fix  |  Select & Dry-Run  |  Target = {}".format(target))
    print("="*55)
    print("\n[Selected/To Fix] {} object(s):".format(len(targets)))
    for comp, sz in targets:
        kind = "Skeleton" if isinstance(comp, FBModelSkeleton) else "Null"
        print("  [{:8}]  {:35s}  size={:.4g}".format(kind, comp.LongName, sz))
    print("\n[Already OK] {} object(s)".format(len(skipped)))
    print("="*55 + "\n")

    status("Selected {} to fix, {} already OK.".format(len(targets), len(skipped)))
    FBMessageBox("Select & Dry-Run Result",
                 "Selected to fix: {} object(s)\nAlready OK: {} object(s)\n\nSee Python Console for details.".format(
                     len(targets), len(skipped)), "OK")

def OnDeleteLights(control, event):
    lights = [l for l in FBSystem().Scene.Lights]
    deleted = 0
    for l in lights:
        try:
            l.FBDelete()
            deleted += 1
        except Exception as e:
            print("[DisplayFix] Failed to delete light '{}': {}".format(l.Name, e))
    FBSystem().Scene.Evaluate()
    status("Deleted {} light(s).".format(deleted))
    if deleted > 0:
        FBMessageBox("Done", "Deleted {} light(s).".format(deleted), "OK")
    else:
        FBMessageBox("Clean Scene", "No lights found to delete.", "OK")

def OnDeleteCameras(control, event):
    cameras = []
    for comp in FBSystem().Scene.Components:
        if isinstance(comp, FBCamera) and not comp.SystemCamera:
            cameras.append(comp)
    
    deleted = 0
    for cam in cameras:
        try:
            cam.FBDelete()
            deleted += 1
        except Exception as e:
            print("[DisplayFix] Failed to delete camera '{}': {}".format(cam.Name, e))
    FBSystem().Scene.Evaluate()
    status("Deleted {} camera(s).".format(deleted))
    if deleted > 0:
        FBMessageBox("Done", "Deleted {} camera(s).".format(deleted), "OK")
    else:
        FBMessageBox("Clean Scene", "No custom cameras found to delete.", "OK")

def OnSetTextureShader(control, event):
    # 1. Set global renderer display mode to Texture
    try:
        lRenderer = FBSystem().Renderer
        lViewingOptions = lRenderer.GetViewingOptions()
        lViewingOptions.DisplayMode = FBDisplayMode.kFBDisplayModeTexture
        lRenderer.SetViewingOptions(lViewingOptions)
    except Exception as e:
        print("[DisplayFix] Failed to set viewport display mode: {}".format(e))

    # 2. Set all models ShadingMode to kFBModelShadingAll (Lighted, shaded, and textured)
    count = 0
    for comp in FBSystem().Scene.Components:
        if isinstance(comp, FBModel) and hasattr(comp, "ShadingMode"):
            try:
                comp.ShadingMode = FBModelShadingMode.kFBModelShadingAll
                count += 1
            except:
                pass

    FBSystem().Scene.Evaluate()
    status("Set Texture+Shader on {} model(s).".format(count))
    FBMessageBox("Done", "Set Texture + Shader on {} model(s) and set viewport to Texture mode.".format(count), "OK")

def OnEnableTransparency(control, event):
    sel_only = g_ui["chk_sel"].State == 1

    # 1. Retrieve or create Lighted Shader
    shader_name = "Accurate_Transparency_Shader"
    shader = None
    for s in FBSystem().Scene.Shaders:
        if s.Name == shader_name:
            shader = s
            break

    if not shader:
        shader = FBShaderLighted(shader_name)

    # 2. Set transparency to Accurate
    try:
        shader.Transparency = FBAlphaSource.kFBAlphaSourceAccurate
    except Exception as e:
        print("[DisplayFix] Failed to set FBAlphaSource: {}".format(e))
        # Fallback
        try:
            for member in dir(FBAlphaSource):
                if "Accurate" in member:
                    setattr(shader, "Transparency", getattr(FBAlphaSource, member))
                    break
        except:
            pass

    # 3. Find models (ignoring skeletons and nulls)
    models = []
    for comp in FBSystem().Scene.Components:
        if isinstance(comp, FBModel) and not isinstance(comp, (FBModelSkeleton, FBModelNull)):
            if sel_only and not comp.Selected:
                continue
            models.append(comp)

    # 4. Process models
    count = 0
    for model in models:
        try:
            # Clear existing shaders
            for i in range(len(model.Shaders) - 1, -1, -1):
                try:
                    model.Shaders.pop(i)
                except:
                    pass
            # Append new shader
            shader.Append(model)
            count += 1
        except Exception as e:
            print("[DisplayFix] Failed to assign shader to {}: {}".format(model.LongName, e))

    FBSystem().Scene.Evaluate()
    status("Applied transparency shader to {} model(s).".format(count))
    if count > 0:
        FBMessageBox("Done", "Applied Lighted Shader with Accurate Transparency to {} model(s).".format(count), "OK")
    else:
        FBMessageBox("Enable Transparency", "No models found to apply shader.", "OK")


def PopulateTool(tool):
    tool.StartSizeX = 290
    tool.StartSizeY = 510

    x = FBAddRegionParam(0, FBAttachType.kFBAttachLeft,   "")
    y = FBAddRegionParam(0, FBAttachType.kFBAttachTop,    "")
    w = FBAddRegionParam(0, FBAttachType.kFBAttachRight,  "")
    h = FBAddRegionParam(0, FBAttachType.kFBAttachBottom, "")
    tool.AddRegion("main", "main", x, y, w, h)

    lay = FBVBoxLayout()
    tool.SetControl("main", lay)

    # Title
    lay.Add(hdr("Saint's MobuDisplayFix"), 25)

    lay.Add(make_spacer(), 6)

    # Target size row
    r_sz = FBHBoxLayout()
    lbl_sz = FBLabel(); lbl_sz.Caption = "Target Size:"
    g_ui["edit_size"] = FBEdit(); g_ui["edit_size"].Text = "1"
    r_sz.Add(lbl_sz, 90); r_sz.Add(g_ui["edit_size"], 70)
    lay.Add(r_sz, 26)

    lay.Add(make_spacer(), 4)

    # Checkboxes
    g_ui["chk_skeleton"] = FBButton()
    g_ui["chk_skeleton"].Style   = FBButtonStyle.kFBCheckbox
    g_ui["chk_skeleton"].Caption = "Skeleton"
    g_ui["chk_skeleton"].State   = 1
    lay.Add(g_ui["chk_skeleton"], 24)

    g_ui["chk_null"] = FBButton()
    g_ui["chk_null"].Style   = FBButtonStyle.kFBCheckbox
    g_ui["chk_null"].Caption = "Null"
    g_ui["chk_null"].State   = 1
    lay.Add(g_ui["chk_null"], 24)

    g_ui["chk_sel"] = FBButton()
    g_ui["chk_sel"].Style   = FBButtonStyle.kFBCheckbox
    g_ui["chk_sel"].Caption = "Selected Only"
    g_ui["chk_sel"].State   = 0
    lay.Add(g_ui["chk_sel"], 24)

    lay.Add(make_spacer(), 8)

    # Select oversized button (combined with Dry-Run report)
    b_sel = FBButton()
    b_sel.Caption = "Select Oversized (Dry-Run)"
    b_sel.OnClick.Add(OnSelectAll)
    lay.Add(b_sel, 30)

    lay.Add(make_spacer(), 4)

    # Fix button
    b_fix = FBButton()
    b_fix.Caption = "Fix Display Size"
    b_fix.OnClick.Add(OnFix)
    lay.Add(b_fix, 36)

    # ── Clean Scene ──
    lay.Add(make_spacer(), 4)
    lay.Add(hdr("Clean Scene & Utilities"), 25)
    lay.Add(make_spacer(), 4)

    r_clean = FBHBoxLayout()
    b_del_lights = FBButton()
    b_del_lights.Caption = "Delete Lights"
    b_del_lights.OnClick.Add(OnDeleteLights)
    r_clean.Add(b_del_lights, 125)

    b_del_cams = FBButton()
    b_del_cams.Caption = "Delete Cameras"
    b_del_cams.OnClick.Add(OnDeleteCameras)
    r_clean.Add(b_del_cams, 125)
    lay.Add(r_clean, 30)

    lay.Add(make_spacer(), 4)

    # Set Texture + Shader button
    b_tex_shader = FBButton()
    b_tex_shader.Caption = "Set All Models: Texture + Shader"
    b_tex_shader.OnClick.Add(OnSetTextureShader)
    lay.Add(b_tex_shader, 30)

    lay.Add(make_spacer(), 4)

    # Enable Transparency button
    b_trans = FBButton()
    b_trans.Caption = "Enable Transparency (Accurate)"
    b_trans.OnClick.Add(OnEnableTransparency)
    lay.Add(b_trans, 30)

    lay.Add(make_spacer(), 8)

    # Status
    g_ui["lbl_status"] = FBLabel()
    g_ui["lbl_status"].Caption = "Ready."
    g_ui["lbl_status"].Justify = FBTextJustify.kFBTextJustifyCenter
    lay.Add(g_ui["lbl_status"], 22)


def CreateTool():
    tool = FBCreateUniqueTool("Saint's MobuDisplayFix")
    if tool:
        PopulateTool(tool)
        ShowTool(tool)
        FBMessageBox("Welcome", "MobuCharacter_DisplayFix\n本工具由小聖腦絲與Antigravity協作完成\nhttps://www.facebook.com/hysaint3d.mocap", "OK")
    else:
        print("[DisplayFix] FBCreateUniqueTool returned None.")

CreateTool()
