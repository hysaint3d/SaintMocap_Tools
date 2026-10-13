# 0.4.0 validation - 2026-10-13

Environment: Blender 5.2.0 LTS, MotionBuilder 2026.1, Windows x64.

Changes:
- Removed Test FBX path and the three Test buttons/operators.
- Added always-visible Send to Mobu and Send as New Scene controls.
- Discover selected installed Mobu version's processes without a prior incoming transfer.
- Native local link discovery uses AppInfo IDs and matches the chosen process ID.
- Automatically launch Mobu if none is running; retry native handshakes during startup.
- Capture selected objects and their FBX at click time; bind sent objects for name-based returns.
- Added Automatic target selection; multiple running targets require a chosen PID.
- FBX IO continues to use Blender's built-in operators only.

Passed:
- blender_smoke.py: repeated static merge, original identity, guarded rejection, registration.
- export_paths.py: blank and explicit paths, directory/extension rejection.
- agent_lifecycle.py: Online/Offline, both identities, crash/restart and unregister cleanup.
- rig_roundtrip.py: three rig/action/skin updates retain object identity and weights.
- blender_first_blender.py: Maya 2026 identity, first send to existing Mobu without prior Mobu Send To; preserves existing Mobu content, returns into original Blender object, sends again.
- blender_first_blender.py: auto-launch with Max 2027 identity and actual Mobu 2026; selection changed during startup, original captured FBX still delivered; full return and second send passed.
- native_sync_blender.py with SEND2_TEST_INSTALLED=1: installed 0.4.0 receives rig/skin, sends modified geometry and bone animation, merges Mobu edits/new object without replacing the original Blender objects.
- ZIP, project source and installed add-on contents match for all 6 packaged files.

Diagnostic Mobu Python scripts are test observers only and are not installed or packaged. Runtime needs no Mobu script/plugin and no Maya/Max executable. Other actual Mobu versions were not tested.

ZIP SHA256: 07c23e9cd4dc15a1492e1f38614c73ad6537d8eec3f4a8773f20bc8292a4e6b6
