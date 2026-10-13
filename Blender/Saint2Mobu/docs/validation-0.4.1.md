# Saint2Mobu 0.4.1 validation - 2026-10-13

Changes:
- Native Mobu Send as New Scene opens a genuinely new, empty, unsaved .blend.
- Existing file contents are cleared. The internal file load bypasses this add-on's normal disconnect handler; Online and the same native host process remain active.
- Brief Windows heartbeat-file sharing violations reuse a fresh, verified host snapshot; stale snapshots still report Unresponsive.
- Transfer settings are restored in the new file. Normal user file loading still disconnects.
- Point Bones to Children adds child-directed custom viewport shapes, with branching and terminal shapes, without changing original bone/rest/pose matrices.
- Unlinked display helpers do not enter sync collections or selected-object FBX exports. Original/custom display can be restored with the panel checkbox.

Passed on Blender 5.2.0 LTS / MotionBuilder 2026.1:
- rig_roundtrip.py: three updates retain original objects, parents, weights, armature links and animated bones.
- new_file_receive.py: real new file, old data cleared, unsaved filepath reset, same native process and directory, settings retained, repeated Current updates, correct child-tip positions, no helper leaks, original rest matrices retained, second New, ordinary load disconnect.
- agent_lifecycle.py: original lifecycle coverage plus temporary sharing-lock recovery and stale-heartbeat rejection.
- Custom display objects are evaluated by the Blender dependency graph while remaining unlinked from the scene.
- blender_smoke.py: static roundtrip, repeated update, guarded rejection and registration.
- native_sync_blender.py: real Mobu New -> new Blender file -> Blender geometry/bone animation update -> native Mobu Current update and new object. Existing synced object identities and an unrelated same-name object added after New are retained on Current updates.

Display changes apply in Object/Pose Mode. Edit Mode retains original FBX bone axes. No change to FBX importer/exporter choice or native transport ABI.
