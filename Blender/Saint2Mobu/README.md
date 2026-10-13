# Saint2Mobu 0.4.3 (Beta)

This package updates the existing [Saint2Mobu 0.4.0 Beta 1 release](https://github.com/hysaint3d/SaintMocap_Tools/releases/tag/saint2mobu-v0.4.0-beta.1). Its release title and tag are retained; the add-on inside the installation ZIP is version **0.4.3**.

Windows Blender 5.2 ↔ MotionBuilder native Send To bridge. No Maya/3ds Max installation or running process is required. FBX reading/writing uses Blender's built-in `bpy.ops.wm.fbx_import` and `bpy.ops.export_scene.fbx` exclusively.

## Install and use

1. Install `dist/SaintMocap_Send2Mobu-0.4.3.zip` in Blender (Preferences → Add-ons → Install from Disk). If replacing an older version, restart Blender.
2. Open Viewport → N panel → Send2Mobu. Choose Emulate Maya or 3ds Max, declared Version (2023–2027), and the actual installed MotionBuilder version. Default: Maya 2026 / Mobu 2026.
3. Click **Online**. The hidden native host loads `synHub.dll` from the selected MotionBuilder installation. No Autodesk DLL is copied or bundled.
4. If using a newly registered identity, restart MotionBuilder after Online, or click **Launch MotionBuilder**. This opens a new Mobu instance with isolated registration settings. An already running Mobu may cache its old product list.
5. **Start from Blender:** select objects, choose a **Target Mobu** PID if more than one process is running, and click **Send to Mobu**. It connects directly to that Mobu and updates its current scene. No initial Mobu Send To is required. If no selected-version Mobu is running, the button launches it with isolated registration and waits for startup. Parent objects and skin armatures are included automatically. Selecting an Armature also includes every mesh in the current scene whose Armature modifier targets it, even when the mesh has a different parent. Mesh-only selection includes its rig/parents; it does not automatically select all sibling meshes. Hidden or unselectable dependencies are named in an error so no bound mesh is silently omitted. Selection/FBX is captured when the button is clicked.
6. **Send as New Scene** replaces the selected Mobu scene through Autodesk's native New Scene behavior. **Sync Collection to Mobu** updates all objects associated with that connection's most recent transfer. The Export Animation option applies to both send buttons. Test FBX controls have been removed.
7. **Start from Mobu or send edits back:** use its unchanged **File > Send to Maya / Send to 3ds Max > Send as New Scene / Update Current Scene**. Send as New Scene opens a new empty .blend, clears the current file contents and imports the cached FBX on the following main-thread timer tick using a rebuilt window context, while keeping Online connected. Save your Blender work before using it. Update matches original FBX names against the associated sent/received collection, retaining original Blender object identities and adding new objects. Blender-first sends establish this association automatically.
8. Click **Offline** to stop the host and remove this session's owned system registration. Loading another .blend or disabling the add-on also takes it Offline.

This is file-based Send/Update, not streaming. Receiving waits until Blender is in Object Mode and its interface is unlocked. Incoming failures are shown in the panel; after correcting the issue use **Retry Last Receive**. Received FBX copies are retained for retry and diagnostics.

## Registration and versions

Online writes only a uniquely named `Send2.<product>.<year>.syncfg` in `%PROGRAMDATA%/Autodesk/Synergy` when writable and when there is no real registration for that same identity. Existing Autodesk registration files are retained. If a real product is already registered, or the system directory is not writable, use **Launch MotionBuilder** so this new process receives an isolated configuration. No MotionBuilder plugin/script is installed.

One Blender session can own each emulated product/year at a time. Select another identity or take the first session Offline before reusing it. Multiple Mobu processes can connect to the same host; replies are addressed to their native link, with process IDs displayed in the panel.

The Version field is the declared DCC identity, separate from the installed MotionBuilder version that supplies the transport DLL. The launcher maps its Mobu registration to that declared year. Cross-version identity routing is verified for emulated Maya 2027 with actual Mobu 2026. This does not guarantee all FBX features across all application releases.

## Supported merge behavior and limits

- Exact original FBX object names are stored on received objects. Blender name suffixes caused by unrelated scene objects do not change the names sent back to Mobu.
- Mesh data/topology, transforms, parent hierarchies, FK armatures/rest bones, vertex groups/skin weights and active imported animation actions update while retaining existing Blender object identities.
- Existing destination material slots are retained; additional incoming slots are appended. Complex shader graphs are subject to Blender's native FBX support.
- Shared destination mesh data, destination constraints, non-armature modifiers, drivers, NLA tracks and bone constraints are rejected before merge. Bake/simplify the destination rig first. Imported FBX is not a transfer of Mobu Character definitions, control rigs, constraints or arbitrary Blender procedural data.
- Missing objects are retained: a native transfer may contain only a selection, so absence does not imply deletion. Renaming upstream is treated as a new object; deletion/rename propagation is not implemented.
- New Scene on receive creates a genuinely new unsaved .blend and a new sync collection. Previous scenes/objects are cleared. Repeated Update operates on that connection's most recently received collection. Connection/collection routing resets on Offline or loading a .blend; the next send from either application establishes it again.
- **Point Bones to Children** uses custom viewport shapes directed toward child joints, including branching chains. Original rest axes, joint positions, weights and animation are retained. Turn it off to restore the original display. Edit Mode continues to show original bone axes. Display helpers are unlinked from scenes and excluded from selected-object FBX export.
- Initial reception adopts FBX frame rate and available animation range. Export bakes the current Blender scene range and active animation. Review playback range before sending.
- Sync reports completion after native Mobu Busy → Ready; check the Mobu scene for any application-specific import issues. A disconnected native link can remain listed until the process closes or sending reports a failure.
- Verified with Blender 5.2.0 LTS and MotionBuilder 2026.1. Other declared years are configurable; actual Mobu 2023/2024/2025/2027 operation has not been end-to-end verified.

## Runtime and build

The x64 .NET Framework host source is `probe/NativeHost.cs`. Build with the Windows .NET Framework C# compiler, `/target:winexe /platform:x64 /r:System.Web.Extensions.dll`, output to `blender_send2/bin/Send2MobuHost.exe`. Run `tools/build.py` with Python to create the add-on ZIP. The executable contains transport code only, no FBX IO or Autodesk binaries.

Runtime files/logs are under `%LOCALAPPDATA%/SaintMocap/Send2Mobu/<identity>/session-*`. The host is tied to its Blender parent process. Retained session files may be removed manually while Offline.

## Validation

Run each test using Blender `--background --factory-startup --python-exit-code 1 --python <test>` from this directory:

- `tests/blender_smoke.py`: static mesh roundtrip, persistent object identity, repeated update, guarded rejection and ten registration identities.
- `tests/export_paths.py`: blank path, extension handling, directory rejection and nested paths.
- `tests/agent_lifecycle.py`: real native host startup/shutdown, both identities, duplicate Online, crash detection/restart and add-on unregister cleanup. Uses isolated registrations.
- `tests/rig_roundtrip.py`: repeated rig/action updates, skin weights and armature links.
- `tests/blender_first_blender.py`: starts from Blender without any prior Mobu Send To, preserves the current Mobu scene, receives a native Mobu update into the original Blender object, then sends again. Set `SEND2_TEST_AUTOLAUNCH=1` to exercise automatic launch with no Mobu running. `tests/blender_first_mobu.py` is a diagnostic scene observer, not a runtime dependency.
- `tests/new_file_receive.py`: verifies a real new unsaved .blend, old data removal, preservation of the native host and settings, repeat updates, child-directed bone shapes and unchanged rest matrices. Run `tests/rig_roundtrip.py` first to generate its FBX fixture.
- `tests/armature_selection.py`: selecting an armature exports all of its bound meshes, includes mesh-parent dependencies, deduplicates objects and preserves mesh-only selection behavior; tests shared armature data, other-scene exclusion and hidden-dependency errors.
- `tests/native_sync_blender.py`: launches its own disposable Mobu scene through `tests/native_sync_mobu.py`, imports a rig and skinned mesh, changes geometry/object position and a bone animation key, sends through native SynHub, checks Mobu world coordinates, then changes/adds objects in Mobu and verifies a name-based merge back in Blender. Includes a pre-existing unrelated same-name Blender object. Test scripts are diagnostics only and are not installed into Mobu.

Native integration variants: environment `SEND2_TEST_PRODUCT=3ds Max`, `SEND2_TEST_YEAR=2027`, or `SEND2_TEST_SYSTEM=1` (system registration, normal Mobu launch). Run these sequentially; the test uses shared diagnostic filenames. No Maya/Max processes are launched. Native runtime operation depends only on Blender, .NET Framework and the selected installed MotionBuilder.
