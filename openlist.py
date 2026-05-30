import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from tkinter import font as tkfont
import os
import sys
import time
import json
import socket
import shutil
import zipfile
import ctypes
import psutil
import requests
import webbrowser
import platform
import threading
import subprocess
from io import BytesIO
from PIL import Image, ImageTk, ImageDraw, ImageOps

# =========================
# 路径与基础配置
# =========================
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_DIR)

CONFIG_FILE = os.path.join(BASE_DIR, ".openlist_path")
REFRESH_CONFIG_FILE = os.path.join(BASE_DIR, ".openlist_refresh_task.json")

APP_TITLE = "OpenList Companion v1.5.7"
APP_ICON_CANDIDATES = ("openlist.png", "openlist.ico")

DEFAULT_PORT = 5244
DEFAULT_REFRESH_INTERVAL = 60
DEFAULT_REFRESH_TIMEOUT = 5
DEFAULT_RESTART_WAIT = 15
DEFAULT_IDLE_GUARD = 300

MY_QQ_NUMBER = "3478728818"
AUTHOR_DISPLAY_NAME = "余宣灵."
OFFICIAL_DOC_URL = "https://doc.openlist.team"

SYSTEM = platform.system()
MAIN_FONT = ("Microsoft YaHei UI", 10) if SYSTEM == "Windows" else ("Noto Sans", 10)
SMALL_FONT = (MAIN_FONT[0], 9)
BOLD_FONT = (MAIN_FONT[0], 10, "bold")
TITLE_FONT = (MAIN_FONT[0], 15, "bold")
BIG_FONT = (MAIN_FONT[0], 20, "bold")
MONO_FONT = ("Consolas", 10) if SYSTEM == "Windows" else ("Monospace", 10)

COLORS = {
    "bg": "#F7F8FA",
    "white": "#FFFFFF",
    "text": "#212529",
    "muted": "#868E96",
    "border": "#E9ECEF",
    "soft": "#F1F3F5",
    "soft2": "#F8F9FA",
    "blue": "#4C6EF5",
    "blue_hover": "#4263EB",
    "blue_soft": "#EDF2FF",
    "blue_border": "#DBE4FF",
    "blue_text": "#364FC7",
    "purple": "#7950F2",
    "purple_hover": "#7048E8",
    "orange": "#FD7E14",
    "orange_soft": "#FFF4E6",
    "orange_border": "#FFE8CC",
    "red": "#FA5252",
    "green": "#40C057",
    "terminal": "#1F2328",
}


def get_creation_flags():
    return 0x08000000 if SYSTEM == "Windows" else 0


def set_windows_app_id():
    if SYSTEM != "Windows":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("OpenList.Companion.v1.5.7")
    except Exception:
        pass


def find_app_icon_path():
    search_dirs = [BASE_DIR]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and meipass not in search_dirs:
        search_dirs.append(meipass)

    for folder in search_dirs:
        for filename in APP_ICON_CANDIDATES:
            path = os.path.join(folder, filename)
            if os.path.exists(path):
                return path
    return None


def hide_file_attributes(file_path):
    """【增量更新】如果是 Windows 系统，将指定的临时/配置文件设置为隐藏属性"""
    if SYSTEM == "Windows" and os.path.exists(file_path):
        try:
            # 0x02 代表 FILE_ATTRIBUTE_HIDDEN
            ctypes.windll.kernel32.SetFileAttributesW(str(file_path), 0x02)
        except Exception:
            pass


def prepare_file_for_write(file_path):
    """写入隐藏配置文件前恢复普通属性，避免 Windows 对隐藏文件 CREATE_ALWAYS 时报 PermissionError。"""
    if not os.path.exists(file_path):
        return
    try:
        os.chmod(file_path, 0o666)
    except Exception:
        pass
    if SYSTEM == "Windows":
        try:
            # 0x80 代表 FILE_ATTRIBUTE_NORMAL
            ctypes.windll.kernel32.SetFileAttributesW(str(file_path), 0x80)
        except Exception:
            pass


def parent_bg(widget, fallback=COLORS["white"]):
    try:
        return widget.cget("bg")
    except Exception:
        return fallback


def rounded_rgba(width, height, radius, fill, outline=None, border=1):
    """Pillow 绘制抗锯齿圆角，避免 Tk 原生按钮右侧缺角、半截圆角。"""
    width = max(2, int(width))
    height = max(2, int(height))
    scale = 3
    big = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(big)
    r = max(1, min(int(radius), width // 2, height // 2)) * scale
    rect = (0, 0, width * scale - 1, height * scale - 1)
    if outline:
        draw.rounded_rectangle(rect, radius=r, fill=fill, outline=outline, width=max(1, border * scale))
    else:
        draw.rounded_rectangle(rect, radius=r, fill=fill)
    return big.resize((width, height), Image.LANCZOS)


class RoundedButton(tk.Canvas):
    """自适应圆角按钮，按文字真实宽度保留安全边距。"""

    def __init__(self, parent, text, command=None, fill=COLORS["soft"], fg=COLORS["text"],
                 hover_fill=None, height=42, radius=16, font=None, min_width=120,
                 pad_x=22, disabled=False):
        self.text = text
        self.command = command
        self.fill = fill
        self.normal_fill = fill
        self.hover_fill = hover_fill or fill
        self.fg = fg
        self.height_value = int(height)
        self.radius = int(radius)
        self.font = font or BOLD_FONT
        self.pad_x = int(pad_x)
        self.disabled = disabled
        measured_width = self._measure_text_width(parent, text, self.font) + self.pad_x * 2
        initial_width = max(int(min_width), measured_width)
        super().__init__(
            parent,
            width=initial_width,
            height=self.height_value,
            bg=parent_bg(parent),
            highlightthickness=0,
            bd=0,
            cursor="arrow" if disabled else "hand2",
        )
        self._photo = None
        self.bind("<Configure>", self._redraw)
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.after_idle(self._ensure_text_safe_width)
        self._redraw()

    def _measure_text_width(self, parent, text, font_value):
        try:
            return tkfont.Font(root=parent.winfo_toplevel(), font=font_value).measure(str(text))
        except Exception:
            return max(60, len(str(text)) * 14)

    def _ensure_text_safe_width(self):
        needed = self._measure_text_width(self.master, self.text, self.font) + self.pad_x * 2
        current = max(int(self.cget("width")), self.winfo_width())
        if needed > current:
            self.configure(width=needed)

    def _redraw(self, _event=None):
        self._ensure_text_safe_width()
        width = max(2, self.winfo_width() or int(self.cget("width")))
        height = max(2, self.height_value)
        if int(self.cget("height")) != height:
            self.configure(height=height)
        self.delete("all")
        fill = self.fill
        text_fill = self.fg
        radius = min(self.radius, height // 2)
        self._photo = ImageTk.PhotoImage(rounded_rgba(width, height, radius, fill))
        self.create_image(0, 0, image=self._photo, anchor="nw")
        self.create_text(width // 2, height // 2, text=self.text, fill=text_fill, font=self.font)

    def _click(self, _event):
        if self.disabled:
            return
        if callable(self.command):
            self.command()

    def _enter(self, _event):
        if self.disabled:
            return
        self.fill = self.hover_fill
        self._redraw()

    def _leave(self, _event):
        if self.disabled:
            return
        self.fill = self.normal_fill
        self._redraw()

    def set_state(self, text=None, fill=None, fg=None, disabled=None):
        if text is not None:
            self.text = text
        if fill is not None:
            self.fill = fill
            self.normal_fill = fill
        if fg is not None:
            self.fg = fg
        if disabled is not None:
            self.disabled = bool(disabled)
            self.configure(cursor="arrow" if self.disabled else "hand2")
        self._ensure_text_safe_width()
        self._redraw()


class RoundedEntry(tk.Canvas):
    """圆角矩形输入框，替代 Tk 原生 Entry 的直角边框。"""

    def __init__(self, parent, textvariable=None, show="", fill="#F3F5F7",
                 outline="#E9ECEF", focus_outline=None, fg=None, height=46,
                 radius=14, font=None, pad_x=14, width=260):
        self.fill = fill
        self.outline = outline
        self.focus_outline = focus_outline or COLORS["blue"]
        self.fg = fg or COLORS["text"]
        self.height_value = int(height)
        self.radius = int(radius)
        self.font = font or BOLD_FONT
        self.pad_x = int(pad_x)
        self._focused = False
        self._photo = None

        super().__init__(
            parent,
            width=int(width),
            height=self.height_value,
            bg=parent_bg(parent),
            highlightthickness=0,
            bd=0,
            cursor="xterm",
        )

        self.entry = tk.Entry(
            self,
            textvariable=textvariable,
            relief="flat",
            bd=0,
            highlightthickness=0,
            bg=self.fill,
            fg=self.fg,
            insertbackground=self.fg,
            font=self.font,
            show=show or "",
        )
        self._window = self.create_window(
            self.pad_x,
            self.height_value // 2,
            anchor="w",
            window=self.entry,
        )

        super().bind("<Configure>", self._redraw)
        super().bind("<Button-1>", self._focus_entry)
        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self._redraw()

    def _redraw(self, _event=None):
        width = max(2, self.winfo_width() or int(self.cget("width")))
        height = max(2, self.height_value)
        if int(self.cget("height")) != height:
            self.configure(height=height)
        outline = self.focus_outline if self._focused else self.outline
        self.delete("bg")
        self._photo = ImageTk.PhotoImage(rounded_rgba(width, height, self.radius, self.fill, outline, border=1))
        self.create_image(0, 0, image=self._photo, anchor="nw", tags="bg")
        self.tag_lower("bg")
        self.coords(self._window, self.pad_x, height // 2)
        self.itemconfigure(self._window, width=max(10, width - self.pad_x * 2), height=max(20, height - 14))

    def _focus_entry(self, _event=None):
        self.entry.focus_set()

    def _on_focus_in(self, _event=None):
        self._focused = True
        self._redraw()

    def _on_focus_out(self, _event=None):
        self._focused = False
        self._redraw()

    def focus_set(self):
        self.entry.focus_set()

    def get(self):
        return self.entry.get()

    def insert(self, index, string):
        return self.entry.insert(index, string)

    def delete(self, first, last=None):
        if first == "bg":
            return super().delete(first)
        return self.entry.delete(first, last)

    def bind(self, sequence=None, func=None, add=None):
        key_sequences = {"<Return>", "<Escape>", "<Key>", "<KeyRelease>", "<KeyPress>"}
        if sequence in key_sequences or (isinstance(sequence, str) and sequence.startswith("<Key")):
            return self.entry.bind(sequence, func, add)
        return super().bind(sequence, func, add)


class RoundedPanel(tk.Canvas):
    """自适应圆角卡片，内容高度不足时自动增高，避免按钮与文字被裁切。"""

    def __init__(self, parent, fill=COLORS["white"], outline=COLORS["border"],
                 radius=20, inner_pad=16, height=100, min_width=120, auto_height=True):
        super().__init__(
            parent,
            width=min_width,
            height=height,
            bg=parent_bg(parent, COLORS["bg"]),
            highlightthickness=0,
            bd=0,
        )
        self.fill = fill
        self.outline = outline
        self.radius = int(radius)
        self.inner_pad = int(inner_pad)
        self.auto_height = bool(auto_height)
        self._photo = None
        self._fit_pending = False
        self.body = tk.Frame(self, bg=fill, highlightthickness=0, bd=0)
        self._window = self.create_window(self.inner_pad, self.inner_pad, anchor="nw", window=self.body)
        self.bind("<Configure>", self._redraw)
        self.after_idle(self._fit_to_content)
        self._redraw()

    def _redraw(self, _event=None):
        width = max(2, self.winfo_width() or int(self.cget("width")))
        height = max(2, self.winfo_height() or int(self.cget("height")))
        self.delete("bg")
        self._photo = ImageTk.PhotoImage(rounded_rgba(width, height, self.radius, self.fill, self.outline))
        self.create_image(0, 0, image=self._photo, anchor="nw", tags="bg")
        self.tag_lower("bg")
        self.body.update_idletasks()
        body_width = max(10, width - self.inner_pad * 2)
        body_height = max(10, height - self.inner_pad * 2, self.body.winfo_reqheight())
        self.coords(self._window, self.inner_pad, self.inner_pad)
        self.itemconfigure(self._window, width=body_width, height=body_height)
        if self.auto_height and not self._fit_pending:
            self._fit_pending = True
            self.after_idle(self._fit_to_content)

    def _fit_to_content(self):
        self._fit_pending = False
        if not self.auto_height:
            return
        try:
            self.body.update_idletasks()
            needed = self.body.winfo_reqheight() + self.inner_pad * 2
            current = max(int(self.cget("height")), self.winfo_height())
            if needed > current + 1:
                self.configure(height=needed)
                self._redraw()
        except Exception:
            pass


class ModernScrollbar(tk.Canvas):
    """日志专用圆角滚动条，替代 Tk 默认细窄滚动条。"""

    def __init__(self, parent, command=None, width=20,
                 track_fill="#EEF0F3", thumb_fill="#CED4DA", thumb_hover="#ADB5BD",
                 radius=9, min_thumb=52):
        super().__init__(
            parent,
            width=width,
            bg=parent_bg(parent, COLORS["soft2"]),
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.command = command
        self.track_fill = track_fill
        self.thumb_fill = thumb_fill
        self.thumb_hover = thumb_hover
        self.radius = int(radius)
        self.min_thumb = int(min_thumb)
        self.first = 0.0
        self.last = 1.0
        self.drag_offset = 0
        self.hover = False
        self.thumb_rect = (0, 0, 0, 0)
        self.bind("<Configure>", self._redraw)
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<MouseWheel>", self._on_mousewheel)
        self.bind("<Button-4>", lambda event: self._scroll_units(-3))
        self.bind("<Button-5>", lambda event: self._scroll_units(3))

    def set(self, first, last):
        try:
            self.first = max(0.0, min(1.0, float(first)))
            self.last = max(self.first, min(1.0, float(last)))
        except Exception:
            self.first, self.last = 0.0, 1.0
        self._redraw()

    def _rounded_rect(self, x1, y1, x2, y2, radius, fill, tags):
        x1, y1, x2, y2 = float(x1), float(y1), float(x2), float(y2)
        if x2 <= x1 or y2 <= y1:
            return
        radius = max(1, min(float(radius), (x2 - x1) / 2, (y2 - y1) / 2))
        self.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline="", tags=tags)
        self.create_rectangle(x1, y1 + radius, x2, y2 - radius, fill=fill, outline="", tags=tags)
        self.create_oval(x1, y1, x1 + radius * 2, y1 + radius * 2, fill=fill, outline="", tags=tags)
        self.create_oval(x2 - radius * 2, y1, x2, y1 + radius * 2, fill=fill, outline="", tags=tags)
        self.create_oval(x1, y2 - radius * 2, x1 + radius * 2, y2, fill=fill, outline="", tags=tags)
        self.create_oval(x2 - radius * 2, y2 - radius * 2, x2, y2, fill=fill, outline="", tags=tags)

    def _redraw(self, _event=None):
        width = max(18, self.winfo_width() or int(self.cget("width")))
        height = max(40, self.winfo_height())
        self.delete("all")

        track_pad_x = 3
        track_pad_y = 4
        x1 = track_pad_x
        x2 = width - track_pad_x
        y1 = track_pad_y
        y2 = height - track_pad_y
        self._rounded_rect(x1, y1, x2, y2, self.radius, self.track_fill, "track")

        track_h = max(1, y2 - y1)
        visible_ratio = max(0.04, min(1.0, self.last - self.first))
        thumb_h = min(track_h, max(self.min_thumb, track_h * visible_ratio))
        available = max(0, track_h - thumb_h)
        top = y1 + available * self.first
        bottom = top + thumb_h
        thumb_x1 = x1 + 3
        thumb_x2 = x2 - 3
        thumb_color = self.thumb_hover if self.hover else self.thumb_fill
        self.thumb_rect = (thumb_x1, top, thumb_x2, bottom)
        self._rounded_rect(thumb_x1, top, thumb_x2, bottom, max(6, self.radius - 2), thumb_color, "thumb")

    def _on_enter(self, _event):
        self.hover = True
        self._redraw()

    def _on_leave(self, _event):
        self.hover = False
        self._redraw()

    def _on_press(self, event):
        x1, y1, x2, y2 = self.thumb_rect
        if y1 <= event.y <= y2:
            self.drag_offset = event.y - y1
        else:
            self.drag_offset = max(0, (y2 - y1) / 2)
            self._move_thumb_to(event.y - self.drag_offset)

    def _on_drag(self, event):
        self._move_thumb_to(event.y - self.drag_offset)

    def _move_thumb_to(self, thumb_top):
        if not callable(self.command):
            return
        height = max(40, self.winfo_height())
        track_pad_y = 4
        track_h = max(1, height - track_pad_y * 2)
        visible_ratio = max(0.04, min(1.0, self.last - self.first))
        thumb_h = min(track_h, max(self.min_thumb, track_h * visible_ratio))
        available = max(1, track_h - thumb_h)
        fraction = (thumb_top - track_pad_y) / available
        fraction = max(0.0, min(1.0, fraction))
        self.command("moveto", f"{fraction:.6f}")

    def _on_mousewheel(self, event):
        delta = getattr(event, "delta", 0)
        if delta == 0:
            return
        self._scroll_units(-3 if delta > 0 else 3)

    def _scroll_units(self, amount):
        if callable(self.command):
            self.command("scroll", int(amount), "units")


class ModernScrollFrame(tk.Frame):
    """单卡片弹窗内部滚动容器，配合 ModernScrollbar 使用。"""

    def __init__(self, parent, bg=COLORS["white"], scrollbar_width=22):
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0)
        self.bg = bg
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self,
            bg=bg,
            highlightthickness=0,
            bd=0,
            relief="flat",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.body = tk.Frame(self.canvas, bg=bg, highlightthickness=0, bd=0)
        self._window = self.canvas.create_window(0, 0, anchor="nw", window=self.body)

        self.scrollbar = ModernScrollbar(
            self,
            command=self.canvas.yview,
            width=scrollbar_width,
            track_fill="#F1F3F5",
            thumb_fill="#CED4DA",
            thumb_hover="#ADB5BD",
            radius=10,
            min_thumb=68,
        )
        self.scrollbar.grid(row=0, column=1, sticky="ns", padx=(12, 0), pady=2)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.body.bind("<Configure>", self._on_body_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel, add="+")
        self.canvas.bind("<Button-4>", lambda event: self.canvas.yview_scroll(-3, "units"), add="+")
        self.canvas.bind("<Button-5>", lambda event: self.canvas.yview_scroll(3, "units"), add="+")

    def _on_body_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._window, width=max(1, event.width))

    def _on_mousewheel(self, event):
        delta = getattr(event, "delta", 0)
        if delta > 0:
            self.canvas.yview_scroll(-3, "units")
        elif delta < 0:
            self.canvas.yview_scroll(3, "units")
        return "break"

    def bind_mousewheel_tree(self, widget=None):
        widget = widget or self.body
        try:
            widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
            widget.bind("<Button-4>", lambda event: self.canvas.yview_scroll(-3, "units"), add="+")
            widget.bind("<Button-5>", lambda event: self.canvas.yview_scroll(3, "units"), add="+")
        except Exception:
            pass
        for child in widget.winfo_children():
            self.bind_mousewheel_tree(child)


class AvatarCanvas(tk.Canvas):
    """带安全边距的头像组件，避免圆形遮罩贴边导致头像显示不完整。"""

    def __init__(self, parent, size=86, avatar_size=76):
        super().__init__(parent, width=size, height=size, bg=parent_bg(parent), highlightthickness=0, bd=0)
        self.size = int(size)
        self.avatar_size = int(avatar_size)
        self._photo = None
        self.draw_placeholder()

    def draw_placeholder(self):
        self.delete("all")
        cx = cy = self.size // 2
        r = self.avatar_size // 2
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=COLORS["soft"], outline=COLORS["border"], width=1)
        self.create_text(cx, cy, text="OL", fill=COLORS["muted"], font=TITLE_FONT)

    def set_pil_image(self, image):
        canvas = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        avatar = ImageOps.fit(image.convert("RGBA"), (self.avatar_size, self.avatar_size), method=Image.LANCZOS, centering=(0.5, 0.5))
        mask = Image.new("L", (self.avatar_size, self.avatar_size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((1, 1, self.avatar_size - 2, self.avatar_size - 2), fill=255)
        avatar.putalpha(mask)
        offset = ((self.size - self.avatar_size) // 2, (self.size - self.avatar_size) // 2)
        canvas.alpha_composite(avatar, offset)
        ring = ImageDraw.Draw(canvas)
        x0 = offset[0]
        y0 = offset[1]
        ring.ellipse((x0, y0, x0 + self.avatar_size - 1, y0 + self.avatar_size - 1), outline="#FFFFFF", width=3)
        ring.ellipse((x0 + 2, y0 + 2, x0 + self.avatar_size - 3, y0 + self.avatar_size - 3), outline=COLORS["border"], width=1)
        self._photo = ImageTk.PhotoImage(canvas)
        self.delete("all")
        self.create_image(self.size // 2, self.size // 2, image=self._photo)


class OpenListCompanion(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.apply_window_icon()
        self.geometry("1240x900")
        self.minsize(980, 720)
        self.configure(bg=COLORS["bg"])
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.app_path = self.auto_find_path()
        self.proc_handle = None
        self.photo = None

        self.refresh_after_id = None
        self.refresh_running = False
        self.refresh_task_generation = 0
        self.refresh_running_generation = None
        self.refresh_round = 0
        self.last_refresh_ok = None
        self.last_refresh_time = "--:--"
        self.last_activity_time = 0
        self.refresh_settings_window = None

        self.refresh_url = f"http://127.0.0.1:{DEFAULT_PORT}"
        self.refresh_interval = DEFAULT_REFRESH_INTERVAL
        self.refresh_timeout = DEFAULT_REFRESH_TIMEOUT
        self.restart_wait = DEFAULT_RESTART_WAIT
        self.idle_guard_seconds = DEFAULT_IDLE_GUARD
        self.normal_refresh_enabled = True
        self.restart_refresh_enabled = True
        self.playback_guard_enabled = True
        self.load_refresh_settings()

        self.init_ui()
        self.load_author_info()
        self.start_monitor()
        if self.normal_refresh_enabled:
            self.start_auto_refresh_task(silent=True, first_delay=3000)

    def apply_window_icon(self):
        icon_path = find_app_icon_path()
        self._window_icon_photo = None
        if not icon_path:
            return

        try:
            if icon_path.lower().endswith(".ico") and SYSTEM == "Windows":
                try:
                    self.iconbitmap(icon_path)
                except Exception:
                    pass

            image = Image.open(icon_path).convert("RGBA")
            image.thumbnail((256, 256), Image.LANCZOS)
            self._window_icon_photo = ImageTk.PhotoImage(image)
            self.iconphoto(True, self._window_icon_photo)
        except Exception:
            self._window_icon_photo = None

    # =========================
    # 基础服务控制
    # =========================
    def auto_find_path(self):
        ext = ".exe" if SYSTEM == "Windows" else ""
        local_alist = os.path.join(BASE_DIR, f"alist{ext}")
        if os.path.exists(local_alist):
            return os.path.normpath(local_alist)
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved_path = f.read().strip()
                    if saved_path and os.path.exists(saved_path):
                        return os.path.normpath(saved_path)
            except Exception:
                pass
        return ""

    def on_closing(self):
        self.stop_auto_refresh_task(silent=True)
        self.kill_process_tree()
        self.destroy()
        sys.exit(0)

    def kill_process_tree(self):
        target_name = os.path.basename(self.app_path).lower() if self.app_path else "alist.exe"
        for p in psutil.process_iter(["name", "exe"]):
            try:
                pname = (p.info.get("name") or "").lower()
                pexe = (p.info.get("exe") or "").lower()
                if pname == target_name or (self.app_path and pexe == self.app_path.lower()):
                    p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        time.sleep(0.25)

    def release_port(self):
        found = False
        self.log(f"🔍 正在扫描端口 {DEFAULT_PORT}...", "orange")
        for conn in psutil.net_connections(kind="inet"):
            try:
                if not conn.laddr or conn.laddr.port != DEFAULT_PORT:
                    continue
                pid = conn.pid
                if not pid:
                    continue
                p = psutil.Process(pid)
                name = p.name()
                p.kill()
                self.log(f"✅ 已结束占用进程: {name} (PID: {pid})", "green")
                found = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                continue
        self.log("✨ 端口已释放" if found else f"ℹ️ 端口 {DEFAULT_PORT} 当前未被占用", "green")
        self.update_all_status()

    def is_service_ready(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.25)
                return s.connect_ex(("127.0.0.1", DEFAULT_PORT)) == 0
        except Exception:
            return False

    def get_service_state(self):
        if self.is_service_ready():
            return "running"
        proc = getattr(self, "proc_handle", None)
        if proc is not None:
            try:
                if proc.poll() is None:
                    return "starting"
            except Exception:
                pass
        return "stopped"

    def run_cmd(self, action):
        if not self.app_path:
            messagebox.showwarning("提示", "请先选择 alist.exe 路径")
            self.change_path()
            return

        if action == "stop":
            self.kill_process_tree()
            self.proc_handle = None
            self.log("🛑 服务已停止", "red")
            self.update_all_status(state="stopped")
            self.update_refresh_status_label("等待服务", COLORS["orange"])
            return

        if action == "start":
            self.kill_process_tree()
            self.log("🚀 启动服务中...", "green")
            self.update_all_status(state="starting")
            threading.Thread(target=self._worker, daemon=True).start()
            if self.normal_refresh_enabled:
                self.start_auto_refresh_task(silent=True, first_delay=3000)
            current_generation = self.refresh_task_generation
            self.after(500, lambda g=current_generation: self.wait_service_then_refresh("服务启动提交", generation=g))
            return

        if action == "restart":
            self.kill_process_tree()
            self.log("🔄 正在重启服务...", "orange")
            self.update_all_status(state="starting")
            self.after(800, lambda: self.run_cmd("start"))
            return

    def _worker(self):
        proc = None
        try:
            cmd = [self.app_path, "server", "--force-bin-dir"]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=os.path.dirname(self.app_path),
                creationflags=get_creation_flags(),
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            self.proc_handle = proc
            self.after(0, lambda: self.update_all_status(state="starting"))
            for line in proc.stdout:
                msg = line.strip()
                if not msg:
                    continue
                if "password" in msg.lower():
                    self.log("🔐 管理凭证已处理", "orange")
                else:
                    self.log(msg, "green" if "start" in msg.lower() else None)
            proc.wait()
            if self.proc_handle is proc:
                self.proc_handle = None
            self.after(0, self.update_all_status)
        except Exception as e:
            if proc is not None and self.proc_handle is proc:
                self.proc_handle = None
            self.log(f"运行出错: {e}", "red")
            self.after(0, self.update_all_status)

    # =========================
    # 数据维护
    # =========================
    def export_data(self):
        if not self.app_path:
            messagebox.showwarning("提示", "请先选择 alist.exe 路径")
            return
        data_dir = os.path.join(os.path.dirname(self.app_path), "data")
        if not os.path.exists(data_dir):
            messagebox.showerror("错误", "找不到 data 文件夹")
            return
        save_file = filedialog.asksaveasfilename(defaultextension=".zip", initialfile="alist_backup.zip")
        if not save_file:
            return
        self.kill_process_tree()
        try:
            target = save_file[:-4] if save_file.lower().endswith(".zip") else save_file
            shutil.make_archive(target, "zip", data_dir)
            self.log("✅ 备份成功", "green")
            self.run_cmd("start")
        except Exception as e:
            self.log(f"备份失败: {e}", "red")

    def import_data(self):
        if not self.app_path:
            messagebox.showwarning("提示", "请先选择 alist.exe 路径")
            return
        zip_path = filedialog.askopenfilename(filetypes=[("Zip", "*.zip")])
        if not zip_path:
            return
        if not messagebox.askyesno("确认", "还原将删除现有数据，确定？"):
            return
        self.kill_process_tree()
        data_dir = os.path.join(os.path.dirname(self.app_path), "data")
        try:
            if os.path.exists(data_dir):
                shutil.rmtree(data_dir)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(data_dir)
            self.log("✅ 还原成功", "green")
            self.run_cmd("start")
        except Exception as e:
            self.log(f"还原失败: {e}", "red")

    def change_path(self):
        filetypes = [("EXE", "*.exe"), ("All", "*.*")] if SYSTEM == "Windows" else [("All", "*.*")]
        p = filedialog.askopenfilename(filetypes=filetypes)
        if not p:
            return
        self.app_path = os.path.normpath(p)
        try:
            prepare_file_for_write(CONFIG_FILE)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(self.app_path)
            hide_file_attributes(CONFIG_FILE)  # 【增量更新】隐藏生成的配置文件
            self.path_value.config(text=self.compact_path(self.app_path))
            self.log(f"⚙️ 路径已保存并记忆：{self.app_path}", "orange")
        except Exception as e:
            self.log(f"❌ 路径保存失败：{e}", "red")

    def compact_path(self, value, limit=72):
        if not value:
            return "未设置 alist 路径"
        text = str(value)
        if len(text) <= limit:
            return text
        return text[:28] + "..." + text[-36:]

    # =========================
    # 自动刷新配置
    # =========================
    def load_refresh_settings(self):
        try:
            if not os.path.exists(REFRESH_CONFIG_FILE):
                return
            with open(REFRESH_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.refresh_url = str(data.get("url", self.refresh_url)).strip() or self.refresh_url
            self.refresh_interval = max(5, int(data.get("interval", DEFAULT_REFRESH_INTERVAL)))
            self.refresh_timeout = max(1, int(data.get("timeout", DEFAULT_REFRESH_TIMEOUT)))
            self.restart_wait = max(0, int(data.get("restart_wait", DEFAULT_RESTART_WAIT)))
            self.idle_guard_seconds = max(0, int(data.get("idle_guard_seconds", DEFAULT_IDLE_GUARD)))
            self.normal_refresh_enabled = bool(data.get("normal_refresh_enabled", True))
            self.restart_refresh_enabled = bool(data.get("restart_refresh_enabled", True))
            self.playback_guard_enabled = bool(data.get("playback_guard_enabled", True))
        except Exception:
            self.refresh_url = f"http://127.0.0.1:{DEFAULT_PORT}"
            self.refresh_interval = DEFAULT_REFRESH_INTERVAL
            self.refresh_timeout = DEFAULT_REFRESH_TIMEOUT
            self.restart_wait = DEFAULT_RESTART_WAIT
            self.idle_guard_seconds = DEFAULT_IDLE_GUARD
            self.normal_refresh_enabled = True
            self.restart_refresh_enabled = True
            self.playback_guard_enabled = True

    def save_refresh_settings_to_file(self):
        data = {
            "url": self.refresh_url,
            "interval": self.refresh_interval,
            "timeout": self.refresh_timeout,
            "restart_wait": self.restart_wait,
            "idle_guard_seconds": self.idle_guard_seconds,
            "normal_refresh_enabled": self.normal_refresh_enabled,
            "restart_refresh_enabled": self.restart_refresh_enabled,
            "playback_guard_enabled": self.playback_guard_enabled,
        }
        prepare_file_for_write(REFRESH_CONFIG_FILE)
        with open(REFRESH_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        hide_file_attributes(REFRESH_CONFIG_FILE)  # 【增量更新】隐藏任务配置文件

    def save_refresh_settings_safely(self):
        try:
            self.save_refresh_settings_to_file()
        except Exception as e:
            self.log(f"❌ 自动任务设置保存失败：{e}", "red")

    def start_auto_refresh_task(self, silent=False, first_delay=None):
        self.stop_auto_refresh_task(silent=True, invalidate=False)
        self.refresh_task_generation += 1
        current_generation = self.refresh_task_generation
        self.update_refresh_status_label()
        if not silent:
            self.log(f"🔁 自动任务已开启：每 {self.refresh_interval} 秒执行", "green")
        delay = first_delay if first_delay is not None else self.refresh_interval * 1000
        self.refresh_after_id = self.after(delay, lambda g=current_generation: self._auto_refresh_tick(g))

    def stop_auto_refresh_task(self, silent=False, invalidate=True):
        if invalidate:
            self.refresh_task_generation += 1
        if self.refresh_after_id is not None:
            try:
                self.after_cancel(self.refresh_after_id)
            except Exception:
                pass
            self.refresh_after_id = None
        if not silent:
            self.log("⏹️ 自动任务已暂停", "orange")

    def restart_auto_refresh_task(self, reason="设置更新", immediate=False):
        if self.normal_refresh_enabled:
            first_delay = 1000 if immediate else self.refresh_interval * 1000
            self.start_auto_refresh_task(silent=True, first_delay=first_delay)
            self.log(f"♻️ 自动任务已重载：{reason}", "green")
        else:
            self.stop_auto_refresh_task(silent=True)
            self.update_refresh_status_label("普通刷新已关", COLORS["muted"])

    def _auto_refresh_tick(self, generation=None):
        if generation is None:
            generation = self.refresh_task_generation
        if generation != self.refresh_task_generation:
            return
        self.refresh_after_id = None

        if not self.normal_refresh_enabled:
            self.update_refresh_status_label("普通刷新已关", COLORS["muted"])
            return

        self.refresh_round += 1
        round_no = self.refresh_round

        if not self.is_service_ready():
            self.last_refresh_ok = False
            self.update_refresh_status_label("等待服务", COLORS["orange"])
            self.log(f"⏳ 自动任务第 {round_no} 轮：服务未就绪，跳过本轮", "orange")
        else:
            should_restart = self.restart_refresh_enabled and round_no % 2 == 0
            if should_restart:
                self.run_restart_refresh_cycle(round_no, generation)
            else:
                self.run_auto_refresh_once(source=f"自动任务第 {round_no} 轮 · 普通刷新", force=True, generation=generation)

        if generation == self.refresh_task_generation:
            self.refresh_after_id = self.after(self.refresh_interval * 1000, lambda g=generation: self._auto_refresh_tick(g))

    def run_auto_refresh_once(self, source="手动刷新", force=False, generation=None):
        if generation is None:
            generation = self.refresh_task_generation
        if generation != self.refresh_task_generation:
            return
        if self.refresh_running and self.refresh_running_generation == generation:
            self.log("⏳ 上一次刷新还在执行，本次跳过", "orange")
            return
        if not force and not self.is_service_ready():
            self.last_refresh_ok = False
            self.update_refresh_status_label("等待服务", COLORS["orange"])
            self.log(f"⏳ {source}：服务未就绪，未提交刷新", "orange")
            return
        self.update_refresh_status_label("提交中", COLORS["orange"])
        threading.Thread(target=self._run_refresh_request_worker, args=(source, generation), daemon=True).start()

    def _run_refresh_request_worker(self, source, generation):
        self.refresh_running = True
        self.refresh_running_generation = generation
        safe_url = self.refresh_url
        safe_timeout = self.refresh_timeout
        self.log(f"🔁 {source}：正在访问 {safe_url}", "orange")
        try:
            response = requests.get(safe_url, timeout=safe_timeout)
            if generation != self.refresh_task_generation:
                return
            self.last_refresh_ok = bool(response.ok)
            self.last_refresh_time = time.strftime("%H:%M")
            if response.ok:
                self.log(f"✅ {source}完成：HTTP {response.status_code}", "green")
            else:
                self.log(f"⚠️ {source}返回异常：HTTP {response.status_code}", "orange")
            self.after(0, self.update_refresh_status_label)
        except Exception as e:
            if generation != self.refresh_task_generation:
                return
            self.last_refresh_ok = False
            self.log(f"❌ {source}失败：{e}", "red")
            self.after(0, self.update_refresh_status_label)
        finally:
            if generation == self.refresh_task_generation:
                self.refresh_running = False
                self.refresh_running_generation = None

    def wait_service_then_refresh(self, source="服务启动提交", retries=36, delay_ms=500, generation=None):
        if generation is None:
            generation = self.refresh_task_generation
        if generation != self.refresh_task_generation:
            return
        if self.is_service_ready():
            self.update_all_status(state="running")
            self.run_auto_refresh_once(source=source, force=True, generation=generation)
            return
        if retries <= 0:
            self.last_refresh_ok = False
            self.update_refresh_status_label("等待服务", COLORS["orange"])
            self.log(f"⏳ {source}：服务暂未就绪，等待下一次自动任务", "orange")
            return
        self.update_refresh_status_label("等待服务启动", COLORS["orange"])
        self.after(delay_ms, lambda g=generation: self.wait_service_then_refresh(source, retries - 1, delay_ms, g))

    def get_active_connection_count(self):
        count = 0
        try:
            for conn in psutil.net_connections(kind="inet"):
                try:
                    if not conn.laddr or conn.laddr.port != DEFAULT_PORT:
                        continue
                    if conn.status == psutil.CONN_ESTABLISHED:
                        count += 1
                except Exception:
                    continue
        except Exception:
            return 0
        return count

    def update_activity_guard(self):
        active_count = self.get_active_connection_count()
        if active_count > 0:
            self.last_activity_time = time.time()
        return active_count

    def is_restart_allowed_by_guard(self):
        if not self.playback_guard_enabled:
            return True, 0, 0
        active_count = self.update_activity_guard()
        if active_count > 0:
            return False, active_count, self.idle_guard_seconds
        if self.last_activity_time <= 0:
            return True, 0, 0
        elapsed = time.time() - self.last_activity_time
        remain = max(0, int(self.idle_guard_seconds - elapsed))
        return remain <= 0, 0, remain

    def run_restart_refresh_cycle(self, round_no, generation):
        source = f"自动任务第 {round_no} 轮 · 重启服务刷新"
        allowed, active_count, remain = self.is_restart_allowed_by_guard()
        if not allowed:
            if active_count > 0:
                self.log(f"🛡️ {source}：检测到 {active_count} 个活跃连接，跳过重启", "orange")
            else:
                self.log(f"🛡️ {source}：最近有访问活动，剩余 {remain} 秒后允许重启", "orange")
            self.run_auto_refresh_once(source=f"{source} · 保护模式普通刷新", force=True, generation=generation)
            return
        self.update_refresh_status_label("重启服务中", COLORS["orange"])
        self.log(f"♻️ {source}：正在重启 OpenList 服务", "orange")
        threading.Thread(target=self._restart_service_worker, args=(source, generation), daemon=True).start()

    def _restart_service_worker(self, source, generation):
        if generation != self.refresh_task_generation:
            return
        try:
            self.kill_process_tree()
            if generation != self.refresh_task_generation:
                return
            self.log(f"🚀 {source}：服务重新启动中...", "green")
            threading.Thread(target=self._worker, daemon=True).start()
            self.after(500, lambda g=generation: self._wait_ready_after_restart(source, g, 60))
        except Exception as e:
            self.log(f"❌ {source}失败：{e}", "red")

    def _wait_ready_after_restart(self, source, generation, retries):
        if generation != self.refresh_task_generation:
            return
        if self.is_service_ready():
            wait_ms = max(0, self.restart_wait) * 1000
            self.log(f"✅ {source}：服务已就绪，等待 {self.restart_wait} 秒后刷新", "green")
            self.update_all_status(state="running")
            self.update_refresh_status_label("服务已就绪", COLORS["green"])
            self.after(wait_ms, lambda g=generation: self.run_auto_refresh_once(source=f"{source}完成", force=True, generation=g))
            return
        if retries <= 0:
            self.last_refresh_ok = False
            self.update_refresh_status_label("重启失败", COLORS["red"])
            self.log(f"❌ {source}：服务重启后未能就绪", "red")
            return
        self.update_refresh_status_label("等待端口就绪", COLORS["orange"])
        self.after(500, lambda g=generation: self._wait_ready_after_restart(source, g, retries - 1))

    # =========================
    # 弹窗工具
    # =========================
    def center_child_window(self, win, width, height):
        self.update_idletasks()
        sw = self.winfo_width()
        sh = self.winfo_height()
        sx = self.winfo_rootx()
        sy = self.winfo_rooty()
        x = sx + max(0, (sw - width) // 2)
        y = sy + max(0, (sh - height) // 2)
        win.geometry(f"{width}x{height}+{x}+{y}")

    # =========================
    # UI 构建
    # =========================
    def init_ui(self):
        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True)
        main.grid_columnconfigure(0, minsize=320)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        self.sidebar = tk.Frame(main, bg=COLORS["white"], width=320)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(8, weight=1)

        self.right_area = tk.Frame(main, bg=COLORS["bg"], padx=26, pady=16)
        self.right_area.grid(row=0, column=1, sticky="nsew")
        self.right_area.grid_columnconfigure(0, weight=1)
        self.right_area.grid_rowconfigure(4, weight=1)

        self.build_sidebar()
        self.build_header_card()
        self.build_service_card()
        self.build_data_refresh_card()
        self.build_path_card()
        self.build_log_area()
        self.update_refresh_status_label()
        self.update_toggle_buttons()

    def build_sidebar(self):
        self.canvas_avatar = AvatarCanvas(self.sidebar, size=86, avatar_size=76)
        self.canvas_avatar.grid(row=0, column=0, pady=(28, 6))

        tk.Label(self.sidebar, text=AUTHOR_DISPLAY_NAME, bg=COLORS["white"], fg=COLORS["text"], font=TITLE_FONT).grid(row=1, column=0)
        tk.Label(self.sidebar, text="OpenList Companion", bg=COLORS["white"], fg=COLORS["muted"], font=SMALL_FONT).grid(row=2, column=0, pady=(6, 16))

        self.status_card = RoundedPanel(self.sidebar, fill=COLORS["soft2"], outline=COLORS["border"], radius=20, inner_pad=18, height=108)
        self.status_card.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 12))
        status_body = self.status_card.body
        status_body.grid_columnconfigure(0, weight=1)
        self.status_text = tk.Label(status_body, text="🔴 未运行", bg=COLORS["soft2"], fg=COLORS["red"], font=TITLE_FONT, anchor="w")
        self.status_text.grid(row=0, column=0, sticky="ew", pady=(2, 8))
        self.addr_label = tk.Label(status_body, text=f"http://127.0.0.1:{DEFAULT_PORT}", bg=COLORS["soft2"], fg=COLORS["muted"], font=SMALL_FONT, anchor="w")
        self.addr_label.grid(row=1, column=0, sticky="ew")

        self.account_card = RoundedPanel(self.sidebar, fill=COLORS["white"], outline=COLORS["border"], radius=22, inner_pad=16, height=164)
        self.account_card.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 12))
        account_body = self.account_card.body
        account_body.grid_columnconfigure(0, weight=1)
        account_body.grid_columnconfigure(1, weight=0)

        tk.Label(
            account_body,
            text="管理账户",
            bg=COLORS["white"],
            fg=COLORS["muted"],
            font=SMALL_FONT,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 4))

        tk.Label(
            account_body,
            text="admin",
            bg=COLORS["white"],
            fg=COLORS["text"],
            font=(MAIN_FONT[0], 19, "bold"),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew")

        copy_btn = RoundedButton(
            account_body,
            "复制",
            self.copy_admin_username,
            fill=COLORS["blue_soft"],
            hover_fill=COLORS["blue_border"],
            fg=COLORS["blue_text"],
            height=34,
            radius=13,
            font=BOLD_FONT,
            min_width=64,
            pad_x=14,
        )
        copy_btn.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0), pady=(12, 0))

        tk.Frame(account_body, bg=COLORS["border"], height=1).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 12))

        pwd_btn = RoundedButton(
            account_body,
            "修改管理密码",
            self.set_admin_password,
            fill=COLORS["soft"],
            hover_fill="#E9ECEF",
            fg=COLORS["text"],
            height=38,
            radius=15,
            font=BOLD_FONT,
            min_width=142,
            pad_x=22,
        )
        pwd_btn.grid(row=3, column=0, columnspan=2, sticky="ew")

        nav = tk.Frame(self.sidebar, bg=COLORS["white"])
        nav.grid(row=5, column=0, sticky="ew", padx=16, pady=(4, 0))
        nav.grid_columnconfigure(0, weight=1)

        doc_btn = RoundedButton(
            nav,
            "📚  官方文档",
            lambda: webbrowser.open(OFFICIAL_DOC_URL),
            fill=COLORS["purple"],
            hover_fill=COLORS["purple_hover"],
            fg="white",
            height=42,
            radius=15,
        )
        doc_btn.grid(row=0, column=0, sticky="ew")

    def make_card(self, parent, fill=COLORS["white"], height=120, radius=20, inset=16):
        return RoundedPanel(parent, fill=fill, outline=COLORS["border"], radius=radius, inner_pad=inset, height=height)

    def build_header_card(self):
        card = self.make_card(self.right_area, height=104)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        body = card.body
        body.grid_columnconfigure(0, weight=1)
        title_box = tk.Frame(body, bg=COLORS["white"])
        title_box.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        tk.Label(title_box, text="服务控制中心", bg=COLORS["white"], fg=COLORS["text"], font=BIG_FONT, anchor="w").pack(anchor="w")
        tk.Label(title_box, text="本地地址、自动刷新、重启保护统一管理", bg=COLORS["white"], fg=COLORS["muted"], font=SMALL_FONT, anchor="w").pack(anchor="w", pady=(6, 0))
        self.header_badge = RoundedButton(body, "• 服务离线", fill="#FFF5F5", fg=COLORS["red"], height=36, radius=13, font=BOLD_FONT, min_width=108, disabled=True)
        self.header_badge.grid(row=0, column=1, sticky="e", padx=4)

    def build_service_card(self):
        card = self.make_card(self.right_area, height=154)
        card.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        body = card.body
        body.grid_columnconfigure(0, weight=1)
        tk.Label(body, text="服务控制", bg=COLORS["white"], fg=COLORS["text"], font=TITLE_FONT, anchor="w").grid(row=0, column=0, sticky="w", padx=4, pady=(2, 10))

        row = tk.Frame(body, bg=COLORS["white"])
        row.grid(row=1, column=0, sticky="ew", padx=2)
        for i in range(5):
            row.grid_columnconfigure(i, weight=1, uniform="service")
        buttons = [
            ("🚀 启动服务", COLORS["green"], "white", lambda: self.run_cmd("start")),
            ("🛑 停止服务", COLORS["red"], "white", lambda: self.run_cmd("stop")),
            ("🔄 重启服务", COLORS["orange"], "white", lambda: self.run_cmd("restart")),
            ("🔓 释放端口", COLORS["soft"], COLORS["text"], self.release_port),
            ("🌐 打开面板", COLORS["blue"], "white", lambda: webbrowser.open(f"http://127.0.0.1:{DEFAULT_PORT}")),
        ]
        for i, (text, fill, fg, cmd) in enumerate(buttons):
            btn = RoundedButton(row, text, cmd, fill=fill, fg=fg, height=42, radius=15)
            btn.grid(row=0, column=i, sticky="ew", padx=5)

    def build_data_refresh_card(self):
        card = self.make_card(self.right_area, height=180)
        card.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        body = card.body
        body.grid_columnconfigure(0, weight=1)
        tk.Label(body, text="数据与自动任务", bg=COLORS["white"], fg=COLORS["text"], font=TITLE_FONT, anchor="w").grid(row=0, column=0, sticky="w", padx=4, pady=(2, 8))

        row1 = tk.Frame(body, bg=COLORS["white"])
        row1.grid(row=1, column=0, sticky="ew", padx=2)
        for i in range(4):
            row1.grid_columnconfigure(i, weight=1, uniform="data")
        actions = [
            ("💾 备份 data", COLORS["soft"], COLORS["text"], self.export_data),
            ("📦 还原 data", COLORS["soft"], COLORS["text"], self.import_data),
            ("🔁 手动刷新", COLORS["blue"], "white", lambda: self.run_auto_refresh_once(source="手动刷新")),
            ("⚙ 自动设置", COLORS["purple"], "white", self.open_refresh_settings),
        ]
        for i, (text, fill, fg, cmd) in enumerate(actions):
            btn = RoundedButton(row1, text, cmd, fill=fill, fg=fg, height=36, radius=13)
            btn.grid(row=0, column=i, sticky="ew", padx=5)

        row2 = tk.Frame(body, bg=COLORS["white"])
        row2.grid(row=2, column=0, sticky="ew", padx=2, pady=(10, 0))
        for i in range(3):
            row2.grid_columnconfigure(i, weight=1, uniform="switch")
        self.normal_switch = RoundedButton(row2, "普通刷新", self.toggle_normal_refresh, height=34, radius=13)
        self.restart_switch = RoundedButton(row2, "重启刷新", self.toggle_restart_refresh, height=34, radius=13)
        self.playback_switch = RoundedButton(row2, "播放保护", self.toggle_playback_guard, height=34, radius=13)
        self.normal_switch.grid(row=0, column=0, sticky="ew", padx=5)
        self.restart_switch.grid(row=0, column=1, sticky="ew", padx=5)
        self.playback_switch.grid(row=0, column=2, sticky="ew", padx=5)

        self.refresh_status_label = tk.Label(body, text="自动任务状态：--", bg=COLORS["white"], fg=COLORS["muted"], font=SMALL_FONT, anchor="w")
        self.refresh_status_label.grid(row=3, column=0, sticky="ew", padx=8, pady=(8, 0))

    def build_path_card(self):
        card = self.make_card(self.right_area, height=82)
        card.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        body = card.body
        body.grid_columnconfigure(0, weight=1)
        tk.Label(body, text="当前路径", bg=COLORS["white"], fg=COLORS["muted"], font=SMALL_FONT, anchor="w").grid(row=0, column=0, sticky="ew")
        self.path_value = tk.Label(body, text=self.compact_path(self.app_path), bg=COLORS["white"], fg=COLORS["text"], font=BOLD_FONT, anchor="w")
        self.path_value.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        btn = RoundedButton(body, "选择", self.change_path, fill=COLORS["soft"], fg=COLORS["text"], height=34, radius=12, min_width=76)
        btn.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))

    def build_log_area(self):
        card = self.make_card(self.right_area, fill=COLORS["white"], height=268)
        card.grid(row=4, column=0, sticky="nsew")
        body = card.body
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        header = tk.Frame(body, bg=COLORS["white"])
        header.grid(row=0, column=0, sticky="ew", padx=4, pady=(2, 10))
        header.grid_columnconfigure(0, weight=1)
        tk.Label(header, text="运行日志", bg=COLORS["white"], fg=COLORS["text"], font=TITLE_FONT, anchor="w").grid(row=0, column=0, sticky="w")
        self.log_counter_label = tk.Label(header, text="0 条", bg=COLORS["white"], fg=COLORS["muted"], font=SMALL_FONT, anchor="e")
        self.log_counter_label.grid(row=0, column=1, sticky="e")

        log_shell = RoundedPanel(body, fill=COLORS["soft2"], outline=COLORS["border"], radius=18, inner_pad=10, height=190, auto_height=False)
        log_shell.grid(row=1, column=0, sticky="nsew", padx=2, pady=(0, 2))
        shell_body = log_shell.body
        shell_body.grid_columnconfigure(0, weight=1)
        shell_body.grid_rowconfigure(0, weight=1)

        self.log_box = tk.Text(
            shell_body,
            bg=COLORS["soft2"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            bd=0,
            padx=12,
            pady=12,
            font=MONO_FONT,
            state="disabled",
            wrap="word",
            undo=False,
            height=1,
        )
        self.log_box.grid(row=0, column=0, sticky="nsew")

        self.log_scrollbar = ModernScrollbar(shell_body, command=self.log_box.yview, width=22)
        self.log_scrollbar.grid(row=0, column=1, sticky="ns", padx=(10, 2), pady=2)
        self.log_box.configure(yscrollcommand=self.log_scrollbar.set)

        self.log_box.bind("<MouseWheel>", self._on_log_mousewheel, add="+")
        self.log_box.bind("<Button-4>", lambda event: self.log_box.yview_scroll(-3, "units"), add="+")
        self.log_box.bind("<Button-5>", lambda event: self.log_box.yview_scroll(3, "units"), add="+")
        shell_body.bind("<MouseWheel>", self._on_log_mousewheel, add="+")

        self.log_box.tag_config("green", foreground="#2B8A3E")
        self.log_box.tag_config("red", foreground="#C92A2A")
        self.log_box.tag_config("orange", foreground="#E67700")
        self.log_box.tag_config("muted", foreground=COLORS["muted"])
        self.log_box.tag_config("normal", foreground=COLORS["text"])
        self.log_line_count = 0
        self.log("OpenList Companion 已就绪", "green")

    def _on_log_mousewheel(self, event):
        delta = getattr(event, "delta", 0)
        if delta > 0:
            self.log_box.yview_scroll(-3, "units")
        elif delta < 0:
            self.log_box.yview_scroll(3, "units")
        return "break"

    # =========================
    # UI 状态与交互
    # =========================
    def update_all_status(self, alive=None, state=None):
        if state is None:
            if alive is True:
                state = "running"
            elif alive is False:
                state = "stopped"
            else:
                state = self.get_service_state()

        if state == "running":
            text = "🟢 正在运行"
            color = COLORS["green"]
        elif state == "starting":
            text = "🟠 启动中"
            color = COLORS["orange"]
        else:
            text = "🔴 未运行"
            color = COLORS["red"]

        self.status_text.config(text=text, fg=color)
        self.update_header_badge(state)

    def update_header_badge(self, state):
        if not hasattr(self, "header_badge"):
            return
        if isinstance(state, bool):
            state = "running" if state else "stopped"
        if state == "running":
            self.header_badge.set_state(text="• 服务在线", fill="#EBFBEE", fg=COLORS["green"])
        elif state == "starting":
            self.header_badge.set_state(text="• 启动中", fill="#FFF4E6", fg=COLORS["orange"])
        else:
            self.header_badge.set_state(text="• 服务离线", fill="#FFF5F5", fg=COLORS["red"])

    def update_refresh_status_label(self, text=None, color=None):
        if not hasattr(self, "refresh_status_label"):
            return
        if text is None:
            if not self.normal_refresh_enabled:
                text = "普通刷新已关"
                color = COLORS["muted"]
            elif self.refresh_running:
                text = "刷新中"
                color = COLORS["orange"]
            elif self.last_refresh_ok is True:
                text = f"上次成功 {self.last_refresh_time}"
                color = COLORS["green"]
            elif self.last_refresh_ok is False:
                text = f"上次失败 {self.last_refresh_time}"
                color = COLORS["red"]
            else:
                text = f"待机中 · 每 {self.refresh_interval} 秒"
                color = COLORS["muted"]
        self.refresh_status_label.config(text=f"自动任务状态：{text}", fg=color or COLORS["muted"])

    def update_toggle_buttons(self):
        if not hasattr(self, "normal_switch"):
            return
        self.normal_switch.set_state(
            text="普通刷新：开" if self.normal_refresh_enabled else "普通刷新：关",
            fill="#EBFBEE" if self.normal_refresh_enabled else COLORS["soft"],
            fg=COLORS["green"] if self.normal_refresh_enabled else COLORS["muted"],
        )
        self.restart_switch.set_state(
            text="重启刷新：开" if self.restart_refresh_enabled else "重启刷新：关",
            fill="#EBFBEE" if self.restart_refresh_enabled else COLORS["soft"],
            fg=COLORS["green"] if self.restart_refresh_enabled else COLORS["muted"],
        )
        self.playback_switch.set_state(
            text="播放保护：开" if self.playback_guard_enabled else "播放保护：关",
            fill="#EBFBEE" if self.playback_guard_enabled else COLORS["soft"],
            fg=COLORS["green"] if self.playback_guard_enabled else COLORS["muted"],
        )

    def toggle_normal_refresh(self):
        self.normal_refresh_enabled = not self.normal_refresh_enabled
        self.save_refresh_settings_safely()
        self.update_toggle_buttons()
        self.restart_auto_refresh_task(reason="普通刷新开关更新", immediate=True)

    def toggle_restart_refresh(self):
        self.restart_refresh_enabled = not self.restart_refresh_enabled
        self.save_refresh_settings_safely()
        self.update_toggle_buttons()
        self.log("♻️ 重启刷新已开启" if self.restart_refresh_enabled else "⏸️ 重启刷新已关闭", "green" if self.restart_refresh_enabled else "orange")

    def toggle_playback_guard(self):
        self.playback_guard_enabled = not self.playback_guard_enabled
        self.save_refresh_settings_safely()
        self.update_toggle_buttons()
        self.log("🛡️ 播放保护已开启" if self.playback_guard_enabled else "⚠️ 播放保护已关闭", "green" if self.playback_guard_enabled else "orange")

    def open_refresh_settings(self):
        if self.refresh_settings_window and self.refresh_settings_window.winfo_exists():
            self.refresh_settings_window.lift()
            return
        win = tk.Toplevel(self)
        self.refresh_settings_window = win
        win.title("自动任务设置")
        win.geometry("480x360")
        win.resizable(False, False)
        win.configure(bg=COLORS["white"])
        win.transient(self)

        form = tk.Frame(win, bg=COLORS["white"], padx=24, pady=22)
        form.pack(fill="both", expand=True)
        form.grid_columnconfigure(1, weight=1)

        vars_map = {
            "url": tk.StringVar(value=self.refresh_url),
            "interval": tk.StringVar(value=str(self.refresh_interval)),
            "timeout": tk.StringVar(value=str(self.refresh_timeout)),
            "restart_wait": tk.StringVar(value=str(self.restart_wait)),
            "idle_guard": tk.StringVar(value=str(self.idle_guard_seconds)),
        }
        rows = [
            ("刷新地址", "url"),
            ("间隔秒数", "interval"),
            ("超时秒数", "timeout"),
            ("重启等待", "restart_wait"),
            ("保护秒数", "idle_guard"),
        ]
        for r, (label, key) in enumerate(rows):
            tk.Label(form, text=label, bg=COLORS["white"], fg=COLORS["muted"], font=SMALL_FONT, anchor="w").grid(row=r, column=0, sticky="w", pady=8, padx=(0, 12))
            entry = RoundedEntry(
                form,
                textvariable=vars_map[key],
                fill=COLORS["soft"],
                outline="#E9ECEF",
                fg=COLORS["text"],
                font=BOLD_FONT,
                height=42,
                radius=14,
            )
            entry.grid(row=r, column=1, sticky="ew", pady=8)

        def save_and_close():
            try:
                self.refresh_url = vars_map["url"].get().strip() or f"http://127.0.0.1:{DEFAULT_PORT}"
                self.refresh_interval = max(5, int(vars_map["interval"].get()))
                self.refresh_timeout = max(1, int(vars_map["timeout"].get()))
                self.restart_wait = max(0, int(vars_map["restart_wait"].get()))
                self.idle_guard_seconds = max(0, int(vars_map["idle_guard"].get()))
                self.save_refresh_settings_to_file()
                self.restart_auto_refresh_task(reason="设置保存", immediate=True)
                self.update_refresh_status_label()
                win.destroy()
            except Exception as e:
                messagebox.showerror("错误", f"设置保存失败：{e}")

        btn_row = tk.Frame(form, bg=COLORS["white"])
        btn_row.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        btn_row.grid_columnconfigure(0, weight=1)
        save_btn = RoundedButton(btn_row, "保存设置", save_and_close, fill=COLORS["blue"], hover_fill=COLORS["blue_hover"], fg="white", height=40, radius=15)
        save_btn.grid(row=0, column=0, sticky="ew")

    # =========================
    # 账户与头像
    # =========================
    def copy_admin_username(self):
        self.clipboard_clear()
        self.clipboard_append("admin")
        self.update()
        self.log("✅ 已复制账户名：admin", "green")

    def set_admin_password(self):
        if not self.app_path:
            messagebox.showwarning("提示", "请先选择 alist.exe 路径")
            self.change_path()
            return

        win = tk.Toplevel(self)
        win.title("修改管理密码")
        win.geometry("420x220")
        win.resizable(False, False)
        win.configure(bg=COLORS["white"])
        win.transient(self)
        self.center_child_window(win, 420, 220)
        try:
            if getattr(self, "_window_icon_photo", None):
                win.iconphoto(False, self._window_icon_photo)
        except Exception:
            pass

        body = tk.Frame(win, bg=COLORS["white"], padx=28, pady=24)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=1)

        tk.Label(
            body,
            text="请输入新密码：",
            bg=COLORS["white"],
            fg=COLORS["text"],
            font=BOLD_FONT,
            anchor="w"
        ).grid(row=0, column=0, sticky="ew", pady=(0, 12))

        pwd_var = tk.StringVar()
        entry = RoundedEntry(
            body,
            textvariable=pwd_var,
            fill="#F3F5F7",
            outline="#E9ECEF",
            fg=COLORS["text"],
            font=BOLD_FONT,
            show="*",
            height=48,
            radius=16,
        )
        entry.grid(row=1, column=0, sticky="ew", pady=(0, 22))
        entry.focus_set()

        def do_submit():
            pwd = pwd_var.get()
            if not pwd:
                messagebox.showwarning("提示", "密码不能为空", parent=win)
                return
            win.destroy()
            try:
                subprocess.Popen([self.app_path, "admin", "set", pwd], creationflags=get_creation_flags()).wait()
                self.log("✅ 管理密码已修改", "green")
                self.run_cmd("restart")
            except Exception as e:
                self.log(f"❌ 修改密码失败：{e}", "red")

        btn_row = tk.Frame(body, bg=COLORS["white"])
        btn_row.grid(row=2, column=0, sticky="ew")
        btn_row.grid_columnconfigure(0, weight=1)
        btn_row.grid_columnconfigure(1, weight=1)

        RoundedButton(
            btn_row,
            "取消",
            win.destroy,
            fill=COLORS["soft"],
            hover_fill="#E9ECEF",
            fg=COLORS["text"],
            height=38,
            radius=14
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        RoundedButton(
            btn_row,
            "确认修改",
            do_submit,
            fill=COLORS["blue"],
            hover_fill=COLORS["blue_hover"],
            fg="white",
            height=38,
            radius=14
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        entry.bind("<Return>", lambda e: do_submit())

        try:
            win.grab_set()
        except Exception:
            pass

    def load_author_info(self):
        def download():
            try:
                res = requests.get(f"https://q1.qlogo.cn/g?b=qq&nk={MY_QQ_NUMBER}&s=640", timeout=5)
                res.raise_for_status()
                image = Image.open(BytesIO(res.content))
                self.after(0, lambda img=image: self.canvas_avatar.set_pil_image(img))
            except Exception:
                self.after(0, self.canvas_avatar.draw_placeholder)
        threading.Thread(target=download, daemon=True).start()

    # =========================
    # 监控与日志
    # =========================
    def start_monitor(self):
        def check():
            state = self.get_service_state()
            if state == "running":
                self.update_activity_guard()
            self.update_all_status(state=state)
            self.after(2000, check)
        check()

    def log(self, msg, tag=None):
        self.after(0, self._safe_log, msg, tag)

    def _safe_log(self, msg, tag=None):
        if not hasattr(self, "log_box"):
            return
        now = time.strftime("%H:%M:%S")
        safe_tag = tag if tag in {"green", "red", "orange", "muted"} else "normal"
        self.log_box.config(state="normal")
        self.log_box.insert(tk.END, f"{now}  ", "muted")
        self.log_box.insert(tk.END, f"{msg}\n", safe_tag)
        self.log_box.config(state="disabled")
        self.log_box.see(tk.END)
        self.log_line_count = getattr(self, "log_line_count", 0) + 1
        if hasattr(self, "log_counter_label"):
            self.log_counter_label.config(text=f"{self.log_line_count} 条")


if __name__ == "__main__":
    set_windows_app_id()
    if SYSTEM == "Windows":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
    OpenListCompanion().mainloop()
