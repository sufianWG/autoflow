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

ACTION_TYPES = ["Click", "Input", "Scroll", "Typewrite"]

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
}

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3


class CoordinateSelector:
    """Full-screen overlay for selecting a coordinate point by clicking."""

    def __init__(self, parent, callback):
        self.parent = parent
        self.callback = callback
        self.overlay = None
        self._build()

    def _build(self):
        self.overlay = tk.Toplevel(self.parent)
        self.overlay.attributes("-fullscreen", True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-alpha", 0.35)
        self.overlay.configure(bg="#000000")
        self.overlay.config(cursor="crosshair")

        canvas = tk.Canvas(
            self.overlay,
            bg="#000000",
            highlightthickness=0,
        )
        canvas.pack(fill="both", expand=True)

        screen_w = self.overlay.winfo_screenwidth()
        screen_h = self.overlay.winfo_screenheight()

        canvas.create_text(
            screen_w // 2,
            screen_h // 2,
            text="Click on the target position  |  Press ESC to cancel",
            fill="#ffffff",
            font=("Arial", 20, "bold"),
        )

        canvas.bind("<Button-1>", self._on_click)
        self.overlay.bind("<Escape>", self._on_cancel)
        canvas.focus_set()

    def _on_click(self, event):
        x, y = event.x_root, event.y_root
        self.overlay.destroy()
        self.callback(x, y)

    def _on_cancel(self, event):
        self.overlay.destroy()
        self.callback(None, None)


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
            "action": "Click",
            "x": 0,
            "y": 0,
            "text": "",
            "scroll_direction": "down",
            "scroll_amount": 3,
            "delay": 0.5,
            "description": "",
        }

        self._build()
        self.win.transient(parent)
        self.win.wait_window()

    def _lbl(self, parent, text, row, col=0, colspan=1):
        tk.Label(
            parent,
            text=text,
            bg=COLORS["bg"],
            fg=COLORS["subtext"],
            font=("Segoe UI", 9),
        ).grid(row=row, column=col, columnspan=colspan, sticky="w", padx=8, pady=(6, 0))

    def _build(self):
        pad = {"padx": 12, "pady": 4}
        frame = tk.Frame(self.win, bg=COLORS["bg"], padx=16, pady=16)
        frame.pack(fill="both", expand=True)

        # Description
        self._lbl(frame, "Step Description (optional)", 0)
        self.desc_var = tk.StringVar(value=self.step_data.get("description", ""))
        tk.Entry(
            frame,
            textvariable=self.desc_var,
            bg=COLORS["card"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            font=("Segoe UI", 10),
            width=38,
            relief="flat",
        ).grid(row=1, column=0, columnspan=3, sticky="ew", padx=8, pady=(2, 8))

        # Action type
        self._lbl(frame, "Action Type", 2)
        self.action_var = tk.StringVar(value=self.step_data.get("action", "Click"))
        action_cb = ttk.Combobox(
            frame,
            textvariable=self.action_var,
            values=ACTION_TYPES,
            state="readonly",
            width=16,
        )
        action_cb.grid(row=3, column=0, sticky="w", padx=8, pady=(2, 8))
        action_cb.bind("<<ComboboxSelected>>", lambda e: self._toggle_fields())

        # Coordinate row
        self._lbl(frame, "Target Coordinate", 4)
        coord_row = tk.Frame(frame, bg=COLORS["bg"])
        coord_row.grid(row=5, column=0, columnspan=3, sticky="w", padx=8, pady=(2, 0))

        tk.Label(coord_row, text="X:", bg=COLORS["bg"], fg=COLORS["text"], font=("Segoe UI", 9)).pack(side="left")
        self.x_var = tk.IntVar(value=self.step_data.get("x", 0))
        self.x_entry = tk.Entry(
            coord_row,
            textvariable=self.x_var,
            bg=COLORS["card"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            font=("Segoe UI", 10),
            width=6,
            relief="flat",
        )
        self.x_entry.pack(side="left", padx=(2, 8))

        tk.Label(coord_row, text="Y:", bg=COLORS["bg"], fg=COLORS["text"], font=("Segoe UI", 9)).pack(side="left")
        self.y_var = tk.IntVar(value=self.step_data.get("y", 0))
        self.y_entry = tk.Entry(
            coord_row,
            textvariable=self.y_var,
            bg=COLORS["card"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            font=("Segoe UI", 10),
            width=6,
            relief="flat",
        )
        self.y_entry.pack(side="left", padx=(2, 8))

        self.pick_btn = tk.Button(
            coord_row,
            text="📍 Pick from Screen",
            bg=COLORS["accent2"],
            fg=COLORS["bg"],
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            cursor="hand2",
            command=self._pick_coordinate,
        )
        self.pick_btn.pack(side="left", padx=(0, 4))

        # Text / Typewrite input
        self._lbl(frame, "Text to Type (for Input / Typewrite)", 6)
        self.text_var = tk.StringVar(value=self.step_data.get("text", ""))
        self.text_entry = tk.Entry(
            frame,
            textvariable=self.text_var,
            bg=COLORS["card"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            font=("Segoe UI", 10),
            width=38,
            relief="flat",
        )
        self.text_entry.grid(row=7, column=0, columnspan=3, sticky="ew", padx=8, pady=(2, 8))

        # Scroll controls
        self._lbl(frame, "Scroll Direction", 8)
        self.scroll_dir_var = tk.StringVar(value=self.step_data.get("scroll_direction", "down"))
        self.scroll_dir_cb = ttk.Combobox(
            frame,
            textvariable=self.scroll_dir_var,
            values=["down", "up", "left", "right"],
            state="readonly",
            width=10,
        )
        self.scroll_dir_cb.grid(row=9, column=0, sticky="w", padx=8, pady=(2, 4))

        self._lbl(frame, "Scroll Amount (clicks)", 8, col=1)
        self.scroll_amount_var = tk.IntVar(value=self.step_data.get("scroll_amount", 3))
        self.scroll_amount_spin = tk.Spinbox(
            frame,
            from_=1,
            to=50,
            textvariable=self.scroll_amount_var,
            bg=COLORS["card"],
            fg=COLORS["text"],
            buttonbackground=COLORS["border"],
            font=("Segoe UI", 10),
            width=6,
            relief="flat",
        )
        self.scroll_amount_spin.grid(row=9, column=1, sticky="w", padx=8, pady=(2, 4))

        # Delay
        self._lbl(frame, "Delay after action (seconds)", 10)
        self.delay_var = tk.DoubleVar(value=self.step_data.get("delay", 0.5))
        tk.Spinbox(
            frame,
            from_=0,
            to=30,
            increment=0.1,
            format="%.1f",
            textvariable=self.delay_var,
            bg=COLORS["card"],
            fg=COLORS["text"],
            buttonbackground=COLORS["border"],
            font=("Segoe UI", 10),
            width=8,
            relief="flat",
        ).grid(row=11, column=0, sticky="w", padx=8, pady=(2, 12))

        # Buttons
        btn_row = tk.Frame(frame, bg=COLORS["bg"])
        btn_row.grid(row=12, column=0, columnspan=3, pady=(8, 0))

        tk.Button(
            btn_row,
            text="  Save Step  ",
            bg=COLORS["green"],
            fg=COLORS["bg"],
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            cursor="hand2",
            command=self._save,
        ).pack(side="left", padx=6)

        tk.Button(
            btn_row,
            text="  Cancel  ",
            bg=COLORS["border"],
            fg=COLORS["text"],
            font=("Segoe UI", 10),
            relief="flat",
            cursor="hand2",
            command=self.win.destroy,
        ).pack(side="left", padx=6)

        self._toggle_fields()

    def _toggle_fields(self):
        action = self.action_var.get()
        is_scroll = action == "Scroll"
        is_text = action in ("Input", "Typewrite")
        is_coord = action in ("Click", "Input", "Scroll", "Typewrite")

        state_text = "normal" if is_text else "disabled"
        state_scroll = "readonly" if is_scroll else "disabled"
        state_scroll_n = "normal" if is_scroll else "disabled"
        state_coord = "normal" if is_coord else "disabled"

        self.text_entry.config(state=state_text)
        self.scroll_dir_cb.config(state=state_scroll)
        self.scroll_amount_spin.config(state=state_scroll_n)
        self.x_entry.config(state=state_coord)
        self.y_entry.config(state=state_coord)
        self.pick_btn.config(state=state_coord)

    def _pick_coordinate(self):
        # Toplevel window cannot be iconified when set as transient.
        # Instead, withdraw both the dialog and its parent, then
        # restore them after coordinate selection — same pattern as sufianWG/uniapp.
        self.win.withdraw()
        self.parent.iconify()
        self.win.after(200, self._initiate_coordinate_pick)

    def _initiate_coordinate_pick(self):
        def on_coord(x, y):
            # Restore parent root first, then the dialog
            self.parent.deiconify()
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
            if x is not None and y is not None:
                self.x_var.set(x)
                self.y_var.set(y)

        CoordinateSelector(self.parent, on_coord)

    def _save(self):
        self.step_data["action"] = self.action_var.get()
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


class TaskCard:
    """Widget representing a single task with its steps list."""

    def __init__(self, parent_frame, task_data, app_ref, index):
        self.parent_frame = parent_frame
        self.task_data = task_data
        self.app_ref = app_ref
        self.index = index
        self.is_running = False
        self.steps_visible = True
        self._build()

    def _build(self):
        self.card = tk.Frame(
            self.parent_frame,
            bg=COLORS["card"],
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        self.card.pack(fill="x", padx=10, pady=6)

        # Header
        header = tk.Frame(self.card, bg=COLORS["card"])
        header.pack(fill="x", padx=10, pady=(8, 4))

        # Task name
        self.name_var = tk.StringVar(value=self.task_data.get("name", "Unnamed Task"))
        self.name_label = tk.Label(
            header,
            textvariable=self.name_var,
            bg=COLORS["card"],
            fg=COLORS["accent"],
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        )
        self.name_label.pack(side="left")
        self.name_label.bind("<Double-Button-1>", self._rename_task)

        # Right side buttons
        btn_frame = tk.Frame(header, bg=COLORS["card"])
        btn_frame.pack(side="right")

        self.run_btn = tk.Button(
            btn_frame,
            text="▶  Run Task",
            bg=COLORS["green"],
            fg=COLORS["bg"],
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            cursor="hand2",
            command=self._run_task,
        )
        self.run_btn.pack(side="left", padx=4)

        tk.Button(
            btn_frame,
            text="+ Add Step",
            bg=COLORS["accent2"],
            fg=COLORS["bg"],
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            cursor="hand2",
            command=self._add_step,
        ).pack(side="left", padx=4)

        tk.Button(
            btn_frame,
            text="✎ Rename",
            bg=COLORS["border"],
            fg=COLORS["text"],
            font=("Segoe UI", 9),
            relief="flat",
            cursor="hand2",
            command=self._rename_task,
        ).pack(side="left", padx=4)

        tk.Button(
            btn_frame,
            text="🗑 Delete Task",
            bg=COLORS["red"],
            fg=COLORS["bg"],
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            cursor="hand2",
            command=self._delete_task,
        ).pack(side="left", padx=4)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(
            self.card,
            textvariable=self.status_var,
            bg=COLORS["card"],
            fg=COLORS["subtext"],
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x", padx=10)

        # Steps container
        self.steps_frame = tk.Frame(self.card, bg=COLORS["step_bg"], pady=4)
        self.steps_frame.pack(fill="x", padx=10, pady=(4, 8))

        self._refresh_steps()

    def _refresh_steps(self):
        for widget in self.steps_frame.winfo_children():
            widget.destroy()

        steps = self.task_data.get("steps", [])
        if not steps:
            tk.Label(
                self.steps_frame,
                text="No steps yet. Click '+ Add Step' to begin.",
                bg=COLORS["step_bg"],
                fg=COLORS["subtext"],
                font=("Segoe UI", 9, "italic"),
            ).pack(padx=8, pady=4)
            return

        for i, step in enumerate(steps):
            self._build_step_row(i, step)

    def _build_step_row(self, idx, step):
        row = tk.Frame(self.steps_frame, bg=COLORS["step_bg"])
        row.pack(fill="x", padx=4, pady=2)

        action_colors = {
            "Click": COLORS["accent"],
            "Input": COLORS["accent2"],
            "Scroll": COLORS["yellow"],
            "Typewrite": COLORS["green"],
        }
        action = step.get("action", "Click")
        color = action_colors.get(action, COLORS["text"])

        # Step number badge
        tk.Label(
            row,
            text=f" {idx + 1} ",
            bg=color,
            fg=COLORS["bg"],
            font=("Segoe UI", 8, "bold"),
            width=3,
        ).pack(side="left", padx=(0, 4))

        # Action badge
        tk.Label(
            row,
            text=f"[{action}]",
            bg=COLORS["step_bg"],
            fg=color,
            font=("Segoe UI", 9, "bold"),
            width=10,
            anchor="w",
        ).pack(side="left")

        # Coords
        coord_text = f"({step.get('x', 0)}, {step.get('y', 0)})"
        tk.Label(
            row,
            text=coord_text,
            bg=COLORS["step_bg"],
            fg=COLORS["subtext"],
            font=("Consolas", 9),
            width=12,
            anchor="w",
        ).pack(side="left")

        # Description / text preview
        desc = step.get("description") or step.get("text", "")
        if len(desc) > 30:
            desc = desc[:27] + "..."
        tk.Label(
            row,
            text=desc,
            bg=COLORS["step_bg"],
            fg=COLORS["text"],
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(side="left", padx=(4, 0))

        # Action buttons
        tk.Button(
            row,
            text="Edit",
            bg=COLORS["border"],
            fg=COLORS["text"],
            font=("Segoe UI", 8),
            relief="flat",
            cursor="hand2",
            command=lambda i=idx: self._edit_step(i),
        ).pack(side="right", padx=2)

        tk.Button(
            row,
            text="✕",
            bg=COLORS["red"],
            fg=COLORS["bg"],
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            cursor="hand2",
            command=lambda i=idx: self._delete_step(i),
        ).pack(side="right", padx=2)

        tk.Button(
            row,
            text="↓",
            bg=COLORS["border"],
            fg=COLORS["text"],
            font=("Segoe UI", 8),
            relief="flat",
            cursor="hand2",
            command=lambda i=idx: self._move_step(i, 1),
        ).pack(side="right", padx=1)

        tk.Button(
            row,
            text="↑",
            bg=COLORS["border"],
            fg=COLORS["text"],
            font=("Segoe UI", 8),
            relief="flat",
            cursor="hand2",
            command=lambda i=idx: self._move_step(i, -1),
        ).pack(side="right", padx=1)

    def _add_step(self):
        StepEditorDialog(self.app_ref.root, on_save=self._on_step_saved)

    def _on_step_saved(self, step):
        self.task_data.setdefault("steps", []).append(step)
        self.app_ref.save_data()
        self._refresh_steps()

    def _edit_step(self, idx):
        step = self.task_data["steps"][idx]

        def on_save(updated):
            self.task_data["steps"][idx] = updated
            self.app_ref.save_data()
            self._refresh_steps()

        StepEditorDialog(self.app_ref.root, step_data=step, on_save=on_save)

    def _delete_step(self, idx):
        if messagebox.askyesno("Delete Step", f"Delete step {idx + 1}?"):
            self.task_data["steps"].pop(idx)
            self.app_ref.save_data()
            self._refresh_steps()

    def _move_step(self, idx, direction):
        steps = self.task_data.get("steps", [])
        new_idx = idx + direction
        if 0 <= new_idx < len(steps):
            steps[idx], steps[new_idx] = steps[new_idx], steps[idx]
            self.app_ref.save_data()
            self._refresh_steps()

    def _rename_task(self, event=None):
        new_name = simpledialog.askstring(
            "Rename Task",
            "Enter new task name:",
            initialvalue=self.task_data.get("name", ""),
            parent=self.app_ref.root,
        )
        if new_name and new_name.strip():
            self.task_data["name"] = new_name.strip()
            self.name_var.set(new_name.strip())
            self.app_ref.save_data()

    def _delete_task(self):
        if messagebox.askyesno("Delete Task", f"Delete task '{self.task_data.get('name')}'? This cannot be undone."):
            self.app_ref.delete_task(self.index)

    def _run_task(self):
        if self.is_running:
            return
        steps = self.task_data.get("steps", [])
        if not steps:
            messagebox.showinfo("No Steps", "This task has no steps to run.")
            return
        self.is_running = True
        self.run_btn.config(text="⏳ Running...", state="disabled", bg=COLORS["yellow"])
        self.status_var.set("Running...")
        t = threading.Thread(target=self._execute_steps, daemon=True)
        t.start()

    def _execute_steps(self):
        steps = self.task_data.get("steps", [])
        try:
            for i, step in enumerate(steps):
                action = step.get("action", "Click")
                x = step.get("x", 0)
                y = step.get("y", 0)
                text = step.get("text", "")
                delay = step.get("delay", 0.5)
                self.status_var.set(f"Step {i + 1}/{len(steps)}: {action}")

                if action == "Click":
                    pyautogui.click(x, y)

                elif action == "Input":
                    pyautogui.click(x, y)
                    time.sleep(0.2)
                    pyautogui.hotkey("ctrl", "a")
                    pyautogui.typewrite(text, interval=0.05)

                elif action == "Scroll":
                    direction = step.get("scroll_direction", "down")
                    amount = step.get("scroll_amount", 3)
                    pyautogui.moveTo(x, y)
                    if direction == "down":
                        pyautogui.scroll(-amount)
                    elif direction == "up":
                        pyautogui.scroll(amount)
                    elif direction == "left":
                        pyautogui.hscroll(-amount)
                    elif direction == "right":
                        pyautogui.hscroll(amount)

                elif action == "Typewrite":
                    pyautogui.click(x, y)
                    time.sleep(0.2)
                    pyautogui.typewrite(text, interval=0.08)

                time.sleep(delay)

            self.status_var.set("✅ Completed successfully")
        except pyautogui.FailSafeException:
            self.status_var.set("❌ Stopped: Failsafe triggered (mouse moved to corner)")
        except Exception as e:
            self.status_var.set(f"❌ Error: {str(e)}")
        finally:
            self.is_running = False
            self.run_btn.config(text="▶  Run Task", state="normal", bg=COLORS["green"])


class AutoFlowApp:
    """Main AutoFlow application."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AutoFlow — PyAutoGUI Task Automation Builder")
        self.root.geometry("920x700")
        self.root.configure(bg=COLORS["bg"])
        self.root.minsize(700, 500)

        self.tasks = []
        self.task_cards = []

        self._load_data()
        self._build_ui()
        self._render_tasks()

    def _build_ui(self):
        # Top bar
        topbar = tk.Frame(self.root, bg=COLORS["sidebar"], height=54)
        topbar.pack(fill="x", side="top")
        topbar.pack_propagate(False)

        tk.Label(
            topbar,
            text="⚡ AutoFlow",
            bg=COLORS["sidebar"],
            fg=COLORS["accent"],
            font=("Segoe UI", 16, "bold"),
        ).pack(side="left", padx=16, pady=10)

        tk.Label(
            topbar,
            text="PyAutoGUI Task Automation Builder",
            bg=COLORS["sidebar"],
            fg=COLORS["subtext"],
            font=("Segoe UI", 9),
        ).pack(side="left", padx=4, pady=10)

        tk.Button(
            topbar,
            text="＋ New Task",
            bg=COLORS["accent"],
            fg=COLORS["bg"],
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=6,
            command=self._create_task,
        ).pack(side="right", padx=12, pady=10)

        # Scrollable content area
        container = tk.Frame(self.root, bg=COLORS["bg"])
        container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(container, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.scroll_frame = tk.Frame(self.canvas, bg=COLORS["bg"])
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")

        self.scroll_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Footer
        footer = tk.Frame(self.root, bg=COLORS["sidebar"], height=28)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Label(
            footer,
            text="Tip: Double-click task name to rename  |  Drag ↑↓ buttons to reorder steps  |  Move mouse to top-left corner to trigger Failsafe",
            bg=COLORS["sidebar"],
            fg=COLORS["subtext"],
            font=("Segoe UI", 8),
        ).pack(side="left", padx=12)

    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _create_task(self):
        name = simpledialog.askstring(
            "New Task",
            "Enter a name for the new task:",
            parent=self.root,
        )
        if name and name.strip():
            task = {"name": name.strip(), "steps": []}
            self.tasks.append(task)
            self.save_data()
            self._render_tasks()

    def _render_tasks(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.task_cards = []

        if not self.tasks:
            tk.Label(
                self.scroll_frame,
                text="No tasks yet.\nClick '＋ New Task' to get started!",
                bg=COLORS["bg"],
                fg=COLORS["subtext"],
                font=("Segoe UI", 13),
                justify="center",
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
