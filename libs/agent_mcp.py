"""Local stdio MCP adapter. Only these three project-scoped tools exist."""
import hashlib
import json
import os
import sys
import time
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtNetwork import QLocalSocket


def endpoint():
    profile=os.path.normcase(os.path.realpath(os.path.expanduser('~')))
    return 'LabelImg2-Agent-'+hashlib.sha256(profile.encode()).hexdigest()[:24]


def obj(props, required=()):
    return dict(type='object',properties=props,required=list(required),additionalProperties=False)


STR={'type':'string'}
NUM={'type':'number'}
BOX=obj(dict(class_id={'type':'integer','minimum':0},cx=NUM,cy=NUM,w=NUM,h=NUM,angle_deg=NUM),
        ['class_id','cx','cy','w','h'])
TOOLS={
    'start_task':('Start at the current image. Supply instructions and count (or all_remaining:true). '
                  'Use resume_task_id alone to resume a saved task. Existing labels are always skipped.',
                  obj(dict(instructions=STR,count={'type':'integer','minimum':1},all_remaining={'type':'boolean'},
                           classes={'type':'array','items':STR},resume_task_id=STR))),
    'submit_and_next':('Submit the issued image exactly once and receive the next image. Geometry in original '
                       'oriented image pixels, clockwise angle_deg. Use exact class IDs. '
                       'annotated requires boxes; empty means confirmed background; review requires reason and writes no label.',
                       obj(dict(task_id=STR,image_token=STR,image_revision=STR,outcome={'enum':['annotated','empty','review']},
                                boxes={'type':'array','maxItems':2000,'items':BOX},reason=STR),
                           ['task_id','image_token','image_revision','outcome'])),
    'task_status':('Read project classes and saved progress, including review filenames. No writes or image navigation.',
                   obj(dict(task_id=STR))),
}
VERSIONS=('2025-11-25','2025-06-18','2025-03-26','2024-11-05')


def request_gui(name,args):
    socket=QLocalSocket()
    socket.connectToServer(endpoint())
    if not socket.waitForConnected(2500):
        raise ValueError('Open the image project in LabelImg2 and enable Settings > Agent access (MCP).')
    wire=json.dumps([name,args],allow_nan=False).encode()+b'\n'
    if len(wire)>1024*1024:
        raise ValueError('Request too large')
    socket.write(wire)
    data=bytearray()
    deadline=time.monotonic()+60
    while b'\n' not in data:
        if not socket.bytesAvailable() and not socket.waitForReadyRead(max(1,int((deadline-time.monotonic())*1000))):
            if not socket.bytesAvailable():
                raise ValueError('LabelImg2 disconnected or timed out. Use task_status before retrying.')
        data.extend(bytes(socket.readAll()))
        if len(data)>16*1024*1024 or time.monotonic()>deadline:
            raise ValueError('Response exceeded limit')
    answer=json.loads(data)
    if 'error' in answer:
        raise ValueError(answer['error'])
    return answer['content']


def serve(instream=None,outstream=None,call=request_gui):
    app=QCoreApplication.instance() or QCoreApplication([])
    instream=instream or sys.stdin.buffer
    outstream=outstream or sys.stdout.buffer
    for raw in instream:
        id_=None
        try:
            msg=json.loads(raw)
            if not isinstance(msg,dict) or msg.get('jsonrpc')!='2.0':
                raise ValueError('Invalid request')
            if 'id' not in msg:
                continue
            id_=msg['id']
            method=msg.get('method')
            params=msg.get('params',{})
            if method=='initialize':
                from .version import __version__
                ver=params.get('protocolVersion')
                result=dict(protocolVersion=ver if ver in VERSIONS else VERSIONS[0],
                            capabilities={'tools':{}},serverInfo=dict(name='labelimg2',version=__version__),
                            instructions='Follow user task instructions. Loop submit_and_next until complete. '
                            'If continuation_required, call start_task with resume_task_id. Never invent empty images.')
            elif method=='ping':
                result={}
            elif method=='tools/list':
                result={'tools':[dict(name=k,description=v[0],inputSchema=v[1]) for k,v in TOOLS.items()]}
            elif method=='tools/call':
                name=params.get('name')
                args=params.get('arguments',{})
                if name not in TOOLS or not isinstance(args,dict):
                    raise ValueError('Unknown tool or invalid arguments')
                schema=TOOLS[name][1]
                if set(args)-schema['properties'].keys() or set(schema['required'])-args.keys():
                    raise ValueError('Unknown or missing arguments')
                try:
                    result={'content':call(name,args)}
                except Exception as exc:
                    result={'isError':True,'content':[dict(type='text',text=str(exc))]}
            else:
                raise NotImplementedError('Unknown method')
            reply=dict(jsonrpc='2.0',id=id_,result=result)
        except Exception as exc:
            code=-32700 if isinstance(exc,json.JSONDecodeError) else -32601 if isinstance(exc,NotImplementedError) else -32602
            reply=dict(jsonrpc='2.0',id=id_,error=dict(code=code,message=str(exc)))
        outstream.write(json.dumps(reply,ensure_ascii=True).encode()+b'\n')
        outstream.flush()
    return 0
