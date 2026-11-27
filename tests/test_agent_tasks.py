import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QImage
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
import labelImg
from libs.agent_tasks import AgentQueue, digest, project_image_name
from libs.pascal_voc_io import PascalVocReader
from libs.ui_geometry import screen_work_areas
from test_delete_image import MemorySettings


class ProjectImageNameTests(unittest.TestCase):
    def test_mixed_short_and_long_roots_preserve_relative_case_and_folders(self):
        absolute = os.path.abspath(os.sep)
        root = os.path.join(absolute,'Users','runneradmin','images')
        short = os.path.join(absolute,'Users','RUNNER~1','images','nested','Photo.JPG')
        normalized = os.path.join(root,'nested','Photo.JPG')
        with patch('libs.agent_tasks.os.path.realpath',
                   side_effect=lambda p:normalized if p==short else p):
            self.assertEqual('nested/Photo.JPG',project_image_name(short,root))

    def test_outside_image_never_gets_a_parent_relative_name(self):
        root = os.path.abspath('project/images')
        other = os.path.abspath('project/private/Photo.JPG')
        with self.assertRaisesRegex(ValueError,'relative to the project'):
            project_image_name(other,root)


class AgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root=Path(t.name)
        self.images=root/'images'
        self.labels=root/'labels'
        self.images.mkdir()
        self.labels.mkdir()
        for i in range(4):
            im=QImage(100,80,QImage.Format_RGB32)
            im.fill(Qt.white)
            self.assertTrue(im.save(str(self.images/('%d.png'%i))))
        preset=root/'class.txt'
        preset.write_text('apple\npipe_row\n',encoding='utf8')
        with patch.object(labelImg,'Settings',MemorySettings):
            self.w=labelImg.MainWindow(defaultPrefdefClassFile=str(preset))
        self.addCleanup(self.w.close)
        self.w.importDirImages(str(self.images),annotationDir=str(self.labels))
        self.w.annotationScanTimer.stop()
        self.w.annotationFormat='yolo_obb'
        self.s=self.w.agentSession
        self.db=str(root/'test.sqlite3')
        self.s.queue=AgentQueue(self.db,self.s.context())
        self.box=dict(class_id=1,cx=55,cy=40,w=30,h=10,angle_deg=30)

    def call(self,name,**args):
        return json.loads(self.s.dispatch(name,args)[0]['text'])

    def start(self,**kw):
        return self.call('start_task',instructions='Only pipes',classes=['pipe_row'],**kw)

    def preview(self, info, slot, box):
        return self.call('preview_box', box_id=slot, box=box,
                         **{k:info[k] for k in ('task_id','image_token','image_revision')})

    def test_live_overlay_paints_prior_to_submit_and_is_never_an_annotation(self):
        self.w.show()
        a=self.start(count=2)
        canvas=self.s.monitor.preview
        self.app.processEvents()
        before=canvas.grab().toImage()
        self.assertEqual(1,self.preview(a,1,self.box)['preview_count'])
        self.app.processEvents()
        self.assertNotEqual(before, canvas.grab().toImage())
        self.assertAlmostEqual(55.0,sum(x for x,y in canvas.boxes[1][1])/4)
        self.assertEqual(1,self.preview(a,1,dict(self.box,cx=40))['preview_count'])
        self.assertAlmostEqual(40.0,sum(x for x,y in canvas.boxes[1][1])/4)
        self.assertEqual(2,self.preview(a,2,dict(self.box,cx=70))['preview_count'])
        self.assertFalse(self.w.canvas.shapes)
        self.assertFalse(self.w.dirty)
        self.assertEqual('2.png',Path(self.w.filePath).name)
        self.assertFalse(list(self.labels.iterdir()))
        with self.assertRaises(ValueError):
            self.preview(a,2,dict(self.box,class_id=0))
        # Only the final supplied list may be written, not the two draft boxes.
        b=self.submit(a,'annotated',boxes=[self.box])
        self.assertEqual(1,len((self.labels/'0.txt').read_text().splitlines()))
        self.assertFalse(canvas.boxes)
        with self.assertRaises(ValueError):
            self.preview(a,1,self.box)
        self.preview(b,1,self.box)
        self.s.stop()
        self.assertFalse(canvas.boxes)
        self.assertFalse((self.labels/'1.txt').exists())

    def test_review_discards_overlay_and_late_preview_does_not_advance(self):
        a=self.start(count=2)
        self.preview(a,1,self.box)
        b=self.submit(a,'review',reason='ambiguous')
        self.assertFalse(self.s.monitor.preview.boxes)
        self.assertFalse((self.labels/'0.txt').exists())
        with self.assertRaises(ValueError):
            self.preview(a,2,self.box)
        self.assertEqual('2.png',Path(self.w.filePath).name)
        self.submit(b,'empty')
        with self.assertRaises(ValueError):
            self.preview(b,1,self.box)
        self.assertEqual(b'',(self.labels/'1.txt').read_bytes())

    def test_manual_switch_and_dirty_edit_do_not_interrupt_preview(self):
        a=self.start(count=2)
        self.preview(a,1,self.box)
        self.assertTrue(self.w.openNextImg())
        self.w.dirty=True
        self.assertEqual('3.png',Path(self.w.filePath).name)
        self.assertEqual(1,self.preview(a,1,self.box)['preview_count'])
        self.assertEqual('3.png',Path(self.w.filePath).name)
        self.w.dirty=False
        a=self.call('start_task',resume_task_id=a['task_id'])
        self.preview(a,1,self.box)
        self.call('start_task',resume_task_id=a['task_id'])
        self.assertFalse(self.s.monitor.preview.boxes)
        self.assertFalse(list(self.labels.iterdir()))

    def submit(self,info,outcome,**kw):
        return self.call('submit_and_next',outcome=outcome,
                         **{k:info[k] for k in ('task_id','image_token','image_revision')},**kw)

    def test_mouse_frame_selection_and_right_click_stages_all_rows(self):
        self.w.resize(1000,800)
        self.w.show()
        self.app.processEvents()
        view=self.w.fileListView
        first=view.visualRect(self.w.fileModel.index(1)).center()
        last=view.visualRect(self.w.fileModel.index(3)).center()
        QTest.mousePress(view.viewport(),Qt.LeftButton,Qt.NoModifier,first)
        QTest.mouseMove(view.viewport(),last)
        QTest.mouseRelease(view.viewport(),Qt.LeftButton,Qt.NoModifier,last)
        self.assertEqual([1,2,3],sorted(i.row() for i in self.w.filesm.selectedIndexes()))
        QTest.mousePress(view.viewport(),Qt.RightButton,Qt.NoModifier,last)
        self.assertEqual([1,2,3],sorted(i.row() for i in self.w.filesm.selectedIndexes()))
        def choose(*_):
            self.w.fileListContextMenu.actions()[-1].trigger()
        with patch.object(self.w.fileListContextMenu,'exec_',side_effect=choose):
            self.w.showFileListContextMenu(last)
        self.assertEqual(3,self.call('task_status')['staged_count'])
        self.assertEqual('0.png',Path(self.w.filePath).name)
        for row in (1,2,3):
            self.assertFalse(self.w.fileModel.index(row).flags() & Qt.ItemIsSelectable)
        self.assertFalse(self.w.openNextImg())
        a=self.start(use_staged=True)
        self.assertEqual('1.png',a['image'])
        self.s.monitor.hide()
        b=self.submit(a,'empty')
        self.assertFalse(self.s.monitor.isVisible())
        self.assertEqual('2.png',b['image'])
        self.s.stop_task()
        self.assertTrue(self.w.openNextImg())
        self.assertTrue((self.labels/'1.txt').exists())
        self.assertFalse((self.labels/'2.txt').exists())
        with self.assertRaises(ValueError):
            self.submit(b,'empty')

    def test_candidate_filters_no_locks_and_cannot_open_external_paths(self):
        (self.labels/'1.txt').write_bytes(b'')
        self.assertEqual(['0.png','2.png'],[r['image'] for r in self.call(
            'list_images',unlabeled_only=True,limit=2)['images']])
        with self.assertRaises(ValueError):
            self.call('inspect_image',image='../test.sqlite3')
        with self.assertRaises(ValueError):
            self.start(images=['0.png','../x.png'])
        self.assertFalse(self.s.has_reservations)
        self.assertTrue(self.w.fileModel.index(0).flags() & Qt.ItemIsSelectable)
        a=self.start(images=['2.png','2.png','1.png','3.png'])
        self.assertFalse(self.w.loadFile(str(self.images/'2.png')))
        self.assertEqual('0.png',Path(self.w.filePath).name)
        self.w.dirty=True
        b=self.submit(a,'annotated',boxes=[self.box])
        self.assertEqual('3.png',b['image'])
        self.assertTrue(self.w.dirty)
        self.w.dirty=False
        done=self.submit(b,'empty')
        self.assertEqual((3,1,1),(done['total'],done['skipped'],done['annotated']))
        self.assertTrue(self.w.fileModel.index(2).flags() & Qt.ItemIsSelectable)
        self.assertEqual(1,self.w.fileModel.annotationCount(self.w.fileModel.index(2)))

    @unittest.skipUnless(os.name=='nt','Windows short path aliases only')
    def test_windows_short_image_root_through_listing_task_and_review(self):
        import ctypes
        buffer=ctypes.create_unicode_buffer(32768)
        if not ctypes.windll.kernel32.GetShortPathNameW(str(self.images),buffer,len(buffer)):
            self.skipTest('Windows could not supply a short path for this test volume')
        short=buffer.value
        if os.path.normcase(short)==os.path.normcase(os.path.realpath(self.images)):
            self.skipTest('8.3 aliases are not enabled for this temporary directory')
        self.s.stop()
        self.w.importDirImages(short,annotationDir=str(self.labels))
        self.w.annotationScanTimer.stop()
        self.s.queue=AgentQueue(self.db,self.s.context())
        items=self.call('list_images')['images']
        self.assertEqual(['0.png','1.png','2.png','3.png'],[p['image'] for p in items])
        first=self.start(images=['2.png'])
        self.assertEqual('2.png',first['image'])
        done=self.submit(first,'review',reason='ambiguous')
        self.assertTrue(done['complete'])
        self.assertEqual([{'image':'2.png','reason':'ambiguous'}],done['review'])

    def test_one_dirty_manual_image_cannot_be_reserved(self):
        self.w.dirty=True
        try:
            with self.assertRaisesRegex(ValueError,'manual edit'):
                self.start(images=['0.png','2.png'])
            self.assertFalse(self.s.has_reservations)
            self.assertEqual('0.png',Path(self.w.filePath).name)
        finally:
            self.w.dirty=False

    def test_task_window_recovers_after_minimize_without_resetting_the_task(self):
        self.w.show()
        current=self.start(images=['2.png','3.png'])
        monitor=self.s.monitor
        self.preview(current,1,self.box)
        self.app.processEvents()
        monitor.resize(4484,519)
        monitor.move(3360,1413)
        monitor.showMinimized()
        self.app.processEvents()
        self.s.show_monitor()
        self.app.processEvents()
        self.assertTrue(monitor.isVisible())
        self.assertFalse(monitor.isMinimized())
        self.assertTrue(any(area.contains(monitor.frameGeometry()) for area in screen_work_areas()),
                        monitor.frameGeometry())
        self.assertEqual(1,len(monitor.preview.boxes))
        self.assertEqual(current['task_id'],self.s.active)
        self.assertTrue(self.w.fileModel.isAgentLocked(self.w.fileModel.index(2)))
        nxt=self.submit(current,'annotated',boxes=[self.box])
        self.assertEqual('3.png',nxt['image'])
        self.assertEqual('0.png',Path(self.w.filePath).name)

    def test_late_off_screen_move_recovers_without_reopening_window(self):
        self.w.show()
        current = self.start(images=['2.png', '3.png'])
        monitor = self.s.monitor
        self.preview(current, 1, self.box)
        QTest.qWait(180)  # Let the initial show/restore checks finish first.
        monitor.move(3606, 907)
        self.assertFalse(any(area.intersects(monitor.frameGeometry())
                             for area in screen_work_areas()))
        deadline = time.monotonic() + 1.5
        while not any(area.contains(monitor.frameGeometry()) for area in screen_work_areas()):
            self.assertLess(time.monotonic(), deadline, monitor.frameGeometry())
            QTest.qWait(30)
        self.assertEqual(current['task_id'], self.s.active)
        self.assertEqual(1, len(monitor.preview.boxes))
        monitor.collapseAnimated()
        self.assertFalse(monitor.isVisible())
        self.assertFalse(monitor._placement_timer.isActive())
        self.assertFalse(monitor._placement_watch.isActive())
        self.assertEqual(current['task_id'], self.s.active)

    def test_batch_skip_existing_mark_review_empty_and_retry(self):
        old=self.labels/'0.xml'
        old.write_bytes(b'<keep/>')
        first=self.start(all_remaining=True)
        self.assertEqual('1.png',first['image'])
        nxt=self.submit(first,'annotated',boxes=[self.box])
        path=self.labels/'1.txt'
        original=path.read_bytes()
        self.assertEqual(9,len(original.split()))
        self.assertEqual(b'1',original.split()[0])
        self.assertEqual(nxt,self.submit(first,'annotated',boxes=[self.box]))
        last=self.submit(nxt,'review',reason='occlusion')
        done=self.submit(last,'empty')
        self.assertTrue(done['complete'])
        self.assertEqual(done,self.submit(last,'empty'))
        self.assertEqual(1,done['skipped'])
        self.assertEqual('2.png',done['review'][0]['image'])
        self.assertTrue(self.w.fileModel.isFlagged(self.w.fileModel.index(2)))
        self.assertFalse((self.labels/'2.txt').exists())
        self.assertEqual(b'',(self.labels/'3.txt').read_bytes())
        self.assertEqual(b'<keep/>',old.read_bytes())
        self.assertEqual(original,path.read_bytes())

    def test_stop_resume_stale_rejections_and_existing_file_race(self):
        a=self.start(count=2)
        for box in (dict(self.box,class_id=0),dict(self.box,cx=-1),dict(self.box,w=0)):
            with self.assertRaises(ValueError):
                self.submit(a,'annotated',boxes=[box])
        self.s.stop()
        with self.assertRaises(ValueError):
            self.submit(a,'empty')
        self.s.queue=AgentQueue(self.db,self.s.context())
        self.assertEqual(a['task_id'],self.call('task_status')['task_id'])
        new_a=self.call('start_task',resume_task_id=a['task_id'])
        with self.assertRaises(ValueError):
            self.submit(a,'empty')
        path=self.labels/'0.txt'
        path.write_bytes(b'')
        with self.assertRaises(ValueError):
            self.submit(new_a,'empty')
        b=self.call('start_task',resume_task_id=a['task_id'])
        self.assertEqual('1.png',b['image'])
        original_stamp=b['image_revision']
        img=self.images/'1.png'
        os.utime(img,ns=(img.stat().st_atime_ns,img.stat().st_mtime_ns+2_000_000_000))
        with self.assertRaises(ValueError):
            self.submit(b,'empty')
        b2=self.call('start_task',resume_task_id=a['task_id'])
        self.assertNotEqual(original_stamp,b2['image_revision'])
        with self.assertRaises(ValueError):
            self.submit(b,'empty')
        self.assertTrue(self.submit(b2,'empty')['complete'])

    def test_xml_roundtrip_and_durable_write_recovery(self):
        self.s.stop()
        self.w.annotationFormat='xml'
        self.s.queue=AgentQueue(self.db,self.s.context())
        a=self.start(count=1)
        q=self.s.queue
        with patch.object(q,'finish',side_effect=OSError('simulated crash after atomic install')):
            with self.assertRaises(OSError):
                self.submit(a,'annotated',boxes=[self.box])
        path=self.labels/'0.xml'
        before=digest(path)
        self.s.stop()
        self.s.queue=AgentQueue(self.db,self.s.context())
        done=self.call('start_task',resume_task_id=a['task_id'])
        self.assertEqual(1,done['annotated'])
        self.assertEqual(before,digest(path))
        shape=PascalVocReader(str(path)).getShapes()[0]
        self.assertEqual('pipe_row',shape[0])
        self.assertAlmostEqual(0.5236,shape[6],places=4)

    def test_yolo_uses_original_pixel_dimensions_not_preview_and_stays_in_range(self):
        im=QImage(2048,1024,QImage.Format_RGB32)
        im.fill(Qt.white)
        self.assertTrue(im.save(str(self.images/'0.png')))
        self.s.stop()
        self.w.annotationFormat='yolo'
        self.s.queue=AgentQueue(self.db,self.s.context())
        a=self.start(count=1)
        self.assertEqual((2048,1024,1600,800),
                         tuple(a[k] for k in ('width','height','preview_width','preview_height')))
        with self.assertRaises(ValueError):
            self.submit(a,'annotated',boxes=[self.box])  # no rotated box in ordinary YOLO
        box=dict(class_id=1,cx=1024,cy=512,w=512,h=256)
        self.submit(a,'annotated',boxes=[box])
        self.assertEqual(['1','0.5','0.5','0.25','0.25'],
                         (self.labels/'0.txt').read_text().split())
        self.assertFalse((self.labels/'1.txt').exists())

    def test_output_root_and_project_class_table_locked(self):
        with patch.object(self.w,'annotationBasePathForImage',return_value=str(self.images/'unsafe')):
            with self.assertRaisesRegex(ValueError,'outside'):
                self.start(count=1)
        a=self.start(count=1)
        self.w.predefinedClasses=('pipe_row','apple')
        with self.assertRaisesRegex(ValueError,'changed'):
            self.submit(a,'empty')
        self.assertFalse(list(self.labels.iterdir()))

    def test_stdio_client_to_live_gui(self):
        self.s.stop()
        self.addCleanup(self.s.stop)
        # Keep both data and pipe separate from real user sessions.
        with patch.dict(os.environ,{'LOCALAPPDATA':os.path.dirname(self.db),
                                    'USERPROFILE':os.path.dirname(self.db)}):
            self.s.enable(self.s.context())
            exe=os.environ.get('LABELIMG2_TEST_MCP_EXE')
            cmd=[exe] if exe else [sys.executable,str(Path(labelImg.__file__).parent/'labelimg_mcp.py')]
            proc=subprocess.Popen(cmd,
                                  stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            errors=[]
            def client():
                counter=0
                def rpc(method,params):
                    nonlocal counter
                    counter+=1
                    request=dict(jsonrpc='2.0',id=counter,method=method,params=params)
                    proc.stdin.write((json.dumps(request)+'\n').encode())
                    proc.stdin.flush()
                    response=json.loads(proc.stdout.readline())
                    self.assertEqual(counter,response['id'])
                    result=response['result']
                    self.assertNotIn('isError',result,result)
                    return result
                def tool(name,**args):
                    return rpc('tools/call',{'name':name,'arguments':args})['content']
                try:
                    rpc('initialize',{'protocolVersion':'2025-11-25'})
                    proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
                    self.assertEqual({'start_task','task_status','submit_and_next','preview_box','list_images','inspect_image'},
                                     {t['name'] for t in rpc('tools/list',{})['tools']})
                    page=json.loads(tool('list_images',limit=2,unlabeled_only=True)[0]['text'])
                    names=[item['image'] for item in page['images']]
                    self.assertEqual('image',tool('inspect_image',image=names[0])[1]['type'])
                    blocks=tool('start_task',images=names,instructions='QA')
                    for idx in range(2):
                        self.assertEqual('image',blocks[1]['type'])
                        meta=json.loads(blocks[0]['text'])
                        self.assertEqual('%d.png'%idx,meta['image'])
                        ids={k:meta[k] for k in ('task_id','image_revision','image_token')}
                        ack=json.loads(tool('preview_box',**ids,box_id=1,box=self.box)[0]['text'])
                        self.assertEqual(1,ack['preview_count'])
                        self.assertFalse(ack['saved'])
                        blocks=tool('submit_and_next',**ids,outcome='annotated',boxes=[self.box])
                    self.assertTrue(json.loads(blocks[0]['text'])['complete'])
                    self.assertEqual(2,json.loads(tool('task_status')[0]['text'])['annotated'])
                except Exception as exc:
                    errors.append(exc)
                finally:
                    proc.stdin.close()
            worker=threading.Thread(target=client,daemon=True)
            worker.start()
            deadline=time.monotonic()+15
            while worker.is_alive() and time.monotonic()<deadline:
                self.app.processEvents()
                time.sleep(.005)
            if worker.is_alive():
                proc.kill()
                worker.join(4)
                self.fail('MCP roundtrip timed out')
            self.assertEqual(0,proc.wait(timeout=8))
            proc.stdout.close()
            proc.stderr.close()
            if errors:
                raise errors[0]
            self.assertEqual(2,len(list(self.labels.glob('*.txt'))))
