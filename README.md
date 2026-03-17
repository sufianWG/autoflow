# ⚡ AutoFlow v1.1 — PyAutoGUI Task Automation Builder

A powerful desktop GUI application to build, manage, and run screen automation workflows — **no coding required**.

---

## ✨ Features Overview

| Feature | Description |
|---|---|
| 🗂️ Tasks | Create unlimited named tasks, each with its own steps and settings |
| 📋 Sections | Organise steps into multiple sections within a task |
| 🔁 Loops | Loop the full task N times; optionally loop individual sections independently |
| 🚀 Launcher Icon | Auto-click an app icon **once** before the loop starts |
| 👁️ Coordinate Preview | Visualise one or all step coordinates overlaid on a live screenshot |
| ⏸️ Auto-Pause | Automatically pauses when mouse or keyboard activity is detected |
| ⏸️ Manual Pause/Resume | Pause and resume mid-run at any time |
| ⏹️ Stop | Instantly stop a running task |
| 📍 Visual Coord Picker | Click directly on screen to capture coordinates |
| 💾 Auto-save | All data saved automatically to `autoflow_tasks.json` |

---

## 🎬 Action Types

| Action | Coordinate? | Description |
|---|---|---|
| **Click** | ✅ | Moves mouse to (x, y) and clicks |
| **Input** | ✅ | Clicks field, selects all (`Ctrl+A`), then types text |
| **Scroll** | ✅ | Scrolls at (x, y) — up / down / left / right |
| **Typewrite** | ✅ | Clicks field and types character-by-character |
| **Press Enter** | ❌ | Simulates pressing the `Enter` key |
| **Keyboard Shortcut** | ❌ | Fires a preset shortcut (Ctrl+C, Alt+Tab, F5 … 60+ shortcuts) |

---

## 📦 Installation

```bash
# 1. Clone the repository
git clone https://github.com/sufianWG/autoflow.git
cd autoflow

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
python autoflow.py
```

> **Optional:** Install `pynput` for keyboard activity detection (auto-pause):
> ```bash
> pip install pynput
> ```

---

## 🚀 How to Use

### 1 — Create a Task
Click **＋ New Task** (top-right). Give it a name like `Login to Amazon` or `Fill Form`.

---

### 2 — Configure the Launcher Icon *(optional)*
Enable the **🚀 Launcher Icon** toggle on the task card.  
Click **📍 Set Position** and click the app icon on your screen.  
AutoFlow will click that icon **once** before the task loop begins — useful for re-opening an app each iteration.

---

### 3 — Enable Looping *(optional)*
Tick **🔁 Enable Loop** and set the **Loop Count** (number of full-task iterations).  
When looping is enabled you can also add multiple **Sections** and set a per-section loop count (0 = no section loop).

---

### 4 — Add Sections *(optional)*
Click **+ Add Section** to add more sections inside a task.  
Each section can have its own steps and its own loop count independent of the task loop.

---

### 5 — Add Steps
Click **+ Step** on any section header. The Step Editor opens:

1. **Description** — optional label for your reference
2. **Action Type** — choose from the 6 action types above
3. **Coordinate** — click **📍 Pick from Screen** to capture (x, y) by clicking on screen  
   or click **👁 Preview** to instantly see where the current values land
4. **Text** — (Input / Typewrite only) enter the text to type
5. **Scroll settings** — direction and click amount (Scroll only)
6. **Keyboard Shortcut** — select from 60+ grouped shortcuts (Keyboard Shortcut only)
7. **Delay** — seconds to wait after this step executes
8. Click **Save Step**

---

### 6 — Preview Coordinates

| Button | Where | What it does |
|---|---|---|
| **👁 Preview** | Step Editor | Shows the current X/Y on-screen without closing the editor |
| **👁** (row button) | Each step row | Previews that single step's coordinate on screen |
| **👁 Preview All Coords** | Task header | Shows **all** coordinates from every step + launcher at once |

The overlay renders a **fullscreen screenshot** with colour-coded crosshair markers, filled circles, and tooltip labels showing action type and position.  
Click anywhere or press `ESC` to dismiss.

---

### 7 — Run the Task
Click **▶ Run Task**. AutoFlow will:
- Click the Launcher Icon (if enabled)
- Execute each section's steps in order
- Respect per-section and task-level loop counts
- Show live progress in the status bar
- Report ✅ success or ❌ errors

---

### 8 — Pause / Resume / Stop

| Control | Behaviour |
|---|---|
| **⏸ Pause** | Manually pauses between steps; click again to resume |
| **⚡ Auto-Pause** | Triggers automatically when mouse or keyboard activity is detected; auto-resumes after 2.5 s of idle |
| **⏹ Stop** | Immediately stops the task at the next step boundary |

---

## ⚙️ Data Storage

All tasks, sections, steps and settings are saved automatically to `autoflow_tasks.json` in the app directory.  
Back up or copy this file to transfer your workflows between machines.

---

## 🛡️ Safety

- **Auto-Pause** — any unexpected mouse movement or keypress pauses the automation immediately.
- **Manual Stop** — the **⏹ Stop** button halts execution at any time.
- `pyautogui.FAILSAFE = False` — top-left corner failsafe is disabled in favour of the built-in Auto-Pause system.
- `pyautogui.PAUSE = 0.05` — minimal inter-action pause for speed; add per-step delays as needed.

---

## 🖥️ Requirements

- Python **3.8+**
- Windows / Linux / macOS
- `pyautogui`
- `Pillow`
- `pynput` *(optional — for keyboard auto-pause)*

---

## 📁 Project Structure

```
autoflow/
├── autoflow.py            # Main application (all-in-one)
├── requirements.txt       # Python dependencies
├── autoflow_tasks.json    # Auto-generated task data (created on first run)
└── README.md
```

---

## 📝 Changelog

### v1.1 — March 2026
- ➕ **Press Enter** action type
- ➕ **Keyboard Shortcut** action type with 60+ presets across 6 categories
- ➕ **Sections** — organise steps into named sections inside a task
- ➕ **Per-section loop count** — loop individual sections independently
- ➕ **Task-level Loop** — repeat the entire task N times
- ➕ **Launcher Icon** — auto-click an app icon before the task loop
- ➕ **Auto-Pause Manager** — mouse & keyboard activity detection with auto-resume
- ➕ **Manual Pause / Resume / Stop** controls
- ➕ **👁 Coordinate Preview overlay** — single step and all-task preview
- ➕ **👁 Preview button** in Step Editor
- 🎨 Catppuccin Mocha colour theme

### v1.0 — Initial Release
- Core task / step builder with Click, Input, Scroll, Typewrite
- Visual coordinate picker
- Auto-save to JSON

---

*Built with ❤️ using Python, Tkinter & PyAutoGUI*
