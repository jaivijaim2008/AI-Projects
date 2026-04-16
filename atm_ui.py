from PySide6.QtWidgets import (
    QMainWindow, QWidget, QLabel,
    QVBoxLayout, QHBoxLayout, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QObject, Signal, Slot
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont,
    QLinearGradient, QRadialGradient, QPixmap, QImage
)
import time
import numpy as np

# ── Palette ───────────────────────────────────────────────────────────────────
C_BG       = QColor('#050d1a')
C_MID      = QColor('#0f1e35')
C_CARD     = QColor('#0a1628')
C_CYAN     = QColor('#00d4ff')
C_CYAN_DIM = QColor(0, 212, 255, 60)
C_GREEN    = QColor('#00ff88')
C_RED      = QColor('#ff3355')
C_GOLD     = QColor('#ffd700')
C_WHITE    = QColor('#e8f4fd')
C_GREY     = QColor('#4a6080')


def mono(size, bold=False):
    f = QFont('Courier New', size)
    f.setBold(bold)
    return f


# ── Signal Bridge (safe cross-thread UI calls) ────────────────────────────────
class _Bridge(QObject):
    sig_welcome  = Signal()
    sig_scanning = Signal(str)
    sig_face     = Signal()
    sig_balance  = Signal(str, int, str)
    sig_error    = Signal(str, str, str)
    sig_cam      = Signal(object)   # PIL Image → main thread


# ── Glow Label ────────────────────────────────────────────────────────────────
class GlowLabel(QLabel):
    def __init__(self, text, color=None, parent=None):
        super().__init__(text, parent)
        self._color = color or C_CYAN
        self.setAlignment(Qt.AlignCenter)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = self.width()//2, self.height()//2
        rg = QRadialGradient(cx, cy, max(self.width(), self.height())//2)
        gc = QColor(self._color); gc.setAlpha(70)
        rg.setColorAt(0, gc); rg.setColorAt(1, QColor(0,0,0,0))
        p.fillRect(self.rect(), rg)
        p.end()
        super().paintEvent(event)


# ── Spinner ───────────────────────────────────────────────────────────────────
class SpinnerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 120)
        self._angle = 0
        t = QTimer(self); t.timeout.connect(self._tick); t.start(25)

    def _tick(self):
        self._angle = (self._angle + 6) % 360; self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy, r1, r2 = 60, 60, 54, 36
        p.setPen(QPen(C_CYAN, 4, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(cx-r1, cy-r1, r1*2, r1*2, self._angle*16, 240*16)
        dim = QColor(C_CYAN); dim.setAlpha(50)
        p.setPen(QPen(dim, 3, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(cx-r1, cy-r1, r1*2, r1*2, (self._angle+240)*16, 120*16)
        p.setPen(QPen(C_GREEN, 3, Qt.SolidLine, Qt.RoundCap))
        rev = (-int(self._angle*1.4)) % 360
        p.drawArc(cx-r2, cy-r2, r2*2, r2*2, rev*16, 180*16)
        p.end()


# ── Progress Bar ──────────────────────────────────────────────────────────────
class ProgressBar(QWidget):
    def __init__(self, color=None, duration_ms=2800, parent=None):
        super().__init__(parent)
        self.setFixedHeight(8)
        self._color = color or C_CYAN
        self._pct = 0.0
        steps = 80
        self._step = 1.0/steps
        t = QTimer(self); t.setInterval(max(1, duration_ms//steps))
        t.timeout.connect(self._tick); t.start()

    def _tick(self):
        self._pct = min(1.0, self._pct+self._step); self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setBrush(QBrush(QColor(255,255,255,20))); p.setPen(Qt.NoPen)
        p.drawRoundedRect(0,0,w,h,4,4)
        fw = int(w*self._pct)
        if fw > 0:
            g = QLinearGradient(0,0,fw,0)
            g.setColorAt(0, C_CYAN); g.setColorAt(1, C_GREEN)
            p.setBrush(QBrush(g)); p.drawRoundedRect(0,0,fw,h,4,4)
            gw = QColor(C_GREEN); gw.setAlpha(140)
            p.setBrush(QBrush(gw)); p.drawEllipse(fw-6,-3,12,14)
        p.end()


# ── Screen Panel ──────────────────────────────────────────────────────────────
class ScreenPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._border_color = C_CYAN
        self._flash = False

    def set_border(self, color):
        self._border_color = color; self.update()

    def flash_red(self):
        self._do_flash(0)

    def _do_flash(self, step):
        self._flash = (step % 2 == 0); self.update()
        if step < 5:
            QTimer.singleShot(180, lambda: self._do_flash(step+1))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1,1,-1,-1)
        bg = QLinearGradient(0,0,0,self.height())
        bg.setColorAt(0, QColor('#07101f')); bg.setColorAt(1, QColor('#050d1a'))
        p.fillRect(self.rect(), bg)
        p.setPen(QPen(QColor(0,212,255,8), 1))
        for y in range(0, self.height(), 6):
            p.drawLine(0, y, self.width(), y)
        if self._flash:
            ov = QColor(C_RED); ov.setAlpha(35)
            p.fillRect(self.rect(), ov)
        for i in range(3, 0, -1):
            gc = QColor(self._border_color); gc.setAlpha(25*i)
            p.setPen(QPen(gc, i*2))
            p.drawRoundedRect(r.adjusted(i,i,-i,-i), 8, 8)
        p.setPen(QPen(self._border_color, 1))
        p.drawRoundedRect(r, 8, 8)
        p.end()


# ── Face Frame ────────────────────────────────────────────────────────────────
class FaceFrame(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scan_y = 0
        self._cam_pixmap = None
        t = QTimer(self); t.timeout.connect(self._tick); t.start(30)

    def set_pixmap(self, pix):
        self._cam_pixmap = pix; self.update()

    def _tick(self):
        self._scan_y = (self._scan_y+3) % max(self.height(),1); self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Camera feed or dark background
        if self._cam_pixmap:
            p.drawPixmap(self.rect(), self._cam_pixmap)
        else:
            p.fillRect(self.rect(), QColor('#050d1a'))
            p.setPen(QPen(QColor(0, 212, 255, 120)))
            p.setFont(mono(12))
            p.drawText(self.rect(), Qt.AlignCenter, '[ CAMERA INITIALIZING ]')

        # Scanline sweep
        sy = self._scan_y
        sg = QLinearGradient(0, sy-10, 0, sy+10)
        sg.setColorAt(0,   QColor(0, 212, 255, 0))
        sg.setColorAt(0.5, QColor(0, 212, 255, 200))
        sg.setColorAt(1,   QColor(0, 212, 255, 0))
        p.fillRect(0, sy-10, self.width(), 20, sg)

        # Corner brackets
        L = 36
        p.setPen(QPen(QColor('#00d4ff'), 3))
        for cx, cy, dx, dy in [
            (0, 0, 1, 1),
            (self.width(), 0, -1, 1),
            (0, self.height(), 1, -1),
            (self.width(), self.height(), -1, -1)
        ]:
            p.drawLine(cx, cy, cx + dx*L, cy)
            p.drawLine(cx, cy, cx, cy + dy*L)

        # Vignette
        vg = QRadialGradient(self.width()//2, self.height()//2,
                             max(self.width(), self.height())//2)
        vg.setColorAt(0, QColor(0, 0, 0, 0))
        vg.setColorAt(1, QColor(0, 0, 0, 100))
        p.fillRect(self.rect(), vg)
        p.end()


# ── Badge ─────────────────────────────────────────────────────────────────────
class BadgeWidget(QWidget):
    def __init__(self, symbol, color, bg_color, parent=None):
        super().__init__(parent)
        self.setFixedSize(100, 100)
        self._symbol = symbol; self._color = color
        self._bg_color = bg_color; self._glow = 0; self._dir = 1
        t = QTimer(self); t.timeout.connect(self._pulse); t.start(40)

    def _pulse(self):
        self._glow += self._dir*3
        if self._glow >= 120: self._dir = -1
        if self._glow <= 0:   self._dir = 1
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy, r = 50, 50, 44
        rg = QRadialGradient(cx, cy, r+18)
        gc = QColor(self._color); gc.setAlpha(self._glow)
        rg.setColorAt(0, gc); rg.setColorAt(1, QColor(0,0,0,0))
        p.fillRect(self.rect(), rg)
        bg = QColor(self._bg_color); bg.setAlpha(180)
        p.setBrush(QBrush(bg)); p.setPen(QPen(self._color, 2))
        p.drawEllipse(cx-r, cy-r, r*2, r*2)
        p.setPen(QPen(self._color))
        f = QFont('Courier New', 28); f.setBold(True)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignCenter, self._symbol)
        p.end()


# ── Account Card ──────────────────────────────────────────────────────────────
class AccountCard(QWidget):
    def __init__(self, name, acno, balance, parent=None):
        super().__init__(parent)
        self._name    = name.upper()
        self._acno    = acno
        self._balance = f'Rs. {balance:,}'
        self.setMinimumHeight(220)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(2,2,-2,-2)
        bg = QLinearGradient(0,0,self.width(),self.height())
        bg.setColorAt(0, QColor('#0f1e35')); bg.setColorAt(1, QColor('#071526'))
        p.setBrush(QBrush(bg)); p.setPen(QPen(C_GREEN, 1))
        p.drawRoundedRect(r, 14, 14)
        cr = QColor(0,212,255,15); p.setBrush(QBrush(cr)); p.setPen(Qt.NoPen)
        p.drawEllipse(self.width()-100, -50, 160, 160)
        p.setPen(QPen(C_GREY));  p.setFont(mono(11))
        p.drawText(r.adjusted(24,20,0,0), Qt.AlignTop|Qt.AlignLeft, 'ACCOUNT HOLDER')
        p.setPen(QPen(C_WHITE)); p.setFont(mono(20, True))
        p.drawText(r.adjusted(24,48,0,0), Qt.AlignTop|Qt.AlignLeft, self._name)
        p.setPen(QPen(C_CYAN));  p.setFont(mono(14))
        p.drawText(r.adjusted(24,84,0,0), Qt.AlignTop|Qt.AlignLeft, self._acno)
        p.setPen(QPen(C_GREY, 1))
        y_div = r.top() + 118
        p.drawLine(r.left()+24, y_div, r.right()-24, y_div)
        p.setPen(QPen(C_GREY)); p.setFont(mono(11))
        p.drawText(r.adjusted(24,128,0,0), Qt.AlignTop|Qt.AlignLeft, 'BALANCE')
        rg = QRadialGradient(self.width()//2, r.top()+170, 120)
        gc = QColor(C_GREEN); gc.setAlpha(40)
        rg.setColorAt(0, gc); rg.setColorAt(1, QColor(0,0,0,0))
        p.fillRect(self.rect(), rg)
        p.setPen(QPen(C_GREEN)); p.setFont(mono(26, True))
        p.drawText(r.adjusted(24,148,0,0), Qt.AlignTop|Qt.AlignLeft, self._balance)
        p.end()


# ── Root Proxy ────────────────────────────────────────────────────────────────
class _RootProxy:
    """Allows atm_main.py to call ui.root.after(ms, func) safely from any thread."""
    def __init__(self, bridge):
        self._bridge = bridge

    def after(self, ms, func=None):
        if func:
            QTimer.singleShot(int(ms), func)

    def mainloop(self):
        pass


# ── Cam Proxy ─────────────────────────────────────────────────────────────────
class _CamProxy:
    def __init__(self, bridge):
        self._bridge = bridge
        self.image = None

    def config(self, image=None, text=None):
        if image is None:
            return
        self.image = image
        try:
            self._bridge.sig_cam.emit(image)
        except Exception as e:
            print(f'[CAM] emit error: {e}')

    def after(self, ms, func):
        QTimer.singleShot(int(ms), func)

    def winfo_height(self):
        return 400

    def cget(self, key):
        return '' if self.image is None else self.image


# ── ATM_UI ────────────────────────────────────────────────────────────────────
class ATM_UI:
    def __init__(self, app):
        self._app    = app
        self._bridge = _Bridge()

        # Connect signals to slots (always runs on main thread)
        self._bridge.sig_welcome.connect(self._show_welcome)
        self._bridge.sig_scanning.connect(self._do_scanning)
        self._bridge.sig_face.connect(self._do_face_scan)
        self._bridge.sig_balance.connect(self._do_balance)
        self._bridge.sig_error.connect(self._do_error)
        self._bridge.sig_cam.connect(self._update_cam)

        self._win = QMainWindow()
        self._win.setWindowTitle('SRB BANK — Secure ATM')
        self._win.setStyleSheet('background: #050d1a;')
        # ── FULLSCREEN ──
        self._win.showFullScreen()

        central = QWidget()
        self._win.setCentralWidget(central)
        self._layout = QVBoxLayout(central)
        self._layout.setContentsMargins(32, 20, 32, 20)
        self._layout.setSpacing(0)

        self._build_topbar()
        self._build_screen()
        self._build_bottombar()

        self.root    = _RootProxy(self._bridge)
        self.cam_lbl = _CamProxy(self._bridge)

        self._clock_timer = QTimer()
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

        self._show_welcome()

    # ── Shell ─────────────────────────────────────────────────────────────────
    def _build_topbar(self):
        bar = QWidget(); bar.setFixedHeight(56)
        bar.setStyleSheet('background: transparent;')
        h = QHBoxLayout(bar); h.setContentsMargins(8, 0, 8, 0)

        logo = QLabel('◈  SRB BANK')
        logo.setFont(mono(22, True))
        logo.setStyleSheet(f'color: {C_CYAN.name()}; background: transparent;')
        h.addWidget(logo); h.addStretch()

        self._dot_lbl = QLabel('●')
        self._dot_lbl.setFont(mono(14))
        self._dot_lbl.setStyleSheet(f'color: {C_GREEN.name()};')
        h.addWidget(self._dot_lbl)
        self._layout.addWidget(bar)

        self._dot_state = True
        self._dot_timer = QTimer()
        self._dot_timer.timeout.connect(self._blink_dot)
        self._dot_timer.start(900)

    def _build_screen(self):
        self._screen = ScreenPanel()
        self._screen.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._screen_layout = QVBoxLayout(self._screen)
        self._screen_layout.setContentsMargins(40, 30, 40, 30)
        self._screen_layout.setSpacing(12)
        self._layout.addWidget(self._screen, 1)

    def _build_bottombar(self):
        bar = QWidget(); bar.setFixedHeight(40)
        bar.setStyleSheet('background: transparent;')
        h = QHBoxLayout(bar); h.setContentsMargins(8, 0, 8, 0)

        slot = QLabel('CARD SLOT  ▬')
        slot.setFont(mono(10)); slot.setStyleSheet(f'color: {C_GREY.name()};')
        h.addWidget(slot)

        self._clock_lbl = QLabel('')
        self._clock_lbl.setFont(mono(10))
        self._clock_lbl.setStyleSheet(f'color: {C_GREY.name()};')
        h.addWidget(self._clock_lbl); h.addStretch()

        esc = QLabel('Press ESC to exit')
        esc.setFont(mono(9)); esc.setStyleSheet(f'color: {C_GREY.name()};')
        h.addWidget(esc)

        cam = QLabel('CAM ●')
        cam.setFont(mono(10)); cam.setStyleSheet(f'color: {C_GREEN.name()};')
        h.addWidget(cam)
        self._layout.addWidget(bar)

    def _clear(self):
        while self._screen_layout.count():
            item = self._screen_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._screen.set_border(C_CYAN)

    def _spacer(self):
        sp = QWidget()
        sp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sp.setStyleSheet('background: transparent;')
        return sp

    # ── Screens ───────────────────────────────────────────────────────────────
    @Slot()
    def _show_welcome(self):
        self._clear()
        self._screen_layout.addWidget(self._spacer())

        badge = BadgeWidget('▣', C_GOLD, C_CARD)
        self._screen_layout.addWidget(badge, 0, Qt.AlignCenter)

        title = GlowLabel('WELCOME', C_CYAN)
        title.setFont(mono(36, True))
        title.setStyleSheet(f'color: {C_WHITE.name()}; background: transparent;')
        self._screen_layout.addWidget(title, 0, Qt.AlignCenter)

        sub = QLabel('SCAN YOUR CARD TO BEGIN')
        sub.setFont(mono(14)); sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f'color: {C_CYAN.name()}; background: transparent;')
        self._screen_layout.addWidget(sub)

        self._screen_layout.addWidget(self._spacer())

        self._prompt = QLabel('▶  WAITING FOR CARD')
        self._prompt.setFont(mono(14)); self._prompt.setAlignment(Qt.AlignCenter)
        self._prompt.setStyleSheet(
            f'color: {C_CYAN.name()}; background: rgba(0,212,255,15);'
            f'border: 1px solid rgba(0,212,255,60); padding: 14px 40px;'
        )
        self._screen_layout.addWidget(self._prompt, 0, Qt.AlignCenter)
        self._screen_layout.addSpacing(30)

        self._pulse_step = 0
        self._pulse_timer = QTimer()
        self._pulse_timer.timeout.connect(self._pulse_prompt)
        self._pulse_timer.start(600)

    def _pulse_prompt(self):
        try:
            alphas  = [15, 45, 15]
            borders = [60, 210, 60]
            a = alphas[self._pulse_step % 3]
            b = borders[self._pulse_step % 3]
            self._prompt.setStyleSheet(
                f'color: {C_CYAN.name()};'
                f'background: rgba(0,212,255,{a});'
                f'border: 1px solid rgba(0,212,255,{b});'
                f'padding: 14px 40px;'
            )
            self._pulse_step += 1
        except Exception:
            self._pulse_timer.stop()

    @Slot(str)
    def _do_scanning(self, uid: str):
        self._clear()
        self._screen_layout.addWidget(self._spacer())
        self._spinner = SpinnerWidget()
        self._screen_layout.addWidget(self._spinner, 0, Qt.AlignCenter)
        lbl = GlowLabel('READING CARD', C_CYAN)
        lbl.setFont(mono(26, True))
        lbl.setStyleSheet(f'color: {C_CYAN.name()}; background: transparent;')
        self._screen_layout.addWidget(lbl, 0, Qt.AlignCenter)
        uid_lbl = QLabel(uid)
        uid_lbl.setFont(mono(18)); uid_lbl.setAlignment(Qt.AlignCenter)
        uid_lbl.setStyleSheet(f'color: {C_GREEN.name()}; background: transparent;')
        self._screen_layout.addWidget(uid_lbl)
        pb = ProgressBar(C_CYAN, 2800)
        self._screen_layout.addWidget(pb, 0, Qt.AlignCenter)
        self._screen_layout.addWidget(self._spacer())

    @Slot()
    def _do_face_scan(self):
        self._clear()
        lbl_title = GlowLabel('FACE VERIFICATION', C_CYAN)
        lbl_title.setFont(mono(26, True))
        lbl_title.setStyleSheet(f'color: {C_CYAN.name()}; background: transparent;')
        self._screen_layout.addWidget(lbl_title, 0, Qt.AlignCenter)
        sub = QLabel('LOOK DIRECTLY AT THE CAMERA')
        sub.setFont(mono(13)); sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f'color: {C_GREY.name()}; background: transparent;')
        self._screen_layout.addWidget(sub)
        self._face_frame = FaceFrame()
        self._face_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._face_frame.setMinimumHeight(400)
        self._screen_layout.addWidget(self._face_frame, 1)
        pb = ProgressBar(C_GREEN, 3500)
        self._screen_layout.addWidget(pb, 0, Qt.AlignCenter)
        self._screen_layout.addWidget(self._spacer())

    @Slot(str, int, str)
    def _do_balance(self, name: str, balance: int, acno: str):
        self._clear()
        self._screen.set_border(C_GREEN)
        self._screen_layout.addSpacing(16)
        badge = BadgeWidget('✓', C_GREEN, C_CARD)
        self._screen_layout.addWidget(badge, 0, Qt.AlignCenter)
        granted = GlowLabel('ACCESS GRANTED', C_GREEN)
        granted.setFont(mono(28, True))
        granted.setStyleSheet(f'color: {C_GREEN.name()}; background: transparent;')
        self._screen_layout.addWidget(granted, 0, Qt.AlignCenter)
        card = AccountCard(name, acno, balance)
        self._screen_layout.addWidget(card)
        self._screen_layout.addWidget(self._spacer())
        self._glow_step = 0
        self._glow_timer = QTimer()
        self._glow_timer.timeout.connect(self._glow_pulse)
        self._glow_timer.start(400)

    def _glow_pulse(self):
        colors = [C_GREEN, C_CYAN_DIM, C_GREEN, C_CYAN_DIM, C_GREEN]
        if self._glow_step < len(colors):
            self._screen.set_border(colors[self._glow_step])
            self._glow_step += 1
        else:
            self._glow_timer.stop()

    @Slot(str, str, str)
    def _do_error(self, title: str, msg: str, hint: str):
        self._clear()
        self._screen.set_border(C_RED)
        self._screen_layout.addWidget(self._spacer())

        badge = BadgeWidget('✕', C_RED, C_CARD)
        self._screen_layout.addWidget(badge, 0, Qt.AlignCenter)

        t = GlowLabel(title, C_RED)
        t.setFont(mono(26, True))
        t.setStyleSheet(f'color: {C_RED.name()}; background: transparent;')
        self._screen_layout.addWidget(t, 0, Qt.AlignCenter)

        # Divider line
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet(f'background: {C_RED.name()}; opacity: 0.3;')
        self._screen_layout.addWidget(line)

        m = QLabel(msg)
        m.setFont(mono(16)); m.setAlignment(Qt.AlignCenter)
        m.setStyleSheet(f'color: {C_RED.name()}; background: transparent;')
        self._screen_layout.addWidget(m)

        h = QLabel(hint)
        h.setFont(mono(12)); h.setAlignment(Qt.AlignCenter)
        h.setStyleSheet(f'color: {C_GREY.name()}; background: transparent; padding-top: 6px;')
        self._screen_layout.addWidget(h)

        self._screen_layout.addWidget(self._spacer())
        self._screen.flash_red()

    @Slot(object)
    def _update_cam(self, pil_img):
        try:
            if not hasattr(self, '_face_frame'):
                return
            # Check widget is still alive
            try:
                _ = self._face_frame.width()
            except RuntimeError:
                del self._face_frame
                return
            import numpy as np
            w = self._face_frame.width()  or 800
            h = self._face_frame.height() or 500
            pil_resized = pil_img.resize((w, h))
            arr = np.ascontiguousarray(np.array(pil_resized))
            fh, fw, ch = arr.shape
            bytes_per_line = fw * ch
            self._cam_arr = arr
            qi  = QImage(self._cam_arr.data, fw, fh,
                         bytes_per_line, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qi.copy())
            self._face_frame.set_pixmap(pix)
        except RuntimeError:
            if hasattr(self, '_face_frame'):
                del self._face_frame
        except Exception as e:
            pass

    # Public methods called by atm_main.py (thread-safe via signals)
    def show_scanning(self, uid: str):
        self._bridge.sig_scanning.emit(uid)

    def show_face_scan(self):
        self._bridge.sig_face.emit()

    def show_balance(self, name: str, balance: int, acno: str):
        self._bridge.sig_balance.emit(name, balance, acno)

    def show_error(self, title: str, msg: str, hint: str):
        self._bridge.sig_error.emit(title, msg, hint)

    def _blink_dot(self):
        self._dot_state = not self._dot_state
        self._dot_lbl.setStyleSheet(
            f'color: {"#00ff88" if self._dot_state else "#050d1a"};'
        )

    def _update_clock(self):
        self._clock_lbl.setText(time.strftime('%H:%M:%S'))

    # ESC to exit fullscreen
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._win.close()