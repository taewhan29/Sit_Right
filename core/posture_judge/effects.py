"""Production warning UI. Call update(result) on the main/UI thread each frame.

Explicit construction creates windows; importing this module does not.
Requires Windows and Pillow. No keyboard hooks, OS lock, or file writes.
"""
try:
    import tkinter as tk
    from .desktop_blur import DesktopBlur
except (ImportError, ModuleNotFoundError):
    tk = None
    DesktopBlur = None


class WarningEffects:
    def __init__(self, preview_only=False):
        self.preview_only = preview_only
        self.desktop = None
        self.root = None
        self.popup = None
        self.camera_photo = None
        self.camera_item = None
        if tk is None:
            return
        try:
            if preview_only:
                self.root = tk.Tk()
                self.root.withdraw()
            else:
                self.desktop = DesktopBlur()
                self.root = self.desktop.root
        except Exception:
            self.close()
            raise

    def _close_popup(self):
        if self.popup is not None:
            self.popup.destroy()
            self.popup = None

    def _show_popup(self):
        self._close_popup()
        self.popup = tk.Toplevel(self.root)
        self.popup.title('1차 자세 경고')
        self.popup.geometry('390x160')
        self.popup.attributes('-topmost', True)
        tk.Label(self.popup, text='잘못된 자세가 누적되었습니다.\n바른 자세로 돌아와 주세요.',
                 font=('맑은 고딕', 12), pady=22).pack()
        tk.Button(self.popup, text='확인', command=self._close_popup).pack()
        self.popup.protocol('WM_DELETE_WINDOW', self._close_popup)

    def update(self, result, frame=None):
        if self.root is None:
            action = result.get('action')
            if action:
                print(f"[경고 효과 알림] {action}", flush=True)
            return
        action = result.get('action')
        level = result['effect_level']
        if level != 1 or action in ('clear_warnings', 'suspend_warnings'):
            self._close_popup()
        elif action == 'show_popup':
            self._show_popup()
        if self.desktop is not None:
            self.desktop.update(level)
            canvas = self.desktop.canvas
            canvas.delete('correction_notice')
            if level != 3 or self.desktop.dismissed:
                canvas.delete('correction_camera')
                self.camera_item = self.camera_photo = None
            if level == 3 and not self.desktop.dismissed:
                x, y = (self.desktop.user.GetSystemMetrics(i) for i in (76, 77))
                center = -x + self.desktop.user.GetSystemMetrics(0) // 2
                top = -y + 100
                hold = result.get('correction_good_duration', 0.0)
                text = ('3차 자세 교정\n기준 자세를 연속 5초 유지하세요.'
                        f'\n정상 자세 유지: {hold:.1f} / 5.0초'
                        '\nCtrl+Shift+F12 또는 Esc: 긴급 화면 해제')
                # Text only, without the old black instruction box.
                canvas.create_text(center + 2, top + 2, text=text, fill='black',
                                   font=('맑은 고딕', 22), justify='center',
                                   tags='correction_notice')
                canvas.create_text(center, top, text=text, fill='white',
                                   font=('맑은 고딕', 22), justify='center',
                                   tags='correction_notice')
                # A distinct live camera view is raised with the correction overlay.
                # Desktop blur remains a frozen snapshot; this view updates each call.
                if frame is not None:
                    from PIL import Image, ImageTk
                    if frame.ndim != 3 or frame.shape[2] != 3:
                        raise ValueError('frame must be an HxWx3 BGR image.')
                    image = Image.fromarray(frame[:, :, ::-1].copy())
                    primary_width = self.desktop.user.GetSystemMetrics(0)
                    primary_height = self.desktop.user.GetSystemMetrics(1)
                    image.thumbnail((max(1, min(800, primary_width - 60)),
                                     max(1, primary_height - 230)))
                    self.camera_photo = ImageTk.PhotoImage(image, master=self.root)
                    camera_y = -y + 200
                    if self.camera_item is None or not canvas.find_withtag('correction_camera'):
                        self.camera_item = canvas.create_image(
                            center, camera_y, anchor='n', image=self.camera_photo,
                            tags='correction_camera')
                    else:
                        canvas.itemconfigure(self.camera_item, image=self.camera_photo)
                        canvas.coords(self.camera_item, center, camera_y)
                    canvas.tag_raise('correction_camera')
                else:
                    canvas.delete('correction_camera')
                    self.camera_item = self.camera_photo = None
                    canvas.create_text(center, -y + 240,
                                       text='웹캠 영상 대기 중 — 자세 데이터 연결을 확인하세요.',
                                       fill='white', font=('맑은 고딕', 16),
                                       tags='correction_notice')
        self.root.update_idletasks()
        self.root.update()

    def clear(self):
        """Clear UI after an explicit reference/session reset. Does not reset logic."""
        self._close_popup()
        if self.desktop is not None:
            self.desktop.update(0)
            self.desktop.canvas.delete('correction_notice')
            self.desktop.canvas.delete('correction_camera')
        self.camera_item = self.camera_photo = None

    def close(self):
        self._close_popup()
        self.camera_item = self.camera_photo = None
        if self.desktop is not None:
            self.desktop.close()
            self.desktop = None
            self.root = None
        elif self.root is not None:
            self.root.destroy()
            self.root = None
