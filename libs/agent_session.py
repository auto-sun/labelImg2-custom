"""GUI-thread endpoint. The user grants access to one open project, never arbitrary paths."""
import base64
from collections import Counter
import json
import os
import sys
from PyQt5.QtCore import (QBuffer, QIODevice, QItemSelectionModel, QLockFile,
                          QObject, Qt, QTimer)
from PyQt5.QtGui import QImageReader
from PyQt5.QtNetwork import QLocalServer
from PyQt5.QtWidgets import QAction, QApplication, QLabel, QMessageBox, QPushButton

from .agent_mcp import TOOLS, endpoint
from .agent_tasks import AgentQueue, box_geometry, canonical, exists_label, inside, stamp
from .constants import SETTING_FLAGGED_IMAGES
from .i18n import translate


class AgentSession(QObject):
    def __init__(self,window):
        super().__init__(window)
        self.w=window
        self.server=QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.UserAccessOption)
        self.server.newConnection.connect(self.accept)
        self.queue=None
        self.active=None
        self.issued=None
        self.busy=False
        self.clients=set()
        self.lock=None
        self.rows={}
        self.action=QAction('Agent access (MCP)',window)
        self.action.setCheckable(True)
        self.action.triggered.connect(self.toggle)
        config=QAction('Copy MCP configuration',window)
        config.triggered.connect(self.copy_config)
        window.menus.settings.addSeparator()
        window.menus.settings.addAction(self.action)
        window.menus.settings.addAction(config)
        self.progress=QLabel()
        self.stop_button=QPushButton('Stop MCP')
        self.stop_button.clicked.connect(self.stop)
        for widget in (self.progress,self.stop_button):
            window.statusBar().addPermanentWidget(widget)
            widget.hide()

    def tr_ui(self,text):
        return translate(text,self.w.languageManager.language)

    def copy_config(self):
        if getattr(sys,'frozen',False):
            command=os.path.join(os.path.dirname(sys.executable),'LabelImg2MCP.exe')
            args=[]
        else:
            command=os.path.join(os.path.dirname(sys.executable),'python.exe') if os.name=='nt' else sys.executable
            args=[os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'labelimg_mcp.py')]
        config={'mcpServers':{'labelimg2':{'command':command,'args':args}}}
        QApplication.clipboard().setText(json.dumps(config,ensure_ascii=False,indent=2))
        self.w.status(self.tr_ui('MCP configuration copied'))

    def context(self):
        w=self.w
        if not w.dirname or not w.defaultSaveDir or not w.predefinedClasses:
            raise ValueError('Open an image folder, annotation folder and class preset first.')
        classes=list(w.predefinedClasses)
        if len(set(classes))!=len(classes):
            raise ValueError('Ambiguous duplicate entries in the class preset')
        preset=w.classFilePath or ''
        return dict(images=canonical(w.dirname),labels=canonical(w.defaultSaveDir),
                    classes=classes,format=w.annotationFormat,preset=preset,
                    preset_revision=stamp(preset) if os.path.isfile(preset) else None)

    def toggle(self,on):
        if not on:
            self.stop()
            return
        try:
            ctx=self.context()
            prompt=self.tr_ui('Allow the connected agent to read images and save new labels in this project? Images may be sent to its model provider.')
            if QMessageBox.question(self.w,'MCP',prompt+'\n\n'+ctx['images']+'\n'+ctx['labels'],
                                    QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:
                self.stop()
                return
            self.enable(ctx)
        except Exception as exc:
            self.stop()
            QMessageBox.warning(self.w,'MCP',str(exc))

    def enable(self,ctx):
        root=os.environ.get('LOCALAPPDATA') or os.path.expanduser('~/.local/share')
        folder=os.path.join(root,'LabelImg2Custom','agent')
        os.makedirs(folder,exist_ok=True)
        self.lock=QLockFile(os.path.join(folder,'agent.lock'))
        self.lock.setStaleLockTime(0)
        if not self.lock.tryLock(0):
            raise ValueError('Another LabelImg2 window is already sharing a project.')
        if not self.server.listen(endpoint()):
            self.lock.unlock()
            raise ValueError('Unable to open the local MCP endpoint.')
        self.queue=AgentQueue(os.path.join(folder,'tasks.sqlite3'),ctx)
        self.progress.setText('MCP ✓')
        self.progress.show()
        self.stop_button.show()

    def stop(self):
        self.w.canvas.clearAgentPreview()
        self.server.close()
        for sock in list(self.clients):
            sock.abort()
        if self.queue:
            self.queue.db.close()
        if self.lock and self.lock.isLocked():
            self.lock.unlock()
        self.lock=None
        self.queue=self.active=self.issued=None
        self.rows={}
        self.action.setChecked(False)
        self.progress.hide()
        self.stop_button.hide()

    def accept(self):
        while self.server.hasPendingConnections():
            sock=self.server.nextPendingConnection()
            self.clients.add(sock)
            sock.setReadBufferSize(1024*1024+1)
            timer=QTimer(sock)
            timer.setSingleShot(True)
            timer.timeout.connect(sock.abort)
            timer.start(65000)
            sock.disconnected.connect(lambda s=sock: self.clients.discard(s))
            sock.disconnected.connect(sock.deleteLater)
            sock.readyRead.connect(lambda s=sock:self.read_request(s))
            self.read_request(sock)

    def read_request(self,sock):
        if sock.bytesAvailable()>1024*1024:
            sock.abort()
            return
        if not sock.canReadLine() or sock.property('used'):
            return
        sock.setProperty('used',True)
        try:
            name,args=json.loads(bytes(sock.readLine()))
            if self.busy or QApplication.activeModalWidget():
                raise ValueError('LabelImg2 is busy; finish the open dialog and retry')
            self.busy=True
            try:
                answer={'content':self.dispatch(name,args)}
            finally:
                self.busy=False
        except Exception as exc:
            answer={'error':str(exc)}
        if sock in self.clients:
            sock.write(json.dumps(answer,ensure_ascii=True).encode()+b'\n')
            sock.disconnectFromServer()

    def row_for(self,path):
        model=self.w.fileModel
        row=self.rows.get(path,-1)
        if row<0 or model.index(row).data(Qt.EditRole)!=path:
            self.rows={p:i for i,p in enumerate(model.stringList())}
            row=self.rows.get(path,-1)
        return row

    def check_ui(self):
        w=self.w
        if (w.dirty or w._labelEditorActive or w.canvas.current is not None or
                w.playing or w.autoAnnotationThread is not None):
            raise ValueError('Save/finish the manual edit, playback or model job before continuing')

    def dispatch(self,name,args):
        if name not in TOOLS or not isinstance(args,dict):
            raise ValueError('Unsupported MCP request')
        q=self.queue
        if not q or self.context()!=q.ctx:
            raise ValueError('Project, class preset or output format changed. Re-enable MCP for this project.')
        self.check_args(name,args)
        if name=='task_status':
            job=args.get('task_id') or self.active or q.latest()
            info=q.summary(job) if job else {}
            info.update(classes=q.ctx['classes'],format=q.ctx['format'],active=bool(job and job==self.active))
            return self.content(info)
        self.check_ui()
        if name=='start_task':
            resume=args.get('resume_task_id')
            if resume:
                if len(args)!=1:
                    raise ValueError('Resume with resume_task_id alone')
                q.job(resume)
                if self.active and resume!=self.active:
                    raise ValueError('A different task is active')
                self.active=resume
            else:
                if self.active:
                    raise ValueError('Use task_status and resume_task_id for the active task')
                paths=self.w.fileModel.stringList()
                if self.w.filePath not in paths:
                    raise ValueError('Select the first image of the requested range')
                n=args.get('count')
                if ((type(n) is not int or n<1 or args.get('all_remaining')) if n is not None
                        else args.get('all_remaining') is not True):
                    raise ValueError('Specify count OR all_remaining:true')
                begin=paths.index(self.w.filePath)
                subset=paths[begin:begin+n if n is not None else None]
                # Never assign a shared label basename to two distinct source images.
                stems=Counter(os.path.normcase(os.path.splitext(p)[0]) for p in paths)
                entries=[]
                destinations=set()
                for p in subset:
                    base=self.w.annotationBasePathForImage(p)
                    key=canonical(base)
                    if stems[os.path.normcase(os.path.splitext(p)[0])]>1 or key in destinations:
                        raise ValueError('Ambiguous label destination: '+os.path.basename(p))
                    destinations.add(key)
                    entries.append((p,base))
                self.active=q.create(entries,args.get('instructions'),args.get('classes',q.ctx['classes']))
            self.w.canvas.clearAgentPreview()
            return self.deliver()
        job=args.get('task_id')
        preview = name == 'preview_box'
        if not preview and job and not self.active and job==q.latest():
            last=q.summary(job)
            if not last['remaining'] and q.db.execute('SELECT 1 FROM frame WHERE job=? AND token=?',
                    (job,args['image_token'])).fetchone():
                return self.content(dict(last,complete=True))
        if self.active!=job or not job:
            raise ValueError('Task is inactive. Check task_status and explicitly resume.')
        token=args['image_token']
        r=q.db.execute('SELECT * FROM frame WHERE job=? AND token=?',(job,token)).fetchone()
        if not r:
            raise ValueError('Wrong image token')
        if r['state'] not in ('pending','writing'):
            if preview:
                raise ValueError('This image has already been processed')
            return self.deliver()  # duplicate after a lost response
        w=self.w
        if (self.issued!=(job,token,args['image_revision']) or r['image']!=w.filePath or
                r['stamp']!=args['image_revision'] or self.row_for(r['image'])<0 or
                canonical(w.annotationBasePathForImage(r['image']))!=canonical(r['base'])):
            raise ValueError('Image, label destination or revision changed; resume task to obtain the image again')
        if preview:
            slot = args['box_id']
            if not 1 <= slot <= 2000:
                raise ValueError('box_id must be 1..2000')
            if (r['state'] != 'pending' or stamp(inside(r['image'], q.ctx['images'])) != r['stamp']
                    or exists_label(r['base'])):
                raise ValueError('Image or label changed; resume the task')
            label, points, _ = box_geometry(args['box'], r['w'], r['h'], q.ctx['classes'],
                                            json.loads(q.job(job)['allowed']), q.ctx['format'])
            count = w.canvas.showAgentPreviewBox(slot, label, points)
            return self.content(dict(box_id=slot, preview_count=count, saved=False))
        boxes=args.get('boxes',[])
        q.submit(job,token,args['outcome'],boxes,args.get('reason',''))
        w.canvas.clearAgentPreview()
        self.issued=None
        row=self.row_for(r['image'])
        if args['outcome']=='review':
            w.fileModel.setFlagged(w.fileModel.index(row),True)
            w.settings[SETTING_FLAGGED_IMAGES]=w.fileModel.flaggedPaths()
            w.settings.save()
        else:
            w.fileModel.updateAnnotationCount(row,r['image'],len(boxes))
            w.loadFile(r['image'])
        return self.deliver()

    @staticmethod
    def check_args(name,args):
        schema=TOOLS[name][1]
        if set(args)-schema['properties'].keys() or set(schema['required'])-args.keys():
            raise ValueError('Unknown or missing arguments')
        types={'string':str,'array':list,'integer':int,'boolean':bool,'object':dict}
        for key,value in args.items():
            definition=schema['properties'][key]
            if 'type' in definition and type(value) is not types[definition['type']]:
                raise ValueError('Invalid type for '+key)

    @staticmethod
    def content(info,image=None):
        blocks=[dict(type='text',text=json.dumps(info,ensure_ascii=False))]
        if image is not None:
            blocks.append(dict(type='image',mimeType='image/jpeg',data=image))
        return blocks

    def deliver(self):
        q=self.queue
        job=self.active
        r=q.next(job)
        summary=q.summary(job,details=False)
        self.progress.setText('MCP: %d/%d' % (summary['total']-summary['remaining'],summary['total']))
        if r is None:
            if summary['remaining']:
                summary['continuation_required']=True
            else:
                summary['complete']=True
                self.active=self.issued=None
            return self.content(summary)
        path=r['image']
        row=self.row_for(path)
        if row<0 or canonical(self.w.annotationBasePathForImage(path))!=canonical(r['base']):
            raise ValueError('Image list or label destination changed. Restore the project before resuming.')
        signature=stamp(path)
        reader=QImageReader(path)
        reader.setAutoTransform(True)
        image=reader.read()
        if image.isNull():
            q.finish(r,'review','unreadable image')
            self.w.fileModel.setFlagged(self.w.fileModel.index(row),True)
            self.w.settings[SETTING_FLAGGED_IMAGES]=self.w.fileModel.flaggedPaths()
            self.w.settings.save()
            return self.content(dict(task_id=job,continuation_required=True))
        w=self.w
        if path!=w.filePath or self.issued is None or signature!=r['stamp']:
            index=w.fileModel.index(row)
            with w.restoringFileRow():
                w.filesm.setCurrentIndex(index,QItemSelectionModel.ClearAndSelect)
            if not w.loadFile(path):
                raise ValueError('Unable to display image')
            w.centerFileListIndex(index)
            w.statFile.setText('%d/%d' % (row+1,w.fileModel.rowCount()))
        width,height=image.width(),image.height()
        if max(width,height)>1600:
            image=image.scaled(1600,1600,Qt.KeepAspectRatio,Qt.SmoothTransformation)
        buffer=QBuffer()
        buffer.open(QIODevice.WriteOnly)
        if not image.save(buffer,'JPEG',88) or signature!=stamp(path):
            raise ValueError('Image changed or preview encoding failed; resume task')
        q.issue(r,width,height,signature)
        self.issued=(job,r['token'],signature)
        task=q.job(job)
        info=dict(task_id=job,image_token=r['token'],image_revision=signature,
                  image=os.path.relpath(path,q.ctx['images']),width=width,height=height,
                  preview_width=image.width(),preview_height=image.height(),
                  coordinates='original oriented pixels, x right, y down, clockwise degrees',
                  live_preview='Call preview_box for each detected target immediately, then submit_and_next with all final boxes.',
                  format=q.ctx['format'],classes=q.ctx['classes'],allowed=json.loads(task['allowed']),
                  instructions=task['rules'],remaining=summary['remaining'])
        return self.content(info,base64.b64encode(bytes(buffer.data())).decode('ascii'))
