# Saint2Mobu 0.4.2 validation - 2026-10-13

Selecting an Armature now includes all meshes in the current scene whose Armature modifier targets that exact object, even when the meshes have another parent. Dependencies and duplicate selections are deduplicated. Mesh-only selection still includes its rig and parents without automatically adding all sibling skins. Hidden/unselectable dependencies are named in a pre-export error rather than silently omitted.

Passed:
- armature_selection.py: two bound meshes (including a different-parent mesh), duplicate Armature modifiers, two rigs sharing the same armature data, parent dependencies, mesh-only scope, other-scene exclusion, original selection/name restoration and hidden-mesh error. Native FBX reimport contains exactly one rig, both skinned meshes and the required parent, with skin weights retained.
- native_sync_blender.py with SEND2_TEST_INSTALLED=1: only the imported armature is selected before pressing Send to Mobu; Mobu receives the bound mesh geometry/transform and bone animation edits; subsequent Mobu Update merges back into the original Blender objects.
- The seven packaged files match project source and the installed add-on.

Includes the 0.4.1 new-file and bone-display fixes. Source, native host and FBX IO otherwise retain their existing behavior.

ZIP SHA256: 62524a65b7422dd4eb36f45f4f82d524f2af4c377154907670bf4366147ac4a7
