"""Frozen desktop snapshot blur. Images stay in memory; no saving or transmission."""
import ctypes
import os
import tkinter as tk
from ctypes import wintypes

class DesktopBlur:
    def __init__(self):
        if os.name != 'nt':
            raise RuntimeError('Windows required.')
        try:
            from PIL import ImageGrab, ImageFilter, ImageTk, ImageEnhance
        except ImportError as error:
            raise RuntimeError('Run: python -m pip install pillow') from error
        self.grab, self.filter, self.photo_type, self.enhance = ImageGrab, ImageFilter, ImageTk, ImageEnhance
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.user.GetParent.argtypes = [wintypes.HWND]
        self.user.GetParent.restype = wintypes.HWND
        self.user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        self.user.SetWindowPos.restype = wintypes.BOOL
        self.user.GetAsyncKeyState.restype = ctypes.c_short
        self.old_dpi = None
        try:
            self.user.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
            self.user.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
            self.old_dpi = self.user.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        except AttributeError:
            pass
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            if self.old_dpi:
                self.user.SetThreadDpiAwarenessContext(self.old_dpi)
            raise RuntimeError('Overlay window creation failed.') from error
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.canvas = tk.Canvas(self.root, highlightthickness=0, bg='black')
        self.canvas.pack(fill='both', expand=True)
        self.root.bind('<Escape>', lambda event: self.dismiss())
        self.level, self.dismissed = 0, False
        self.snapshot = self.photo = None

    def dismiss(self):
        self.dismissed = True
        self.root.withdraw()

    def update(self, level):
        changed = level != self.level
        if changed:
            self.level, self.dismissed = level, False
        if all(self.user.GetAsyncKeyState(k) & 0x8000 for k in (0x11, 0x10, 0x7B)):
            self.dismiss()
        try:
            if level < 2 or self.dismissed:
                if self.root.winfo_ismapped():
                    self.root.withdraw()
                self.snapshot = self.photo = None
            elif changed:
                x, y, width, height = (self.user.GetSystemMetrics(i) for i in (76, 77, 78, 79))
                if self.snapshot is None:
                    self.root.withdraw()
                    self.root.update()
                    self.snapshot = self.grab.grab(all_screens=True).convert('RGB')
                image = self.snapshot.resize((max(1, width // 4), max(1, height // 4)))
                image = image.filter(self.filter.GaussianBlur(6)).resize((width, height))
                if level == 3:
                    image = self.enhance.Brightness(image).enhance(0.4)
                self.photo = self.photo_type.PhotoImage(image, master=self.root)
                self.canvas.delete('all')
                self.canvas.create_image(0, 0, image=self.photo, anchor='nw')
                self.root.geometry(f'{width}x{height}+0+0')
                self.root.deiconify()
                self.root.update_idletasks()
                inner = self.root.winfo_id()
                hwnd = self.user.GetParent(inner) or inner
                if not self.user.SetWindowPos(hwnd, wintypes.HWND(-1), x, y, width, height, 0x0040):
                    raise ctypes.WinError(ctypes.get_last_error())
                self.root.lift()
            self.root.update_idletasks()
            self.root.update()
        except (OSError, tk.TclError, ValueError) as error:
            self.root.withdraw()
            raise RuntimeError(f'Desktop overlay failed: {error}') from error

    def close(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        self.snapshot = self.photo = None
        if self.old_dpi:
            self.user.SetThreadDpiAwarenessContext(self.old_dpi)
            self.old_dpi = None
