"""Durable, skip-existing annotation jobs. No GUI or transport dependencies."""
import hashlib
import json
import math
import os
import sqlite3
import tempfile
import uuid
from collections import Counter

from .pascal_voc_io import PascalVocWriter
from .yolo_obb_io import save_yolo_annotations


def canonical(path):
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def inside(path, root):
    if os.path.commonpath([canonical(path), canonical(root)]) != canonical(root):
        raise ValueError('Path outside the authorized project')
    return path


def project_image_name(path, root):
    """Return an MCP image name, handling Windows path aliases without I/O in the common case.

    Keep the project's displayed subdirectory names when both paths use
    the same spelling. If they do not (e.g. RUNNER~1 vs runneradmin),
    resolve both before attempting to compute the relative name again.
    This is for display/lookup; callers still use inside() for file access.
    """
    def relative(candidate, start):
        try:
            name = os.path.relpath(candidate, start)
        except ValueError:
            return None
        if name in (os.curdir, os.pardir) or name.startswith(os.pardir + os.sep):
            return None
        return name

    name = relative(path, root)
    if name is None:
        name = relative(os.path.realpath(path), os.path.realpath(root))
    if name is None:
        raise ValueError('Image is not relative to the project')
    return name.replace(os.sep, '/')


def stamp(path):
    stat = os.stat(path)
    return '%s:%s:%s' % (stat.st_ino, stat.st_size, stat.st_mtime_ns)


def digest(path):
    with open(path, 'rb') as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def exists_label(base):
    return any(os.path.lexists(base + ext) for ext in ('.xml', '.txt'))


def box_geometry(box, width, height, classes, allowed, fmt):
    """Validate one box for both the live overlay and the output writer."""
    if not isinstance(box, dict) or set(box) - {'class_id','cx','cy','w','h','angle_deg'}:
        raise ValueError('Invalid box fields')
    cid = box.get('class_id')
    if type(cid) is not int or not 0 <= cid < len(classes) or classes[cid] not in allowed:
        raise ValueError('class_id outside task class list')
    values = [box.get(k) for k in ('cx','cy','w','h')] + [box.get('angle_deg', 0)]
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError('Box geometry must contain finite numbers')
    cx, cy, w, h, degrees = values
    if min(w, h) <= 0 or (fmt == 'yolo' and degrees != 0):
        raise ValueError('Invalid size or rotated box in horizontal YOLO format')
    angle = math.radians(degrees % 360)
    c, s = math.cos(angle), math.sin(angle)
    points = [(cx+c*x-s*y, cy+s*x+c*y) for x,y in
              ((-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2))]
    if any(not (-1e-7 <= x <= width+1e-7 and -1e-7 <= y <= height+1e-7)
           for x,y in points):
        raise ValueError('Box exceeds image bounds; correct it before resubmitting')
    label = classes[cid]
    if fmt == 'xml' and not angle:
        x0, y0 = map(round, points[0])
        x1, y1 = map(round, points[2])
        if x1 <= x0 or y1 <= y0:
            raise ValueError('Box is too small for integer XML bounds')
    return label, points, angle


def write_boxes(path, image, width, height, classes, allowed, fmt, boxes):
    """Coordinates are original, display-oriented pixels; clockwise degrees."""
    writer = PascalVocWriter(os.path.basename(os.path.dirname(image)),
                             os.path.basename(image), [height, width, 3], localImgPath=image)
    shapes = []
    for box in boxes:
        label, points, angle = box_geometry(box, width, height, classes, allowed, fmt)
        shapes.append(dict(label=label, points=points))
        if fmt == 'xml':
            if angle:
                writer.addRotatedBndBox(box['cx'], box['cy'], box['w'], box['h'], angle, label, False, '')
            else:
                writer.addBndBox(*map(round, points[0] + points[2]), label, False, '')
    if fmt == 'xml':
        writer.save(path)
    else:
        save_yolo_annotations(path,shapes,width,height,classes,fmt)


class AgentQueue:
    def __init__(self, db_path, context):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self.ctx = context
        self.context_key = json.dumps(context, ensure_ascii=False, sort_keys=True)
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS job(id TEXT PRIMARY KEY, context TEXT, rules TEXT, allowed TEXT);
          CREATE TABLE IF NOT EXISTS frame(job TEXT, seq INTEGER, image TEXT, base TEXT,
            token TEXT, state TEXT DEFAULT 'pending', stamp TEXT, w INTEGER, h INTEGER,
            expected TEXT, outcome TEXT, reason TEXT, PRIMARY KEY(job,seq), UNIQUE(job,token));
          CREATE INDEX IF NOT EXISTS pending_agent_frames ON frame(job,seq) WHERE state IN ('pending','writing');
        """)

    def create(self, entries, rules, allowed):
        if not entries or not isinstance(rules,str) or not rules.strip() or len(rules)>12000:
            raise ValueError('Supply task instructions and a nonempty range')
        classes = self.ctx['classes']
        if not isinstance(allowed,list) or not allowed or any(c not in classes for c in allowed):
            raise ValueError('Allowed classes must exactly match project classes')
        job = uuid.uuid4().hex
        with self.db:
            self.db.execute('INSERT INTO job VALUES(?,?,?,?)',
                            (job,self.context_key,rules,json.dumps(allowed)))
            self.db.executemany('INSERT INTO frame(job,seq,image,base,token) VALUES(?,?,?,?,?)',
                                ((job,i,inside(img,self.ctx['images']),inside(base,self.ctx['labels']),
                                  uuid.uuid4().hex) for i,(img,base) in enumerate(entries)))
        return job

    def job(self, job):
        row = self.db.execute('SELECT * FROM job WHERE id=? AND context=?',
                              (job,self.context_key)).fetchone()
        if row is None:
            raise ValueError('Task not found for this project, class list and format')
        return row

    def latest(self):
        row = self.db.execute('SELECT id FROM job WHERE context=? ORDER BY rowid DESC LIMIT 1',
                              (self.context_key,)).fetchone()
        return row[0] if row else None

    def head(self, job):
        return self.db.execute("SELECT * FROM frame WHERE job=? AND state IN ('pending','writing') ORDER BY seq LIMIT 1",
                               (job,)).fetchone()

    def frames(self, job, start=0, end=2147483647):
        return self.db.execute('SELECT * FROM frame WHERE job=? AND seq>=? AND seq<? ORDER BY seq',
                               (job, start, end))

    def finish(self, r, state, reason=''):
        with self.db:
            self.db.execute('UPDATE frame SET state=?,reason=? WHERE job=? AND seq=?',
                            (state,reason,r['job'],r['seq']))

    def target(self,r):
        base = inside(r['base'],self.ctx['labels'])
        return inside(base + ('.xml' if self.ctx['format']=='xml' else '.txt'), self.ctx['labels'])

    def next(self, job):
        self.job(job)
        # One bounded pass; the client can continue polling large already-labelled ranges.
        for _ in range(128):
            r = self.head(job)
            if r is None:
                return None
            path = self.target(r)
            if r['state']=='writing':
                if os.path.isfile(path) and digest(path)==r['expected']:
                    self.finish(r,r['outcome'])
                    continue
                if not exists_label(r['base']):
                    self.finish(r,'pending')
                    continue
            if exists_label(r['base']):
                self.finish(r,'skipped','existing label')
            elif not os.path.isfile(inside(r['image'],self.ctx['images'])):
                self.finish(r,'review','missing image')
            else:
                return r
        return None

    def issue(self,r,w,h,revision):
        with self.db:
            self.db.execute('UPDATE frame SET stamp=?,w=?,h=? WHERE job=? AND seq=?',
                            (revision,w,h,r['job'],r['seq']))

    def submit(self,job,token,outcome,boxes,reason=''):
        j = self.job(job)
        if outcome not in ('annotated','empty','review') or not isinstance(boxes,list) or len(boxes)>2000:
            raise ValueError('Invalid outcome or box list (max 2000)')
        if bool(boxes) != (outcome=='annotated') or not isinstance(reason,str) or len(reason)>1000:
            raise ValueError('Only annotated accepts boxes; explicitly choose empty or review')
        if outcome=='review' and not reason.strip():
            raise ValueError('Provide a review reason')
        r = self.db.execute('SELECT * FROM frame WHERE job=? AND token=?',(job,token)).fetchone()
        if r is None:
            raise ValueError('Image token does not belong to this task')
        if r['state'] not in ('pending','writing'):
            return False  # Lost response or duplicate submission; do not write twice.
        if self.head(job)['token']!=token or not r['stamp'] or stamp(inside(r['image'],self.ctx['images']))!=r['stamp']:
            raise ValueError('Stale or unissued image; explicitly resume the task')
        target = self.target(r)
        if exists_label(r['base']):
            raise ValueError('A label already exists. Resume to skip it; never overwrite.')
        if outcome=='review':
            self.finish(r,'review',reason)
            return True
        folder=os.path.dirname(target)
        os.makedirs(folder,exist_ok=True)
        fd,tmp=tempfile.mkstemp(dir=folder,prefix='.labelimg-agent-')
        os.close(fd)
        try:
            write_boxes(tmp,r['image'],r['w'],r['h'],self.ctx['classes'],json.loads(j['allowed']),
                        self.ctx['format'],boxes)
            if stamp(r['image']) != r['stamp']:
                raise ValueError('Image changed while validating boxes')
            with self.db:
                self.db.execute("UPDATE frame SET state='writing',expected=?,outcome=? WHERE job=? AND token=?",
                                (digest(tmp),outcome,job,token))
            if exists_label(r['base']):
                raise ValueError('Label appeared while saving')
            if os.name=='nt':
                os.rename(tmp,target)  # Windows rename refuses an existing destination.
            else:
                os.link(tmp,target)
            self.finish(r,outcome)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return True

    def summary(self,job,details=True):
        self.job(job)
        counts=Counter({r[0]:r[1] for r in self.db.execute(
            'SELECT state,count(*) FROM frame WHERE job=? GROUP BY state',(job,))})
        remaining=counts['pending']+counts['writing']
        review=([{'image':project_image_name(r[0],self.ctx['images']),'reason':r[1]}
                for r in self.db.execute("SELECT image,reason FROM frame WHERE job=? AND state='review' ORDER BY seq",(job,))]
                if details or not remaining else [])
        return dict(task_id=job,total=sum(counts.values()),annotated=counts['annotated'],
                    empty=counts['empty'],skipped=counts['skipped'],review=review,
                    review_count=counts['review'],remaining=remaining)
