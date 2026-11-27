"""Short, interruptible animations for application-owned windows."""
from PyQt5.QtCore import QEasingCurve, QObject, QRect, Qt, QVariantAnimation, pyqtSignal
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QApplication, QDialog, QWidget


def widget_rect(widget):
    if widget is None or not widget.isVisible():
        return QRect()
    return QRect(widget.mapToGlobal(widget.rect().topLeft()),widget.size())


def menu_rect(window, menu):
    bar=window.menuBar()
    rect=bar.actionGeometry(menu.menuAction())
    return QRect(bar.mapToGlobal(rect.topLeft()),rect.size()) if bar.isVisible() else QRect()


class WindowSnapshot(QWidget):
    def __init__(self,owner,pixmap):
        flags=Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput
        super().__init__(owner,flags)
        self.pixmap=pixmap
        self.alpha=1.0
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setOpacity(self.alpha)
        painter.drawPixmap(self.rect(),self.pixmap)


class WindowMotion(QObject):
    enabledChanged = pyqtSignal(bool)

    def __init__(self,owner,settings):
        super().__init__(owner)
        self.owner=owner
        self.settings=settings
        self.running={}

    def enabled(self):
        return bool(self.settings.get('interfaceAnimations',True))

    def available(self):
        return (self.enabled() and self.owner.isVisible() and not self.owner.isMinimized()
                and QApplication.platformName() not in ('offscreen','minimal')
                and not QApplication.closingDown())

    def setEnabled(self,enabled):
        self.settings['interfaceAnimations']=bool(enabled)
        self.settings.save()
        if not enabled:
            self.finishAll()
        self.enabledChanged.emit(bool(enabled))

    def finishAll(self):
        for window in list(self.running):
            self.finish(window)

    def finish(self,window):
        transition=self.running.pop(window,None)
        if transition is None:
            return
        animation,ghost,reveal=transition
        animation.stop()
        animation.deleteLater()
        ghost.hide()
        ghost.deleteLater()
        if reveal:
            try:
                window.setWindowOpacity(1)
            except RuntimeError:
                pass

    def play(self,window,anchor=None,opening=False):
        self.finish(window)
        if not self.available() or not window.isVisible() or window.isMinimized():
            return False
        full=widget_rect(window)
        if not full.isValid():
            return False
        target=anchor() if callable(anchor) else widget_rect(anchor)
        if opening and not target.isValid():
            return False
        # A hidden or unavailable entry still gets a short fade, not a jump
        # toward an arbitrary point on the desktop.
        target=target if target.isValid() else full
        ghost=WindowSnapshot(self.owner,window.grab())
        animation=QVariantAnimation(self)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setDuration(215 if opening else 180)
        animation.setEasingCurve(QEasingCurve.OutCubic if opening else QEasingCurve.InOutCubic)
        self.running[window]=(animation,ghost,opening)

        def frame(progress):
            t=progress if opening else 1.0-progress
            blend=lambda a,b:round(a+(b-a)*t)
            ghost.setGeometry(blend(target.x(),full.x()),blend(target.y(),full.y()),
                              max(1,blend(target.width(),full.width())),
                              max(1,blend(target.height(),full.height())))
            ghost.alpha=t
            ghost.update()

        frame(0.0)
        ghost.show()
        if opening:
            window.setWindowOpacity(0)
        animation.valueChanged.connect(frame)
        animation.finished.connect(lambda:self.finish(window))
        animation.start()
        return True


class MotionDialog(QDialog):
    """Keep QDialog acceptance/rejection immediate; animate a noninteractive copy."""
    motionAnchor=None

    def animator(self):
        owner=self.parentWidget()
        while owner is not None:
            controller=getattr(owner,'windowMotion',None)
            if controller is not None:
                return controller
            owner=owner.parentWidget()
        return None

    def done(self,result):
        animator=self.animator()
        if animator is not None:
            animator.play(self,self.motionAnchor)
        super().done(result)

    def showAnimated(self):
        already_visible=self.isVisible() and not self.isMinimized()
        self.showNormal()
        self.raise_()
        self.activateWindow()
        animator=self.animator()
        if animator is not None and not already_visible:
            animator.play(self,self.motionAnchor,opening=True)

    def collapseAnimated(self):
        animator=self.animator()
        if animator is not None:
            animator.play(self,self.motionAnchor)
        self.hide()
