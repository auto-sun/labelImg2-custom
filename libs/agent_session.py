"""GUI-thread endpoint. The user grants access to one open project, never arbitrary paths."""
import base64
from collections import Counter
import json
import os
import sys
import uuid
from PyQt5.QtCore import (QBuffer, QIODevice, QItemSelectionModel, QLockFile,
                          QObject, Qt, QTimer)
from PyQt5.QtGui import QImageReader
from PyQt5.QtNetwork import QLocalServer
from PyQt5.QtWidgets import QAction, QApplication, QLabel, QMessageBox, QPushButton

from .agent_mcp import TOOLS, endpoint
from .agent_tasks import AgentQueue, box_geometry, canonical, exists_label, inside, stamp
from .agent_window import AgentTaskWindow
from .window_motion import menu_rect
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
        self.staged={}
        self.claimed=set()
        self.rendered_seq=0
        self.window_state='Waiting for a task'
        self.window_progress=''
        self.action=QAction('Agent access (MCP)',window)
        self.action.setCheckable(True)
        self.action.triggered.connect(self.toggle)
        config=QAction('Copy MCP configuration',window)
        config.triggered.connect(self.copy_config)
        window.menus.settings.addSeparator()
        window.menus.settings.addAction(self.action)
        window.menus.settings.addAction(config)
        self.monitor_action=QAction('Agent Task Window',window)
        self.monitor_action.triggered.connect(self.show_monitor)
        window.menus.settings.addAction(self.monitor_action)
        self.monitor=AgentTaskWindow(window,self.stop_task)
        self.monitor.setAttribute(Qt.WA_ShowWithoutActivating,True)
        self.monitor_button=QPushButton('Agent Task Window')
        self.monitor.motionAnchor=self.monitor_button
        self.monitor_button.clicked.connect(self.show_monitor)
        self.progress=QLabel()
        self.stop_button=QPushButton('Stop MCP')
        self.stop_button.clicked.connect(self.stop)
        for widget in (self.monitor_button,self.progress,self.stop_button):
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
        self.action.setChecked(True)
        self.progress.setText('MCP ✓')
        self.progress.show()
        self.stop_button.show()
        self.monitor_button.show()
        self.update_monitor('Waiting for a task')

    def stop(self):
        self.stop_task()
        self.monitor.hide()
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
        self.monitor_button.hide()

    def update_monitor(self,state=None,progress=None):
        if state:
            self.window_state=state
            self.window_progress=''
        if progress is not None:
            self.window_progress=progress
        progress=self.window_progress
        title=self.tr_ui('Agent Task Window')
        self.monitor.setWindowTitle(title)
        self.monitor.collapse.setText(self.tr_ui('Collapse'))
        self.monitor.stop.setText(self.tr_ui('Stop Agent Task'))
        self.monitor.stop.setEnabled(bool(self.active or self.staged))
        self.monitor.title.setText(self.tr_ui(self.window_state)+(' · '+progress if progress else ''))
        self.monitor_button.setText(title+(' · '+progress if progress else ''))

    def show_monitor(self):
        self.update_monitor()
        if not self.monitor.isVisible():
            # Capture the entry now; the QAction sender is no longer active
            # by the time a later click closes the task window.
            if self.sender() is self.monitor_action:
                self.monitor.motionAnchor=lambda:menu_rect(self.w,self.w.menus.settings)
            else:
                self.monitor.motionAnchor=self.monitor_button
        self.monitor.showAnimated()

    @property
    def has_reservations(self):
        return bool(self.staged or self.active)

    def sync_reservations(self, relocate=True):
        model=self.w.fileModel
        paths=self.claimed | set(self.staged)
        model.setAgentLockedPaths(paths,self.tr_ui('Reserved for agent task'))
        if not relocate or not model.isAgentLockedPath(self.w.filePath):
            return
        row=self.w.currentImageFileModelIndex().row()
        next_index=self.w.availableFileIndex(max(row,0),1)
        if not next_index.isValid():
            next_index=self.w.availableFileIndex(row,-1)
        with self.w.restoringFileRow():
            self.w.filesm.clear()
            self.w.filesm.setCurrentIndex(next_index,QItemSelectionModel.ClearAndSelect)
        if next_index.isValid():
            self.w.loadFile(model.data(next_index,Qt.EditRole))
            self.w.centerFileListIndex(next_index)
            self.w.statFile.setText('%d/%d' % (next_index.row()+1,model.rowCount()))
        else:
            self.w.resetState()
            self.w.canvas.setEnabled(False)
            self.w.toggleActions(False)
            self.w.statFile.clear()

    def stop_task(self):
        if self.active and self.queue:
            self.update_task_rows(None)
        had_work=self.has_reservations
        self.active=self.issued=None
        self.claimed.clear()
        self.staged.clear()
        self.monitor.preview.setImage()
        self.sync_reservations(relocate=False)
        if had_work:
            self.update_monitor('Task stopped; images released')
            self.progress.setText('MCP ✓')

    def stage_selection(self, paths):
        try:
            if self.w.autoAnnotationThread is not None or self.active:
                raise ValueError(self.tr_ui('Finish the running task before adding another batch.'))
            if not self.queue:
                self.toggle(True)
            if not self.queue:
                return
            entries=self.entries(paths)
            available=[(path,base) for path,base in entries if not exists_label(base)]
            self.check_reservation(path for path,_ in available)
            self.staged.update(available)
            self.monitor.setFiles(self.relative(path) for path in self.staged)
            self.sync_reservations()
            self.update_monitor('Waiting for the agent',str(len(self.staged)))
            self.show_monitor()
            if not available:
                self.w.status(self.tr_ui('No unlabeled images to add.'))
        except (ValueError,OSError) as exc:
            QMessageBox.warning(self.w,self.tr_ui('Agent Task Window'),str(exc))

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
            if self.busy:
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

    def relative(self,path):
        return os.path.relpath(path,self.queue.ctx['images']).replace(os.sep,'/')

    def catalog(self):
        return {self.relative(p):p for p in self.w.fileModel.stringList()}

    def candidate(self,name,catalog):
        path=catalog.get(name.replace('\\','/'))
        if not path:
            raise ValueError('Use an exact project-relative image path from list_images')
        return inside(path,self.queue.ctx['images'])

    def entries(self,paths):
        # Check the image and label root, and refuse filenames that share a
        # label destination. Keep selection order and remove exact duplicates.
        all_paths=self.w.fileModel.stringList()
        known=set(all_paths)
        stems=Counter(os.path.normcase(os.path.splitext(p)[0]) for p in all_paths)
        seen_images,seen_bases=set(),set()
        result=[]
        for path in dict.fromkeys(paths):
            if path not in known:
                raise ValueError('The selected image is no longer in the project')
            image=canonical(inside(path,self.queue.ctx['images']))
            base=inside(self.w.annotationBasePathForImage(path),self.queue.ctx['labels'])
            key=canonical(base)
            if stems[os.path.normcase(os.path.splitext(path)[0])]>1 or key in seen_bases or image in seen_images:
                raise ValueError('Ambiguous image or label destination: '+self.relative(path))
            seen_images.add(image)
            seen_bases.add(key)
            result.append((path,base))
        return result

    def check_reservation(self, paths):
        w=self.w
        if w.autoAnnotationThread is not None:
            raise ValueError('Finish the local model job before starting an agent task')
        if w.filePath and any(w.fileModel._pathKey(p)==w.fileModel._pathKey(w.filePath) for p in paths):
            if (w.dirty or w._labelEditorActive or w.canvas.current is not None or
                    w.playing or QApplication.mouseButtons() & Qt.LeftButton or QApplication.activeModalWidget()):
                raise ValueError('Finish and save the manual edit of the image you want to reserve')

    def list_images(self,args):
        folder=args.get('folder','').replace('\\','/').rstrip('/')
        if (folder.startswith('/') or ':' in folder or
                any(p in ('.','..','') for p in folder.split('/') if folder)):
            raise ValueError('Use a project-relative folder')
        match=args.get('contains','').casefold()
        paths=list(self.staged) if args.get('staged_only') else self.w.fileModel.stringList()
        offset=args.get('offset',0)
        limit=args.get('limit',100)
        if not 0<=offset or not 1<=limit<=200:
            raise ValueError('Invalid offset or limit (1..200)')
        items=[]
        cursor=min(offset,len(paths))
        end=min(cursor+600,len(paths))
        while cursor<end and len(items)<limit:
            path=paths[cursor]
            cursor+=1
            name=self.relative(path)
            if folder and not name.casefold().startswith(folder.casefold()+'/'):
                continue
            if match and match not in os.path.basename(name).casefold():
                continue
            try:
                inside(path,self.queue.ctx['images'])
                base=inside(self.w.annotationBasePathForImage(path),self.queue.ctx['labels'])
            except (ValueError,OSError):
                continue
            annotated=exists_label(base)
            if annotated and args.get('unlabeled_only'):
                continue
            items.append(dict(image=name,has_label=annotated,reserved=self.w.fileModel.isAgentLockedPath(path),
                              staged=path in self.staged))
        return self.content(dict(images=items,next_offset=cursor if cursor<len(paths) else None))

    def initiate(self,args):
        q=self.queue
        resume=args.get('resume_task_id')
        if 'resume_task_id' in args:
            if not resume or len(args)!=1:
                raise ValueError('Resume with resume_task_id alone')
            if self.active and self.active!=resume:
                raise ValueError('A different task is running')
            if self.staged:
                raise ValueError('Start or clear the staged selection before resuming a saved task')
            q.job(resume)
            frames=list(q.frames(resume))
            self.entries([r['image'] for r in frames if r['state'] in ('pending','writing')])
            for r in frames:
                if (r['state'] in ('pending','writing') and
                        canonical(self.w.annotationBasePathForImage(r['image']))!=canonical(r['base'])):
                    raise ValueError('Label destination changed; restore the original project before resuming')
            claimed=set(self.claimed) if self.active else {
                r['image'] for r in frames if r['state'] in ('pending','writing') and not exists_label(r['base'])}
            self.check_reservation(claimed)
            self.active=resume
        else:
            if self.active:
                raise ValueError('A task is running. Use task_status or resume_task_id for that task')
            modes=set(args) & {'count','all_remaining','images','use_staged'}
            if len(modes)!=1:
                raise ValueError('Specify one of images, use_staged, count, or all_remaining')
            staged=args.get('use_staged') is True
            if self.staged and not staged:
                raise ValueError('Start or clear the staged selection first (use_staged:true)')
            if staged:
                paths=list(self.staged)
            elif 'images' in modes:
                names=args['images']
                if not 1<=len(names)<=10000 or any(not isinstance(p,str) for p in names):
                    raise ValueError('Supply 1..10000 project-relative image paths')
                catalog=self.catalog()
                paths=[self.candidate(p,catalog) for p in names]
            else:
                paths=self.w.fileModel.stringList()
                if self.w.filePath not in paths:
                    raise ValueError('Select the first image or supply an explicit list of images')
                first=paths.index(self.w.filePath)
                count=args.get('count')
                if count is not None and count<1 or 'all_remaining' in modes and args['all_remaining'] is not True:
                    raise ValueError('Supply a positive count or all_remaining:true')
                paths=paths[first:first+count if count is not None else None]
            entries=self.entries(paths)
            claimed={path for path,base in entries if not exists_label(base)}
            self.check_reservation(claimed)
            self.active=q.create(entries,args.get('instructions'),args.get('classes',q.ctx['classes']))
            frames=list(q.frames(self.active))
            self.staged.clear()
        self.claimed=claimed
        self.issued=None
        self.rendered_seq=0
        self.monitor.setFiles(self.relative(r['image']) for r in frames)
        self.sync_reservations()
        self.update_monitor('Agent annotation in progress')
        if not resume and not self.monitor.isVisible():
            self.monitor.motionAnchor=self.monitor_button
            self.monitor.show()
        return self.deliver()

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
            info.update(classes=q.ctx['classes'],format=q.ctx['format'],active=bool(job and job==self.active),
                        staged_count=len(self.staged))
            return self.content(info)
        if name=='list_images':
            return self.list_images(args)
        if name=='inspect_image':
            path=self.candidate(args['image'],self.catalog())
            image,encoded,(w,h),_=self.read_image(path)
            return self.content(dict(image=self.relative(path),width=w,height=h,
                                     preview_width=image.width(),preview_height=image.height()),encoded)
        if name=='start_task':
            return self.initiate(args)
        job=args['task_id']
        preview = name == 'preview_box'
        if not preview and job and not self.active:
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
        if (not self.issued or self.issued[:3]!=(job,token,args['image_revision'])
                or self.issued[3]!=r['stamp'] or self.row_for(r['image'])<0 or
                canonical(self.w.annotationBasePathForImage(r['image']))!=canonical(r['base'])):
            raise ValueError('Image, label destination or revision changed; resume task to obtain the image again')
        if preview:
            slot = args['box_id']
            if not 1 <= slot <= 2000:
                raise ValueError('box_id must be 1..2000')
            if (r['state'] != 'pending' or stamp(inside(r['image'],q.ctx['images'])) != r['stamp']
                    or exists_label(r['base'])):
                raise ValueError('Image or label changed; resume the task')
            label, points, _ = box_geometry(args['box'], r['w'], r['h'], q.ctx['classes'],
                                            json.loads(q.job(job)['allowed']), q.ctx['format'])
            count = self.monitor.preview.showBox(slot,label,points)
            return self.content(dict(box_id=slot, preview_count=count, saved=False))
        boxes=args.get('boxes',[])
        q.submit(job,token,args['outcome'],boxes,args.get('reason',''))
        self.monitor.preview.clearBoxes()
        self.issued=None
        row=self.row_for(r['image'])
        if args['outcome']=='review':
            self.mark_review(row)
        else:
            self.w.fileModel.updateAnnotationCount(row,r['image'],len(boxes))
            self.w.updateLabelStatistics()
        return self.deliver()

    def mark_review(self,row):
        if row>=0:
            w=self.w
            w.fileModel.setFlagged(w.fileModel.index(row),True)
            w.settings[SETTING_FLAGGED_IMAGES]=w.fileModel.flaggedPaths()
            w.settings.save()

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

    def update_task_rows(self, active_seq):
        end=active_seq if active_seq is not None else 2147483647
        rows=list(self.queue.frames(self.active,self.rendered_seq,end))
        self.monitor.updateRows(rows,active_seq,self.tr_ui)
        self.rendered_seq=end

    def read_image(self,path):
        path=inside(path,self.queue.ctx['images'])
        signature=stamp(path)
        reader=QImageReader(path)
        reader.setAutoTransform(True)
        image=reader.read()
        if image.isNull():
            raise ValueError('Unreadable candidate image')
        size=image.width(),image.height()
        if max(size)>1600:
            image=image.scaled(1600,1600,Qt.KeepAspectRatio,Qt.SmoothTransformation)
        buffer=QBuffer()
        buffer.open(QIODevice.WriteOnly)
        if not image.save(buffer,'JPEG',88) or signature!=stamp(path):
            raise ValueError('Image changed or preview encoding failed; try again')
        return image,base64.b64encode(bytes(buffer.data())).decode('ascii'),size,signature

    def deliver(self):
        q=self.queue
        job=self.active
        r=q.next(job)
        summary=q.summary(job,details=False)
        progress='%d/%d' % (summary['total']-summary['remaining'],summary['total'])
        self.progress.setText('MCP: '+progress)
        self.update_monitor('Agent annotation in progress',progress)
        if r is None:
            if summary['remaining']:
                summary['continuation_required']=True
            else:
                summary['complete']=True
                self.update_task_rows(None)
                self.active=self.issued=None
                self.claimed.clear()
                self.monitor.preview.setImage()
                self.sync_reservations(relocate=False)
                self.update_monitor('Agent task completed',progress)
            return self.content(summary)
        path=r['image']
        row=self.row_for(path)
        if row<0 or canonical(self.w.annotationBasePathForImage(path))!=canonical(r['base']):
            raise ValueError('Image list or label destination changed. Restore the project before resuming.')
        if not self.w.fileModel.isAgentLockedPath(path):
            # A previously labeled image might have lost its sidecar after the
            # task began. Recheck it before allowing the agent to own it.
            self.check_reservation([path])
            self.claimed.add(path)
            self.sync_reservations()
        try:
            image,encoded,(width,height),signature=self.read_image(path)
        except ValueError as exc:
            if str(exc)!='Unreadable candidate image':
                raise
            q.finish(r,'review','unreadable image')
            self.mark_review(row)
            return self.content(dict(task_id=job,continuation_required=True))
        same_image=(self.issued and self.issued[:2]==(job,r['token']) and self.issued[3]==signature)
        revision=self.issued[2] if same_image else uuid.uuid4().hex
        if not same_image:
            self.monitor.preview.setImage(image,(width,height))
        self.update_task_rows(r['seq'])
        q.issue(r,width,height,signature)
        self.issued=(job,r['token'],revision,signature)
        task=q.job(job)
        info=dict(task_id=job,image_token=r['token'],image_revision=revision,
                  image=self.relative(path),width=width,height=height,
                  preview_width=image.width(),preview_height=image.height(),
                  coordinates='original oriented pixels, x right, y down, clockwise degrees',
                  live_preview='Call preview_box for each detected target immediately, then submit_and_next with all final boxes.',
                  format=q.ctx['format'],classes=q.ctx['classes'],allowed=json.loads(task['allowed']),
                  instructions=task['rules'],remaining=summary['remaining'])
        return self.content(info,encoded)
