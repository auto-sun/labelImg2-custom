"""Version-specific illustrated tours. The demonstration never sends UI input."""
from PyQt5.QtCore import QElapsedTimer, QObject, QRect, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QPushButton,
                             QVBoxLayout, QWidget)

from .i18n import translate
from .ui_geometry import available_screen_geometry
from .window_motion import MotionDialog, menu_rect, widget_rect


TOURS = {
    '2.8.4': (
        ('Batch image actions',
         'Drag across rows in File List, then right-click. Mark or unmark the selection, or recycle the images and matching labels after confirming.'),
        ('Windows collapse back to their entry',
         'Collapse the Agent Task Window to its status-bar button. Annotation keeps running. Click the button to bring it back.'),
        ('Replay the guide or reduce motion',
         'Reopen this guide from Help. Under Settings, you can turn off interface animations or the automatic guide after updates.'),
    ),
}


def should_offer_tour(settings,version):
    seen=settings.get('seenReleaseTours',[])
    return version in TOURS and settings.get('showReleaseTours',True) and version not in seen


class TourDemo(QWidget):
    """Small vector mock-up with fictitious rows, not a screen automation."""
    def __init__(self,translate_text,motion):
        super().__init__()
        self.setMinimumHeight(150)
        self.tr_text=translate_text
        self.motion=motion
        self.page=0
        self.clock=QElapsedTimer()
        self.timer=QTimer(self,interval=32)
        self.timer.timeout.connect(self.update)

    def reset(self,page):
        self.page=page
        self.clock.restart()
        self.update()

    def showEvent(self,event):
        self.clock.start()
        self.setAnimated(self.motion())
        super().showEvent(event)

    def hideEvent(self,event):
        self.timer.stop()
        super().hideEvent(event)

    def setAnimated(self,enabled):
        if enabled and self.isVisible():
            self.timer.start()
        else:
            self.timer.stop()
        self.update()

    def paintEvent(self,event):
        style='#1b2330'
        panel='#2d3a50'
        text='#f4f7ff'
        accent='#68e6d1'
        painter=QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(),QColor(style))
        scale=min(self.width()/460,self.height()/156)
        painter.translate((self.width()-460*scale)/2,(self.height()-156*scale)/2)
        painter.scale(scale,scale)
        t=(self.clock.elapsed()%3400)/1000 if self.motion() and self.clock.isValid() else 2.4

        def box(x,y,w,h,color):
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRectF(x,y,w,h),6,6)

        def label(x,y,w,string,color=text):
            painter.setPen(QColor(color))
            painter.drawText(QRectF(x+8,y,w-16,24),
                             Qt.AlignVCenter | Qt.AlignLeft,self.tr_text(string))

        if self.page==0:
            box(12,10,150,137,panel)
            label(12,12,150,'File List')
            for i in range(3):
                y=43+30*i
                box(22,y,129,24,'#35666e' if t>i*0.32 else style)
                label(22,y,129,'sample_%02d.jpg' % (i+1))
            box(172,28,274,101,panel)
            label(179,34,254,'Mark selected images')
            label(179,63,254,'Unmark selected images')
            if t>1:
                box(178,92,262,25,'#35666e')
            label(179,92,254,'Recycle selected images',accent)
        elif self.page==1:
            box(12,11,436,134,panel)
            box(235,116,198,23,'#35666e')
            label(235,116,198,'Agent Task Window',accent)
            t=max(0.0,min(1.0,(t-0.65)/1.3))
            t=t*t*(3-2*t)
            x,y=22+215*t,20+96*t
            width,height=235-37*t,89-65*t
            if t<0.99:
                box(x,y,width,height,'#4c6588')
                label(x+3,y+2,width-3,'Agent annotation in progress')
                if height>47:
                    painter.setPen(QPen(QColor(accent),2,Qt.DashLine))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(QRectF(x+42,y+30,37,20))
        else:
            box(12,10,435,135,panel)
            for y,line in ((22,'New Features Guide'),(66,'Interface Animations'),
                           (105,'Show Guide After Updates')):
                box(23,y,414,28,'#35666e' if (t<1.1)==(y==22) else style)
                label(29,y+2,392,line,accent if y==22 else text)


class ReleaseTour(MotionDialog):
    def __init__(self,owner,version,tr):
        super().__init__(owner)
        self.tr_text=tr
        self.pages=TOURS[version]
        self.page=0
        self.setWindowTitle(tr('New Features Guide')+' · v'+version)
        self.motionAnchor=lambda:menu_rect(owner,owner.menus.help)
        area=available_screen_geometry(self)
        self.resize(min(620,area.width()-48),min(370,area.height()-48))
        self.heading=QLabel()
        font=self.heading.font()
        font.setPointSize(font.pointSize()+3)
        font.setBold(True)
        self.heading.setFont(font)
        self.heading.setWordWrap(True)
        self.description=QLabel()
        self.description.setWordWrap(True)
        self.counter=QLabel()
        self.demo=TourDemo(tr,owner.windowMotion.enabled)
        owner.windowMotion.enabledChanged.connect(self.demo.setAnimated)
        self.previous=QPushButton(tr('Previous'))
        self.previous.clicked.connect(lambda:self.setPage(self.page-1))
        self.forward=QPushButton()
        self.forward.clicked.connect(self.advance)
        self.skip=QPushButton(tr('Skip Guide'))
        self.skip.clicked.connect(self.reject)
        controls=QHBoxLayout()
        for widget in (self.counter,self.skip):
            controls.addWidget(widget)
        controls.addStretch()
        for widget in (self.previous,self.forward):
            controls.addWidget(widget)
        layout=QVBoxLayout(self)
        for widget in (self.heading,self.demo,self.description):
            layout.addWidget(widget,1 if widget is self.demo else 0)
        layout.addLayout(controls)
        self.halo=QFrame(owner)
        self.halo.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.halo.setStyleSheet('border: 2px solid #39bfa5; border-radius: 5px; background: transparent;')
        self.halo.hide()
        self.halo_timer=QTimer(self,interval=180)
        self.halo_timer.timeout.connect(self.updateHalo)
        self.destroyed.connect(self.halo.deleteLater)
        self.setPage(0)

    def setPage(self,page):
        self.page=max(0,min(page,len(self.pages)-1))
        heading,description=self.pages[self.page]
        self.heading.setText(self.tr_text(heading))
        self.description.setText(self.tr_text(description))
        self.counter.setText('%d/%d' % (self.page+1,len(self.pages)))
        self.previous.setEnabled(self.page>0)
        self.forward.setText(self.tr_text('Finish Guide' if self.page==len(self.pages)-1 else 'Next'))
        self.demo.reset(self.page)
        self.updateHalo()

    def updateHalo(self):
        owner=self.parentWidget()
        if not self.isVisible() or owner.isMinimized():
            self.halo.hide()
            return
        if self.page==0:
            rect=widget_rect(owner.fileListView)
        elif self.page==1:
            rect=widget_rect(owner.agentSession.monitor_button)
            if not rect.isValid():
                rect=menu_rect(owner,owner.menus.settings)
        else:
            rect=menu_rect(owner,owner.menus.help)
        if rect.isValid():
            self.halo.setGeometry(QRect(owner.mapFromGlobal(rect.topLeft()),rect.size()))
            self.halo.raise_()
            self.halo.show()
        else:
            self.halo.hide()

    def showEvent(self,event):
        super().showEvent(event)
        self.halo_timer.start()
        self.updateHalo()

    def hideEvent(self,event):
        self.halo_timer.stop()
        self.halo.hide()
        super().hideEvent(event)

    def advance(self):
        if self.page==len(self.pages)-1:
            self.accept()
        else:
            self.setPage(self.page+1)


class ReleaseTourController(QObject):
    def __init__(self,owner,settings,version):
        super().__init__(owner)
        self.owner,self.settings,self.version=owner,settings,version
        self.dialog=None
        self.timer=QTimer(self,interval=1500)
        self.timer.timeout.connect(self.maybeShow)
        if (should_offer_tour(settings,version)
                and QApplication.platformName() not in ('offscreen','minimal')):
            self.timer.start()

    def setAutomatic(self,enabled):
        self.settings['showReleaseTours']=bool(enabled)
        self.settings.save()
        if not enabled:
            self.timer.stop()

    def maybeShow(self):
        if not should_offer_tour(self.settings,self.version):
            self.timer.stop()
            return False
        w=self.owner
        if (not w.isVisible() or not w.isActiveWindow() or w.isMinimized() or w.dirty
                or w._labelEditorActive or w.canvas.current is not None
                or w.autoAnnotationThread is not None or w.playing or QApplication.mouseButtons()
                or QApplication.activeModalWidget() or QApplication.activePopupWidget()):
            return False
        self.show()
        return True

    def show(self):
        if self.dialog is not None and self.dialog.isVisible():
            self.dialog.raise_()
            self.dialog.activateWindow()
            return
        self.timer.stop()
        if not TOURS:
            return
        version=self.version if self.version in TOURS else next(reversed(TOURS))
        tr=lambda text:translate(text,self.owner.languageManager.language)
        self.dialog=ReleaseTour(self.owner,version,tr)
        self.dialog.setAttribute(Qt.WA_DeleteOnClose)
        self.dialog.finished.connect(self.finished)
        self.dialog.showAnimated()
        seen=list(self.settings.get('seenReleaseTours',[]))
        if version not in seen:
            seen.append(version)
            self.settings['seenReleaseTours']=seen
            self.settings.save()

    def finished(self,*_):
        self.dialog=None
