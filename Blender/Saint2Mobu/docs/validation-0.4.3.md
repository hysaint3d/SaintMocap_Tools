# Saint2Mobu 0.4.3 validation - 2026-10-13

Root cause: the interactive Blender timer context can lose selected_objects after wm.read_homefile. Background/manual polling tests did not expose the same UI reload timing.

Fix:
- Cache incoming FBX before opening the new file.
- Journal new_file_started in the incoming request and return from the timer after the file load.
- Import on the next tick using a fresh window/screen/area context override. Wait if no usable window context exists yet.
- Retrying an import that already opened its new file does not repeatedly clear the current file.
- Select imported assets after initial reception and report empty imports as an error.
- Save failed receive tracebacks in the local session receive-errors.log.

Verified:
- Actual user Blender 5.2 interactive UI: retried the previously failed cached FBX after confirming the scene was empty. The new file now contains 23 scene objects: 21 meshes, 1 armature and 1 empty. Receive error is empty and no failed request remains.
- new_file_receive.py: verifies the explicit deferred phase, request journal, next-call import, same native process, repeated Current updates, display helpers and regular load disconnect.
- native_sync_blender.py from installed 0.4.3: real native Mobu New -> deferred Blender import -> armature-only send with skin/animation -> native Mobu Current merge and added object. Used emulated Max 2027 with actual Mobu 2026.1 to keep the user's separate Maya 2026 session isolated.
- Installed add-on and ZIP match the seven project source/package files.

ZIP SHA256: 94953f7efdd5199fefdd19ea51fb960e4e7e1c4cb944db5901f91597e35f7ecb
