# Twist Bone Calculator v5 - 使用說明手冊 / User Manual
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 📖 為什麼需要這個工具？ / Why is this tool needed?

在現代的遊戲與動畫管線中（如 **Unreal Engine Metahumans** 或 **Character Creator CC4 / AccuRig** 骨架），**Twist Bones（扭轉骨骼）** 通常是以**分支（Sibling/Branch）** 結構附著在主骨骼旁，以優化遊戲引擎內的物理/動畫解算。

In modern game and animation pipelines (such as **Unreal Engine Metahumans** or **Character Creator CC4 / AccuRig** skeletons), **Twist Bones** are usually attached as **sibling/branch** structures next to the main bones to optimize physical/animation simulation inside game engines.

然而，MotionBuilder 的 **HumanIK (HIK)** 系統只接受嚴格的**線性階層**扭轉骨骼。如果直接將分支 Twist 骨骼映射給 HIK，會導致 Retargeting 解算錯誤；如果不映射，動捕或 Retargeting 時 Twist 骨骼就不會跟著扭轉，導致手肘或大腿在大角度扭轉時產生極難看的「**糖果紙擰扭破面（Candy-wrapper effect）**」。

**本工具正是為此而生！** 它能讓您保持 HIK 角色定義的乾淨，並透過 Python 自動在背景為分支 Twist 骨骼建立完美的 **Relation Constraints（關係約束）**。

---

## 🌟 v5 新功能 / What's New in v5

### 1. 整合角色骨架 JSON 模板 (Template Integration)
**Skeleton** 下拉選單現在會自動掃描 `Templates/` 資料夾（與 HIK Character Toolkit 共用同一套模板），並動態顯示所有可用的角色規格，包括：
- Unreal Engine Mannequin / MetaHuman
- AccuRig / Character Creator CC4
- VRoid Studio
- Blender Auto-Rig Pro / Rigify
- Maya Advanced Skeleton
- Daz3D Genesis 8
- 3dsMax Biped
- MMD / VMC
- 以及任何自訂角色模板！

若沒有找到 `Templates/` 資料夾，選單下方仍保有「[ Legacy ]」傳統預設規則作為備援。

### 2. 智慧骨骼軸向自動偵測 (Auto Twist Axis Detection) ⭐
**Twist Axis** 下拉選單新增了第一個選項：`Auto (detect from bone direction)`。

**原理：**  
骨骼的扭轉軸通常就是指向其子關節的方向軸。例如：
- 前臂（Forearm）的子關節是手腕（Hand），若手腕在前臂的**局部座標**中偏移量最大的是 X 軸（如 `[24.5, 0.0, 0.0]`），則扭轉軸自動設定為 **X 軸**。
- 大腿（Thigh）的子關節是膝蓋（Calf），若膝蓋偏移量最大的是 Y 軸，則扭轉軸自動設定為 **Y 軸**。

此功能能支援「手臂和腿使用不同扭轉軸」的複雜骨架，**完全免除手動試軸的麻煩**！

---

## 🛠️ 核心功能亮點 / Key Features

1. **整合骨架模板（JSON Template Integration）**：自動讀取 `Templates/` 目錄中的骨架定義，適用任何角色規格，完全免除硬編碼需求。
2. **智慧軸向自動偵測（Auto Axis Detection）**：分析驅動骨骼的子關節局部位置，自動判斷最適合的扭轉軸向（X/Y/Z）。
3. **模糊配對演算法（Fuzzy Twist Bone Matching）**：從模板骨骼名稱中提取骨架段名、濾除左右側標記，再以模糊關鍵字配對 Twist 骨骼，支援 `twist`、`tw`、`roll` 等常見關鍵字。
4. **手部驅動模式 (Hand/Wrist Driver Mode)**：支援「手部/手腕骨骼驅動前臂扭轉」選項，更符合人體工學。
5. **自動命名空間檢測（Auto-Detect Namespace）**：點擊 **Auto** 自動提取活躍 HIK 角色或選中骨骼的命名空間。
6. **線性權重分佈與輔助節點**：多根 Twist 骨骼自動進行線性漸變權重分佈，並建立隱藏的 `_TwistW_` 權重輔助節點確保計算穩定。
7. **一鍵控制面板**：支援一鍵生成、一鍵清除。

---

## 🚀 快速使用指南 / Quick Start Guide

### 第一步：在 MotionBuilder 中運行工具 / Step 1: Run the Tool
1. 在 MotionBuilder 的 **Python Editor** 中打開 `MobuTwistBone_Calculator.py`。
2. 點擊 **Execute** 運行，即可看到獨立的 GUI 控制面板。

### 第二步：配置參數 / Step 2: Configure Parameters

| 參數 | 說明 |
|------|------|
| **Skeleton** | 選擇與您角色對應的骨架模板。工具會自動掃描 `Templates/` 目錄填入選單，若無可用模板則顯示傳統規則（[Legacy]）。 |
| **Forearm Twist driven by Hand/Wrist** | ✅ 勾選（建議）：前臂扭轉由手腕骨骼驅動，解算更穩定。❌ 取消：由前臂骨骼本身驅動（傳統模式）。 |
| **Twist Axis** | `Auto`（建議）：自動從骨骼子關節位置判斷扭轉軸。`X / Y / Z`：手動指定固定軸向。 |
| **Base Weight** | 扭轉主關節旋轉對 Twist 骨骼的最大影響權重（範圍 0.01 – 1.0，預設 0.5）。 |
| **Namespace** | 點擊 **Auto** 自動偵測命名空間，或手動輸入（如 `Char`）。 |

### 第三步：偵測與生成 / Step 3: Detect & Build
1. **Auto-Detect Twistbone**：執行 Dry-Run，在 Python Console 列印所有匹配的骨骼對與自動偵測的軸向。
2. **Build Twist constraint**：正式建立 Relation Constraint 與輔助節點，Twist 骨骼即時跟隨扭轉。
3. **Remove All Twist Constraints**：一鍵安全清除所有工具產生的約束與輔助節點。

---

## 📦 導出至 Unreal Engine / 遊戲引擎的工作流 / Exporting Workflow

1. 動畫或動捕 Retargeting 調整完畢後，執行 **Plot Character**（將動畫烘焙至骨骼）。
2. 烘焙過程中，MotionBuilder 會自動將關係約束計算出的扭轉角度**精準烘焙為關鍵幀**，寫入 `twist_01` 等骨骼中。
3. 導出 FBX 並匯入 Unreal Engine。
4. **效能優化**：由於 Twist 動畫已完整烘焙在 FBX 中，遊戲引擎執行時不需要在 AnimGraph 運算任何額外 RBF 或 Twist 節點，大幅節省 CPU 資源！

---

## 🔍 如何新增自訂角色模板 / How to Add Custom Templates

只需將您的 JSON 模板（格式與 HIK Character Toolkit 相同）放入同目錄下的 `Templates/` 資料夾，重新執行工具，新模板會自動出現在 **Skeleton** 下拉選單中。

### 模板 JSON 格式範例 / Template Format Example
```json
{
    "DisplayName": "My Custom Rig",
    "Description": "My custom character rig naming.",
    "LeftForeArmLink": { "Name": "forearm_l" },
    "LeftHandLink":    { "Name": "hand_l" },
    "LeftArmLink":     { "Name": "upperarm_l" },
    "LeftLegLink":     { "Name": "calf_l" },
    "LeftUpLegLink":   { "Name": "thigh_l" },
    "LeftFootLink":    { "Name": "foot_l" },
    ...
}
```

---

[小聖腦絲的粉專 / Saint's Facebook Page](https://www.facebook.com/hysaint3d.mocap)
