from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .crypto import random_bytes
from .db import Database
from .services import audit, now, uid

MAX_ATTACHMENT_BYTES=25*1024*1024
ALLOWED_TYPES={'client','subscription','vehicle','fleet'}
EXT_MIME={'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp','.pdf':'application/pdf'}


def _detect_mime(data:bytes)->str:
    if data.startswith(b'\x89PNG\r\n\x1a\n'): return 'image/png'
    if data.startswith(b'\xff\xd8\xff'): return 'image/jpeg'
    if len(data)>=12 and data[:4]==b'RIFF' and data[8:12]==b'WEBP': return 'image/webp'
    if data.startswith(b'%PDF-'): return 'application/pdf'
    raise ValueError('unsupported attachment file signature')


def _validate_entity(entity_type:str,entity_id:str):
    entity_type=str(entity_type or '').strip().lower(); entity_id=str(entity_id or '').strip()
    if entity_type not in ALLOWED_TYPES or not entity_id: raise ValueError('invalid attachment entity')
    return entity_type,entity_id


def _seal(key:bytes,payload:bytes,aad:bytes)->bytes:
    nonce=random_bytes(12); return nonce+AESGCM(key).encrypt(nonce,payload,aad)

def _open(key:bytes,payload:bytes,aad:bytes)->bytes:
    if len(payload)<13: raise ValueError('invalid encrypted attachment')
    return AESGCM(key).decrypt(payload[:12],payload[12:],aad)


class LocalAttachmentStore:
    def __init__(self,root:Path|str,environment:str,key:bytes):
        self.root=Path(root); self.environment=environment; self.key=key
    def _base(self)->Path:
        p=self.root/'UserData'/'Attachments'/self.environment; p.mkdir(parents=True,exist_ok=True); return p
    def put(self,attachment_id:str,data:bytes)->str:
        self._base()
        rel=Path('UserData')/'Attachments'/self.environment/f'{attachment_id}.aead'
        final=self.root/rel; pending=final.with_suffix('.aead.pending')
        pending.write_bytes(_seal(self.key,data,f'{attachment_id}:attachment:v1'.encode()))
        pending.replace(final); return rel.as_posix()
    def get(self,attachment_id:str,local_path:str)->bytes:
        path=self.root/Path(local_path)
        if not path.exists(): raise FileNotFoundError('attachment file missing')
        return _open(self.key,path.read_bytes(),f'{attachment_id}:attachment:v1'.encode())
    def delete(self,local_path:str|None):
        if local_path:(self.root/Path(local_path)).unlink(missing_ok=True)


class DriveAttachmentStore:
    enabled=False
    def put(self,*args,**kwargs): raise RuntimeError('DriveAttachmentStore is disabled')
    def get(self,*args,**kwargs): raise RuntimeError('DriveAttachmentStore is disabled')


def _relation_columns(db:Database,entity_type:str,entity_id:str)->dict:
    mapping={'client':('clients','client_id'),'subscription':('subscriptions','subscription_id'),'vehicle':('vehicles','vehicle_id'),'fleet':('fleets','fleet_id')}
    table,column=mapping[entity_type]
    exists=db.one(f'SELECT id FROM {table} WHERE id=?',(entity_id,))
    return {column:entity_id} if exists else {}


def store_attachment(root:Path|str,db:Database,actor:int,key:bytes,entity_type:str,entity_id:str,filename:str,content_type:str|None,data:bytes)->dict:
    entity_type,entity_id=_validate_entity(entity_type,entity_id)
    if len(data)>MAX_ATTACHMENT_BYTES: raise ValueError('attachment exceeds 25 MiB')
    filename=Path(filename or '').name
    suffix=Path(filename).suffix.lower()
    if suffix not in EXT_MIME: raise ValueError('file extension is not allowed')
    detected=_detect_mime(data)
    if detected!=EXT_MIME[suffix]: raise ValueError('file extension does not match its real signature')
    if content_type and content_type not in {'application/octet-stream',detected}: raise ValueError('declared MIME does not match file signature')
    digest=hashlib.sha256(data).hexdigest()
    if db.one("SELECT id FROM attachments WHERE origin='LOCAL' AND sha256=?",(digest,)): raise ValueError('duplicate attachment hash')
    aid=uid(); ts=now(); store=LocalAttachmentStore(root,db.environment,key); local_path=store.put(aid,data)
    relations=_relation_columns(db,entity_type,entity_id)
    rec={'id':aid,'entity_type':entity_type,'entity_id':entity_id,'client_id':None,'subscription_id':None,'vehicle_id':None,'fleet_id':None,
         'filename':filename,'mime':detected,'size_bytes':len(data),'sha256':digest,'origin':'LOCAL','local_path':local_path,'url':None,'created_at':ts,'updated_at':ts}
    rec.update(relations)
    try:
        with db.transaction() as con:
            con.execute('''INSERT INTO attachments(id,entity_type,entity_id,client_id,subscription_id,vehicle_id,fleet_id,filename,mime,size_bytes,sha256,origin,local_path,url,created_at,updated_at)
                           VALUES(:id,:entity_type,:entity_id,:client_id,:subscription_id,:vehicle_id,:fleet_id,:filename,:mime,:size_bytes,:sha256,:origin,:local_path,:url,:created_at,:updated_at)''',rec)
            audit(con,actor,'ATTACHMENT_CREATE','attachment',aid,None,{k:v for k,v in rec.items() if k not in {'local_path','url'}})
        return rec
    except Exception:
        store.delete(local_path); raise


def store_link(db:Database,actor:int,entity_type:str,entity_id:str,url:str,filename:str|None=None)->dict:
    entity_type,entity_id=_validate_entity(entity_type,entity_id); url=str(url or '').strip(); parsed=urlparse(url)
    if parsed.scheme not in {'http','https'} or not parsed.netloc: raise ValueError('attachment link must use http or https')
    aid=uid(); ts=now(); relations=_relation_columns(db,entity_type,entity_id)
    rec={'id':aid,'entity_type':entity_type,'entity_id':entity_id,'client_id':None,'subscription_id':None,'vehicle_id':None,'fleet_id':None,
         'filename':filename or None,'mime':'text/uri-list','size_bytes':0,'sha256':None,'origin':'LINK','local_path':None,'url':url,'created_at':ts,'updated_at':ts}
    rec.update(relations)
    with db.transaction() as con:
        con.execute('''INSERT INTO attachments(id,entity_type,entity_id,client_id,subscription_id,vehicle_id,fleet_id,filename,mime,size_bytes,sha256,origin,local_path,url,created_at,updated_at)
                       VALUES(:id,:entity_type,:entity_id,:client_id,:subscription_id,:vehicle_id,:fleet_id,:filename,:mime,:size_bytes,:sha256,:origin,:local_path,:url,:created_at,:updated_at)''',rec)
        audit(con,actor,'ATTACHMENT_LINK_CREATE','attachment',aid,None,{**rec,'url':'[LINK]'})
    return rec


def list_attachments(db:Database,entity_type:str|None=None,entity_id:str|None=None)->list[dict]:
    where=[];args=[]
    if entity_type:where.append('entity_type=?');args.append(entity_type)
    if entity_id:where.append('entity_id=?');args.append(entity_id)
    sql='SELECT id,entity_type,entity_id,filename,mime,size_bytes,sha256,origin,url,created_at,updated_at FROM attachments'
    if where:sql+=' WHERE '+' AND '.join(where)
    sql+=' ORDER BY created_at DESC'
    return [dict(r) for r in db.query(sql,tuple(args))]


def load_attachment(root:Path|str,db:Database,key:bytes,attachment_id:str)->tuple[bytes,str,str]:
    row=db.one('SELECT * FROM attachments WHERE id=?',(attachment_id,))
    if not row: raise KeyError('attachment not found')
    if row['origin']!='LOCAL': raise ValueError('linked attachment has no local payload')
    data=LocalAttachmentStore(root,db.environment,key).get(attachment_id,row['local_path'])
    return data,row['mime'],row['filename'] or 'attachment'
