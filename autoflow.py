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
    "section_bg": "#1a1a2e",
    "section_header": "#2a2a3e",
    "loop_accent": "#fab387",
}

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3


# ---------------------------------------------------------------------------
# CoordinateSelector
# ---------------------------------------------------------------------------
class CoordinateSelector:
    """Full-screen screenshot overlay for selecting a coordinate by dragging."""

    def __init__(self, parent, callback):
        self.parent = parent
        self.callback = callback
        self._build()

    def _build(self):
        try:
            screenshot = ImageGrab.grab()
        except Exception as e:
            messagebox.showerror("Screenshot Error", f"Failed to capture screen: {e}", parent=self.parent)
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

        screen_w = screenshot.width
        screen_h = screenshot.height

        instruction_state = {"bg_id": None, "text_id": None}
        INSTRUCTION_TEXT = "Click and drag to select target area  |  Press ESC to cancel"
        BAR_HEIGHT = 50
        MARGIN = 10

        def draw_instruction(mouse_y):
            if instruction_state["bg_id"] is not None:
                canvas.delete(instruction_state["bg_id"])
            if instruction_state["text_id"] is not None:
                canvas.delete(instruction_state["text_id"])
            if mouse_y < screen_h / 3:
                y1 = screen_h - BAR_HEIGHT - MARGIN
                y2 = screen_h - MARGIN
            else:
                y1 = MARGIN
                y2 = MARGIN + BAR_HEIGHT
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
            rect_state["x2"] = canvas.canvasx(e.x)
            rect_state["y2"] = canvas.canvasy(e.y)
            x1 = min(rect_state["x1"], rect_state["x2"])
            x2 = max(rect_state["x1"], rect_state["x2"])
            y1 = min(rect_state["y1"], rect_state["y2"])
            y2 = max(rect_state["y1"], rect_state["y2"])
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            sel_win.grab_release()
            sel_win.destroy()
            self.callback(cx, cy)

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


# ---------------------------------------------------------------------------
# StepEditorDialog
# ---------------------------------------------------------------------------
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
        }

        self._build()
        self.win.transient(parent)
        self.win.wait_window()

    def _lbl(self, parent, text, row, col=0, colspan=1):
        tk.Label(parent, text=text, bg=COLORS["bg"], fg=COLORS["subtext"],
                 font=("Segoe UI", 9)).grid(
            row=row, column=col, columnspan=colspan, sticky="w", padx=8, pady=(6, 0))

    def _build(self):
        frame = tk.Frame(self.win, bg=COLORS["bg"], padx=16, pady=16)
        frame.pack(fill="both", expand=True)

        self._lbl(frame, "Step Description (optional)", 0)
        self.desc_var = tk.StringVar(value=self.step_data.get("description", ""))
        tk.Entry(frame, textvariable=self.desc_var, bg=COLORS["card"], fg=COLORS["text"],
                 insertbackground=COLORS["text"], font=("Segoe UI", 10), width=38,
                 relief="flat").grid(row=1, column=0, columnspan=3, sticky="ew", padx=8, pady=(2, 8))

        self._lbl(frame, "Action Type", 2)
        self.action_var = tk.StringVar(value=self.step_data.get("action", "Click"))
        action_cb = ttk.Combobox(frame, textvariable=self.action_var, values=ACTION_TYPES,
                                 state="readonly", width=16)
        action_cb.grid(row=3, column=0, sticky="w", padx=8, pady=(2, 8))
        action_cb.bind("<<ComboboxSelected>>", lambda e: self._toggle_fields())

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

        self.pick_btn = tk.Button(coord_row, text="\U0001f4cd Pick from Screen",
                                  bg=COLORS["accent2"], fg=COLORS["bg"],
                                  font=("Segoe UI", 9, "bold"), relief="flat",
                                  cursor="hand2", command=self._pick_coordinate)
        self.pick_btn.pack(side="left", padx=(0, 4))

        self._lbl(frame, "Text to Type (for Input / Typewrite)", 6)
        self.text_var = tk.StringVar(value=self.step_data.get("text", ""))
        self.text_entry = tk.Entry(frame, textvariable=self.text_var, bg=COLORS["card"],
                                   fg=COLORS["text"], insertbackground=COLORS["text"],
                                   font=("Segoe UI", 10), width=38, relief="flat")
        self.text_entry.grid(row=7, column=0, columnspan=3, sticky="ew", padx=8, pady=(2, 8))

        self._lbl(frame, "Scroll Direction", 8)
        self.scroll_dir_var = tk.StringVar(value=self.step_data.get("scroll_direction", "down"))
        self.scroll_dir_cb = ttk.Combobox(frame, textvariable=self.scroll_dir_var,
                                          values=["down", "up", "left", "right"],
                                          state="readonly", width=10)
        self.scroll_dir_cb.grid(row=9, column=0, sticky="w", padx=8, pady=(2, 4))

        self._lbl(frame, "Scroll Amount (clicks)", 8, col=1)
        self.scroll_amount_var = tk.IntVar(value=self.step_data.get("scroll_amount", 3))
        self.scroll_amount_spin = tk.Spinbox(frame, from_=1, to=50,
                                             textvariable=self.scroll_amount_var,
                                             bg=COLORS["card"], fg=COLORS["text"],
                                             buttonbackground=COLORS["border"],
                                             font=("Segoe UI", 10), width=6, relief="flat")
        self.scroll_amount_spin.grid(row=9, column=1, sticky="w", padx=8, pady=(2, 4))

        self._lbl(frame, "Delay after action (seconds)", 10)
        self.delay_var = tk.DoubleVar(value=self.step_data.get("delay", 0.5))
        tk.Spinbox(frame, from_=0, to=30, increment=0.1, format="%.1f",
                   textvariable=self.delay_var, bg=COLORS["card"], fg=COLORS["text"],
                   buttonbackground=COLORS["border"], font=("Segoe UI", 10), width=8,
                   relief="flat").grid(row=11, column=0, sticky="w", padx=8, pady=(2, 12))

        btn_row = tk.Frame(frame, bg=COLORS["bg"])
        btn_row.grid(row=12, column=0, columnspan=3, pady=(8, 0))
        tk.Button(btn_row, text="  Save Step  ", bg=COLORS["green"], fg=COLORS["bg"],
                  font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
                  command=self._save).pack(side="left", padx=6)
        tk.Button(btn_row, text="  Cancel  ", bg=COLORS["border"], fg=COLORS["text"],
                  font=("Segoe UI", 10), relief="flat", cursor="hand2",
                  command=self.win.destroy).pack(side="left", padx=6)

        self._toggle_fields()

    def _toggle_fields(self):
        action = self.action_var.get()
        is_scroll = action == "Scroll"
        is_text = action in ("Input", "Typewrite")
        self.text_entry.config(state="normal" if is_text else "disabled")
        self.scroll_dir_cb.config(state="readonly" if is_scroll else "disabled")
        self.scroll_amount_spin.config(state="normal" if is_scroll else "disabled")
        self.x_entry.config(state="normal")
        self.y_entry.config(state="normal")
        self.pick_btn.config(state="normal")

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


# ---------------------------------------------------------------------------
# TaskCard  (with Loop + Section support)
# ---------------------------------------------------------------------------
class TaskCard:
    """Widget representing a single task with optional loop sections."""

    def __init__(self, parent_frame, task_data, app_ref, index):
        self.parent_frame = parent_frame
        self.task_data = task_data
        self.app_ref = app_ref
        self.index = index
        self.is_running = False

        # Ensure data structure is initialised
        if "loop_enabled" not in self.task_data:
            self.task_data["loop_enabled"] = False
        if "loop_count" not in self.task_data:
            self.task_data["loop_count"] = 1
        # Legacy: if task has flat 'steps', migrate to sections
        if "steps" in self.task_data and "sections" not in self.task_data:
            self.task_data["sections"] = [
                {"name": "Section 1", "loop_count": 0, "steps": self.task_data.pop("steps")}
            ]
        if "sections" not in self.task_data:
            self.task_data["sections"] = [
                {"name": "Section 1", "loop_count": 0, "steps": []}
            ]

        self._build()

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------
    def _build(self):
        self.card = tk.Frame(self.parent_frame, bg=COLORS["card"], bd=0,
                             highlightthickness=1, highlightbackground=COLORS["border"])
        self.card.pack(fill="x", padx=10, pady=6)

        # ---- Header row ----
        header = tk.Frame(self.card, bg=COLORS["card"])
        header.pack(fill="x", padx=10, pady=(8, 4))

        self.name_var = tk.StringVar(value=self.task_data.get("name", "Unnamed Task"))
        name_lbl = tk.Label(header, textvariable=self.name_var, bg=COLORS["card"],
                            fg=COLORS["accent"], font=("Segoe UI", 12, "bold"), anchor="w")
        name_lbl.pack(side="left")
        name_lbl.bind("<Double-Button-1>", self._rename_task)

        btn_frame = tk.Frame(header, bg=COLORS["card"])
        btn_frame.pack(side="right")

        self.run_btn = tk.Button(btn_frame, text="\u25b6  Run Task", bg=COLORS["green"],
                                 fg=COLORS["bg"], font=("Segoe UI", 9, "bold"),
                                 relief="flat", cursor="hand2", command=self._run_task)
        self.run_btn.pack(side="left", padx=4)

        tk.Button(btn_frame, text="\u270e Rename", bg=COLORS["border"], fg=COLORS["text"],
                  font=("Segoe UI", 9), relief="flat", cursor="hand2",
                  command=self._rename_task).pack(side="left", padx=4)

        tk.Button(btn_frame, text="\U0001f5d1 Delete Task", bg=COLORS["red"], fg=COLORS["bg"],
                  font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
                  command=self._delete_task).pack(side="left", padx=4)

        # ---- Loop control bar ----
        loop_bar = tk.Frame(self.card, bg=COLORS["card"])
        loop_bar.pack(fill="x", padx=10, pady=(0, 4))

        self.loop_enabled_var = tk.BooleanVar(value=self.task_data.get("loop_enabled", False))
        loop_chk = tk.Checkbutton(
            loop_bar, text="\U0001f501  Enable Loop",
            variable=self.loop_enabled_var,
            bg=COLORS["card"], fg=COLORS["loop_accent"],
            selectcolor=COLORS["bg"], activebackground=COLORS["card"],
            activeforeground=COLORS["loop_accent"],
            font=("Segoe UI", 9, "bold"),
            command=self._on_loop_toggle,
        )
        loop_chk.pack(side="left")

        tk.Label(loop_bar, text="   Loop Count:", bg=COLORS["card"],
                 fg=COLORS["subtext"], font=("Segoe UI", 9)).pack(side="left")

        self.loop_count_var = tk.IntVar(value=max(1, self.task_data.get("loop_count", 1)))
        self.loop_count_spin = tk.Spinbox(
            loop_bar, from_=1, to=9999, textvariable=self.loop_count_var,
            bg=COLORS["card"], fg=COLORS["loop_accent"],
            buttonbackground=COLORS["border"],
            font=("Segoe UI", 9, "bold"), width=6, relief="flat",
            command=self._save_loop_settings,
        )
        self.loop_count_spin.pack(side="left", padx=(4, 12))
        self.loop_count_spin.bind("<FocusOut>", lambda e: self._save_loop_settings())

        tk.Label(loop_bar, text="times", bg=COLORS["card"],
                 fg=COLORS["subtext"], font=("Segoe UI", 9)).pack(side="left")

        # Add Section button (visible only when loop enabled)
        self.add_section_btn = tk.Button(
            loop_bar, text="+ Add Section", bg=COLORS["loop_accent"], fg=COLORS["bg"],
            font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
            command=self._add_section,
        )
        self.add_section_btn.pack(side="left", padx=(16, 0))

        # ---- Status ----
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self.card, textvariable=self.status_var, bg=COLORS["card"],
                 fg=COLORS["subtext"], font=("Segoe UI", 8), anchor="w").pack(
            fill="x", padx=10)

        # ---- Sections container ----
        self.sections_frame = tk.Frame(self.card, bg=COLORS["step_bg"], pady=4)
        self.sections_frame.pack(fill="x", padx=10, pady=(4, 8))

        self._refresh_ui()

    # ------------------------------------------------------------------
    # Loop toggle
    # ------------------------------------------------------------------
    def _on_loop_toggle(self):
        enabled = self.loop_enabled_var.get()
        self.task_data["loop_enabled"] = enabled
        self.app_ref.save_data()
        self._refresh_ui()

    def _save_loop_settings(self):
        self.task_data["loop_enabled"] = self.loop_enabled_var.get()
        try:
            self.task_data["loop_count"] = int(self.loop_count_var.get())
        except Exception:
            self.task_data["loop_count"] = 1
        self.app_ref.save_data()

    # ------------------------------------------------------------------
    # Section management
    # ------------------------------------------------------------------
    def _add_section(self):
        name = simpledialog.askstring(
            "New Section", "Enter section name:",
            initialvalue=f"Section {len(self.task_data['sections']) + 1}",
            parent=self.app_ref.root,
        )
        if name and name.strip():
            self.task_data["sections"].append(
                {"name": name.strip(), "loop_count": 0, "steps": []}
            )
            self.app_ref.save_data()
            self._refresh_ui()

    def _delete_section(self, sec_idx):
        if len(self.task_data["sections"]) <= 1:
            messagebox.showwarning("Cannot Delete",
                                   "A task must have at least one section.",
                                   parent=self.app_ref.root)
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
            initialvalue=sec["name"], parent=self.app_ref.root,
        )
        if new_name and new_name.strip():
            sec["name"] = new_name.strip()
            self.app_ref.save_data()
            self._refresh_ui()

    # ------------------------------------------------------------------
    # Full UI refresh
    # ------------------------------------------------------------------
    def _refresh_ui(self):
        loop_enabled = self.loop_enabled_var.get()

        # Show/hide loop-related controls
        if loop_enabled:
            self.loop_count_spin.config(state="normal")
            self.add_section_btn.pack(side="left", padx=(16, 0))
        else:
            self.loop_count_spin.config(state="disabled")
            self.add_section_btn.pack_forget()

        for widget in self.sections_frame.winfo_children():
            widget.destroy()

        sections = self.task_data.get("sections", [])
        for sec_idx, section in enumerate(sections):
            self._build_section(sec_idx, section, loop_enabled)

    def _build_section(self, sec_idx, section, loop_enabled):
        # Section container
        sec_frame = tk.Frame(self.sections_frame, bg=COLORS["section_bg"],
                             highlightthickness=1,
                             highlightbackground=COLORS["border"] if not loop_enabled
                             else COLORS["loop_accent"])
        sec_frame.pack(fill="x", padx=4, pady=4)

        # Section header
        sec_header = tk.Frame(sec_frame, bg=COLORS["section_header"])
        sec_header.pack(fill="x")

        # Section name label
        tk.Label(sec_header,
                 text=f"\U0001f4c2  {section['name']}",
                 bg=COLORS["section_header"],
                 fg=COLORS["loop_accent"] if loop_enabled else COLORS["accent2"],
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=8, pady=4)

        # Loop count for this section (only visible when loop enabled)
        if loop_enabled:
            tk.Label(sec_header, text="Loop:", bg=COLORS["section_header"],
                     fg=COLORS["subtext"], font=("Segoe UI", 8)).pack(side="left", padx=(8, 2))

            sec_loop_var = tk.IntVar(value=section.get("loop_count", 0))

            def make_sec_loop_handler(idx, var):
                def handler(*args):
                    try:
                        self.task_data["sections"][idx]["loop_count"] = int(var.get())
                    except Exception:
                        self.task_data["sections"][idx]["loop_count"] = 0
                    self.app_ref.save_data()
                return handler

            sec_spin = tk.Spinbox(
                sec_header, from_=0, to=9999, textvariable=sec_loop_var,
                bg=COLORS["section_header"], fg=COLORS["loop_accent"],
                buttonbackground=COLORS["border"],
                font=("Segoe UI", 8, "bold"), width=5, relief="flat",
                command=make_sec_loop_handler(sec_idx, sec_loop_var),
            )
            sec_spin.pack(side="left", padx=(0, 4))
            sec_spin.bind("<FocusOut>", make_sec_loop_handler(sec_idx, sec_loop_var))

            # Loop count hint
            hint = "(0 = no loop)" if section.get("loop_count", 0) == 0 else f"\u21ba {section.get('loop_count')}x"
            tk.Label(sec_header, text=hint,
                     bg=COLORS["section_header"],
                     fg=COLORS["yellow"] if section.get("loop_count", 0) > 0 else COLORS["subtext"],
                     font=("Segoe UI", 8, "italic")).pack(side="left", padx=2)

        # Section action buttons
        sec_btns = tk.Frame(sec_header, bg=COLORS["section_header"])
        sec_btns.pack(side="right", padx=4)

        tk.Button(sec_btns, text="+ Step", bg=COLORS["accent2"], fg=COLORS["bg"],
                  font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
                  command=lambda i=sec_idx: self._add_step(i)).pack(side="left", padx=2, pady=2)

        if loop_enabled:
            tk.Button(sec_btns, text="Rename", bg=COLORS["border"], fg=COLORS["text"],
                      font=("Segoe UI", 8), relief="flat", cursor="hand2",
                      command=lambda i=sec_idx: self._rename_section(i)).pack(side="left", padx=2, pady=2)

            tk.Button(sec_btns, text="\u2715 Del", bg=COLORS["red"], fg=COLORS["bg"],
                      font=("Segoe UI", 8, "bold"), relief="flat", cursor="hand2",
                      command=lambda i=sec_idx: self._delete_section(i)).pack(side="left", padx=2, pady=2)

        # Steps inside section
        steps = section.get("steps", [])
        if not steps:
            tk.Label(sec_frame, text="No steps. Click '+ Step' to add.",
                     bg=COLORS["section_bg"], fg=COLORS["subtext"],
                     font=("Segoe UI", 8, "italic")).pack(padx=12, pady=4, anchor="w")
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
        }
        action = step.get("action", "Click")
        color = action_colors.get(action, COLORS["text"])

        tk.Label(row, text=f" {step_idx + 1} ", bg=color, fg=COLORS["bg"],
                 font=("Segoe UI", 8, "bold"), width=3).pack(side="left", padx=(0, 4))
        tk.Label(row, text=f"[{action}]", bg=COLORS["section_bg"], fg=color,
                 font=("Segoe UI", 9, "bold"), width=10, anchor="w").pack(side="left")
        tk.Label(row, text=f"({step.get('x', 0)}, {step.get('y', 0)})",
                 bg=COLORS["section_bg"], fg=COLORS["subtext"],
                 font=("Consolas", 9), width=12, anchor="w").pack(side="left")

        desc = step.get("description") or step.get("text", "")
        if len(desc) > 28:
            desc = desc[:25] + "..."
        tk.Label(row, text=desc, bg=COLORS["section_bg"], fg=COLORS["text"],
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

    # ------------------------------------------------------------------
    # Step CRUD
    # ------------------------------------------------------------------
    def _add_step(self, sec_idx):
        StepEditorDialog(self.app_ref.root,
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

    # ------------------------------------------------------------------
    # Rename / Delete task
    # ------------------------------------------------------------------
    def _rename_task(self, event=None):
        new_name = simpledialog.askstring(
            "Rename Task", "Enter new task name:",
            initialvalue=self.task_data.get("name", ""),
            parent=self.app_ref.root,
        )
        if new_name and new_name.strip():
            self.task_data["name"] = new_name.strip()
            self.name_var.set(new_name.strip())
            self.app_ref.save_data()

    def _delete_task(self):
        if messagebox.askyesno("Delete Task",
                               f"Delete task '{self.task_data.get('name')}'? This cannot be undone."):
            self.app_ref.delete_task(self.index)

    # ------------------------------------------------------------------
    # Run task
    # ------------------------------------------------------------------
    def _run_task(self):
        if self.is_running:
            return
        # Validate at least one step exists
        total_steps = sum(len(s.get("steps", [])) for s in self.task_data.get("sections", []))
        if total_steps == 0:
            messagebox.showinfo("No Steps", "This task has no steps to run.")
            return
        self._save_loop_settings()
        self.is_running = True
        self.run_btn.config(text="\u23f3 Running...", state="disabled", bg=COLORS["yellow"])
        self.status_var.set("Running...")
        threading.Thread(target=self._execute_task, daemon=True).start()

    def _execute_step(self, step):
        action = step.get("action", "Click")
        x, y = step.get("x", 0), step.get("y", 0)
        text = step.get("text", "")
        delay = step.get("delay", 0.5)

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

    def _execute_task(self):
        loop_enabled = self.task_data.get("loop_enabled", False)
        task_loop_count = max(1, self.task_data.get("loop_count", 1))
        sections = self.task_data.get("sections", [])

        try:
            if not loop_enabled:
                # No loop: run all sections once, straight through
                for sec in sections:
                    for step_idx, step in enumerate(sec.get("steps", [])):
                        self.status_var.set(
                            f"[{sec['name']}] Step {step_idx + 1}: {step.get('action')}"
                        )
                        self._execute_step(step)
            else:
                # Loop mode: repeat for task_loop_count iterations
                for iteration in range(1, task_loop_count + 1):
                    self.status_var.set(f"Loop iteration {iteration}/{task_loop_count}...")
                    for sec in sections:
                        sec_loop = sec.get("loop_count", 0)
                        steps = sec.get("steps", [])
                        if not steps:
                            continue

                        if sec_loop == 0:
                            # Section loop count is 0 -> run once (no looping)
                            for step_idx, step in enumerate(steps):
                                self.status_var.set(
                                    f"[Iter {iteration}/{task_loop_count}] "
                                    f"[{sec['name']}] Step {step_idx + 1}: {step.get('action')}"
                                )
                                self._execute_step(step)
                        else:
                            # Section loops sec_loop times
                            for sec_iter in range(1, sec_loop + 1):
                                for step_idx, step in enumerate(steps):
                                    self.status_var.set(
                                        f"[Iter {iteration}/{task_loop_count}] "
                                        f"[{sec['name']} Loop {sec_iter}/{sec_loop}] "
                                        f"Step {step_idx + 1}: {step.get('action')}"
                                    )
                                    self._execute_step(step)

            self.status_var.set("\u2705 Completed successfully")
        except pyautogui.FailSafeException:
            self.status_var.set("\u274c Stopped: Failsafe triggered (mouse moved to corner)")
        except Exception as e:
            self.status_var.set(f"\u274c Error: {str(e)}")
        finally:
            self.is_running = False
            self.run_btn.config(text="\u25b6  Run Task", state="normal", bg=COLORS["green"])


# ---------------------------------------------------------------------------
# AutoFlowApp
# ---------------------------------------------------------------------------
class AutoFlowApp:
    """Main AutoFlow application."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AutoFlow \u2014 PyAutoGUI Task Automation Builder")
        self.root.geometry("960x720")
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

        tk.Label(topbar, text="\u26a1 AutoFlow", bg=COLORS["sidebar"],
                 fg=COLORS["accent"], font=("Segoe UI", 16, "bold")).pack(
            side="left", padx=16, pady=10)
        tk.Label(topbar, text="PyAutoGUI Task Automation Builder",
                 bg=COLORS["sidebar"], fg=COLORS["subtext"],
                 font=("Segoe UI", 9)).pack(side="left", padx=4, pady=10)
        tk.Button(topbar, text="\uff0b New Task", bg=COLORS["accent"], fg=COLORS["bg"],
                  font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
                  padx=14, pady=6, command=self._create_task).pack(
            side="right", padx=12, pady=10)

        container = tk.Frame(self.root, bg=COLORS["bg"])
        container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(container, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.scroll_frame = tk.Frame(self.canvas, bg=COLORS["bg"])
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scroll_frame,
                                                       anchor="nw")
        self.scroll_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        footer = tk.Frame(self.root, bg=COLORS["sidebar"], height=28)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Label(footer,
                 text="Tip: Enable Loop on a task to use Sections. Section loop_count=0 means run once without looping.",
                 bg=COLORS["sidebar"], fg=COLORS["subtext"],
                 font=("Segoe UI", 8)).pack(side="left", padx=12)

    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _create_task(self):
        name = simpledialog.askstring("New Task", "Enter a name for the new task:",
                                      parent=self.root)
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
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        self.task_cards = []

        if not self.tasks:
            tk.Label(self.scroll_frame,
                     text="No tasks yet.\nClick '\uff0b New Task' to get started!",
                     bg=COLORS["bg"], fg=COLORS["subtext"],
                     font=("Segoe UI", 13), justify="center").pack(pady=80)
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
