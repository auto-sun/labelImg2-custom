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
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication
import labelImg
from libs.agent_tasks import AgentQueue, digest
from libs.pascal_voc_io import PascalVocReader
from test_delete_image import MemorySettings


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

    def submit(self,info,outcome,**kw):
        return self.call('submit_and_next',outcome=outcome,
                         **{k:info[k] for k in ('task_id','image_token','image_revision')},**kw)

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
        self.w.dirty=True
        with self.assertRaises(ValueError):
            self.submit(a,'empty')
        self.w.dirty=False
        self.w.openNextImg()
        with self.assertRaises(ValueError):
            self.submit(a,'empty')
        self.s.stop()
        with self.assertRaises(ValueError):
            self.submit(a,'empty')
        self.s.queue=AgentQueue(self.db,self.s.context())
        self.assertEqual(a['task_id'],self.call('task_status')['task_id'])
        self.call('start_task',resume_task_id=a['task_id'])
        path=self.labels/'0.txt'
        path.write_bytes(b'')
        with self.assertRaises(ValueError):
            self.submit(a,'empty')
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
                    self.assertEqual(3,len(rpc('tools/list',{})['tools']))
                    blocks=tool('start_task',count=2,instructions='QA')
                    for idx in range(2):
                        self.assertEqual('image',blocks[1]['type'])
                        meta=json.loads(blocks[0]['text'])
                        self.assertEqual('%d.png'%idx,meta['image'])
                        ids={k:meta[k] for k in ('task_id','image_revision','image_token')}
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
