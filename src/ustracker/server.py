from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import Body, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import activation
from .auth import AuthService, Session
from .attachments import list_attachments, load_attachment, store_attachment, store_link
from .codes import resolve_entity_ref
from .backup import create_backup, maybe_automatic_backup, prune_backups, restore_backup, verify_backup
from .branding import asset_dir, store_brand_asset
from .billing import client_payment_options, register_fleet_payment, register_subscription_payment, subscription_payment_status
from .catalog import list_catalog, remove_catalog_item
from .cloud import CLOUD_EPOCH, CloudError, CloudSync, apply_pending_restore, restore_from_cloud
from .trash import list_trash, restore as restore_trash
from .subscription_edit import amend_subscription
from .expenses import convert_expense_to_sale, create_company_expense, delete_expense, pay_expense, run_recurring_expenses, stop_recurring_expense
from .commercial import commercial_snapshot, create_coverage
from .finance import ensure_fiscal_expense, finance_snapshot
from .overview import client_activity_overview
from .db import Database, SCHEMA_VERSION
from .extensions import (
    add_charge_adjustment,
    create_fleet,
    dashboard_extended,
    generate_recurring_expense,
    reverse_disbursement,
    run_idempotent,
    set_subscription_status,
    transfer_vehicle,
    update_catalog,
    verify_audit_chain,
)
from .access import describe as describe_access, global_only, required_permission, restrict_dashboard, strip_costs
from .mobility_delete import PlateExists, check_plate, delete_fleet, delete_vehicle
from .mobility import (
    cancel_transfer_case,
    complete_transfer_case,
    create_transfer_case,
    fleet_profile,
    list_mobility,
    mobility_subscription_detail,
    list_transfer_cases,
    move_vehicle,
    update_fleet,
)
from .media import load as load_media, recover_media_journals, remove as remove_media, store as store_media
from .paths import ProductPaths
from .public_projection import read as read_public, rebuild as rebuild_public
from .repository import LocalRepository
from .recovery import export_recovery
from .reports import REPORTS, report_csv, report_xlsx
from .services import (
    add_disbursement,
    apply_credit,
    create_catalog,
    archive_clients,
    create_client,
    create_client_company,
    create_client_document,
    create_direct_sale,
    create_expense,
    create_fiscal,
    create_payment,
    create_subscription,
    create_vehicle,
    client_profile,
    dashboard,
    generate_charge,
    list_client_companies,
    list_client_documents,
    list_clients,
    list_subscriptions,
    list_table,
    list_direct_sales,
    reverse_payment,
    search,
    search_client_entities,
    set_direct_sale_status,
    update_client,
)
from .station import (
    claim_pending_writer,
    emergency_takeover,
    ensure_station,
    list_stations,
    reclaim_writer_after_failed_transfer,
    relinquish_writer,
    require_writer,
)
from .versioning import read_version


_LOCAL_ORIGIN = __import__('re').compile(r'http://(127\.0\.0\.1|localhost)(:\d{1,5})?')


def create_app(root: Path | str) -> FastAPI:
    paths = ProductPaths.from_root(root)
    root = paths.app_root
    root.mkdir(parents=True, exist_ok=True)
    paths.ensure_runtime_directories()
    # 2.5.0: any older installation starts clean (backup with SHA-256 first; all or nothing; once)
    clean_start_info = {'cleaned': False, 'backup': None}
    try:
        clean_start_info = activation.clean_start(root)
    except Exception as exc:  # backup failed: nothing removed; the screen shows the problem
        clean_start_info = {'cleaned': False, 'backup': None, 'error': str(exc)[:300]}
    repository = LocalRepository(root)
    product_version = read_version(root)
    auth = AuthService(root)
    app = FastAPI(title='UStracker', version=product_version, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.root = root
    app.state.auth = auth
    app.state.server = None
    app.state.clean_start = clean_start_info
    read_public(root)

    def get_db(session: Session) -> Database:
        return repository.database(session.environment, session.db_key)

    cloud = CloudSync(root, auth)
    app.state.cloud = cloud

    def daily_backup(session) -> None:  # 2.6: cópia conferida também com o sistema aberto por dias
        db = repository.database('production', session.db_key)
        settings = {r['key']: r['value'] for r in db.query('SELECT key,value FROM settings')}
        maybe_automatic_backup(root, db, session.vrk, retention=int(settings.get('backup_retention', 14)), db_key=session.db_key)
    cloud.on_tick = daily_backup
    from .update_channel import UpdateService, can_apply as update_can_apply
    updates = UpdateService(root)
    app.state.updates = updates

    @app.middleware('http')
    async def security_headers(request: Request, call_next):
        correlation = request.headers.get('X-Correlation-ID', '').strip()
        if not correlation or len(correlation) > 128:
            correlation = str(uuid.uuid4())
        request.state.correlation_id = correlation
        host = request.headers.get('host', '').split(':')[0].lower()
        if host not in {'127.0.0.1', 'localhost'}:
            return JSONResponse({'error': 'INVALID_HOST', 'correlation_id': correlation}, status_code=400)
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            origin = request.headers.get('origin')
            if origin and not _LOCAL_ORIGIN.fullmatch(origin):
                return JSONResponse({'error': 'INVALID_ORIGIN', 'correlation_id': correlation}, status_code=403)
        # U-05: package permissions are enforced here for every API route (the UI only hides).
        hide_costs = False
        if request.url.path.startswith('/api/v1/'):
            session = auth.get_session(request.cookies.get('us_session'))
            if session is not None and session.is_admin and not session.is_global and global_only(request.method, request.url.path):
                return JSONResponse({'error': 'FORBIDDEN', 'detail': 'Adm Global required', 'correlation_id': correlation}, status_code=403)
            if session is not None and not session.is_admin:
                need = required_permission(request.method, request.url.path)
                if not session.can(need):
                    return JSONResponse({'error': 'FORBIDDEN', 'detail': 'permission denied', 'permission': need if isinstance(need, str) else list(need),
                                         'correlation_id': correlation}, status_code=403)
                hide_costs = request.method == 'GET' and not session.can('catalog.costs')
        response = await call_next(request)
        if hide_costs and response.headers.get('content-type', '').startswith('application/json'):
            # 2.2.0: no cost/margin field leaves the server for packages without "Ver custo e margem", on ANY screen
            raw = b''.join([chunk async for chunk in response.body_iterator])
            try:
                cleaned = json.dumps(strip_costs(json.loads(raw)), ensure_ascii=False).encode('utf-8')
            except ValueError:
                cleaned = raw
            headers = {k: v for k, v in response.headers.items() if k.lower() != 'content-length'}
            response = Response(cleaned, status_code=response.status_code, headers=headers, media_type='application/json')
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Correlation-ID'] = correlation
        return response

    def _err(request: Request, code: str, detail: str):
        return {'error': code, 'detail': detail, 'correlation_id': getattr(request.state, 'correlation_id', '')}

    @app.exception_handler(PlateExists)
    async def plate_exists(request: Request, exc: PlateExists):
        body = _err(request, 'PLATE_EXISTS', str(exc)); body['vehicle'] = exc.info
        return JSONResponse(body, status_code=409)

    @app.exception_handler(ValueError)
    async def value_error(request: Request, exc: ValueError):
        return JSONResponse(_err(request, 'VALIDATION', str(exc)), status_code=422)

    @app.exception_handler(KeyError)
    async def key_error(request: Request, exc: KeyError):
        return JSONResponse(_err(request, 'NOT_FOUND', str(exc.args[0]) if exc.args else 'not found'), status_code=404)

    @app.exception_handler(PermissionError)
    async def permission_error(request: Request, exc: PermissionError):
        return JSONResponse(_err(request, 'FORBIDDEN', str(exc)), status_code=403)

    @app.exception_handler(RuntimeError)
    async def runtime_error(request: Request, exc: RuntimeError):
        status = 409 if 'pending from a previous interrupted attempt' in str(exc) else 500
        return JSONResponse(_err(request, 'CONFLICT' if status == 409 else 'RUNTIME', str(exc)), status_code=status)

    def _log_error(request: Request, exc: BaseException) -> None:
        try:
            import traceback
            log = root / 'UserData' / 'Logs' / 'erros.log'
            log.parent.mkdir(parents=True, exist_ok=True)
            if log.exists() and log.stat().st_size > 2_000_000:
                log.replace(log.with_suffix('.log.1'))
            stamp = datetime.now().isoformat(timespec='seconds')
            text = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-6000:]
            with log.open('a', encoding='utf-8') as fh:
                fh.write(f"--- {stamp} {request.method} {request.url.path} cid={getattr(request.state, 'correlation_id', '')}\n{text}\n")
        except Exception:
            pass

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        _log_error(request, exc)
        return JSONResponse(_err(request, 'INTERNAL', f'Erro interno ({type(exc).__name__}). Detalhes em UserData/Logs/erros.log'),
                            status_code=500)

    def session_required(request: Request, human: bool = False) -> Session:
        token = request.cookies.get('us_session')
        session = auth.get_session(token, human_activity=human)
        if not session:
            raise HTTPException(401, 'ADMIN session required')
        return session

    def csrf_required(request: Request, session: Session | None = None):
        supplied = request.headers.get('X-CSRF-Token', '')
        if session:
            if not supplied or not secrets.compare_digest(supplied, session.csrf):
                raise HTTPException(403, 'invalid csrf')
            return
        cookie = request.cookies.get('us_csrf', '')
        if not supplied or not cookie or not secrets.compare_digest(supplied, cookie):
            raise HTTPException(403, 'invalid csrf')

    def take_turn(session: Session, db: Database) -> None:
        """S-03 — with the shared cloud: automatic turn (+ newest data first). Without it: the single writer station."""
        if cloud.enabled():
            try:
                cloud.acquire_turn(session)
            except CloudError as exc:
                raise HTTPException(409, detail={'code': f'CLOUD_{exc.code}', 'detail': exc.detail, 'message': exc.detail}) from exc
        else:
            require_writer(root, db)

    def mutation(request: Request, session: Session, route: str, payload, fn, *, writer: bool = True):
        csrf_required(request, session)
        db = get_db(session)
        if writer and session.environment == 'production':
            take_turn(session, db)
        operation_id = request.headers.get('X-Operation-ID', '')
        with cloud.db_gate:
            result = run_idempotent(db, session.slot, route, operation_id, payload, lambda: fn(db))
        if session.environment == 'production':
            cloud.mark_dirty()
        return result

    def authorize_file_mutation(request: Request, session: Session, *, writer: bool = True) -> Database:
        csrf_required(request, session)
        db = get_db(session)
        if writer and session.environment == 'production':
            take_turn(session, db)
            cloud.mark_dirty()
        return db

    @app.get('/api/v1/sync/state')
    def sync_state_get(request: Request):
        session = session_required(request)
        return {**cloud.sync_state(), 'environment': session.environment}

    @app.get('/api/v1/health')
    def health():
        return {'status': 'ok', 'product': 'UStracker', 'version': product_version}

    @app.get('/api/v1/public')
    def public():
        return read_public(root)

    @app.get('/api/v1/auth/setup-status')
    def setup_status():
        from .adm_global import load_trust
        return {**auth.setup_status(), 'global_configured': bool(load_trust(root))}

    @app.get('/api/v1/auth/csrf')
    def csrf(response: Response):
        token = secrets.token_urlsafe(24)
        response.set_cookie('us_csrf', token, httponly=False, samesite='strict', secure=False)
        return {'csrf': token}

    @app.post('/api/v1/auth/bootstrap')
    def bootstrap(request: Request, p: dict = Body(...)):
        csrf_required(request)
        from .adm_global import load_trust
        if load_trust(root):  # 2.2.0: installations with an Adm Global are activated by it (/auth/activate)
            raise HTTPException(403, 'activation by the Adm Global required')
        return auth.bootstrap(p.get('name', ''), p.get('password', ''))

    @app.post('/api/v1/auth/enroll')
    def enroll(request: Request, p: dict = Body(...)):
        csrf_required(request)
        return auth.enroll(p.get('ticket', ''), p.get('name', ''), p.get('password', ''))

    @app.post('/api/v1/auth/login')
    def login(request: Request, response: Response, p: dict = Body(...)):
        csrf_required(request)
        from . import adm_global
        trust = adm_global.load_trust(root)
        recovery_key = None
        if trust and str(p.get('name', '')).strip().casefold() == trust['login'].casefold():
            # G-04 — Adm Global: login + PIN, then the fake question whose answer is the same PIN
            ident = trust['login'].casefold()
            state = auth.global_lock_state(ident)
            if state['locked_minutes']:
                return JSONResponse({'error': 'LOCKED', 'detail': f"login temporarily locked; try again in {state['locked_minutes']} minutes",
                                     'retry_minutes': state['locked_minutes']}, status_code=429)
            if 'answer' not in p:
                return {'challenge': auth.global_question(ident)}
            denied = {'error': 'INVALID', 'detail': 'invalid credentials'}
            if str(p.get('answer', '')) != str(p.get('password', '')):
                return JSONResponse({**denied, 'hint': auth.global_failure(ident, 'answer')['hint']}, status_code=422)
            try:
                session = auth.global_login(root, trust, p.get('password', ''), 'production')
            except adm_global.AccessDenied as exc:
                if str(exc) == 'invalid credentials':
                    return JSONResponse({**denied, 'hint': auth.global_failure(ident, 'pin')['hint']}, status_code=422)
                if str(exc) == 'installation not prepared':  # 2.3.0: PIN was right; say what is really missing
                    return JSONResponse({'error': 'NOT_PREPARED', 'detail': 'this installation was not activated by the Adm Global'}, status_code=409)
                return JSONResponse({**denied, 'hint': adm_global.hint_for(state['question_id'] or 1, max(1, state['attempts']))}, status_code=422)
        else:
            session = auth.login(p.get('name', ''), p.get('password', ''), p.get('environment', 'production'))
            if session.kind == 'admin':
                if auth.ensure_global_wrap(session, trust):
                    cloud.mark_dirty()
                recovery_key = auth.ensure_recovery(session)
        return enter(response, session, recovery_key)

    def keep_directory(session: Session, db) -> None:
        """2.5: o cadastro global de usuários usa a mesma nuvem + chave da empresa (guardado protegido nesta máquina)."""
        try:
            if cloud.enabled():
                company_key = cloud.company_key(session, db)
                if company_key:
                    auth.set_directory(cloud.state.get('url'), cloud.state.secret(session.vrk), company_key)
                    auth.refresh_users(quiet=True)
        except Exception:
            pass

    def enter(response: Response, session: Session, recovery_key: str | None = None, extra: dict | None = None) -> dict:
        """Common end of every sign in: cookies, cloud restore/attach, station, backups."""
        factory_reset = None
        response.set_cookie('us_session', session.token, httponly=True, samesite='strict', secure=False, max_age=43200)
        response.set_cookie('us_csrf', session.csrf, httponly=False, samesite='strict', secure=False, max_age=43200)
        db = get_db(session)
        cloud_restore = None
        if session.environment == 'production':
            cloud_restore = apply_pending_restore(root, db, session, cloud)
            if cloud_restore:
                db = get_db(session)
        try:  # 2.7.0: assinaturas antigas de frota viram uma por veículo (histórico dividido, totais iguais)
            from .fleet_split import split_all
            if split_all(db, session.slot)['split'] and session.environment == 'production':
                cloud.mark_dirty()
        except Exception:
            pass
        station = ensure_station(root, db) if session.environment == 'production' else None
        if session.environment == 'production':
            cloud.attach(session)
            keep_directory(session, db)
            try:
                cloud.purge_trash(session)
            except Exception:
                pass
            cloud.start()
            def _placa():
                try:
                    cloud.last_placa = time.time()
                    cloud.check_placa(session)
                except Exception as exc:
                    cloud.status['placa_error'] = str(exc)[:200]
            threading.Thread(target=_placa, daemon=True).start()
        media_recovery = recover_media_journals(root, db)
        if session.environment == 'production':
            rebuild_public(root, db)
        settings = {r['key']: r['value'] for r in db.query('SELECT key,value FROM settings')}
        backup_info = None
        backup_warning = None
        try:
            created = maybe_automatic_backup(root, db, session.vrk, retention=int(settings.get('backup_retention', 14)), db_key=session.db_key)
            backup_info = created.name if created else None
        except Exception as exc:
            backup_warning = str(exc)
        return {
            'slot': session.slot,
            'name': session.name,
            'environment': session.environment,
            **access_profile(session),
            'csrf': session.csrf,
            'station': station,
            'cloud_restore': cloud_restore,
            'factory_reset': factory_reset,
            'recovery_key': recovery_key,
            'media_recovery': media_recovery,
            'automatic_backup': backup_info,
            'backup_warning': backup_warning,
            **(extra or {}),
        }

    @app.post('/api/v1/session/environment')
    def session_environment(request: Request, response: Response, p: dict = Body(...)):
        """G-03 — Administrator only: enter the Teste database (local, never sent to the cloud) or go back to Real."""
        session = session_required(request, True); csrf_required(request, session)
        if not session.is_admin:
            raise HTTPException(403, 'administrator required')
        target = p.get('environment')
        new = auth.switch_environment(session, target)
        if session.environment == 'test':
            auth.logout(session.token)
        if target == 'production':
            old = auth.get_session(cloud.token)
            if old is not None and old.slot == new.slot and old.token != new.token:
                auth.logout(old.token)
            cloud.attach(new)
            cloud.start()
        response.set_cookie('us_session', new.token, httponly=True, samesite='strict', secure=False, max_age=43200)
        response.set_cookie('us_csrf', new.csrf, httponly=False, samesite='strict', secure=False, max_age=43200)
        db = get_db(new)
        station = ensure_station(root, db) if target == 'production' else None
        return {'slot': new.slot, 'name': new.name, 'environment': new.environment, **access_profile(new), 'csrf': new.csrf, 'station': station}

    # ------------------------------------------------------------------ G-04 Adm Local / Adm Global
    @app.post('/api/v1/auth/recover')
    def auth_recover(request: Request, p: dict = Body(...)):
        csrf_required(request)
        out = auth.recover(p.get('code', ''), p.get('new_password', ''))
        cloud.mark_dirty()
        return out

    def global_session(request: Request):
        session = session_required(request, True); csrf_required(request, session)
        if not session.is_global:
            raise HTTPException(403, 'Adm Global required')
        return session

    @app.post('/api/v1/admin-local/password')
    def admin_local_password(request: Request, p: dict = Body(...)):
        out = auth.reset_local_admin(global_session(request), p.get('new_password', ''))
        cloud.mark_dirty()  # accesses live in the cloud: the new password reaches every Servidor
        return out

    @app.post('/api/v1/admin-local/create')
    def admin_local_create(request: Request, p: dict = Body(...)):
        out = auth.create_local_admin(global_session(request), str(p.get('name', '')), str(p.get('password', '')))
        cloud.mark_dirty()  # accesses live in the cloud
        return out

    @app.post('/api/v1/admin-local/recovery-key')
    def admin_local_recovery(request: Request):
        code = auth.regenerate_recovery(global_session(request))
        cloud.mark_dirty()
        return {'recovery_key': code}

    @app.post('/api/v1/global/pass')
    def global_pass(request: Request):
        from . import adm_global
        session = global_session(request)
        trust = adm_global.load_trust(root)
        token = adm_global.current_token(root, trust)
        return {'pass': adm_global.make_pass(token, session.global_keys, hours=24), 'file': 'passe-adm-global.json'}

    @app.post('/api/v1/global/pin')
    def global_pin(request: Request, p: dict = Body(...)):
        """New PIN: a new Token Mestre goes to UserData/State for publishing in acesso-UStracker."""
        from . import adm_global
        session = global_session(request)
        if str(p.get('new_pin', '')) != str(p.get('pin_confirm', p.get('new_pin', ''))):
            raise ValueError('PIN confirmation does not match')
        token = adm_global.change_pin({'login': session.name}, session.global_keys, p.get('new_pin', ''))
        return {'ok': True, 'token': token, 'file': 'token-mestre.json'}  # downloaded by the browser, never left on disk

    @app.post('/api/v1/global/setup')
    def global_setup(request: Request, p: dict = Body(...)):
        """First time only (no Trust/adm-global.json yet): the owner chooses login + PIN on his own machine."""
        from . import adm_global
        session = session_required(request, True); csrf_required(request, session)
        if session.kind != 'admin' or adm_global.load_trust(root):
            raise HTTPException(403, 'setup not available')
        login_name = str(p.get('login', '')).strip()
        if not login_name or login_name.casefold() in {str(a.get('name') or '').casefold() for a in auth.setup_status()['admins']} \
                or login_name.casefold() in {u['name'].casefold() for u in auth.list_users()}:
            raise ValueError('choose a login name that nobody uses')
        if str(p.get('pin', '')) != str(p.get('pin_confirm', '')):
            raise ValueError('PIN confirmation does not match')
        trust, token, _ = adm_global.create(login_name, p.get('pin', ''), url=adm_global.DEFAULT_URL, read_token='')
        adm_global.save_trust(root, trust)
        auth.ensure_global_wrap(session, trust)
        cloud.mark_dirty()
        return {'ok': True, 'login': login_name, 'token': token, 'file': 'token-mestre.json'}

    # ------------------------------------------------------------------ G-05 atualização pela nuvem
    @app.get('/api/v1/update/status')
    def update_status(request: Request):
        session = session_required(request)
        st = dict(updates.state)
        st['current'] = product_version
        st['can_apply'] = update_can_apply(st, is_admin=session.is_admin, permissions=session.permissions)
        return st

    @app.post('/api/v1/update/apply-now')
    def update_apply_now(request: Request):
        session = session_required(request, True); csrf_required(request, session)
        st = dict(updates.state)
        if not update_can_apply(st, is_admin=session.is_admin, permissions=session.permissions):
            raise HTTPException(403, 'permission denied')
        if not st.get('downloaded'):
            updates.download()
        try:
            cloud.flush(timeout=60)
        except Exception:
            pass
        cloud.stop(); updates.stop()
        updates.restart()
        if app.state.server is not None:
            def stop(): time.sleep(.3); app.state.server.should_exit = True
            threading.Thread(target=stop, daemon=True).start()
        return {'ok': True, 'restarting': True, 'version': st.get('version')}

    @app.post('/api/v1/auth/logout')
    def logout(request: Request, response: Response):
        session = session_required(request)
        csrf_required(request, session)
        if session.environment == 'production':
            try: cloud.flush(timeout=30)
            except Exception: pass
        cloud.detach(session.token)
        auth.logout(session.token)
        response.delete_cookie('us_session')
        response.delete_cookie('us_csrf')
        return {'ok': True}

    @app.get('/api/v1/auth/me')
    def me(request: Request):
        session = session_required(request, True)
        station = ensure_station(root, get_db(session)) if session.environment == 'production' else None
        return {'slot': session.slot, 'name': session.name, 'environment': session.environment, **access_profile(session), 'setup': auth.setup_status(), 'station': station}

    # ------------------------------------------------------------------ U-01..U-04 usuários e pacotes
    def access_profile(session) -> dict:
        from .access import ALL
        perms = sorted(ALL) if session.is_admin else sorted(session.permissions)
        return {'kind': session.kind, 'role': session.package_title, 'package': session.package, 'permissions': perms,
                'is_global': session.is_global, 'must_change': session.must_change}

    def admin_required(request: Request):
        session = session_required(request, True)
        if not session.is_admin:
            raise HTTPException(403, 'administrator required')
        return session

    def manage_required(request: Request):
        session = session_required(request, True)
        if not session.can('users.manage'):
            raise HTTPException(403, 'administrator required')
        return session

    @app.get('/api/v1/access')
    def access_catalog(request: Request):
        session_required(request, True)
        return describe_access()

    @app.get('/api/v1/users')
    def users_list(request: Request):
        session = manage_required(request)
        packages = [{**pk, 'allowed': session.is_admin or 'system' not in pk['permissions']} for pk in auth.list_packages()]
        allowed = {pk['id'] for pk in packages if pk['allowed']}
        return {'items': [u for u in auth.list_users() if u['package_id'] in allowed], 'packages': packages, **describe_access(),
                'can_packages': session.is_admin, 'global_users': auth.global_users()}

    @app.post('/api/v1/users', status_code=201)
    def users_create(request: Request, p: dict = Body(...)):
        session = manage_required(request); csrf_required(request, session)
        out = auth.create_user(session, p); cloud.mark_dirty(); return out

    @app.patch('/api/v1/users/{user_id}')
    def users_update(user_id: int, request: Request, p: dict = Body(...)):
        session = manage_required(request); csrf_required(request, session)
        out = auth.update_user(session, user_id, p); cloud.mark_dirty(); return out

    @app.post('/api/v1/packages', status_code=201)
    def packages_create(request: Request, p: dict = Body(...)):
        session = admin_required(request); csrf_required(request, session)
        out = auth.save_package(session, p); cloud.mark_dirty(); return out

    @app.patch('/api/v1/packages/{package_id}')
    def packages_update(package_id: str, request: Request, p: dict = Body(...)):
        session = admin_required(request); csrf_required(request, session)
        out = auth.save_package(session, p, package_id); cloud.mark_dirty(); return out

    @app.delete('/api/v1/packages/{package_id}')
    def packages_delete(package_id: str, request: Request):
        session = admin_required(request); csrf_required(request, session)
        out = auth.delete_package(session, package_id); cloud.mark_dirty(); return out

    @app.post('/api/v1/auth/change-password')
    def change_password(request: Request, response: Response, p: dict = Body(...)):
        session = session_required(request, True)
        csrf_required(request, session)
        auth.change_password(session, p.get('current_password', ''), p.get('new_password', ''))
        cloud.mark_dirty()
        response.delete_cookie('us_session')
        response.delete_cookie('us_csrf')
        return {'ok': True, 'session_revoked': True}

    @app.post('/api/v1/auth/reset-admin/{slot}')
    def reset_admin(slot: int, request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        csrf_required(request, session)
        ticket = auth.reset_admin(session, slot, p.get('reason', ''))
        return {'slot': slot, 'ticket': ticket, 'expires_in_seconds': 900}

    @app.get('/api/v1/clients')
    def clients(request: Request):
        return {'items': list_clients(get_db(session_required(request, True)))}  # 2.6: sem corte em 500 (a tela pagina)

    @app.get('/api/v1/entities/clients')
    def client_entities(request: Request, q: str = Query(default=''), limit: int = Query(default=20)):
        session=session_required(request, True)
        bounded=max(1,min(int(limit),30))
        return {'items':search_client_entities(get_db(session),q,limit=bounded),'query':q,'limit':bounded}

    @app.post('/api/v1/clients', status_code=201)
    def clients_create(request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        def action(db):
            rec = create_client(db, session.slot, p)
            if session.environment == 'production': rebuild_public(root, db)
            return rec
        return mutation(request, session, 'POST /clients', p, action)

    @app.patch('/api/v1/clients/{cid}')
    def clients_update(cid: str, request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        if str(p.get('status') or '').upper() == 'CANCELLED' and not session.can('clients.delete'):
            raise HTTPException(403, 'permission denied')
        def action(db):
            rec = update_client(db, session.slot, cid, p)
            if session.environment == 'production': rebuild_public(root, db)
            return rec
        return mutation(request, session, f'PATCH /clients/{cid}', p, action)

    @app.get('/api/v1/clients/{cid}/export')
    def client_export(cid: str, request: Request):
        """2.6 LGPD — todos os dados de um cliente num .zip (JSON + página para imprimir/PDF + fotos). Só administradores."""
        session = admin_required(request)
        from . import retention
        blob, name = retention.export_client(root, get_db(session), session.media_key, cid)
        with get_db(session).transaction() as con:
            from .services import audit
            audit(con, session.slot, 'CLIENT_EXPORT', 'client', cid, None, {'exported': True})
        return Response(blob, media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="{name}"'})

    @app.get('/api/v1/clients/{cid}/profile')
    def clients_profile(cid: str, request: Request):
        return client_profile(get_db(session_required(request, True)), cid)


    @app.get('/api/v1/clients/{cid}/documents')
    def clients_documents(cid: str, request: Request):
        return {'items': list_client_documents(get_db(session_required(request, True)), cid)}

    @app.post('/api/v1/clients/{cid}/documents', status_code=201)
    def clients_documents_create(cid: str, request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, f'POST /clients/{cid}/documents', p,
                        lambda db: create_client_document(db, session.slot, cid, p))

    @app.get('/api/v1/clients/{cid}/companies')
    def clients_companies(cid: str, request: Request):
        return {'items': list_client_companies(get_db(session_required(request, True)), cid)}

    @app.post('/api/v1/clients/{cid}/companies', status_code=201)
    def clients_companies_create(cid: str, request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, f'POST /clients/{cid}/companies', p,
                        lambda db: create_client_company(db, session.slot, cid, p))

    @app.post('/api/v1/clients/archive')
    def clients_archive(request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        client_ids = p.get('client_ids') or []
        def action(db):
            result = archive_clients(db, session.slot, client_ids)
            if session.environment == 'production': rebuild_public(root, db)
            return result
        return mutation(request, session, 'POST /clients/archive', p, action)

    @app.get('/api/v1/mobility')
    def mobility(request: Request, client_id: str | None = None, fleet_id: str | None = None, plate: str | None = None,
                 company_id: str | None = None, group: str | None = None):
        db = get_db(session_required(request, True))
        return list_mobility(db, client_id=client_id, fleet_id=fleet_id, plate=plate, company_id=company_id, group=group)

    @app.get('/api/v1/mobility/subscriptions')
    def mobility_subscriptions(request: Request, vehicle_id: str | None = None, fleet_id: str | None = None):
        db = get_db(session_required(request, True))
        return mobility_subscription_detail(db, vehicle_id=vehicle_id, fleet_id=fleet_id)

    @app.get('/api/v1/fleets/{fid}/profile')
    def fleet_profile_route(fid: str, request: Request):
        return fleet_profile(get_db(session_required(request, True)), fid)

    @app.patch('/api/v1/fleets/{fid}')
    def fleet_update(fid: str, request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, f'PATCH /fleets/{fid}', p, lambda db: update_fleet(db, session.slot, fid, p))

    @app.get('/api/v1/vehicles/{vid}/transfer-cases')
    def vehicle_transfer_cases(vid: str, request: Request):
        return {'items': list_transfer_cases(get_db(session_required(request, True)), vid)}

    @app.post('/api/v1/vehicles/{vid}/transfer-cases', status_code=201)
    def vehicle_transfer_case_create(vid: str, request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, f'POST /vehicles/{vid}/transfer-cases', p, lambda db: create_transfer_case(db, session.slot, vid, p))

    @app.post('/api/v1/vehicle-transfer-cases/{case_id}/cancel')
    def vehicle_transfer_case_cancel(case_id: str, request: Request):
        session = session_required(request, True)
        return mutation(request, session, f'POST /vehicle-transfer-cases/{case_id}/cancel', {}, lambda db: cancel_transfer_case(db, session.slot, case_id))

    @app.post('/api/v1/vehicle-transfer-cases/{case_id}/complete')
    def vehicle_transfer_case_complete(case_id: str, request: Request):
        session = session_required(request, True)
        return mutation(request, session, f'POST /vehicle-transfer-cases/{case_id}/complete', {}, lambda db: complete_transfer_case(db, session.slot, case_id))

    @app.get('/api/v1/fleets')
    def fleets(request: Request, client_id: str | None = None, limit: int = 100):
        db = get_db(session_required(request, True))
        bounded = max(1, min(int(limit or 100), 100))
        if client_id:
            return {'items': list_table(db, 'fleets', 'client_id=? AND archived=0', (client_id,), 'name ASC', bounded)}
        return {'items': list_table(db, 'fleets', 'archived=0', (), 'name ASC', bounded)}

    @app.post('/api/v1/fleets', status_code=201)
    def fleets_create(request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, 'POST /fleets', p, lambda db: create_fleet(db, session.slot, p))

    @app.get('/api/v1/vehicles')
    def vehicles(request: Request):
        return {'items': list_table(get_db(session_required(request, True)), 'vehicles', limit=20000)}

    @app.post('/api/v1/vehicles', status_code=201)
    def vehicles_create(request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, 'POST /vehicles', p, lambda db: create_vehicle(db, session.slot, p))

    @app.get('/api/v1/vehicles/plate-check')
    def vehicles_plate_check(request: Request, plate: str = ''):
        return check_plate(get_db(session_required(request, True)), plate)

    @app.delete('/api/v1/vehicles/{vid}')
    def vehicles_delete(vid: str, request: Request):
        session = session_required(request, True)
        return mutation(request, session, f'DELETE /vehicles/{vid}', {}, lambda db: delete_vehicle(db, session.slot, vid))

    @app.delete('/api/v1/fleets/{fid}')
    def fleets_delete(fid: str, request: Request, mode: str = 'detach'):
        session = session_required(request, True)
        return mutation(request, session, f'DELETE /fleets/{fid}', {'mode': mode}, lambda db: delete_fleet(db, session.slot, fid, mode))

    @app.get('/api/v1/vehicles/{vid}/ownerships')
    def vehicle_ownerships(vid: str, request: Request):
        db = get_db(session_required(request, True))
        return {'items': [dict(r) for r in db.query('SELECT * FROM ownerships WHERE vehicle_id=? ORDER BY effective_from DESC', (vid,))]}

    @app.post('/api/v1/vehicles/{vid}/move')
    def vehicle_move(vid: str, request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, f'POST /vehicles/{vid}/move', p, lambda db: move_vehicle(db, session.slot, vid, p))

    @app.post('/api/v1/vehicles/{vid}/transfer')
    def vehicle_transfer(vid: str, request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, f'POST /vehicles/{vid}/transfer', p, lambda db: transfer_vehicle(db, session.slot, vid, p))

    @app.get('/api/v1/finance')
    def finance(request: Request):
        session = session_required(request, True)
        out = finance_snapshot(get_db(session))
        if not session.can('expenses.view'):
            for key in ('expenses', 'disbursements', 'realized_expenses_cents', 'cash_result_cents', 'recurring_pending'):
                out.pop(key, None)
        if not session.can('fiscal.view'):
            out.pop('fiscal', None)
        if not session.can('finance.view'):
            for key in ('payments', 'active_payments', 'realized_received_cents', 'charges', 'receivables'):
                out.pop(key, None)
        return out

    @app.post('/api/v1/fiscal/{fiscal_id}/ensure-expense')
    def fiscal_ensure_expense(fiscal_id: str, request: Request):
        session = session_required(request, True)
        payload = {'fiscal_id': fiscal_id}
        return mutation(request, session, f'POST /fiscal/{fiscal_id}/ensure-expense', payload, lambda db: ensure_fiscal_expense(db, session.slot, fiscal_id))

    @app.get('/api/v1/commercial')
    def commercial(request: Request):
        session = session_required(request, True)
        out = commercial_snapshot(get_db(session))
        return out if session.can('catalog.costs') else strip_costs(out)

    @app.post('/api/v1/commercial/coverage', status_code=201)
    def commercial_coverage(request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, 'POST /commercial/coverage', p, lambda db: create_coverage(db, session.slot, p))

    @app.get('/api/v1/catalog')
    def catalog(request: Request):
        session = session_required(request, True)
        out = {'items': list_catalog(get_db(session))}
        return out if session.can('catalog.costs') else strip_costs(out)

    @app.post('/api/v1/catalog', status_code=201)
    def catalog_create(request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        def action(db):
            rec = create_catalog(db, session.slot, p)
            if session.environment == 'production': rebuild_public(root, db)
            return rec
        return mutation(request, session, 'POST /catalog', p, action)

    @app.patch('/api/v1/catalog/{catalog_id}')
    def catalog_update(catalog_id: str, request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        if not session.can('catalog.costs'):
            p = {k: v for k, v in p.items() if k not in ('cost', 'cost_components')}  # cannot see costs → cannot change them
        def action(db):
            rec = update_catalog(db, session.slot, catalog_id, p)
            if session.environment == 'production': rebuild_public(root, db)
            return rec
        return mutation(request, session, f'PATCH /catalog/{catalog_id}', p, action)

    @app.delete('/api/v1/catalog/{catalog_id}')
    def catalog_delete(catalog_id: str, request: Request):
        session = session_required(request, True)
        def action(db):
            rec = remove_catalog_item(db, session.slot, catalog_id)
            if session.environment == 'production': rebuild_public(root, db)
            return rec
        return mutation(request, session, f'DELETE /catalog/{catalog_id}', {'id': catalog_id}, action)

    @app.get('/api/v1/catalog/{catalog_id}/prices')
    def catalog_prices(catalog_id: str, request: Request):
        db = get_db(session_required(request, True))
        return {'items': [dict(r) for r in db.query('SELECT * FROM catalog_prices WHERE catalog_id=? ORDER BY effective_from DESC', (catalog_id,))]}

    @app.get('/api/v1/subscriptions')
    def subscriptions(request: Request):
        return {'items': list_subscriptions(get_db(session_required(request, True)), limit=500)}

    @app.post('/api/v1/subscriptions', status_code=201)
    def subscriptions_create(request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, 'POST /subscriptions', p, lambda db: create_subscription(db, session.slot, p))

    @app.patch('/api/v1/subscriptions/{sid}/status')
    def subscriptions_status(sid: str, request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        if str(p.get('lifecycle_status') or '').upper() in {'CANCELLED', 'ENDED'} and not session.can('commercial.delete'):
            raise HTTPException(403, 'permission denied')
        return mutation(request, session, f'PATCH /subscriptions/{sid}/status', p, lambda db: set_subscription_status(db, session.slot, sid, p))

    @app.patch('/api/v1/subscriptions/{sid}')
    def subscriptions_amend(sid: str, request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, f'PATCH /subscriptions/{sid}', p, lambda db: amend_subscription(db, session.slot, sid, p))

    @app.post('/api/v1/subscriptions/{sid}/charges/{competence}')
    def charge_generate(sid: str, competence: str, request: Request):
        session = session_required(request, True)
        payload = {'subscription_id': sid, 'competence': competence}
        return mutation(request, session, f'POST /subscriptions/{sid}/charges/{competence}', payload, lambda db: generate_charge(db, session.slot, sid, competence))

    @app.get('/api/v1/direct-sales')
    def direct_sales_list(request: Request):
        return {'items': list_direct_sales(get_db(session_required(request, True)))}

    @app.post('/api/v1/direct-sales', status_code=201)
    def direct_sales_create(request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, 'POST /direct-sales', p,
                        lambda db: create_direct_sale(db, session.slot, p))

    @app.patch('/api/v1/direct-sales/{sale_id}/status')
    def direct_sales_status(sale_id: str, request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        if str(p.get('status') or '').upper() == 'CANCELLED' and not session.can('commercial.delete'):
            raise HTTPException(403, 'permission denied')
        return mutation(request, session, f'PATCH /direct-sales/{sale_id}/status', p,
                        lambda db: set_direct_sale_status(db, session.slot, sale_id, p))

    @app.get('/api/v1/charges')
    def charges(request: Request):
        return {'items': list_table(get_db(session_required(request, True)), 'charges', order='due_on DESC', limit=500)}

    @app.get('/api/v1/charges/{charge_id}/adjustments')
    def charge_adjustments(charge_id: str, request: Request):
        db = get_db(session_required(request, True))
        return {'items': [dict(r) for r in db.query('SELECT * FROM charge_adjustments WHERE charge_id=? ORDER BY effective_on DESC', (charge_id,))]}

    @app.post('/api/v1/charges/{charge_id}/adjustments', status_code=201)
    def charge_adjustment_create(charge_id: str, request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, f'POST /charges/{charge_id}/adjustments', p, lambda db: add_charge_adjustment(db, session.slot, charge_id, p))

    @app.get('/api/v1/payments')
    def payments(request: Request):
        return {'items': list_table(get_db(session_required(request, True)), 'payments', order='paid_on DESC', limit=500)}

    @app.post('/api/v1/payments', status_code=201)
    def payments_create(request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, 'POST /payments', p, lambda db: create_payment(db, session.slot, p))

    # AJ-12 — one-click subscription payment
    @app.get('/api/v1/billing/clients/{client_id}')
    def billing_client(client_id: str, request: Request):
        return client_payment_options(get_db(session_required(request, True)), client_id)

    @app.get('/api/v1/billing/subscriptions/{sid}')
    def billing_subscription(sid: str, request: Request):
        return subscription_payment_status(get_db(session_required(request, True)), sid)

    @app.post('/api/v1/billing/payments', status_code=201)
    def billing_payment(request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, 'POST /billing/payments', p, lambda db: register_subscription_payment(db, session.slot, p))

    @app.post('/api/v1/billing/fleet-payments', status_code=201)
    def billing_fleet_payment(request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, 'POST /billing/fleet-payments', p, lambda db: register_fleet_payment(db, session.slot, p))

    @app.post('/api/v1/payments/{pid}/reverse')
    def payments_reverse(pid: str, request: Request, p: dict = Body(default={})):
        session = session_required(request, True)
        return mutation(request, session, f'POST /payments/{pid}/reverse', p, lambda db: reverse_payment(db, session.slot, pid))

    @app.get('/api/v1/credits')
    def credits(request: Request):
        return {'items': list_table(get_db(session_required(request, True)), 'credits', limit=500)}

    @app.post('/api/v1/credits/{credit_id}/apply')
    def credits_apply(credit_id: str, request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, f'POST /credits/{credit_id}/apply', p, lambda db: apply_credit(db, session.slot, credit_id, p.get('charge_id', ''), p.get('amount', '0')))

    @app.get('/api/v1/expenses')
    def expenses(request: Request):
        return {'items': list_table(get_db(session_required(request, True)), 'expenses', limit=500)}

    @app.post('/api/v1/expenses', status_code=201)
    def expenses_create(request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        # AJ-13: the simple form (repeat + amount) creates a company expense; the legacy contract is kept.
        if 'repeat' in p or 'amount' in p:
            return mutation(request, session, 'POST /expenses', p, lambda db: create_company_expense(db, session.slot, p))
        return mutation(request, session, 'POST /expenses', p, lambda db: create_expense(db, session.slot, p))

    @app.post('/api/v1/expenses/recurring/run')
    def expenses_recurring_run(request: Request):
        session = session_required(request, True)
        return mutation(request, session, 'POST /expenses/recurring/run', {}, lambda db: run_recurring_expenses(db, session.slot))

    @app.post('/api/v1/expenses/{eid}/pay')
    def expenses_pay(eid: str, request: Request, p: dict = Body(default={})):
        session = session_required(request, True)
        return mutation(request, session, f'POST /expenses/{eid}/pay', p, lambda db: pay_expense(db, session.slot, eid, p))

    @app.post('/api/v1/expenses/{eid}/stop-repeat')
    def expenses_stop(eid: str, request: Request):
        session = session_required(request, True)
        return mutation(request, session, f'POST /expenses/{eid}/stop-repeat', {'id': eid}, lambda db: stop_recurring_expense(db, session.slot, eid))

    @app.post('/api/v1/expenses/{eid}/convert-sale', status_code=201)
    def expenses_convert(eid: str, request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, f'POST /expenses/{eid}/convert-sale', p, lambda db: convert_expense_to_sale(db, session.slot, eid, p))

    @app.patch('/api/v1/expenses/{eid}')
    def expenses_update(eid: str, request: Request, p: dict = Body(...)):
        from .expenses import update_expense
        session = session_required(request, True)
        return mutation(request, session, f'PATCH /expenses/{eid}', p, lambda db: update_expense(db, session.slot, eid, p))

    @app.delete('/api/v1/expenses/{eid}')
    def expenses_delete(eid: str, request: Request):
        session = session_required(request, True)
        return mutation(request, session, f'DELETE /expenses/{eid}', {'id': eid}, lambda db: delete_expense(db, session.slot, eid))

    @app.get('/api/v1/expenses/{eid}/disbursements')
    def expense_disbursements(eid: str, request: Request):
        db = get_db(session_required(request, True))
        return {'items': [dict(r) for r in db.query('SELECT * FROM disbursements WHERE expense_id=? ORDER BY paid_on DESC', (eid,))]}

    @app.post('/api/v1/expenses/{eid}/disbursements', status_code=201)
    def expenses_disburse(eid: str, request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, f'POST /expenses/{eid}/disbursements', p, lambda db: add_disbursement(db, session.slot, eid, p))

    @app.post('/api/v1/disbursements/{did}/reverse')
    def disbursements_reverse(did: str, request: Request, p: dict = Body(default={})):
        session = session_required(request, True)
        return mutation(request, session, f'POST /disbursements/{did}/reverse', p, lambda db: reverse_disbursement(db, session.slot, did))

    @app.post('/api/v1/expenses/{eid}/recur/{competence}')
    def expenses_recur(eid: str, competence: str, request: Request):
        session = session_required(request, True)
        payload = {'source_expense_id': eid, 'competence': competence}
        return mutation(request, session, f'POST /expenses/{eid}/recur/{competence}', payload, lambda db: generate_recurring_expense(db, session.slot, eid, competence))

    @app.get('/api/v1/fiscal')
    def fiscal(request: Request):
        return {'items': list_table(get_db(session_required(request, True)), 'fiscal_obligations', limit=500)}

    @app.post('/api/v1/fiscal', status_code=201)
    def fiscal_create(request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, 'POST /fiscal', p, lambda db: create_fiscal(db, session.slot, p))

    @app.get('/api/v1/dashboard')
    def dashboard_get(request: Request, q: str = Query(default=''), year: int | None = Query(default=None)):
        session = session_required(request, True)
        db = get_db(session)
        out = {**dashboard(db, year=year), **dashboard_extended(db), 'client_activity': client_activity_overview(db, q)}
        if not session.can('dashboard.full'):
            out = restrict_dashboard(out)
        return out

    @app.get('/api/v1/dashboard/drilldown')
    def dashboard_drilldown(request: Request, year: int | None = Query(default=None)):
        from .projections import overview_drilldown
        return overview_drilldown(get_db(session_required(request, True)), year)

    @app.get('/api/v1/search')
    def search_get(q: str, request: Request):
        return {'items': search(get_db(session_required(request, True)), q)}

    @app.get('/api/v1/settings')
    def settings_get(request: Request):
        db = get_db(session_required(request, True))
        return {r['key']: r['value'] for r in db.query('SELECT key,value FROM settings')}

    @app.put('/api/v1/settings')
    def settings_put(request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        allowed = {
            'company_legal_name','company_display_name','contact_phone','contact_email','address_display',
            'default_grace_days','theme_primary','theme_accent','backup_retention',
        }
        def action(db):
            with db.transaction() as con:
                for k, v in p.items():
                    if k not in allowed: raise ValueError(f'setting not allowed: {k}')
                    if k == 'backup_retention' and not (1 <= int(v) <= 100): raise ValueError('backup_retention must be 1..100')
                    con.execute("INSERT OR REPLACE INTO settings(key,value,updated_at) VALUES(?,?,datetime('now'))", (k, str(v)))
            if session.environment == 'production': rebuild_public(root, db)
            return {'ok': True}
        return mutation(request, session, 'PUT /settings', p, action)

    @app.post('/api/v1/branding/{kind}', status_code=201)
    async def branding_upload(kind: str, request: Request, file: UploadFile = File(...)):
        session = session_required(request, True)
        db = authorize_file_mutation(request, session)
        data = await file.read()
        rec = store_brand_asset(root, kind, data)
        if session.environment == 'production': rebuild_public(root, db)
        return rec

    @app.get('/api/v1/media')
    def media_list(request: Request, entity_type: str | None = None, entity_id: str | None = None):
        db = get_db(session_required(request, True))
        where = []
        args = []
        if entity_type:
            where.append('entity_type=?'); args.append(entity_type)
        if entity_id:
            where.append('entity_id=?'); args.append(entity_id)
        sql = 'SELECT id,entity_type,entity_id,(SELECT lc.code FROM logical_codes lc WHERE lc.entity_id=media.entity_id ORDER BY lc.retired_at IS NOT NULL,lc.issued_at DESC LIMIT 1) AS entity_code,mime,width,height,sha256,created_at FROM media'
        if where: sql += ' WHERE ' + ' AND '.join(where)
        sql += ' ORDER BY created_at DESC LIMIT 500'
        return {'items': [dict(r) for r in db.query(sql, tuple(args))]}

    @app.post('/api/v1/media/{entity_type}/{entity_id}', status_code=201)
    async def media_upload(entity_type: str, entity_id: str, request: Request, file: UploadFile = File(...), retain_original: bool = False):
        session = session_required(request, True)
        db = authorize_file_mutation(request, session)
        entity_id = resolve_entity_ref(db, entity_type, entity_id)
        data = await file.read()
        return store_media(root, db, session.slot, session.media_key, entity_type, entity_id, data, retain_original)

    @app.get('/api/v1/media/{mid}/{variant}')
    def media_get(mid: str, variant: str, request: Request):
        session = session_required(request, True)
        data, mime = load_media(root, get_db(session), session.media_key, mid, variant)
        return Response(data, media_type=mime, headers={'Cache-Control': 'no-store'})

    @app.delete('/api/v1/media/{mid}')
    def media_delete(mid: str, request: Request):
        session = session_required(request, True)
        return mutation(request, session, f'DELETE /media/{mid}', {'id': mid}, lambda db: remove_media(root, db, session.slot, mid))

    @app.get('/api/v1/attachments')
    def attachments_list(request: Request, entity_type: str | None = None, entity_id: str | None = None):
        db = get_db(session_required(request, True))
        return {'items': list_attachments(db, entity_type, entity_id)}

    @app.post('/api/v1/attachments/{entity_type}/{entity_id}', status_code=201)
    async def attachment_upload(entity_type: str, entity_id: str, request: Request, file: UploadFile = File(...)):
        session = session_required(request, True)
        db = authorize_file_mutation(request, session)
        entity_id = resolve_entity_ref(db, entity_type, entity_id)
        data = await file.read()
        return store_attachment(root, db, session.slot, session.media_key, entity_type, entity_id, file.filename or 'attachment', file.content_type, data)

    @app.post('/api/v1/attachments/link', status_code=201)
    def attachment_link_create(request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, 'POST /attachments/link', p, lambda db: store_link(db, session.slot, p.get('entity_type'), resolve_entity_ref(db, p.get('entity_type'), p.get('entity_id')), p.get('url'), p.get('filename')))

    @app.get('/api/v1/attachments/{attachment_id}')
    def attachment_download(attachment_id: str, request: Request):
        session = session_required(request, True)
        data, mime, filename = load_attachment(root, get_db(session), session.media_key, attachment_id)
        safe = Path(filename).name.replace('\"', '').replace('\r', '').replace('\n', '') or 'attachment'
        return Response(data, media_type=mime, headers={'Cache-Control':'no-store','Content-Disposition':f'attachment; filename="{safe}"'})

    @app.get('/api/v1/reports/{name}.csv')
    def report_csv_get(name: str, request: Request):
        if name not in REPORTS: raise KeyError('report not found')
        data = report_csv(get_db(session_required(request, True)), name)
        return Response(data, media_type='text/csv; charset=utf-8', headers={'Content-Disposition': f'attachment; filename="{name}.csv"'})

    @app.get('/api/v1/reports/{name}.xlsx')
    def report_xlsx_get(name: str, request: Request):
        if name not in REPORTS: raise KeyError('report not found')
        data = report_xlsx(get_db(session_required(request, True)), name)
        return Response(data, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition': f'attachment; filename="{name}.xlsx"'})

    @app.get('/api/v1/backups')
    def backups(request: Request):
        session_required(request, True)
        directory = root/'UserData'/'Backups'; directory.mkdir(parents=True, exist_ok=True)
        return {'items': [{'name':p.name,'size':p.stat().st_size,'modified_at':datetime.fromtimestamp(p.stat().st_mtime).isoformat()} for p in sorted(directory.glob('*.usbk'), key=lambda p:p.stat().st_mtime, reverse=True)]}

    @app.post('/api/v1/backups', status_code=201)
    def backup_create(request: Request):
        session = session_required(request, True)
        csrf_required(request, session)
        path = create_backup(root, get_db(session), session.vrk)
        settings = {r['key']: r['value'] for r in get_db(session).query('SELECT key,value FROM settings')}
        prune_backups(root, session.environment, int(settings.get('backup_retention', 14)))
        return {'name': path.name, 'size': path.stat().st_size}

    @app.post('/api/v1/backups/restore')
    async def backup_restore(request: Request, file: UploadFile = File(...)):
        session = session_required(request, True)
        db = authorize_file_mutation(request, session)
        raw = await file.read()
        temp = root/'UserData'/'Backups'/'_restore_upload.usbk'; temp.parent.mkdir(parents=True, exist_ok=True); temp.write_bytes(raw)
        try:
            verify_backup(temp, session.vrk)
            restore_backup(root, db, session.vrk, temp)
        finally:
            temp.unlink(missing_ok=True)
        if session.environment == 'production': rebuild_public(root, get_db(session))
        return {'ok': True}

    @app.post('/api/v1/recovery/export', status_code=201)
    def recovery_export(request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        csrf_required(request, session)
        if session.environment != 'production': raise ValueError('recovery export must be started from Production')
        db = get_db(session)
        transfer = bool(p.get('transfer'))
        if transfer: require_writer(root, db)
        out_dir = root/'UserData'/'Backups'/'Recovery'; out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir/f"UStracker_recovery_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.usre"
        relinquished = False
        try:
            transfer_info = relinquish_writer(root, db) if transfer else None
            relinquished = transfer
            export_recovery(root, out, p.get('passphrase', ''))
            return {'name': out.name, 'size': out.stat().st_size, 'transfer': transfer_info}
        except Exception:
            if relinquished: reclaim_writer_after_failed_transfer(root, db)
            raise

    @app.get('/api/v1/recovery/{name}')
    def recovery_download(name: str, request: Request):
        session_required(request, True)
        safe = Path(name).name
        if safe != name or not safe.endswith('.usre'): raise ValueError('invalid recovery file name')
        path = root/'UserData'/'Backups'/'Recovery'/safe
        if not path.exists(): raise KeyError('recovery package not found')
        return FileResponse(path, media_type='application/octet-stream', filename=safe)

    @app.get('/api/v1/stations')
    def stations(request: Request):
        session = session_required(request, True)
        if session.environment != 'production': return {'current_station_id': None, 'items': []}
        return list_stations(root, get_db(session))

    @app.post('/api/v1/stations/claim')
    def station_claim(request: Request, p: dict = Body(...)):
        session = session_required(request, True); csrf_required(request, session)
        return claim_pending_writer(root, get_db(session), p.get('confirm', ''))

    @app.post('/api/v1/stations/emergency-takeover')
    def station_emergency(request: Request, p: dict = Body(...)):
        session = session_required(request, True); csrf_required(request, session)
        return emergency_takeover(root, get_db(session), p.get('confirm', ''), p.get('reason', ''))

    @app.get('/api/v1/audit')
    def audit_list(request: Request, limit: int = Query(100, ge=1, le=500)):
        db = get_db(session_required(request, True))
        return {'items': [dict(r) for r in db.query('SELECT id,at,actor_slot,action,entity_type,entity_id,previous_hash,event_hash FROM audit_events ORDER BY id DESC LIMIT ?', (limit,))]}

    @app.get('/api/v1/audit/verify')
    def audit_verify(request: Request):
        return verify_audit_chain(get_db(session_required(request, True)))

    @app.post('/api/v1/sandbox/reset')
    def sandbox_reset(request: Request, p: dict = Body(...)):
        session = session_required(request, True); csrf_required(request, session)
        if session.environment != 'test' or p.get('confirm') != 'LIMPAR TESTES': raise ValueError('test session and exact confirmation required')
        db = get_db(session); db.path.unlink(missing_ok=True); shutil.rmtree(root/'UserData'/'Media'/'test', ignore_errors=True); shutil.rmtree(root/'UserData'/'Attachments'/'test', ignore_errors=True); repository.database('test', session.db_key)
        return {'ok': True}

    # ------------------------------------------------------------- C-04..C-06 nuvem e C-09 lixeira
    def cloud_session(request: Request, *, write: bool = False) -> Session:
        session = session_required(request, True)
        if session.environment != 'production':
            raise ValueError('cloud is available only in Production')
        if write:
            csrf_required(request, session)
            if not cloud.enabled():  # 2.6: com a nuvem ligada vale a vez de gravar (S-03), não a estação única antiga
                require_writer(root, get_db(session))
        cloud.attach(session)
        return session

    def CloudErrorHTTP(code: str, detail: str) -> HTTPException:  # noqa: N802 — reads like an exception at the raise site
        return HTTPException(502, detail={'code': f'CLOUD_{code}', 'detail': detail, 'message': detail})

    def cloud_call(fn):
        try:
            return fn()
        except CloudError as exc:
            raise HTTPException(409 if exc.code in ('CONFLICT', 'READ_ONLY', 'BUSY') else 502,
                                detail={'code': f'CLOUD_{exc.code}', 'detail': exc.detail, 'message': exc.detail}) from exc

    @app.get('/api/v1/cloud/status')
    def cloud_status(request: Request):
        session_required(request, True)
        return cloud.describe()

    @app.post('/api/v1/cloud/connect')
    def cloud_connect(request: Request, p: dict = Body(...)):
        session = cloud_session(request, write=True)
        return cloud_call(lambda: cloud.connect(session, p.get('url', ''), p.get('secret', ''), mode=p.get('mode')))

    @app.post('/api/v1/cloud/sync')
    def cloud_sync_now(request: Request, p: dict = Body(default={})):
        session = cloud_session(request, write=True)
        if p.get('force') and not session.is_global:
            raise HTTPException(403, 'Adm Global required')
        return cloud_call(lambda: cloud.sync_now(session, force=bool(p.get('force')) and p.get('confirm') == 'SUBSTITUIR NUVEM'))

    @app.post('/api/v1/cloud/disconnect')
    def cloud_disconnect(request: Request):
        cloud_session(request, write=True)
        cloud.state.set(enabled=False)
        return cloud.describe()

    @app.get('/api/v1/cloud/points')
    def cloud_points(request: Request):
        session = cloud_session(request)
        return {'items': cloud_call(lambda: cloud.points(session))}

    @app.post('/api/v1/cloud/points/{snapshot_id}/restore')
    def cloud_point_restore(snapshot_id: str, request: Request, p: dict = Body(default={})):
        session = cloud_session(request, write=True)
        if p.get('confirm') != 'RESTAURAR PONTO':
            raise ValueError('confirmation RESTAURAR PONTO required')
        out = cloud_call(lambda: cloud.restore_point(session, snapshot_id))
        rebuild_public(root, get_db(session))
        return out

    @app.post('/api/v1/cloud/restore')
    def cloud_restore(request: Request, p: dict = Body(...)):
        """C-05 — administrator only (Sistema › Nuvem › Avançado). New computers download by themselves (/auth/join)."""
        session = admin_session(request)
        csrf_required(request, session)
        if p.get('confirm') != 'RESTAURAR DA NUVEM':
            raise ValueError('confirmation RESTAURAR DA NUVEM required')
        out = cloud_call(lambda: restore_from_cloud(root, p.get('url', ''), p.get('secret', '')))
        auth._init_store()  # the cloud copy may come from an older version
        auth.clear_sessions()
        cloud.state = type(cloud.state)(root)
        cloud.pending_secret = str(p.get('secret', '')).strip()
        return out

    # ------------------------------------------------------------------ S-05..S-07 placa de direção
    placa_cache: dict = {}

    def placa_banks_public() -> dict | None:
        """Pre-login: read the signed placa (cached 60 s). None when this install has no placa."""
        from .placa import fetch_placa, load_bootstrap, read_placa
        boot = load_bootstrap(root)
        if not boot or not boot.get('placa_url'):
            return None
        if placa_cache.get('at', 0) > time.time() - 60:
            return placa_cache['value']
        value = read_placa(fetch_placa(boot['placa_url']), boot)
        placa_cache.update(at=time.time(), value=value)
        return value

    @app.get('/api/v1/cloud/bootstrap')
    def cloud_bootstrap():
        """New computer: which first screen? (no secrets in the answer)

        2.2.0 — with an Adm Global in Trust/, every new computer is ACTIVATED by the Adm Global (the company key
        is not in the installer any more). Without it (old installers), the first Administrator is created here."""
        from .adm_global import load_trust
        from .placa import load_bootstrap
        trust = load_trust(root)
        boot = load_bootstrap(root)
        return {'activation': bool(trust), 'available': bool(boot), 'global_login': trust['login'] if trust else None}

    activations: dict = {}

    def _activation_ticket(p: dict) -> dict:
        now = time.time()
        for key in [k for k, v in activations.items() if v['expires'] < now]:
            activations.pop(key, None)
        item = activations.get(str(p.get('ticket') or ''))
        if not item:
            raise ValueError('activation expired; sign in with the Adm Global again')
        return item

    @app.post('/api/v1/auth/activate')
    def auth_activate(request: Request, response: Response, p: dict = Body(...)):
        """2.2.0 — first use on a new computer: ONLY the Adm Global activates it.

        1) name + PIN, the fake question (answer = PIN) and the 30-minute lock, exactly like the normal sign in;
        2) the Token Mestre opens with the PIN → company key (company-key.json) → placa → company cloud;
        3a) the cloud has data: everything comes down and the Adm Global enters;
        3b) the cloud is empty (new company): the Adm Global creates the company Administrator next."""
        from . import adm_global
        from .cloud import CloudClient
        from .placa import fetch_placa, load_bootstrap, read_placa
        csrf_required(request)
        st = auth.setup_status()
        if st['activated']:
            raise ValueError('this computer is already activated; use the normal sign in')
        trust = adm_global.load_trust(root)
        if not trust:
            raise ValueError('this installation has no Adm Global')
        denied = {'error': 'INVALID', 'detail': 'invalid credentials'}
        ident = trust['login'].casefold()
        state = auth.global_lock_state(ident)
        if state['locked_minutes']:
            return JSONResponse({'error': 'LOCKED', 'detail': f"login temporarily locked; try again in {state['locked_minutes']} minutes",
                                 'retry_minutes': state['locked_minutes']}, status_code=429)
        if str(p.get('name', '')).strip().casefold() != ident:
            return JSONResponse({**denied, 'hint': auth.global_failure(ident, 'name')['hint']}, status_code=422)
        if 'answer' not in p:
            return {'challenge': auth.global_question(ident)}
        pin = str(p.get('password', ''))
        if str(p.get('answer', '')) != pin:
            return JSONResponse({**denied, 'hint': auth.global_failure(ident, 'answer')['hint']}, status_code=422)
        try:
            token = adm_global.current_token(root, trust)
            keys = adm_global.open_keys(token, pin, trust)
        except adm_global.AccessDenied as exc:
            if str(exc) == 'invalid credentials':
                return JSONResponse({**denied, 'hint': auth.global_failure(ident, 'pin')['hint']}, status_code=422)
            raise ValueError(f'Adm Global unavailable: {exc}') from exc
        # --- credentials verified: nothing was changed on this computer before this point
        try:
            doc = adm_global.fetch_company_key(trust)
        except OSError as exc:
            raise CloudErrorHTTP('OFFLINE', 'no internet: activation needs the internet once') from exc
        boot = load_bootstrap(root)
        company_key = adm_global.open_company_key(doc, keys) if doc else (boot or {}).get('company_key')
        banks, seq = [], 0
        if boot and company_key:
            try:
                placa = read_placa(fetch_placa(boot['placa_url']), boot, company_key)
            except ValueError as exc:
                raise CloudErrorHTTP('PLACA', str(exc)) from exc
            banks, seq = placa['banks'], placa['seq']
        has_data = False
        cloud_reset = False
        if banks:
            try:
                client = CloudClient(banks[0]['url'], banks[0]['key'])
                ping = client.call('ping', {}, retries=2, check_epoch=False)
                if int(ping.get('epoch') or 0) < CLOUD_EPOCH:
                    # 2.5.0: the first 2.5 activation starts the company clean ONCE (old cloud goes to _lixeira)
                    client.call('reset_company', {'epoch': CLOUD_EPOCH}, retries=1)
                    cloud_reset = True
                    ping = client.call('ping', {}, retries=2)
            except CloudError as exc:
                raise CloudErrorHTTP(exc.code, exc.detail) from exc
            has_data = bool(ping.get('head') and ping.get('auth_head'))
        if has_data:
            bank = banks[0]
            cloud_call(lambda: restore_from_cloud(root, bank['url'], bank['key']))
            auth._init_store()  # the cloud copy may come from an older version
            auth.clear_sessions()
            cloud.state = type(cloud.state)(root)
            cloud.pending_secret = bank['key']
            cloud.state.set(placa_seq=0)
            try:
                session = auth.global_session(trust, keys, 'production')
            except adm_global.AccessDenied:
                session = None
            if session is not None:
                out = enter(response, session, None, {'activated': True, 'restored': True, 'cloud_reset': False})
                try:
                    cloud.keep_company_key(session, company_key)
                except Exception:
                    pass
                return out
            # 2.5.0: every cloud of this epoch was started by the Adm Global (the old one went to _lixeira)
            raise CloudErrorHTTP('INVALID_CLOUD', 'the company cloud has no Adm Global access; contact support')
        # 3b) new company (empty cloud or no cloud): the Adm Global enters at once; the local admin is created inside (Sistema)
        session = auth.bootstrap_global(trust, keys, 'production')
        cloud_info = {'connected': False}
        if banks:
            if company_key:
                cloud.keep_company_key(session, company_key)
            cloud.apply_banks(session, banks, seq)
            cloud.mark_dirty()
        out = enter(response, session, None, {'activated': True, 'new_company': True, 'cloud_reset': cloud_reset})
        if banks:
            try:  # accesses and the empty base go up right now
                cloud_info = {'connected': True, **cloud.sync_now(session, force=True)}
            except Exception as exc:
                cloud_info = {'connected': True, 'error': str(exc)[:200]}
        out['cloud'] = cloud_info
        return out

    @app.post('/api/v1/auth/activate/admin')
    def auth_activate_admin():
        raise HTTPException(410, 'replaced in 2.3.0: the Adm Global creates the local admin in Sistema')

    @app.post('/api/v1/auth/join')
    def auth_join(request: Request):
        raise HTTPException(410, 'replaced by /auth/activate (Adm Global)')

    def admin_session(request: Request):
        session = session_required(request, True)
        if not session.is_admin:
            raise HTTPException(403, 'administrator required')
        return session

    @app.get('/api/v1/cloud/placa')
    def placa_get(request: Request):
        from .placa import load_bootstrap, render_form
        session = admin_session(request)
        banks = []
        if cloud.state.get('url') and cloud.state.get('secret'):
            banks.append({'url': cloud.state.get('url'), 'key': cloud.state.secret(session.vrk)})
        for m in cloud.state.get('mirrors') or []:
            banks.append({'url': m['url'], 'key': cloud.state.unseal(session.vrk, m['secret'])})
        boot = load_bootstrap(root) or {}
        gh = cloud.state.get('github') or {}
        return {'form': render_form(banks or [{'url': '', 'key': ''}]), 'seq': cloud.state.get('placa_seq') or 0,
                'placa_url': boot.get('placa_url') or '', 'github': {k: gh.get(k) for k in ('repo', 'path', 'branch')},
                'github_token_saved': bool(gh.get('token')), 'has_master': bool(cloud.master(session, get_db(session)))}

    @app.post('/api/v1/cloud/placa/publish')
    def placa_publish(request: Request, p: dict = Body(...)):
        from .placa import build_placa, github_publish, parse_form, raw_url, save_bootstrap
        session = admin_session(request); csrf_required(request, session)
        if session.environment != 'production':
            raise ValueError('cloud is available only in Production')
        banks = parse_form(p.get('form', ''))
        db = get_db(session)
        take_turn(session, db)
        master = cloud.master(session, db, create=True)
        seq = int(cloud.state.get('placa_seq') or 0) + 1
        placa = build_placa(banks, master, seq)
        gh = dict(cloud.state.get('github') or {})
        g = p.get('github') or {}
        for key in ('repo', 'path', 'branch'):
            if str(g.get(key) or '').strip():
                gh[key] = str(g[key]).strip()
        if str(g.get('token') or '').strip():
            gh['token'] = cloud.state.seal(session.vrk, str(g['token']).strip())
        cloud.state.set(github=gh)
        published = None
        url = str(p.get('placa_url') or '').strip()
        if gh.get('repo') and gh.get('token'):
            published = github_publish(placa, repo=gh['repo'], path=gh.get('path') or 'placa.json', branch=gh.get('branch') or 'main',
                                       token=cloud.state.unseal(session.vrk, gh['token']))
            url = raw_url(gh['repo'], gh.get('path') or 'placa.json', gh.get('branch') or 'main')
        bootstrap_saved = None
        if url:
            try:
                save_bootstrap(root, url=url, master=master)
                bootstrap_saved = True
            except OSError:  # Program Files: only the installer writes Trust/ (the next installer carries the new address)
                bootstrap_saved = False
            placa_cache.clear()
        applied = cloud.apply_banks(session, banks, seq)
        cloud.mark_dirty()
        return {'placa': placa, 'seq': seq, 'published': published, 'placa_url': url, 'applied': applied, 'bootstrap_saved': bootstrap_saved,
                'banks': [{'n': i, 'url': b['url']} for i, b in enumerate(banks, 1)]}

    @app.post('/api/v1/cloud/placa/check')
    def placa_check(request: Request):
        session = admin_session(request); csrf_required(request, session)
        return cloud_call(lambda: cloud.check_placa(session, force=True))

    @app.get('/api/v1/trash')
    def trash_list(request: Request):
        return {'items': list_trash(get_db(session_required(request, True))), 'retention_days': 14}

    @app.post('/api/v1/trash/{trash_id}/restore')
    def trash_restore(trash_id: str, request: Request):
        session = session_required(request, True)
        return mutation(request, session, f'POST /trash/{trash_id}/restore', {'id': trash_id}, lambda db: restore_trash(db, session.slot, trash_id))

    @app.get('/api/v1/integrations')
    def integrations(request: Request):
        session_required(request, True)
        return {'drive':{'enabled':cloud.enabled(),'implemented':True},'tracking':{'enabled':False,'implemented':False},'fiscal_official':{'enabled':False,'implemented':False}}

    # ------------------------------------------------------------------ 2.6 Diagnóstico (só administradores)
    def cloud_facts() -> dict:
        return {**cloud.describe(), 'pending_since': cloud.state.get('dirty_since')}

    @app.get('/api/v1/system/alerts')
    def system_alerts(request: Request):
        session = session_required(request)
        if not session.is_admin:
            return {'items': []}
        from . import diagnostics
        return {'items': diagnostics.alerts(root, cloud_facts())}

    @app.get('/api/v1/system/diagnostics')
    def system_diagnostics(request: Request):
        session = admin_required(request)
        from . import diagnostics
        users_active = sum(1 for u in auth.list_users() if u['active'])
        return {**diagnostics.snapshot(root, get_db(session), cloud_facts(), users_active), 'alerts': diagnostics.alerts(root, cloud_facts())}

    @app.get('/api/v1/system/support-package')
    def system_support_package(request: Request):
        session = admin_required(request)
        from . import diagnostics
        users_active = sum(1 for u in auth.list_users() if u['active'])
        blob = diagnostics.support_package(root, get_db(session), cloud_facts(), users_active)
        name = f"UStracker_suporte_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
        return Response(blob, media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="{name}"'})

    @app.get('/api/v1/system/runtime')
    def runtime_status(request: Request):
        session = session_required(request, True)
        journal_path = paths.state_root / 'update_journal.json'
        journal = None
        if journal_path.exists():
            try:
                journal = json.loads(journal_path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                journal = {'state': 'UNREADABLE'}
        return {
            'version': product_version,
            'schema_version': SCHEMA_VERSION,
            'app_root': str(paths.app_root),
            'data_root': str(paths.data_root),
            'cache_root': str(paths.cache_root),
            'backup_root': str(paths.backup_root),
            'log_root': str(paths.log_root),
            'environment': session.environment,
            'update': journal,
        }

    @app.post('/api/v1/integrations/{provider}/{action}')
    def integration_disabled(provider: str, action: str, request: Request):
        session = session_required(request, True); csrf_required(request, session)
        raise HTTPException(501, detail={'code':'INTEGRATION_NOT_IMPLEMENTED','provider':provider,'action':action})

    @app.post('/api/v1/shell/detach')
    def shell_detach():
        return {'ok': True}

    @app.post('/api/v1/system/shutdown')
    def shutdown(request: Request):
        session = auth.get_session(request.cookies.get('us_session'))
        csrf_required(request, session)  # 2.2.0: no anonymous shutdown
        try:
            cloud.flush(timeout=60)  # C-03: send pending changes before closing
        except Exception:
            pass
        cloud.stop()
        if app.state.server is not None:
            def stop(): time.sleep(.2); app.state.server.should_exit = True
            threading.Thread(target=stop, daemon=True).start()
        return {'ok': True, 'shutting_down': True}

    frontend = root/'frontend'
    if frontend.exists():
        app.mount('/assets', StaticFiles(directory=str(frontend)), name='assets')
        app.mount('/public-assets', StaticFiles(directory=str(asset_dir(root))), name='public-assets')
        @app.get('/', response_class=HTMLResponse)
        def index(): return (frontend/'index.html').read_text(encoding='utf-8')
    else:
        @app.get('/', response_class=HTMLResponse)
        def index_missing(): return '<html><body><h1>UStracker</h1><p>Frontend not packaged.</p></body></html>'
    return app


def run(root: Path | str, port: int = 0):
    paths = ProductPaths.from_root(root); paths.ensure_runtime_directories(); root = paths.app_root; state_dir = paths.state_root; port_file = state_dir/'backend.json'
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM); sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    for attempt in range(50):  # G-05: "Atualizar agora" reuses the port the window is already using
        try:
            sock.bind(('127.0.0.1', port)); break
        except OSError:
            if not port or attempt == 49: raise
            time.sleep(0.2)
    sock.listen(2048); port = sock.getsockname()[1]
    app = create_app(root); app.state.updates.start(); config = uvicorn.Config(app, host='127.0.0.1', port=port, log_level='info', access_log=False, log_config=None); server = uvicorn.Server(config); app.state.server = server
    tmp = port_file.with_suffix('.tmp'); tmp.write_text(json.dumps({'port':port,'pid':os.getpid(),'version':app.version}), encoding='utf-8'); tmp.replace(port_file)
    try: server.run(sockets=[sock])
    finally: port_file.unlink(missing_ok=True)


def main(argv=None):
    import argparse, subprocess, sys
    parser = argparse.ArgumentParser(); parser.add_argument('--root', default=os.getcwd()); parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--wait-pid', type=int, default=0); args = parser.parse_args(argv)
    root = ProductPaths.from_root(args.root).app_root
    if args.wait_pid:  # G-05: the previous backend is closing; wait until it let go of backend.json
        until = time.time() + 30
        while (root/'UserData'/'State'/'backend.json').exists() and time.time() < until: time.sleep(0.2)
    from .update_channel import UpdateError, apply_pending
    try:
        applied = apply_pending(root)
    except UpdateError:
        applied = None  # already rolled back and logged in UserData/State/update_history.json
    if applied:  # start the NEW program in a fresh interpreter
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        subprocess.Popen([sys.executable, '-m', 'ustracker.server', '--root', str(root), '--port', str(args.port)], cwd=str(root), creationflags=flags, close_fds=True)
        return
    run(root, args.port)


if __name__ == '__main__':
    main()
