# Saint's MobuDisplayFix 使用說明 / User Manual

本工具是 MotionBuilder 中的場景顯示修正與清理利器，旨在解決骨骼顯示比例異常、垃圾節點堆積以及透明材質顯示錯誤等常見導入問題。

This toolkit is an essential viewport display correction and scene cleanup utility in MotionBuilder, designed to resolve bone display scale anomalies, scene clutter, and transparency rendering issues.

---

## 1. 核心功能模組 / Key Functional Modules

### 🦴 骨骼顯示尺寸修正 (Display Size Fix)
* **功能 / Purpose**：一鍵修正 Skeleton 和 Null 的顯示尺寸（預設值為 1.0）。
  * Batch fix display sizes of Skeletons and Nulls to a target value (default: 1.0).
* **主要功能 / Key Actions**：
  * **Target Size**: 指定目標顯示大小（例如 1.0 或 0.5）。
  * **Skeleton / Null / Selected Only**: 勾選要套用的對象（骨骼、空物件）與是否只處理選取節點。
  * **Select Oversized (Dry-Run)**: 自動選取場景中尺寸不符的骨骼，並在控制台（Python Console）輸出詳細的預覽報表。
  * **Fix Display Size**: 一鍵執行尺寸重置。
* **應用場景 / Use Case**：解決從 Blender/Maya 匯出 FBX 至 MotionBuilder 後，骨骼與空物件顯示尺寸過大（通常大到 100 倍遮擋畫面）的問題。
  * Solves the oversized display issue (often 100x too large, blocking the viewport) of bones and nulls imported from Blender or Maya.

### 🧹 場景清理與模型著色器工具 (Clean Scene & Utilities)
* **Delete Lights (刪除燈光)**：
  * 一鍵清除場景中所有自訂燈光，保持大綱與場景清爽。
  * Delete all custom lights in the scene with a single click to keep the scene clean.
* **Delete Cameras (刪除攝影機)**：
  * 一鍵清除場景中的自訂攝影機。
  * Delete all custom cameras in the scene.
  * **安全保護 (Safety Check)**：自動過濾並保留內建的 Producer 系統攝影機（如 Producer Perspective/Front 等），避免刪除核心系統相機。
  * Automatically filters and retains MotionBuilder's internal Producer cameras to prevent system errors.
* **Set All Models: Texture + Shader (模型貼圖+著色器模式)**：
  * 一鍵將所有模型的 ShadingMode 設為 `ShadingAll`（包含著色器與貼圖的完整顯示），同時將 Viewport 顯示模式切換為 Texture 模式。
  * Set all models' shading mode to `ShadingAll` (lighted + shaded + textured) and switch the viewport to Texture display mode in one click.
* **Enable Transparency (Accurate) (啟動精確透明度)**：
  * 清除選取（或所有）模型原有的 Shaders，並套用一個全新 `FBShaderLighted`，且透明度運算模式設為精確透明度（`Accurate Transparency`）。
  * Replaces current shaders on models with a Lighted shader configured for Accurate Transparency. Supports the "Selected Only" filter.

---

## 2. 操作流程建議 / Recommended Workflow

### 流程 A：處理全新導入的模型骨骼 / Workflow A: Fixing Imported Bone Sizes
1. 在 `Target Size` 輸入想要的顯示大小（預設 1）。
   * Input the desired size in `Target Size` (default: 1).
2. 點擊 **Select Oversized (Dry-Run)** 檢查並預覽將被修改的骨頭。
   * Click **Select Oversized (Dry-Run)** to select and inspect the bones to be modified.
3. 點擊 **Fix Display Size** 完成尺寸修復。
   * Click **Fix Display Size** to apply.

### 流程 B：一鍵快速清理場景與透明度修正 / Workflow B: Scene Clean-up & Transparency Fix
1. 點擊 **Delete Lights** 與 **Delete Cameras** 移除多餘的導入垃圾。
   * Click **Delete Lights** and **Delete Cameras** to remove imported clutter.
2. 點擊 **Set All Models: Texture + Shader** 確保貼圖能被正常照亮與顯示。
   * Click **Set All Models: Texture + Shader** to ensure textures are correctly displayed and lit.
3. 若角色衣服或頭髮的透明顯示有破面/穿幫，勾選 **Selected Only** 並選取該模型，點擊 **Enable Transparency (Accurate)**。
   * If the character's hair or clothing renders transparency incorrectly, check **Selected Only**, select the model, and click **Enable Transparency (Accurate)**.

---

## 3. 常見問答 (Q&A)

**Q: 為什麼按了 Delete Cameras 後有些相機沒有被刪掉？**  
A: 工具會故意保留 Producer 系統相機（例如 Perspective, Front 等），這些是 MotionBuilder 的內建相機。此保護機制能防範系統因遺失相機而崩潰。  
* **Q: Why are some cameras not deleted after clicking Delete Cameras?**  
* A: The toolkit intentionally retains default Producer cameras (Perspective, Front, etc.). This protective mechanism prevents viewport layout crashes.

**Q: 精確透明度 (Accurate Transparency) 與一般透明度有什麼差別？**  
A: 精確透明度會提供更好的深度排序與半透明混色效果，非常適合解決 3D 動漫角色頭髮、睫毛與半透明衣物等容易產生的透明度遮擋穿幫（sorting error）問題。  
* **Q: What is the difference between Accurate Transparency and standard transparency?**  
* A: Accurate Transparency provides superior depth sorting and translucent blending, making it ideal for resolving sorting errors common in anime character hair, eyelashes, and clothing.

---
**由 小聖腦絲 × Antigravity 協作記錄**  
**Collaboratively recorded by Saint & Antigravity**  
[小聖腦絲的粉專 / Saint's Facebook Page](https://www.facebook.com/hysaint3d.mocap)
