興趣使然的以AI協作開發了一些Mobu/Mocap用的小工具，好解決教學研究或專案上所發掘的一些需求，如果剛好用得到，也請不用客氣在創用CC (CC BY-SA) 授權下使用(但使用上也請自負責任)，若有什麼問題或是有什麼建議，也歡迎提出一起討論。 2026.6.1


## Blender add-ons

| Project | Purpose | Version | Install ZIP |
| --- | --- | --- | --- |
| [Saint2Mobu](Blender/Saint2Mobu/) | Blender and MotionBuilder: bidirectional FBX Send / Update | 0.4.0 Beta | [Download](Blender/Saint2Mobu/dist/SaintMocap_Send2Mobu-0.4.0.zip?raw=true) |
| [SaintMocap Live Link Receiver](Blender/BlenderLiveLink/) | Receive MotionBuilder Live Link animation in Blender | 0.5.3 Experimental | [Download](Blender/BlenderLiveLink/SaintMocap_LiveLink_Receiver-0.5.3.zip?raw=true) |

Install each ZIP separately through Blender 5.2: **Edit > Preferences > Add-ons > Install from Disk**. See each project's README for setup and supported workflows.

Saint2Mobu currently appears in Blender as **SaintMocap Send2Mobu**, in the **Send2Mobu** sidebar tab. It requires an installed MotionBuilder and uses Blender's built-in FBX IO; Maya/3ds Max are not required. The Live Link receiver requires Epic's MotionBuilder Live Link plugin and an existing matching Blender armature.
