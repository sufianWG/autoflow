import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import os
import time
import threading
import pyautogui
from PIL import ImageGrab, ImageTk
import copy

DATA_FILE = "autoflow_tasks.json"

ACTION_TYPES = ["Click", "Input", "Scroll", "Typewrite", "Press Enter", "Keyboard Shortcut"]

# ---------------------------------------------------------------------------
# All keyboard shortcuts grouped by category.
# Each entry: (display_label, pyautogui_hotkey_args_tuple)
# ---------------------------------------------------------------------------
KEYBOARD_SHORTCUTS = {
    "\U0001f4cb  Edit": [
        ("Ctrl+C  — Copy",          ("ctrl", "c")),
        ("Ctrl+X  — Cut",           ("ctrl", "x")),
        ("Ctrl+V  — Paste",         ("ctrl", "v")),
        ("Ctrl+Z  — Undo",          ("ctrl", "z")),
        ("Ctrl+Y  — Redo",          ("ctrl", "y")),
        ("Ctrl+A  — Select All",    ("ctrl", "a")),
        ("Ctrl+D  — Delete/Deselect",("ctrl", "d")),
    ],
    "\U0001f4c2  File": [
        ("Ctrl+S  — Save",          ("ctrl", "s")),
        ("Ctrl+Shift+S  — Save As", ("ctrl", "shift", "s")),
        ("Ctrl+N  — New",           ("ctrl", "n")),
        ("Ctrl+O  — Open",          ("ctrl", "o")),
        ("Ctrl+W  — Close Tab",     ("ctrl", "w")),
        ("Ctrl+P  — Print",         ("ctrl", "p")),
        ("Ctrl+F  — Find",          ("ctrl", "f")),
        ("Ctrl+H  — Find & Replace",("ctrl", "h")),
    ],
    "\U0001f310  Browser": [
        ("Ctrl+T  — New Tab",            ("ctrl", "t")),
        ("Ctrl+Shift+T — Reopen Tab",    ("ctrl", "shift", "t")),
        ("Ctrl+Tab — Next Tab",          ("ctrl", "tab")),
        ("Ctrl+Shift+Tab — Prev Tab",    ("ctrl", "shift", "tab")),
        ("Ctrl+L  — Focus Address Bar",  ("ctrl", "l")),
        ("Ctrl+R  — Refresh",            ("ctrl", "r")),
        ("F5  — Refresh Page",           ("f5",)),
        ("Alt+Left  — Back",             ("alt", "left")),
        ("Alt+Right — Forward",          ("alt", "right")),
        ("Ctrl+Shift+I — DevTools",      ("ctrl", "shift", "i")),
    ],
    "\U0001f4bb  Window": [
        ("Alt+Tab  — Switch Window",     ("alt", "tab")),
        ("Alt+F4   — Close Window",      ("alt", "f4")),
        ("Win+D    — Show Desktop",      ("win", "d")),
        ("Win+L    — Lock Screen",       ("win", "l")),
        ("Win+Tab  — Task View",         ("win", "tab")),
        ("Ctrl+Shift+Esc — Task Manager",("ctrl", "shift", "escape")),
        ("Win+Up   — Maximize",          ("win", "up")),
        ("Win+Down — Minimize",          ("win", "down")),
        ("Win+Left — Snap Left",         ("win", "left")),
        ("Win+Right — Snap Right",       ("win", "right")),
    ],
    "\u2328\ufe0f  Text Nav": [
        ("Home   — Line Start",          ("home",)),
        ("End    — Line End",            ("end",)),
        ("Ctrl+Home — Doc Start",        ("ctrl", "home")),
        ("Ctrl+End  — Doc End",          ("ctrl", "end")),
        ("Ctrl+Right — Next Word",       ("ctrl", "right")),
        ("Ctrl+Left  — Prev Word",       ("ctrl", "left")),
        ("Shift+Home — Select to Start", ("shift", "home")),
        ("Shift+End  — Select to End",   ("shift", "end")),
    ],
    "\U0001f3ae  Function Keys": [
        ("F1  — Help",         ("f1",)),
        ("F2  — Rename",       ("f2",)),
        ("F3  — Search",       ("f3",)),
        ("F4  — Address Bar",  ("f4",)),
        ("F5  — Refresh",      ("f5",)),
        ("F6  — Next Pane",    ("f6",)),
        ("F11 — Fullscreen",   ("f11",)),
        ("F12 — DevTools/Save",("f12",)),
        ("Esc — Escape",       ("escape",)),
        ("Tab — Tab",          ("tab",)),
        ("Delete — Delete",    ("delete",)),
        ("Backspace",          ("backspace",)),
    ],
}

COLORS = {
    "bg": "#1e1e2e",
    "sidebar": "#181825",
    "card": "#313244",
    "accent": "#cba6f7",
    "accent2": "#89b4fa",
    "green": "#a6e3a1",
    "red": "#f38ba8",
    "yellow": "#f9e2af",
    "text": "#cdd6f4",
    "subtext": "#a6adc8",
    "border": "#45475a",
    "hover": "#45475a",
    "step_bg": "#181825",
    "section_bg": "#1a1a2e",
    "section_header": "#2a2a3e",
    "loop_accent": "#fab387",
    "pause_bg": "#45475a",
    "pause_fg": "#f9e2af",
    "enter_accent": "#94e2d5",
    "shortcut_accent": "#f5c2e7",
    "shortcut_bg": "#24273a",
    "shortcut_header": "#1e2030",
}

# Disable PyAutoGUI failsafe to prevent top-left corner from stopping automation.
# We handle stops ourselves via stop_event.
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05


# ===========================================================================
# AutoPauseManager
# ===========================================================================
class AutoPauseManager:
    MOUSE_MOVE_THRESHOLD = 80
    MOUSE_CHECK_INTERVAL = 0.4
    AUTO_RESUME_IDLE_SECS = 2.5
    AUTOMATION_AREA_RADIUS = 60
    MAX_HISTORY = 6

    def __init__(self, on_status_update, root_widget):
        self.on_status_update = on_status_update
        self.root = root_widget
        self.pause_event = threading.Event()
        self.resume_event = threading.Event()
        self.stop_event = threading.Event()
        self.resume_event.set()
        self.manual_pause_active = False
        self.auto_pause_active = False
        self.force_pause_mode = False
        self.pause_timestamp = None
        self.last_mouse_pos = None
        self.automation_running = False
        # Flag: automation thread sets this True just before moving mouse,
        # False right after -- so the monitor ignores those movements.
        self._automation_moving = False
        self._monitor_thread = None
        self._known_automation_coords = []
        self._kb_monitor_thread = None
        self._last_kb_time = 0

    def set_automation_moving(self, moving: bool):
        """Call with True before automation moves mouse, False after."""
        self._automation_moving = moving
        if moving:
            # Update last known position so monitor doesn't false-trigger
            self.last_mouse_pos = pyautogui.position()

    def start(self, automation_coords=None):
        self.stop_event.clear()
        self.pause_event.clear()
        self.resume_event.set()
        self.manual_pause_active = False
        self.auto_pause_active = False
        self.automation_running = True
        self._automation_moving = False
        self._known_automation_coords = automation_coords or []
        self._start_mouse_monitor()
        self._start_keyboard_monitor()

    def stop(self):
        self.stop_event.set()
        self.pause_event.clear()
        self.resume_event.set()
        self.automation_running = False
        self.manual_pause_active = False
        self.auto_pause_active = False

    def manual_pause(self):
        if self.stop_event.is_set():
            return
        self.manual_pause_active = True
        self.auto_pause_active = False
        self.force_pause_mode = True
        self.pause_timestamp = time.time()
        self.resume_event.clear()
        self.pause_event.set()
        self.on_status_update("\u23f8 Paused manually")

    def manual_resume(self):
        if self.stop_event.is_set():
            return
        self.manual_pause_active = False
        self.auto_pause_active = False
        self.force_pause_mode = False
        self.pause_event.clear()
        self.resume_event.set()
        self.on_status_update("\u25b6 Resumed")

    def auto_pause(self, reason="User activity detected"):
        if self.stop_event.is_set() or self.manual_pause_active:
            return
        if self.auto_pause_active:
            return
        self.auto_pause_active = True
        self.pause_timestamp = time.time()
        self.resume_event.clear()
        self.pause_event.set()
        self.on_status_update(f"\u26a1 Auto-paused: {reason}")
        threading.Thread(target=self._auto_resume_watcher, daemon=True).start()

    def _auto_resume_watcher(self):
        last_pos = pyautogui.position()
        while not self.stop_event.is_set():
            time.sleep(0.3)
            if self.stop_event.is_set() or self.manual_pause_active or not self.auto_pause_active:
                break
            current_pos = pyautogui.position()
            dx = current_pos.x - last_pos.x
            dy = current_pos.y - last_pos.y
            if (dx**2 + dy**2)**0.5 < 5:
                elapsed = time.time() - (self.pause_timestamp or time.time())
                if elapsed >= self.AUTO_RESUME_IDLE_SECS:
                    self.auto_pause_active = False
                    self.pause_event.clear()
                    self.resume_event.set()
                    self.on_status_update("\u25b6 Auto-resumed (user idle)")
                    break
            else:
                self.pause_timestamp = time.time()
                last_pos = current_pos

    def wait_if_paused(self):
        while self.pause_event.is_set() and not self.stop_event.is_set():
            time.sleep(0.1)
        return not self.stop_event.is_set()

    @property
    def is_paused(self):
        return self.pause_event.is_set()

    @property
    def is_stopped(self):
        return self.stop_event.is_set()

    def _start_mouse_monitor(self):
        self._monitor_thread = threading.Thread(target=self._mouse_monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _mouse_monitor_loop(self):
        movement_history = []
        self.last_mouse_pos = pyautogui.position()
        while not self.stop_event.is_set():
            try:
                current_pos = pyautogui.position()
                current_time = time.time()
                if (self.automation_running and not self.pause_event.is_set()
                        and not self.manual_pause_active
                        and not self._automation_moving   # <-- skip when automation is moving
                        and self.last_mouse_pos is not None):
                    dx = current_pos.x - self.last_mouse_pos.x
                    dy = current_pos.y - self.last_mouse_pos.y
                    distance = (dx**2 + dy**2)**0.5
                    if len(movement_history) >= self.MAX_HISTORY:
                        movement_history.pop(0)
                    movement_history.append((current_time, distance, dx, dy))
                    is_user_movement = False
                    if distance > self.MOUSE_MOVE_THRESHOLD:
                        near_auto = any(
                            ((current_pos.x - ax)**2 + (current_pos.y - ay)**2)**0.5 < self.AUTOMATION_AREA_RADIUS
                            for ax, ay in self._known_automation_coords)
                        if not near_auto:
                            is_user_movement = True
                        if len(movement_history) >= 3:
                            direction_changes = 0
                            prev_dx, prev_dy = 0, 0
                            for _, _, cdx, cdy in movement_history[1:]:
                                if (prev_dx * cdx < 0) or (prev_dy * cdy < 0):
                                    direction_changes += 1
                                prev_dx, prev_dy = cdx, cdy
                            if direction_changes >= 2:
                                is_user_movement = True
                    if is_user_movement:
                        self.root.after(0, lambda: self.auto_pause("Mouse movement"))
                        self.last_mouse_pos = current_pos
                        time.sleep(1.5)
                        continue
                self.last_mouse_pos = current_pos
            except Exception:
                pass
            for _ in range(int(self.MOUSE_CHECK_INTERVAL / 0.05)):
                if self.stop_event.is_set():
                    break
                time.sleep(0.05)

    def _start_keyboard_monitor(self):
        self._kb_monitor_thread = threading.Thread(target=self._keyboard_monitor_loop, daemon=True)
        self._kb_monitor_thread.start()

    def _keyboard_monitor_loop(self):
        try:
            from pynput import keyboard as pynput_kb
            def on_press(key):
                if self.stop_event.is_set():
                    return False
                if (self.automation_running and not self.pause_event.is_set()
                        and not self.manual_pause_active):
                    self.root.after(0, lambda: self.auto_pause("Keyboard activity"))
            with pynput_kb.Listener(on_press=on_press) as listener:
                while not self.stop_event.is_set():
                    time.sleep(0.2)
                listener.stop()
        except ImportError:
            self._keyboard_monitor_ctypes()

    def _keyboard_monitor_ctypes(self):
        try:
            import ctypes
            MONITORED_KEYS = list(range(0x08, 0x90))
            prev_state = {k: False for k in MONITORED_KEYS}
            while not self.stop_event.is_set():
                if (self.automation_running and not self.pause_event.is_set()
                        and not self.manual_pause_active):
                    for vk in MONITORED_KEYS:
                        state = bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
                        if state and not prev_state[vk]:
                            self.root.after(0, lambda: self.auto_pause("Keyboard activity"))
                            break
                        prev_state[vk] = state
                time.sleep(0.1)
        except Exception:
            pass


# ===========================================================================
# CoordinateSelector
# ===========================================================================
class CoordinateSelector:
    def __init__(self, parent, callback):
        self.parent = parent
        self.callback = callback
        self._build()

    def _build(self):
        try:
            screenshot = ImageGrab.grab()
        except Exception as e:
            messagebox.showerror("Screenshot Error", f"Failed to capture screen: {e}",
                                 parent=self.parent)
            self.callback(None, None)
            return
        sel_win = tk.Toplevel(self.parent)
        sel_win.title("Select Coordinate")
        sel_win.attributes("-fullscreen", True)
        sel_win.attributes("-topmost", True)
        sel_win.overrideredirect(True)
        canvas = tk.Canvas(sel_win, cursor="crosshair", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        tk_image = ImageTk.PhotoImage(screenshot)
        canvas.create_image(0, 0, anchor=tk.NW, image=tk_image)
        canvas.image = tk_image
        screen_w, screen_h = screenshot.width, screenshot.height
        instruction_state = {"bg_id": None, "text_id": None}
        INSTRUCTION_TEXT = "Click and drag to select target area  |  Press ESC to cancel"
        BAR_HEIGHT, MARGIN = 50, 10

        def draw_instruction(mouse_y):
            if instruction_state["bg_id"]:
                canvas.delete(instruction_state["bg_id"])
            if instruction_state["text_id"]:
                canvas.delete(instruction_state["text_id"])
            y1 = (screen_h - BAR_HEIGHT - MARGIN) if mouse_y < screen_h / 3 else MARGIN
            y2 = y1 + BAR_HEIGHT
            instruction_state["bg_id"] = canvas.create_rectangle(
                MARGIN, y1, screen_w - MARGIN, y2, fill="black", outline="white", width=2)
            instruction_state["text_id"] = canvas.create_text(
                screen_w // 2, (y1 + y2) // 2, text=INSTRUCTION_TEXT,
                fill="white", font=("Arial", 16, "bold"))

        draw_instruction(screen_h // 2)
        rect_state = {"x1": 0, "y1": 0, "x2": 0, "y2": 0, "rect_id": None}

        def on_m_down(e):
            rect_state["x1"] = canvas.canvasx(e.x)
            rect_state["y1"] = canvas.canvasy(e.y)
            if rect_state["rect_id"]:
                canvas.delete(rect_state["rect_id"])
            rect_state["rect_id"] = canvas.create_rectangle(
                rect_state["x1"], rect_state["y1"],
                rect_state["x1"], rect_state["y1"], outline="red", width=3)
            draw_instruction(e.y)

        def on_m_move(e):
            draw_instruction(e.y)
            if rect_state["rect_id"]:
                rect_state["x2"] = canvas.canvasx(e.x)
                rect_state["y2"] = canvas.canvasy(e.y)
                canvas.coords(rect_state["rect_id"],
                              rect_state["x1"], rect_state["y1"],
                              rect_state["x2"], rect_state["y2"])

        def on_m_up(e):
            x1 = min(rect_state["x1"], canvas.canvasx(e.x))
            x2 = max(rect_state["x1"], canvas.canvasx(e.x))
            y1 = min(rect_state["y1"], canvas.canvasy(e.y))
            y2 = max(rect_state["y1"], canvas.canvasy(e.y))
            sel_win.grab_release()
            sel_win.destroy()
            self.callback(int((x1 + x2) / 2), int((y1 + y2) / 2))

        def on_escape(e):
            sel_win.grab_release()
            sel_win.destroy()
            self.callback(None, None)

        canvas.bind("<ButtonPress-1>", on_m_down)
        canvas.bind("<B1-Motion>", on_m_move)
        canvas.bind("<ButtonRelease-1>", on_m_up)
        canvas.bind("<Motion>", on_m_move)
        sel_win.bind("<Escape>", on_escape)
        sel_win.update()
        sel_win.focus_force()
        sel_win.grab_set()


# ===========================================================================
# StepEditorDialog
# ===========================================================================
class StepEditorDialog:
    """Dialog window to create or edit a single step."""

    def __init__(self, parent, step_data=None, on_save=None):
        self.parent = parent
        self.on_save = on_save
        self.result = None
        self.win = tk.Toplevel(parent)
        self.win.title("Step Editor")
        self.win.configure(bg=COLORS["bg"])
        self.win.resizable(False, False)
        self.win.grab_set()
        self.step_data = copy.deepcopy(step_data) if step_data else {
            "action": "Click", "x": 0, "y": 0, "text": "",
            "scroll_direction": "down", "scroll_amount": 3,
            "delay": 0.5, "description": "",
            "shortcut_key": None,
        }
        if "shortcut_key" not in self.step_data:
            self.step_data["shortcut_key"] = None
        self._shortcut_vars = {}   # label -> BooleanVar
        self._build()
        self.win.transient(parent)
        self.win.wait_window()

    def _lbl(self, parent, text, row, col=0, colspan=1):
        tk.Label(parent, text=text, bg=COLORS["bg"], fg=COLORS["subtext"],
                 font=("Segoe UI", 9)).grid(
            row=row, column=col, columnspan=colspan,
            sticky="w", padx=8, pady=(6, 0))

    def _build(self):
        frame = tk.Frame(self.win, bg=COLORS["bg"], padx=16, pady=16)
        frame.pack(fill="both", expand=True)

        # Description
        self._lbl(frame, "Step Description (optional)", 0)
        self.desc_var = tk.StringVar(value=self.step_data.get("description", ""))
        tk.Entry(frame, textvariable=self.desc_var, bg=COLORS["card"],
                 fg=COLORS["text"], insertbackground=COLORS["text"],
                 font=("Segoe UI", 10), width=48, relief="flat"
                 ).grid(row=1, column=0, columnspan=3, sticky="ew", padx=8, pady=(2, 8))

        # Action Type
        self._lbl(frame, "Action Type", 2)
        self.action_var = tk.StringVar(value=self.step_data.get("action", "Click"))
        action_cb = ttk.Combobox(frame, textvariable=self.action_var,
                                 values=ACTION_TYPES, state="readonly", width=18)
        action_cb.grid(row=3, column=0, sticky="w", padx=8, pady=(2, 8))
        action_cb.bind("<<ComboboxSelected>>", lambda e: self._toggle_fields())

        # Info badges (hidden by default)
        self.enter_info = tk.Label(
            frame,
            text="\u23ce  Simulates pressing the Enter key (no coordinate needed)",
            bg=COLORS["bg"], fg=COLORS["enter_accent"],
            font=("Segoe UI", 9, "italic"))
        self.enter_info.grid(row=3, column=1, columnspan=2, sticky="w", padx=8, pady=(2, 8))

        self.shortcut_info = tk.Label(
            frame,
            text="\u2328\ufe0f  Select one shortcut below (no coordinate needed)",
            bg=COLORS["bg"], fg=COLORS["shortcut_accent"],
            font=("Segoe UI", 9, "italic"))
        self.shortcut_info.grid(row=3, column=1, columnspan=2, sticky="w", padx=8, pady=(2, 8))

        # Coordinate row
        self._lbl(frame, "Target Coordinate", 4)
        coord_row = tk.Frame(frame, bg=COLORS["bg"])
        coord_row.grid(row=5, column=0, columnspan=3, sticky="w", padx=8, pady=(2, 0))
        tk.Label(coord_row, text="X:", bg=COLORS["bg"], fg=COLORS["text"],
                 font=("Segoe UI", 9)).pack(side="left")
        self.x_var = tk.IntVar(value=self.step_data.get("x", 0))
        self.x_entry = tk.Entry(coord_row, textvariable=self.x_var, bg=COLORS["card"],
                                fg=COLORS["text"], insertbackground=COLORS["text"],
                                font=("Segoe UI", 10), width=6, relief="flat")
        self.x_entry.pack(side="left", padx=(2, 8))
        tk.Label(coord_row, text="Y:", bg=COLORS["bg"], fg=COLORS["text"],
                 font=("Segoe UI", 9)).pack(side="left")
        self.y_var = tk.IntVar(value=self.step_data.get("y", 0))
        self.y_entry = tk.Entry(coord_row, textvariable=self.y_var, bg=COLORS["card"],
                                fg=COLORS["text"], insertbackground=COLORS["text"],
                                font=("Segoe UI", 10), width=6, relief="flat")
        self.y_entry.pack(side="left", padx=(2, 8))
        self.pick_btn = tk.Button(
            coord_row, text="\U0001f4cd Pick from Screen",
            bg=COLORS["accent2"], fg=COLORS["bg"],
            font=("Segoe UI", 9, "bold"), relief="flat",
            cursor="hand2", command=self._pick_coordinate)
        self.pick_btn.pack(side="left", padx=(0, 4))

        # Text entry
        self._lbl(frame, "Text to Type (for Input / Typewrite)", 6)
        self.text_var = tk.StringVar(value=self.step_data.get("text", ""))
        self.text_entry = tk.Entry(
            frame, textvariable=self.text_var, bg=COLORS["card"],
            fg=COLORS["text"], insertbackground=COLORS["text"],
            font=("Segoe UI", 10), width=48, relief="flat")
        self.text_entry.grid(row=7, column=0, columnspan=3, sticky="ew", padx=8, pady=(2, 8))

        # Scroll fields
        self._lbl(frame, "Scroll Direction", 8)
        self.scroll_dir_var = tk.StringVar(value=self.step_data.get("scroll_direction", "down"))
        self.scroll_dir_cb = ttk.Combobox(
            frame, textvariable=self.scroll_dir_var,
            values=["down", "up", "left", "right"],
            state="readonly", width=10)
        self.scroll_dir_cb.grid(row=9, column=0, sticky="w", padx=8, pady=(2, 4))
        self._lbl(frame, "Scroll Amount (clicks)", 8, col=1)
        self.scroll_amount_var = tk.IntVar(value=self.step_data.get("scroll_amount", 3))
        self.scroll_amount_spin = tk.Spinbox(
            frame, from_=1, to=50, textvariable=self.scroll_amount_var,
            bg=COLORS["card"], fg=COLORS["text"], buttonbackground=COLORS["border"],
            font=("Segoe UI", 10), width=6, relief="flat")
        self.scroll_amount_spin.grid(row=9, column=1, sticky="w", padx=8, pady=(2, 4))

        # ----------------------------------------------------------------
        # Keyboard Shortcut Panel  (row 10, shown only for KB Shortcut)
        # ----------------------------------------------------------------
        self.shortcut_outer = tk.Frame(frame, bg=COLORS["bg"])
        self.shortcut_outer.grid(row=10, column=0, columnspan=3, sticky="nsew", padx=8, pady=(4, 4))
        self._build_shortcut_panel(self.shortcut_outer)

        # Delay
        self._lbl(frame, "Delay after action (seconds)", 11)
        self.delay_var = tk.DoubleVar(value=self.step_data.get("delay", 0.5))
        tk.Spinbox(
            frame, from_=0, to=30, increment=0.1, format="%.1f",
            textvariable=self.delay_var,
            bg=COLORS["card"], fg=COLORS["text"], buttonbackground=COLORS["border"],
            font=("Segoe UI", 10), width=8, relief="flat"
        ).grid(row=12, column=0, sticky="w", padx=8, pady=(2, 12))

        # Buttons
        btn_row = tk.Frame(frame, bg=COLORS["bg"])
        btn_row.grid(row=13, column=0, columnspan=3, pady=(8, 0))
        tk.Button(btn_row, text="  Save Step  ", bg=COLORS["green"], fg=COLORS["bg"],
                  font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
                  command=self._save).pack(side="left", padx=6)
        tk.Button(btn_row, text="  Cancel  ", bg=COLORS["border"], fg=COLORS["text"],
                  font=("Segoe UI", 10), relief="flat", cursor="hand2",
                  command=self.win.destroy).pack(side="left", padx=6)

        self._toggle_fields()

    # ------------------------------------------------------------------
    # Keyboard Shortcut Panel builder
    # ------------------------------------------------------------------
    def _build_shortcut_panel(self, parent):
        """Build a scrollable panel with grouped checkboxes for all shortcuts."""
        # Header
        tk.Label(parent, text="\u2328\ufe0f  Choose Keyboard Shortcut",
                 bg=COLORS["shortcut_header"], fg=COLORS["shortcut_accent"],
                 font=("Segoe UI", 9, "bold"),
                 anchor="w", padx=8, pady=4
                 ).pack(fill="x")

        # Scrollable canvas
        scroll_canvas = tk.Canvas(
            parent, bg=COLORS["shortcut_bg"],
            highlightthickness=1, highlightbackground=COLORS["border"],
            height=220)
        sb = ttk.Scrollbar(parent, orient="vertical", command=scroll_canvas.yview)
        scroll_canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        scroll_canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(scroll_canvas, bg=COLORS["shortcut_bg"])
        scroll_canvas.create_window((0, 0), window=inner, anchor="nw")

        currently_selected = self.step_data.get("shortcut_key", None)

        # Track the single selected shortcut
        self._selected_shortcut_label = tk.StringVar(
            value=currently_selected if currently_selected else "")

        # 2-column layout
        left_col = tk.Frame(inner, bg=COLORS["shortcut_bg"])
        left_col.pack(side="left", fill="both", padx=(4, 2), pady=4, anchor="n")
        right_col = tk.Frame(inner, bg=COLORS["shortcut_bg"])
        right_col.pack(side="left", fill="both", padx=(2, 4), pady=4, anchor="n")
        col_frame_list = [left_col, right_col]

        for cat_idx, (cat_name, shortcuts) in enumerate(KEYBOARD_SHORTCUTS.items()):
            target_col = col_frame_list[cat_idx % 2]

            # Category header
            tk.Label(target_col, text=cat_name,
                     bg=COLORS["shortcut_header"],
                     fg=COLORS["shortcut_accent"],
                     font=("Segoe UI", 8, "bold"),
                     anchor="w", padx=6
                     ).pack(fill="x", pady=(6, 2))

            for label, keys in shortcuts:
                var = tk.BooleanVar(value=(currently_selected == label))
                self._shortcut_vars[label] = var

                cb = tk.Checkbutton(
                    target_col,
                    text=label,
                    variable=var,
                    bg=COLORS["shortcut_bg"],
                    fg=COLORS["text"],
                    selectcolor=COLORS["card"],
                    activebackground=COLORS["shortcut_bg"],
                    activeforeground=COLORS["shortcut_accent"],
                    font=("Consolas", 8),
                    anchor="w",
                    cursor="hand2",
                    command=lambda lbl=label: self._on_shortcut_check(lbl)
                )
                cb.pack(fill="x", padx=4, pady=1)

        inner.update_idletasks()
        scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))
        scroll_canvas.bind_all("<MouseWheel>",
            lambda e: scroll_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    def _on_shortcut_check(self, clicked_label):
        """Radio-like behaviour: only one shortcut can be checked at a time."""
        for lbl, var in self._shortcut_vars.items():
            if lbl != clicked_label:
                var.set(False)

    # ------------------------------------------------------------------
    def _toggle_fields(self):
        action = self.action_var.get()
        is_scroll = action == "Scroll"
        is_text = action in ("Input", "Typewrite")
        is_enter = action == "Press Enter"
        is_shortcut = action == "Keyboard Shortcut"
        no_coord = is_enter or is_shortcut

        self.text_entry.config(state="normal" if is_text else "disabled")
        self.scroll_dir_cb.config(state="readonly" if is_scroll else "disabled")
        self.scroll_amount_spin.config(state="normal" if is_scroll else "disabled")
        coord_state = "disabled" if no_coord else "normal"
        self.x_entry.config(state=coord_state)
        self.y_entry.config(state=coord_state)
        self.pick_btn.config(state=coord_state)

        # Info badges
        self.enter_info.grid_remove()
        self.shortcut_info.grid_remove()
        if is_enter:
            self.enter_info.grid()
        elif is_shortcut:
            self.shortcut_info.grid()

        # Shortcut panel
        if is_shortcut:
            self.shortcut_outer.grid()
        else:
            self.shortcut_outer.grid_remove()

    def _pick_coordinate(self):
        self.win.withdraw()
        self.parent.iconify()
        self.win.after(200, self._initiate_coordinate_pick)

    def _initiate_coordinate_pick(self):
        def on_coord(x, y):
            self.parent.deiconify()
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
            if x is not None and y is not None:
                self.x_var.set(x)
                self.y_var.set(y)
        CoordinateSelector(self.parent, on_coord)

    def _save(self):
        action = self.action_var.get()
        # Resolve selected shortcut
        if action == "Keyboard Shortcut":
            selected = None
            for lbl, var in self._shortcut_vars.items():
                if var.get():
                    selected = lbl
                    break
            if selected is None:
                messagebox.showwarning(
                    "No Shortcut Selected",
                    "Please check one keyboard shortcut before saving.",
                    parent=self.win)
                return
            self.step_data["shortcut_key"] = selected
        else:
            self.step_data["shortcut_key"] = None

        self.step_data["action"] = action
        self.step_data["x"] = self.x_var.get()
        self.step_data["y"] = self.y_var.get()
        self.step_data["text"] = self.text_var.get()
        self.step_data["scroll_direction"] = self.scroll_dir_var.get()
        self.step_data["scroll_amount"] = self.scroll_amount_var.get()
        self.step_data["delay"] = round(self.delay_var.get(), 2)
        self.step_data["description"] = self.desc_var.get()
        self.result = copy.deepcopy(self.step_data)
        if self.on_save:
            self.on_save(self.result)
        self.win.destroy()


# ===========================================================================
# TaskCard
# ===========================================================================
class TaskCard:
    def __init__(self, parent_frame, task_data, app_ref, index):
        self.parent_frame = parent_frame
        self.task_data = task_data
        self.app_ref = app_ref
        self.index = index
        self.is_running = False
        self._pause_mgr = None

        if "loop_enabled" not in self.task_data:
            self.task_data["loop_enabled"] = False
        if "loop_count" not in self.task_data:
            self.task_data["loop_count"] = 1
        if "steps" in self.task_data and "sections" not in self.task_data:
            self.task_data["sections"] = [
                {"name": "Section 1", "loop_count": 0, "steps": self.task_data.pop("steps")}]
        if "sections" not in self.task_data:
            self.task_data["sections"] = [
                {"name": "Section 1", "loop_count": 0, "steps": []}]
        self._build()

    def _build(self):
        self.card = tk.Frame(
            self.parent_frame, bg=COLORS["card"], bd=0,
            highlightthickness=1, highlightbackground=COLORS["border"])
        self.card.pack(fill="x", padx=10, pady=6)

        header = tk.Frame(self.card, bg=COLORS["card"])
        header.pack(fill="x", padx=10, pady=(8, 4))

        self.name_var = tk.StringVar(value=self.task_data.get("name", "Unnamed Task"))
        name_lbl = tk.Label(
            header, textvariable=self.name_var, bg=COLORS["card"],
            fg=COLORS["accent"], font=("Segoe UI", 12, "bold"), anchor="w")
        name_lbl.pack(side="left")
        name_lbl.bind("<Double-Button-1>", self._rename_task)

        btn_frame = tk.Frame(header, bg=COLORS["card"])
        btn_frame.pack(side="right")

        self.run_btn = tk.Button(
            btn_frame, text="\u25b6  Run Task",
            bg=COLORS["green"], fg=COLORS["bg"],
            font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
            command=self._run_task)
        self.run_btn.pack(side="left", padx=4)

        self.pause_btn = tk.Button(
            btn_frame, text="\u23f8  Pause",
            bg=COLORS["pause_bg"], fg=COLORS["pause_fg"],
            font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
            state="disabled", command=self._toggle_pause)
        self.pause_btn.pack(side="left", padx=4)

        self.stop_btn = tk.Button(
            btn_frame, text="\u23f9  Stop",
            bg=COLORS["red"], fg=COLORS["bg"],
            font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
            state="disabled", command=self._stop_task)
        self.stop_btn.pack(side="left", padx=4)

        tk.Button(
            btn_frame, text="\u270e Rename",
            bg=COLORS["border"], fg=COLORS["text"],
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            command=self._rename_task).pack(side="left", padx=4)

        tk.Button(
            btn_frame, text="\U0001f5d1 Delete",
            bg=COLORS["red"], fg=COLORS["bg"],
            font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
            command=self._delete_task).pack(side="left", padx=4)

        loop_bar = tk.Frame(self.card, bg=COLORS["card"])
        loop_bar.pack(fill="x", padx=10, pady=(0, 4))

        self.loop_enabled_var = tk.BooleanVar(value=self.task_data.get("loop_enabled", False))
        tk.Checkbutton(
            loop_bar, text="\U0001f501  Enable Loop",
            variable=self.loop_enabled_var,
            bg=COLORS["card"], fg=COLORS["loop_accent"],
            selectcolor=COLORS["bg"],
            activebackground=COLORS["card"],
            activeforeground=COLORS["loop_accent"],
            font=("Segoe UI", 9, "bold"),
            command=self._on_loop_toggle,
        ).pack(side="left")

        tk.Label(loop_bar, text="   Loop Count:",
                 bg=COLORS["card"], fg=COLORS["subtext"],
                 font=("Segoe UI", 9)).pack(side="left")

        self.loop_count_var = tk.IntVar(value=max(1, self.task_data.get("loop_count", 1)))
        self.loop_count_spin = tk.Spinbox(
            loop_bar, from_=1, to=9999,
            textvariable=self.loop_count_var,
            bg=COLORS["card"], fg=COLORS["loop_accent"],
            buttonbackground=COLORS["border"],
            font=("Segoe UI", 9, "bold"), width=6, relief="flat",
            command=self._save_loop_settings)
        self.loop_count_spin.pack(side="left", padx=(4, 12))
        self.loop_count_spin.bind("<FocusOut>", lambda e: self._save_loop_settings())

        tk.Label(loop_bar, text="times",
                 bg=COLORS["card"], fg=COLORS["subtext"],
                 font=("Segoe UI", 9)).pack(side="left")

        self.add_section_btn = tk.Button(
            loop_bar, text="+ Add Section",
            bg=COLORS["loop_accent"], fg=COLORS["bg"],
            font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
            command=self._add_section)
        self.add_section_btn.pack(side="left", padx=(16, 0))

        self.status_var = tk.StringVar(value="Ready")
        self.status_lbl = tk.Label(
            self.card, textvariable=self.status_var,
            bg=COLORS["card"], fg=COLORS["subtext"],
            font=("Segoe UI", 8), anchor="w")
        self.status_lbl.pack(fill="x", padx=10)

        self.sections_frame = tk.Frame(self.card, bg=COLORS["step_bg"], pady=4)
        self.sections_frame.pack(fill="x", padx=10, pady=(4, 8))
        self._refresh_ui()

    def _toggle_pause(self):
        if self._pause_mgr is None:
            return
        if self._pause_mgr.is_paused and self._pause_mgr.manual_pause_active:
            self._pause_mgr.manual_resume()
            self.pause_btn.config(text="\u23f8  Pause", bg=COLORS["pause_bg"])
        else:
            self._pause_mgr.manual_pause()
            self.pause_btn.config(text="\u25b6  Resume", bg=COLORS["green"])
        self._update_status_color()

    def _stop_task(self):
        if self._pause_mgr:
            self._pause_mgr.stop()
        self.status_var.set("\u23f9 Stopped by user")
        self._on_task_finished()

    def _update_status_color(self):
        fg = COLORS["yellow"] if (self._pause_mgr and self._pause_mgr.is_paused) else COLORS["subtext"]
        self.status_lbl.config(fg=fg)

    def _on_loop_toggle(self):
        self.task_data["loop_enabled"] = self.loop_enabled_var.get()
        self.app_ref.save_data()
        self._refresh_ui()

    def _save_loop_settings(self):
        self.task_data["loop_enabled"] = self.loop_enabled_var.get()
        try:
            self.task_data["loop_count"] = int(self.loop_count_var.get())
        except Exception:
            self.task_data["loop_count"] = 1
        self.app_ref.save_data()

    def _add_section(self):
        name = simpledialog.askstring(
            "New Section", "Enter section name:",
            initialvalue=f"Section {len(self.task_data['sections']) + 1}",
            parent=self.app_ref.root)
        if name and name.strip():
            self.task_data["sections"].append(
                {"name": name.strip(), "loop_count": 0, "steps": []})
            self.app_ref.save_data()
            self._refresh_ui()

    def _delete_section(self, sec_idx):
        if len(self.task_data["sections"]) <= 1:
            messagebox.showwarning("Cannot Delete",
                "A task must have at least one section.", parent=self.app_ref.root)
            return
        if messagebox.askyesno("Delete Section",
                f"Delete section '{self.task_data['sections'][sec_idx]['name']}'?"):
            self.task_data["sections"].pop(sec_idx)
            self.app_ref.save_data()
            self._refresh_ui()

    def _rename_section(self, sec_idx):
        sec = self.task_data["sections"][sec_idx]
        new_name = simpledialog.askstring(
            "Rename Section", "Enter new section name:",
            initialvalue=sec["name"], parent=self.app_ref.root)
        if new_name and new_name.strip():
            sec["name"] = new_name.strip()
            self.app_ref.save_data()
            self._refresh_ui()

    def _refresh_ui(self):
        loop_enabled = self.loop_enabled_var.get()
        if loop_enabled:
            self.loop_count_spin.config(state="normal")
            self.add_section_btn.pack(side="left", padx=(16, 0))
        else:
            self.loop_count_spin.config(state="disabled")
            self.add_section_btn.pack_forget()
        for w in self.sections_frame.winfo_children():
            w.destroy()
        for sec_idx, section in enumerate(self.task_data.get("sections", [])):
            self._build_section(sec_idx, section, loop_enabled)

    def _build_section(self, sec_idx, section, loop_enabled):
        sec_frame = tk.Frame(
            self.sections_frame, bg=COLORS["section_bg"],
            highlightthickness=1,
            highlightbackground=COLORS["loop_accent"] if loop_enabled else COLORS["border"])
        sec_frame.pack(fill="x", padx=4, pady=4)

        sec_header = tk.Frame(sec_frame, bg=COLORS["section_header"])
        sec_header.pack(fill="x")

        tk.Label(
            sec_header,
            text=f"\U0001f4c2  {section['name']}",
            bg=COLORS["section_header"],
            fg=COLORS["loop_accent"] if loop_enabled else COLORS["accent2"],
            font=("Segoe UI", 9, "bold")
        ).pack(side="left", padx=8, pady=4)

        if loop_enabled:
            tk.Label(sec_header, text="Loop:",
                     bg=COLORS["section_header"], fg=COLORS["subtext"],
                     font=("Segoe UI", 8)).pack(side="left", padx=(8, 2))
            sec_loop_var = tk.IntVar(value=section.get("loop_count", 0))

            def make_handler(idx, var):
                def h(*_):
                    try:
                        self.task_data["sections"][idx]["loop_count"] = int(var.get())
                    except Exception:
                        self.task_data["sections"][idx]["loop_count"] = 0
                    self.app_ref.save_data()
                return h

            sec_spin = tk.Spinbox(
                sec_header, from_=0, to=9999, textvariable=sec_loop_var,
                bg=COLORS["section_header"], fg=COLORS["loop_accent"],
                buttonbackground=COLORS["border"],
                font=("Segoe UI", 8, "bold"), width=5, relief="flat",
                command=make_handler(sec_idx, sec_loop_var))
            sec_spin.pack(side="left", padx=(0, 4))
            sec_spin.bind("<FocusOut>", make_handler(sec_idx, sec_loop_var))

            lc = section.get("loop_count", 0)
            hint = "(0 = no loop)" if lc == 0 else f"\u21ba {lc}x"
            tk.Label(
                sec_header, text=hint,
                bg=COLORS["section_header"],
                fg=COLORS["yellow"] if lc > 0 else COLORS["subtext"],
                font=("Segoe UI", 8, "italic")
            ).pack(side="left", padx=2)

        sec_btns = tk.Frame(sec_header, bg=COLORS["section_header"])
        sec_btns.pack(side="right", padx=4)
        tk.Button(
            sec_btns, text="+ Step",
            bg=COLORS["accent2"], fg=COLORS["bg"],
            font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
            command=lambda i=sec_idx: self._add_step(i)
        ).pack(side="left", padx=2, pady=2)
        if loop_enabled:
            tk.Button(
                sec_btns, text="Rename",
                bg=COLORS["border"], fg=COLORS["text"],
                font=("Segoe UI", 8), relief="flat", cursor="hand2",
                command=lambda i=sec_idx: self._rename_section(i)
            ).pack(side="left", padx=2, pady=2)
            tk.Button(
                sec_btns, text="\u2715 Del",
                bg=COLORS["red"], fg=COLORS["bg"],
                font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
                command=lambda i=sec_idx: self._delete_section(i)
            ).pack(side="left", padx=2, pady=2)

        steps = section.get("steps", [])
        if not steps:
            tk.Label(
                sec_frame, text="No steps. Click '+ Step' to add.",
                bg=COLORS["section_bg"], fg=COLORS["subtext"],
                font=("Segoe UI", 8, "italic")
            ).pack(padx=12, pady=4, anchor="w")
        else:
            for step_idx, step in enumerate(steps):
                self._build_step_row(sec_frame, sec_idx, step_idx, step)

    def _build_step_row(self, parent, sec_idx, step_idx, step):
        row = tk.Frame(parent, bg=COLORS["section_bg"])
        row.pack(fill="x", padx=8, pady=2)

        action_colors = {
            "Click": COLORS["accent"],
            "Input": COLORS["accent2"],
            "Scroll": COLORS["yellow"],
            "Typewrite": COLORS["green"],
            "Press Enter": COLORS["enter_accent"],
            "Keyboard Shortcut": COLORS["shortcut_accent"],
        }
        action = step.get("action", "Click")
        color = action_colors.get(action, COLORS["text"])

        tk.Label(row, text=f" {step_idx + 1} ",
                 bg=color, fg=COLORS["bg"],
                 font=("Segoe UI", 8, "bold"), width=3).pack(side="left", padx=(0, 4))
        tk.Label(row, text=f"[{action}]",
                 bg=COLORS["section_bg"], fg=color,
                 font=("Segoe UI", 9, "bold"), width=16, anchor="w").pack(side="left")

        no_coord = action in ("Press Enter", "Keyboard Shortcut")
        coord_text = "\u2014" if no_coord else f"({step.get('x', 0)}, {step.get('y', 0)})"
        tk.Label(row, text=coord_text,
                 bg=COLORS["section_bg"], fg=COLORS["subtext"],
                 font=("Consolas", 9), width=12, anchor="w").pack(side="left")

        if action == "Keyboard Shortcut" and step.get("shortcut_key"):
            sk = step["shortcut_key"].split("  \u2014")[0].strip()
            desc = f"\u2328\ufe0f {sk}"
        else:
            desc = step.get("description") or step.get("text", "")
        if len(desc) > 32:
            desc = desc[:29] + "..."
        tk.Label(row, text=desc,
                 bg=COLORS["section_bg"], fg=COLORS["text"],
                 font=("Segoe UI", 9), anchor="w").pack(side="left", padx=(4, 0))

        tk.Button(row, text="Edit", bg=COLORS["border"], fg=COLORS["text"],
                  font=("Segoe UI", 8), relief="flat", cursor="hand2",
                  command=lambda si=sec_idx, st=step_idx: self._edit_step(si, st)
                  ).pack(side="right", padx=2)
        tk.Button(row, text="\u2715", bg=COLORS["red"], fg=COLORS["bg"],
                  font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
                  command=lambda si=sec_idx, st=step_idx: self._delete_step(si, st)
                  ).pack(side="right", padx=2)
        tk.Button(row, text="\u2193", bg=COLORS["border"], fg=COLORS["text"],
                  font=("Segoe UI", 8), relief="flat", cursor="hand2",
                  command=lambda si=sec_idx, st=step_idx: self._move_step(si, st, 1)
                  ).pack(side="right", padx=1)
        tk.Button(row, text="\u2191", bg=COLORS["border"], fg=COLORS["text"],
                  font=("Segoe UI", 8), relief="flat", cursor="hand2",
                  command=lambda si=sec_idx, st=step_idx: self._move_step(si, st, -1)
                  ).pack(side="right", padx=1)

    def _add_step(self, sec_idx):
        StepEditorDialog(
            self.app_ref.root,
            on_save=lambda step: self._on_step_saved(sec_idx, step))

    def _on_step_saved(self, sec_idx, step):
        self.task_data["sections"][sec_idx].setdefault("steps", []).append(step)
        self.app_ref.save_data()
        self._refresh_ui()

    def _edit_step(self, sec_idx, step_idx):
        step = self.task_data["sections"][sec_idx]["steps"][step_idx]
        def on_save(updated):
            self.task_data["sections"][sec_idx]["steps"][step_idx] = updated
            self.app_ref.save_data()
            self._refresh_ui()
        StepEditorDialog(self.app_ref.root, step_data=step, on_save=on_save)

    def _delete_step(self, sec_idx, step_idx):
        if messagebox.askyesno("Delete Step", f"Delete step {step_idx + 1}?"):
            self.task_data["sections"][sec_idx]["steps"].pop(step_idx)
            self.app_ref.save_data()
            self._refresh_ui()

    def _move_step(self, sec_idx, step_idx, direction):
        steps = self.task_data["sections"][sec_idx].get("steps", [])
        new_idx = step_idx + direction
        if 0 <= new_idx < len(steps):
            steps[step_idx], steps[new_idx] = steps[new_idx], steps[step_idx]
            self.app_ref.save_data()
            self._refresh_ui()

    def _rename_task(self, event=None):
        new_name = simpledialog.askstring(
            "Rename Task", "Enter new task name:",
            initialvalue=self.task_data.get("name", ""),
            parent=self.app_ref.root)
        if new_name and new_name.strip():
            self.task_data["name"] = new_name.strip()
            self.name_var.set(new_name.strip())
            self.app_ref.save_data()

    def _delete_task(self):
        if self.is_running:
            messagebox.showwarning("Task Running",
                "Stop the task before deleting.", parent=self.app_ref.root)
            return
        if messagebox.askyesno("Delete Task",
                f"Delete task '{self.task_data.get('name')}'? This cannot be undone."):
            self.app_ref.delete_task(self.index)

    def _run_task(self):
        if self.is_running:
            return
        total_steps = sum(
            len(s.get("steps", [])) for s in self.task_data.get("sections", []))
        if total_steps == 0:
            messagebox.showinfo("No Steps", "This task has no steps to run.")
            return
        self._save_loop_settings()

        coords = [
            (step.get("x", 0), step.get("y", 0))
            for sec in self.task_data.get("sections", [])
            for step in sec.get("steps", [])
            if step.get("action") not in ("Press Enter", "Keyboard Shortcut")
        ]

        def on_status(msg):
            self.status_var.set(msg)
            if self._pause_mgr:
                if self._pause_mgr.is_paused and self._pause_mgr.manual_pause_active:
                    self.pause_btn.config(text="\u25b6  Resume", bg=COLORS["green"])
                    self.status_lbl.config(fg=COLORS["yellow"])
                elif self._pause_mgr.is_paused:
                    self.pause_btn.config(text="\u23f8  Pause", bg=COLORS["pause_bg"])
                    self.status_lbl.config(fg=COLORS["yellow"])
                else:
                    self.pause_btn.config(text="\u23f8  Pause", bg=COLORS["pause_bg"])
                    self.status_lbl.config(fg=COLORS["subtext"])

        self._pause_mgr = AutoPauseManager(
            on_status_update=lambda msg: self.app_ref.root.after(0, lambda m=msg: on_status(m)),
            root_widget=self.app_ref.root)
        self._pause_mgr.start(automation_coords=coords)

        self.is_running = True
        self.run_btn.config(text="\u23f3 Running...", state="disabled", bg=COLORS["yellow"])
        self.pause_btn.config(state="normal")
        self.stop_btn.config(state="normal")
        self.status_var.set("Running...")
        threading.Thread(target=self._execute_task, daemon=True).start()

    def _on_task_finished(self):
        self.is_running = False
        self._pause_mgr = None
        self.run_btn.config(text="\u25b6  Run Task", state="normal", bg=COLORS["green"])
        self.pause_btn.config(text="\u23f8  Pause", state="disabled", bg=COLORS["pause_bg"])
        self.stop_btn.config(state="disabled")
        self.status_lbl.config(fg=COLORS["subtext"])

    # ------------------------------------------------------------------
    # Execute a single step
    # ------------------------------------------------------------------
    def _execute_step(self, step, pm):
        """
        Execute one step.
        pm (AutoPauseManager) is passed explicitly so the step can
        suppress the mouse-movement detector while the automation
        intentionally moves the cursor.
        """
        action = step.get("action", "Click")
        x, y   = step.get("x", 0), step.get("y", 0)
        text   = step.get("text", "")
        delay  = step.get("delay", 0.5)

        if action == "Click":
            pm.set_automation_moving(True)
            pyautogui.click(x, y)
            pm.set_automation_moving(False)

        elif action == "Input":
            pm.set_automation_moving(True)
            pyautogui.click(x, y)
            pm.set_automation_moving(False)
            time.sleep(0.2)
            pyautogui.hotkey("ctrl", "a")
            pyautogui.typewrite(text, interval=0.05)

        elif action == "Scroll":
            direction = step.get("scroll_direction", "down")
            amount    = step.get("scroll_amount", 3)
            # Use pyautogui.scroll/hscroll with explicit x,y so the mouse
            # does NOT physically move to (0,0) — which triggers the failsafe.
            pm.set_automation_moving(True)
            if direction == "down":
                pyautogui.scroll(-amount, x=x, y=y)
            elif direction == "up":
                pyautogui.scroll(amount, x=x, y=y)
            elif direction == "left":
                pyautogui.hscroll(-amount, x=x, y=y)
            elif direction == "right":
                pyautogui.hscroll(amount, x=x, y=y)
            pm.set_automation_moving(False)

        elif action == "Typewrite":
            pm.set_automation_moving(True)
            pyautogui.click(x, y)
            pm.set_automation_moving(False)
            time.sleep(0.2)
            pyautogui.typewrite(text, interval=0.08)

        elif action == "Press Enter":
            pyautogui.press("enter")

        elif action == "Keyboard Shortcut":
            shortcut_label = step.get("shortcut_key")
            if shortcut_label:
                keys = None
                for cat_shortcuts in KEYBOARD_SHORTCUTS.values():
                    for lbl, key_tuple in cat_shortcuts:
                        if lbl == shortcut_label:
                            keys = key_tuple
                            break
                    if keys:
                        break
                if keys:
                    pyautogui.hotkey(*keys)

        time.sleep(delay)

    # ------------------------------------------------------------------
    # Execution engine
    # ------------------------------------------------------------------
    def _execute_task(self):
        pm = self._pause_mgr
        loop_enabled    = self.task_data.get("loop_enabled", False)
        task_loop_count = max(1, self.task_data.get("loop_count", 1))
        sections        = self.task_data.get("sections", [])

        def run_section_once(sec, iteration_label=""):
            for step_idx, step in enumerate(sec.get("steps", [])):
                if not pm.wait_if_paused():
                    return False
                pm.on_status_update(
                    f"{iteration_label}[{sec['name']}] Step {step_idx + 1}: {step.get('action')}")
                self._execute_step(step, pm)
                if pm.is_stopped:
                    return False
            return True

        try:
            pm.automation_running = True
            if not loop_enabled:
                for sec in sections:
                    if not run_section_once(sec):
                        raise StopIteration
            else:
                for iteration in range(1, task_loop_count + 1):
                    if pm.is_stopped:
                        break
                    iter_lbl = f"[Iter {iteration}/{task_loop_count}] "
                    for sec in sections:
                        if pm.is_stopped:
                            break
                        sec_loop = sec.get("loop_count", 0)
                        if not sec.get("steps"):
                            continue
                        if sec_loop == 0:
                            if not run_section_once(sec, iter_lbl):
                                raise StopIteration
                        else:
                            for sec_iter in range(1, sec_loop + 1):
                                if pm.is_stopped:
                                    break
                                sl = f"{iter_lbl}[{sec['name']} Loop {sec_iter}/{sec_loop}] "
                                if not run_section_once(sec, sl):
                                    raise StopIteration
            if not pm.is_stopped:
                pm.on_status_update("\u2705 Completed successfully")
        except StopIteration:
            pass
        except Exception as e:
            pm.on_status_update(f"\u274c Error: {e}")
        finally:
            pm.stop()
            self.app_ref.root.after(0, self._on_task_finished)


# ===========================================================================
# AutoFlowApp
# ===========================================================================
class AutoFlowApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AutoFlow v1.0 \u2014 PyAutoGUI Task Automation Builder")
        self.root.geometry("980x720")
        self.root.configure(bg=COLORS["bg"])
        self.root.minsize(700, 500)
        self.tasks = []
        self.task_cards = []
        self._load_data()
        self._build_ui()
        self._render_tasks()

    def _build_ui(self):
        topbar = tk.Frame(self.root, bg=COLORS["sidebar"], height=54)
        topbar.pack(fill="x", side="top")
        topbar.pack_propagate(False)
        tk.Label(topbar, text="\u26a1 AutoFlow",
                 bg=COLORS["sidebar"], fg=COLORS["accent"],
                 font=("Segoe UI", 16, "bold")
                 ).pack(side="left", padx=16, pady=10)
        tk.Label(topbar, text="v1.0  \u2014  PyAutoGUI Task Automation Builder",
                 bg=COLORS["sidebar"], fg=COLORS["subtext"],
                 font=("Segoe UI", 9)
                 ).pack(side="left", padx=4, pady=10)
        tk.Button(topbar, text="\uff0b New Task",
                  bg=COLORS["accent"], fg=COLORS["bg"],
                  font=("Segoe UI", 10, "bold"), relief="flat",
                  cursor="hand2", padx=14, pady=6,
                  command=self._create_task
                  ).pack(side="right", padx=12, pady=10)

        container = tk.Frame(self.root, bg=COLORS["bg"])
        container.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(container, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll_frame = tk.Frame(self.canvas, bg=COLORS["bg"])
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.scroll_frame, anchor="nw")
        self.scroll_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        footer = tk.Frame(self.root, bg=COLORS["sidebar"], height=28)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Label(
            footer,
            text=("Tip: Auto-pause activates on mouse/keyboard activity during automation. "
                  "Use \u23f8 Pause / \u23f9 Stop for manual control."),
            bg=COLORS["sidebar"], fg=COLORS["subtext"],
            font=("Segoe UI", 8)
        ).pack(side="left", padx=12)

    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _create_task(self):
        name = simpledialog.askstring(
            "New Task", "Enter a name for the new task:", parent=self.root)
        if name and name.strip():
            task = {
                "name": name.strip(),
                "loop_enabled": False,
                "loop_count": 1,
                "sections": [{"name": "Section 1", "loop_count": 0, "steps": []}],
            }
            self.tasks.append(task)
            self.save_data()
            self._render_tasks()

    def _render_tasks(self):
        for w in self.scroll_frame.winfo_children():
            w.destroy()
        self.task_cards = []
        if not self.tasks:
            tk.Label(
                self.scroll_frame,
                text="No tasks yet.\nClick '\uff0b New Task' to get started!",
                bg=COLORS["bg"], fg=COLORS["subtext"],
                font=("Segoe UI", 13), justify="center"
            ).pack(pady=80)
            return
        for i, task in enumerate(self.tasks):
            card = TaskCard(self.scroll_frame, task, self, i)
            self.task_cards.append(card)

    def delete_task(self, index):
        if 0 <= index < len(self.tasks):
            self.tasks.pop(index)
            self.save_data()
            self._render_tasks()

    def _load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    self.tasks = json.load(f)
            except Exception:
                self.tasks = []
        else:
            self.tasks = []

    def save_data(self):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.tasks, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save data: {e}")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = AutoFlowApp()
    app.run()
