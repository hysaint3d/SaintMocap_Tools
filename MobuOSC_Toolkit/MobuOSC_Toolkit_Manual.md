# MobuOSC Toolkit 使用說明 / User Manual

`MobuOSC_Toolkit` 是 MotionBuilder 中強大的雙向 OSC（Open Sound Control）資料傳輸與管理器。支援將外部的 OSC 資料實時導入並烘焙至 MotionBuilder 的自訂屬性上，同時也支援將場景中指定角色的 TRS（位移、旋轉、縮放）與動畫屬性以實時 OSC 封包發送至外部軟體（如 Unreal Engine、Unity 或其他 DCC 工具）。

`MobuOSC_Toolkit` is a powerful bidirectional OSC (Open Sound Control) manager for MotionBuilder. It supports streaming external OSC data into MotionBuilder to drive custom animatable properties, and sending real-time TRS (Translation, Rotation, Scaling) plus animatable properties of selected scene objects as OSC messages to external apps (such as Unreal Engine, Unity, or other DCC tools).

---

## 1. 核心功能 / Key Features

### 📥 OSC 接收端 (OSC Receiver)
* **實時監聽 (Real-time Listening)**：自訂 Bind IP 與 Port，實時解析傳入的 OSC 浮點數、整數與字串封包。
  * Customize Bind IP and Port to parse incoming OSC float, integer, and string packets in real-time.
* **動態通道生成 (Dynamic Channel Generation)**：根據接收到的 OSC Address，自動在 `OSC_Data` Null 節點上生成對應的自訂屬性。
  * Automatically creates corresponding custom properties on the `OSC_Data` Null node based on incoming OSC addresses.
* **模型關係對接 (Constraint Mapping)**：一鍵建立關係約束器（Relation Constraint），將接收到的資料傳遞至選定角色的表情夾（Blendshape）或屬性。
  * One-click creation of Relation Constraints to map received data directly to your target character's blendshapes or custom properties.

### 📤 OSC 發送端 (OSC Sender)
* **物件串流 (Object Streaming)**：支援添加多個場景物件，實時發送其世界座標或局部座標的 TRS 數據。
  * Add multiple scene objects to stream their world or local TRS (Translation, Rotation, Scaling) values.
* **動畫與自訂屬性發送 (Animated & User Properties)**：自動掃描並實時串流發送物件上所有已動畫化（Animated）或使用者自訂（User Properties）的數值。
  * Scan and stream all animatable or user-defined custom properties of the selected objects.
* **發送幀率限制 (FPS Limit)**：可自由調整發送頻率（如 30 FPS、60 FPS），以符合接收端軟體的頻寬要求。
  * Adjust streaming rate (e.g. 30 FPS, 60 FPS) to balance network bandwidth and performance.

---

## 2. 接收端操作流程 / Receiver Workflow

1. **連線監聽 (Bind & Connect)**:
   * 在 **Receiver** 區域輸入本機 IP 與 Port（例如 `127.0.0.1` 埠口 `10001`）。
   * 點擊 **[Connect]** 啟動接收監聽。
   * Enter local IP and Port (e.g. `127.0.0.1` port `10001`) in the **Receiver** panel, then click **[Connect]** to start listening.
2. **建立資料通道 (Create Channels)**:
   * 當開始接收資料後，點擊 **[Create Data Channels]**。
   * 系統會自動在場景中生成名為 `OSC_Data` 的 Null 節點，並為接收到的每個 OSC 參數生成一個同名屬性。
   * Once incoming data is detected, click **[Create Data Channels]**. The tool generates an `OSC_Data` Null node in your scene and populates it with custom properties for each unique OSC address received.
3. **對接至目標角色 (Map to Character)**:
   * 在場景中選取要接收控制的模型（如角色的臉部 Mesh）。
   * 點擊 **[Connect Channels to Selected Model]**，工具會自動建立 Relation Constraint 將資料對接。
   * Select your target mesh in the scene, and click **[Connect Channels to Selected Model]**. The toolkit automatically wires them together via a Relation Constraint.

---

## 3. 發送端操作流程 / Sender Workflow

1. **加入發送物件 (Add Send Objects)**:
   * 在 MotionBuilder 場景中選取一或多個需要發送數據的骨頭、Null 或模型。
   * 點擊 **[Add Selected Object]** 將其加入發送清單。
   * Select one or more bones, Nulls, or meshes in the MotionBuilder scene, then click **[Add Selected Object]** to add them to the stream list.
2. **設定目標與幀率 (Configure Destination & FPS)**:
   * 輸入接收端軟體所在的 `Target IP` 與 `Port`。
   * 在 `FPS Limit` 輸入框設定發送幀率（預設為 60）。
   * Specify the `Target IP` and `Port` of the receiver application, and set the desired `FPS Limit` (default: 60).
3. **開始發送 (Start Streaming)**:
   * 點擊 **[Start Streaming]**。狀態列會顯示當前正在發送的訊息數量。
   * Click **[Start Streaming]**. The status label will update to show active packets being sent.

---

## 4. 資料格式與規範 / Data Format & Constraints

* **自動縮放機制 (Auto-Scaling)**:
  * 當接收到的 OSC Address 中包含 `Blend`、`Expr` 或 `VMC` 字眼時，工具會自動將該數值**乘以 100**，以適應 MotionBuilder Blendshape 預設的 $0.0 \sim 100.0$ 範圍。
  * If the incoming OSC address contains `Blend`, `Expr`, or `VMC`, the value is automatically **multiplied by 100** to align with MotionBuilder's default $0.0 \sim 100.0$ blendshape range.
* **位址命名轉換 (Address Mapping)**:
  * 系統會自動將 OSC 位址中的斜線 `/` 與空格轉換為底線 `_`。例如：`/Face/MouthOpen` 會在 `OSC_Data` 上生成名為 `Face_MouthOpen` 的屬性。
  * The system translates slashes `/` and spaces in OSC addresses into underscores `_`. For example, `/Face/MouthOpen` becomes `Face_MouthOpen` on the `OSC_Data` node.

---

## 5. 常見問題排查 / Troubleshooting

* **Q: 點擊 Connect 後，沒有建立自訂屬性？**
  * A：請確保發送端（如手機或其他軟體）已經開始發送 OSC 數據。只有在 MotionBuilder 實際接收到至少一筆封包後，點擊 **[Create Data Channels]** 才能成功抓取並生成對應屬性。
  * Ensure that the sender app is actively streaming. The tool needs to receive at least one packet before **[Create Data Channels]** can detect the address templates.
* **Q: 關閉視窗後，後台仍在發送或接收數據？**
  * A：本工具在啟動時，會自動清除舊有的 idle 事件與 Socket 連線。如果您想手動停止，請務必在關閉介面前點擊 **[Disconnect]** 與 **[Stop Streaming]**。
  * The toolkit automatically performs cleanup of previous background idle loops and sockets on startup. To manually stop them, make sure to click **[Disconnect]** and **[Stop Streaming]** before closing the GUI.

---
**由 小聖腦絲 × Antigravity 協作記錄**  
**Collaboratively recorded by Saint & Antigravity**  
[小聖腦絲的粉專 / Saint's Facebook Page](https://www.facebook.com/hysaint3d.mocap)
