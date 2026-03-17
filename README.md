# ⚡ AutoFlow — PyAutoGUI Task Automation Builder

A powerful desktop GUI application to build, manage, and run screen automation workflows without writing any code.

---

## ✨ Features

- **Create unlimited Tasks** with custom names
- **Build steps visually** — todo-list style step builder per task
- **4 Action Types** per step:
  | Action | Description |
  |---|---|
  | Click | Moves mouse to coordinate and clicks |
  | Input | Clicks field, selects all, types text |
  | Scroll | Scrolls at a coordinate (up/down/left/right) |
  | Typewrite | Clicks field and types character-by-character |
- **📍 Visual Coordinate Picker** — click directly on screen to capture coordinates (no manual calculation!)
- **Per-task Run button** — each task has its own `▶ Run Task` button
- **Reorder steps** using ↑ ↓ buttons
- **Edit/Delete** steps and tasks anytime
- **Auto-save** — all tasks and steps saved to `autoflow_tasks.json`
- **Failsafe** — move mouse to top-left corner to stop any running automation

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

---

## 🚀 How to Use

### Step 1 — Create a Task
Click the **＋ New Task** button at the top right. Enter a meaningful name (e.g. `Login to Amazon`, `Fill Form`).

### Step 2 — Add Steps
Click **+ Add Step** on any task card. The step editor opens:

1. **Enter a description** (optional, for your reference)
2. **Select an Action Type** (Click / Input / Scroll / Typewrite)
3. **Pick the coordinate** — click 📍 Pick from Screen, your screen will dim and show crosshair. Click exactly where the action should happen.
4. **For Input/Typewrite** — enter the text to type
5. **For Scroll** — choose direction and amount
6. **Set a delay** (seconds to wait after this step completes)
7. Click **Save Step**

### Step 3 — Run the Task
Click **▶ Run Task**. AutoFlow will:
- Hide the running indicator
- Execute each step in order
- Show step progress in the status bar
- Report success or any errors

---

## ⚙️ Data Storage

All tasks and steps are saved automatically to `autoflow_tasks.json` in the app directory. You can back up this file or share it between machines.

---

## 🛡️ Safety

- **Failsafe enabled**: Move your mouse rapidly to the **top-left corner** of the screen at any time to stop the automation immediately.
- `pyautogui.PAUSE = 0.3` — 300ms pause between actions for stability.

---

## 🖥️ Requirements

- Python 3.8+
- Windows / Linux / macOS
- `pyautogui`
- `Pillow`

---

## 📁 Project Structure

```
autoflow/
├── autoflow.py            # Main application
├── requirements.txt       # Python dependencies
├── autoflow_tasks.json    # Auto-generated task data (created on first run)
└── README.md
```

---

*Built with ❤️ using Python, Tkinter & PyAutoGUI*
