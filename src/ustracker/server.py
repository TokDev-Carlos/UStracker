from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import threading
import time
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import Body, Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .auth import AuthService, Session
from .backup import create_backup, restore_backup, verify_backup
from .db import Database
from .media import load as load_media, store as store_media
from .public_projection import read as read_public, rebuild as rebuild_public
from .reports import client_csv, client_xlsx
from .services import (
    add_disbursement, apply_credit, create_catalog, create_client, create_expense, create_fiscal,
    create_payment, create_subscription, create_vehicle, dashboard, generate_charge, list_table,
    reverse_payment, search, update_client,
)

PRODUCT_VERSION='1.00.00.000'


def create_app(root: Path | str) -> FastAPI:
    root=Path(root).resolve(); root.mkdir(parents=True,exist_ok=True)
    auth=AuthService(root)
    app=FastAPI(title='UStracker',version=PRODUCT_VERSION,docs_url=None,redoc_url=None,openapi_url=None)
    app.state.root=root; app.state.auth=auth; app.state.server=None
    app.state.csrf_pre={}
    rebuild_default=lambda: read_public(root)
    rebuild_default()

    def get_db(session:Session)->Database:
        return Database(root,session.environment,session.db_key)

    @app.middleware('http')
    async def security_headers(request:Request, call_next):
        host=request.headers.get('host','').split(':')[0].lower()
        if host not in {'127.0.0.1','localhost','testserver'}:
            return JSONResponse({'error':'INVALID_HOST'},status_code=400)
        if request.method not in {'GET','HEAD','OPTIONS'}:
            origin=request.headers.get('origin')
            if origin and not (origin.startswith('http://127.0.0.1:') or origin.startswith('http://localhost:') or origin.startswith('http://testserver')):
                return JSONResponse({'error':'INVALID_ORIGIN'},status_code=403)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='no-referrer'
        return response

    def session_required(request:Request, human:bool=False)->Session:
        token=request.cookies.get('us_session')
        s=auth.get_session(token,human_activity=human)
        if not s: raise HTTPException(401,'ADMIN session required')
        return s

    def csrf_required(request:Request, session:Session|None=None):
        supplied=request.headers.get('X-CSRF-Token','')
        if session:
            if not supplied or not secrets.compare_digest(supplied,session.csrf): raise HTTPException(403,'invalid csrf')
            return
        cookie=request.cookies.get('us_csrf','')
        if not supplied or not cookie or not secrets.compare_digest(supplied,cookie): raise HTTPException(403,'invalid csrf')

    @app.exception_handler(ValueError)
    async def value_error(_:Request, exc:ValueError): return JSONResponse({'error':'VALIDATION','detail':str(exc)},status_code=422)
    @app.exception_handler(KeyError)
    async def key_error(_:Request, exc:KeyError): return JSONResponse({'error':'NOT_FOUND','detail':str(exc)},status_code=404)

    @app.get('/api/v1/health')
    def health(): return {'status':'ok','product':'UStracker','version':PRODUCT_VERSION}

    @app.get('/api/v1/public')
    def public(): return read_public(root)

    @app.get('/api/v1/auth/setup-status')
    def setup_status(): return auth.setup_status()

    @app.get('/api/v1/auth/csrf')
    def csrf(response:Response):
        token=secrets.token_urlsafe(24); response.set_cookie('us_csrf',token,httponly=False,samesite='strict',secure=False); return {'csrf':token}

    @app.post('/api/v1/auth/bootstrap')
    def bootstrap(request:Request,p:dict=Body(...)):
        csrf_required(request); return auth.bootstrap(p.get('name',''),p.get('password',''))

    @app.post('/api/v1/auth/enroll')
    def enroll(request:Request,p:dict=Body(...)):
        csrf_required(request); return auth.enroll(p.get('ticket',''),p.get('name',''),p.get('password',''))

    @app.post('/api/v1/auth/login')
    def login(request:Request,response:Response,p:dict=Body(...)):
        csrf_required(request); s=auth.login(p.get('name',''),p.get('password',''),p.get('environment','production'))
        response.set_cookie('us_session',s.token,httponly=True,samesite='strict',secure=False,max_age=43200)
        response.set_cookie('us_csrf',s.csrf,httponly=False,samesite='strict',secure=False,max_age=43200)
        # Creating the DB here proves the key/provider path before private access.
        db=get_db(s)
        if s.environment=='production': rebuild_public(root,db)
        return {'slot':s.slot,'name':s.name,'environment':s.environment,'csrf':s.csrf}

    @app.post('/api/v1/auth/logout')
    def logout(request:Request,response:Response):
        s=session_required(request); csrf_required(request,s); auth.logout(s.token); response.delete_cookie('us_session'); response.delete_cookie('us_csrf'); return {'ok':True}

    @app.get('/api/v1/auth/me')
    def me(request:Request):
        s=session_required(request); return {'slot':s.slot,'name':s.name,'environment':s.environment,'setup':auth.setup_status()}

    @app.post('/api/v1/auth/reset-admin/{slot}')
    def reset_admin(slot:int,request:Request,p:dict=Body(...)):
        s=session_required(request,True); csrf_required(request,s); ticket=auth.reset_admin(s,slot,p.get('reason','')); return {'slot':slot,'ticket':ticket,'expires_in_seconds':900}

    @app.get('/api/v1/clients')
    def clients(request:Request): return {'items':list_table(get_db(session_required(request)),'clients')}
    @app.post('/api/v1/clients',status_code=201)
    def clients_create(request:Request,p:dict=Body(...)):
        s=session_required(request,True); csrf_required(request,s); db=get_db(s); rec=create_client(db,s.slot,p); rebuild_public(root,db) if s.environment=='production' else None; return rec
    @app.patch('/api/v1/clients/{cid}')
    def clients_update(cid:str,request:Request,p:dict=Body(...)):
        s=session_required(request,True); csrf_required(request,s); db=get_db(s); rec=update_client(db,s.slot,cid,p); rebuild_public(root,db) if s.environment=='production' else None; return rec

    @app.get('/api/v1/vehicles')
    def vehicles(request:Request): return {'items':list_table(get_db(session_required(request)),'vehicles')}
    @app.post('/api/v1/vehicles',status_code=201)
    def vehicles_create(request:Request,p:dict=Body(...)):
        s=session_required(request,True); csrf_required(request,s); return create_vehicle(get_db(s),s.slot,p)

    @app.get('/api/v1/catalog')
    def catalog(request:Request): return {'items':list_table(get_db(session_required(request)),'catalog')}
    @app.post('/api/v1/catalog',status_code=201)
    def catalog_create(request:Request,p:dict=Body(...)):
        s=session_required(request,True); csrf_required(request,s); db=get_db(s); rec=create_catalog(db,s.slot,p); rebuild_public(root,db) if s.environment=='production' else None; return rec

    @app.get('/api/v1/subscriptions')
    def subscriptions(request:Request): return {'items':list_table(get_db(session_required(request)),'subscriptions')}
    @app.post('/api/v1/subscriptions',status_code=201)
    def subscriptions_create(request:Request,p:dict=Body(...)):
        s=session_required(request,True); csrf_required(request,s); return create_subscription(get_db(s),s.slot,p)
    @app.post('/api/v1/subscriptions/{sid}/charges/{competence}')
    def charge_generate(sid:str,competence:str,request:Request):
        s=session_required(request,True); csrf_required(request,s); return generate_charge(get_db(s),s.slot,sid,competence)
    @app.get('/api/v1/charges')
    def charges(request:Request): return {'items':list_table(get_db(session_required(request)),'charges',order='due_on DESC')}

    @app.get('/api/v1/payments')
    def payments(request:Request): return {'items':list_table(get_db(session_required(request)),'payments',order='paid_on DESC')}
    @app.post('/api/v1/payments',status_code=201)
    def payments_create(request:Request,p:dict=Body(...)):
        s=session_required(request,True); csrf_required(request,s); return create_payment(get_db(s),s.slot,p)
    @app.post('/api/v1/payments/{pid}/reverse')
    def payments_reverse(pid:str,request:Request):
        s=session_required(request,True); csrf_required(request,s); return reverse_payment(get_db(s),s.slot,pid)

    @app.get('/api/v1/credits')
    def credits(request:Request): return {'items':list_table(get_db(session_required(request)),'credits')}
    @app.post('/api/v1/credits/{credit_id}/apply')
    def credits_apply(credit_id:str,request:Request,p:dict=Body(...)):
        s=session_required(request,True); csrf_required(request,s); return apply_credit(get_db(s),s.slot,credit_id,p.get('charge_id',''),p.get('amount','0'))

    @app.get('/api/v1/expenses')
    def expenses(request:Request): return {'items':list_table(get_db(session_required(request)),'expenses')}
    @app.post('/api/v1/expenses',status_code=201)
    def expenses_create(request:Request,p:dict=Body(...)):
        s=session_required(request,True); csrf_required(request,s); return create_expense(get_db(s),s.slot,p)
    @app.post('/api/v1/expenses/{eid}/disbursements',status_code=201)
    def expenses_disburse(eid:str,request:Request,p:dict=Body(...)):
        s=session_required(request,True); csrf_required(request,s); return add_disbursement(get_db(s),s.slot,eid,p)

    @app.get('/api/v1/fiscal')
    def fiscal(request:Request): return {'items':list_table(get_db(session_required(request)),'fiscal_obligations')}
    @app.post('/api/v1/fiscal',status_code=201)
    def fiscal_create(request:Request,p:dict=Body(...)):
        s=session_required(request,True); csrf_required(request,s); return create_fiscal(get_db(s),s.slot,p)

    @app.get('/api/v1/dashboard')
    def dashboard_get(request:Request): return dashboard(get_db(session_required(request)))
    @app.get('/api/v1/search')
    def search_get(q:str,request:Request): return {'items':search(get_db(session_required(request)),q)}

    @app.get('/api/v1/settings')
    def settings_get(request:Request):
        db=get_db(session_required(request)); return {r['key']:r['value'] for r in db.query('SELECT key,value FROM settings')}
    @app.put('/api/v1/settings')
    def settings_put(request:Request,p:dict=Body(...)):
        s=session_required(request,True); csrf_required(request,s); db=get_db(s)
        allowed={'company_legal_name','company_display_name','contact_phone','contact_email','address_display','default_grace_days','theme_primary','theme_accent'}
        with db.transaction() as con:
            for k,v in p.items():
                if k not in allowed: raise ValueError(f'setting not allowed: {k}')
                con.execute('INSERT OR REPLACE INTO settings(key,value,updated_at) VALUES(?,?,datetime(\'now\'))',(k,str(v)))
        if s.environment=='production': rebuild_public(root,db)
        return {'ok':True}

    @app.post('/api/v1/media/{entity_type}/{entity_id}',status_code=201)
    async def media_upload(entity_type:str,entity_id:str,request:Request,file:UploadFile=File(...),retain_original:bool=False):
        s=session_required(request,True); csrf_required(request,s); data=await file.read(); return store_media(root,get_db(s),s.slot,s.media_key,entity_type,entity_id,data,retain_original)
    @app.get('/api/v1/media/{mid}/{variant}')
    def media_get(mid:str,variant:str,request:Request):
        s=session_required(request); data,mime=load_media(root,get_db(s),s.media_key,mid,variant); return Response(data,media_type=mime,headers={'Cache-Control':'no-store'})

    @app.get('/api/v1/reports/clients.csv')
    def report_csv(request:Request):
        data=client_csv(get_db(session_required(request))); return Response(data,media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="clients.csv"'})
    @app.get('/api/v1/reports/clients.xlsx')
    def report_xlsx(request:Request):
        data=client_xlsx(get_db(session_required(request))); return Response(data,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename="clients.xlsx"'})

    @app.get('/api/v1/backups')
    def backups(request:Request):
        session_required(request); d=root/'UserData'/'Backups'; d.mkdir(parents=True,exist_ok=True); return {'items':[{'name':p.name,'size':p.stat().st_size} for p in sorted(d.glob('*.usbk'),reverse=True)]}
    @app.post('/api/v1/backups',status_code=201)
    def backup_create(request:Request):
        s=session_required(request,True); csrf_required(request,s); path=create_backup(root,get_db(s),s.vrk); return {'name':path.name,'size':path.stat().st_size}
    @app.post('/api/v1/backups/restore')
    async def backup_restore(request:Request,file:UploadFile=File(...)):
        s=session_required(request,True); csrf_required(request,s); temp=root/'UserData'/'Backups'/'_restore_upload.usbk'; temp.parent.mkdir(parents=True,exist_ok=True); temp.write_bytes(await file.read())
        try: restore_backup(root,get_db(s),s.vrk,temp)
        finally: temp.unlink(missing_ok=True)
        if s.environment=='production': rebuild_public(root,get_db(s))
        return {'ok':True}

    @app.post('/api/v1/sandbox/reset')
    def sandbox_reset(request:Request,p:dict=Body(...)):
        s=session_required(request,True); csrf_required(request,s)
        if s.environment!='test' or p.get('confirm')!='LIMPAR TESTES': raise ValueError('test session and exact confirmation required')
        db=get_db(s); db.path.unlink(missing_ok=True); media=root/'UserData'/'Media'/'test'; shutil.rmtree(media,ignore_errors=True); Database(root,'test',s.db_key); return {'ok':True}

    @app.get('/api/v1/stations')
    def stations(request:Request): return {'items':list_table(get_db(session_required(request)),'stations')}
    @app.post('/api/v1/stations',status_code=201)
    def station_create(request:Request,p:dict=Body(...)):
        s=session_required(request,True); csrf_required(request,s); db=get_db(s)
        with db.transaction() as con:
            if con.execute('SELECT COUNT(*) FROM stations').fetchone()[0]>=3: raise ValueError('maximum three stations')
            import uuid,datetime
            sid=str(uuid.uuid4()); ts=datetime.datetime.now(datetime.timezone.utc).isoformat(); writer=1 if p.get('is_writer') else 0
            if writer: con.execute('UPDATE stations SET is_writer=0')
            con.execute('INSERT INTO stations(id,name,fingerprint,is_writer,generation,status,created_at,updated_at) VALUES(?,?,?,?,1,?,?,?)',(sid,p.get('name','Station'),p.get('fingerprint'),writer,'ACTIVE',ts,ts))
        return {'id':sid,'name':p.get('name','Station'),'is_writer':bool(writer)}

    @app.get('/api/v1/integrations')
    def integrations(request:Request): session_required(request); return {'drive':{'enabled':False,'implemented':False},'tracking':{'enabled':False,'implemented':False},'fiscal_official':{'enabled':False,'implemented':False}}
    @app.post('/api/v1/integrations/{provider}/{action}')
    def integration_disabled(provider:str,action:str,request:Request):
        s=session_required(request,True); csrf_required(request,s); raise HTTPException(501,detail={'code':'INTEGRATION_NOT_IMPLEMENTED','provider':provider,'action':action})

    @app.post('/api/v1/shell/detach')
    def shell_detach(request:Request,response:Response):
        token=request.cookies.get('us_session'); auth.logout(token); response.delete_cookie('us_session'); return {'ok':True}
    @app.post('/api/v1/system/shutdown')
    def shutdown(request:Request):
        s=session_required(request,True); csrf_required(request,s)
        if app.state.server is not None:
            def stop(): time.sleep(.2); app.state.server.should_exit=True
            threading.Thread(target=stop,daemon=True).start()
        return {'ok':True}

    frontend=root/'frontend'
    if frontend.exists():
        app.mount('/assets',StaticFiles(directory=str(frontend)),name='assets')
        @app.get('/',response_class=HTMLResponse)
        def index(): return (frontend/'index.html').read_text(encoding='utf-8')
    else:
        @app.get('/',response_class=HTMLResponse)
        def index_missing(): return '<html><body><h1>UStracker</h1><p>Frontend not packaged.</p></body></html>'
    return app


def run(root:Path|str):
    root=Path(root).resolve(); state_dir=root/'UserData'/'State'; state_dir.mkdir(parents=True,exist_ok=True); port_file=state_dir/'backend.json'
    sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM); sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); sock.bind(('127.0.0.1',0)); sock.listen(2048); port=sock.getsockname()[1]
    app=create_app(root); config=uvicorn.Config(app,host='127.0.0.1',port=port,log_level='info',access_log=False); server=uvicorn.Server(config); app.state.server=server
    tmp=port_file.with_suffix('.tmp'); tmp.write_text(json.dumps({'port':port,'pid':os.getpid(),'version':PRODUCT_VERSION}),encoding='utf-8'); tmp.replace(port_file)
    try: server.run(sockets=[sock])
    finally: port_file.unlink(missing_ok=True)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument('--root',default=os.getcwd()); args=parser.parse_args(); run(args.root)
