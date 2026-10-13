# SaintMocap Blender Tools

- **[Saint2Mobu](Saint2Mobu/)**: FBX model, rig and animation transfers with MotionBuilder, including return updates. Current build: **0.4.0 Beta**. Blender add-on name: **SaintMocap Send2Mobu**.
- **[SaintMocap Live Link Receiver](BlenderLiveLink/)**: real-time MotionBuilder animation reception into existing Blender armatures. Current build: **0.5.3 Experimental**.

Each add-on can be installed independently. See its README for installation and operation. Install the individual add-on ZIP without extracting it first.

## Releases

- [Saint2Mobu 0.4.0 Beta 1](https://github.com/hysaint3d/SaintMocap_Tools/releases/tag/saint2mobu-v0.4.0-beta.1)
- [Blender LiveLink Receiver 0.5.3 Experimental Beta 1](https://github.com/hysaint3d/SaintMocap_Tools/releases/tag/blender-livelink-v0.5.3-beta.1)

Download the installation ZIP under **Assets** on each release page. Both are prereleases.

## Updating from local development

The local `SaintMocap_LAB/Blender_Send2` and `SaintMocap_LAB/Blender_LiveLink` projects are the development sources. This public repository contains their published copies, current installation packages and public documentation. They do not synchronize automatically.

From this repository root, run:

```powershell
python tools/sync_blender.py --source-root C:/path/to/SaintMocap_LAB
```

The command copies project source and rebuilds both installation ZIPs. It retains this repository's README, packaging and publish documentation, excludes runtime/cache/old build outputs, and removes published source files that disappeared upstream. Use `--dry-run` to preview source changes. Review `git diff` and then commit/push. Do not edit published source separately from the development source.
