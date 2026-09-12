from __future__ import annotations

import io, json, os, shutil, struct, tempfile, zipfile
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .crypto import b64e,b64d,derive_backup_key,random_bytes,sha256_hex
from .db import Database

MAGIC=b'USTRACKER_LOCAL_BACKUP_V1\n'

def create_backup(root:Path, db:Database, vrk:bytes)->Path:
    root=Path(root); out_dir=root/'UserData'/'Backups'; out_dir.mkdir(parents=True,exist_ok=True)
    # Ensure a consistent checkpoint in DELETE journal mode.
    with db.connect() as con: con.execute('PRAGMA wal_checkpoint(FULL)')
    mem=io.BytesIO()
    with zipfile.ZipFile(mem,'w',zipfile.ZIP_DEFLATED) as z:
        z.write(db.path,arcname='database/ustracker.db')
        media_root=root/'UserData'/'Media'/db.environment
        if media_root.exists():
            for p in media_root.rglob('*'):
                if p.is_file(): z.write(p,arcname='media/'+p.relative_to(media_root).as_posix())
        public=root/'UserData'/'Public'/'production'/'view.json'
        if public.exists(): z.write(public,arcname='public/view.json')
    payload=mem.getvalue(); salt=random_bytes(16); nonce=random_bytes(12); key=derive_backup_key(vrk,salt)
    header={'version':1,'environment':db.environment,'salt':b64e(salt),'nonce':b64e(nonce),'sha256_plain':sha256_hex(payload)}
    header_bytes=json.dumps(header,sort_keys=True,separators=(',',':')).encode(); cipher=AESGCM(key).encrypt(nonce,payload,header_bytes)
    name=f"UStracker_{db.environment}_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}.usbk"
    path=out_dir/name; path.write_bytes(MAGIC+struct.pack('>I',len(header_bytes))+header_bytes+cipher)
    verify_backup(path,vrk); return path

def _decrypt(path:Path,vrk:bytes)->tuple[dict,bytes]:
    raw=Path(path).read_bytes()
    if not raw.startswith(MAGIC): raise ValueError('invalid backup magic')
    off=len(MAGIC); hlen=struct.unpack('>I',raw[off:off+4])[0]
    if hlen<2 or hlen>65536: raise ValueError('invalid header size')
    hb=raw[off+4:off+4+hlen]; header=json.loads(hb); key=derive_backup_key(vrk,b64d(header['salt']))
    plain=AESGCM(key).decrypt(b64d(header['nonce']),raw[off+4+hlen:],hb)
    if sha256_hex(plain)!=header['sha256_plain']: raise ValueError('backup hash mismatch')
    return header,plain

def verify_backup(path:Path,vrk:bytes)->dict:
    header,plain=_decrypt(path,vrk)
    with zipfile.ZipFile(io.BytesIO(plain)) as z:
        names=z.namelist()
        if 'database/ustracker.db' not in names: raise ValueError('database missing from backup')
        for n in names:
            if n.startswith('/') or '..' in Path(n).parts: raise ValueError('unsafe backup member')
    return header

def restore_backup(root:Path, db:Database, vrk:bytes, path:Path)->None:
    header,plain=_decrypt(path,vrk)
    if header['environment']!=db.environment: raise ValueError('backup environment mismatch')
    root=Path(root); staging=Path(tempfile.mkdtemp(prefix='ustracker-restore-',dir=str(root/'UserData')))
    try:
        with zipfile.ZipFile(io.BytesIO(plain)) as z:
            for n in z.namelist():
                if n.startswith('/') or '..' in Path(n).parts: raise ValueError('unsafe backup member')
            z.extractall(staging)
        candidate=staging/'database'/'ustracker.db'
        old=db.path.with_suffix('.pre_restore')
        if old.exists(): old.unlink()
        shutil.copy2(db.path,old); shutil.copy2(candidate,db.path)
        try:
            test=Database(root,db.environment,db.key); test.one('SELECT value FROM meta WHERE key=\'schema_version\'')
        except Exception:
            shutil.copy2(old,db.path); raise
        media_src=staging/'media'; media_dst=root/'UserData'/'Media'/db.environment
        if media_src.exists():
            if media_dst.exists(): shutil.rmtree(media_dst)
            shutil.copytree(media_src,media_dst)
    finally:
        shutil.rmtree(staging,ignore_errors=True)
