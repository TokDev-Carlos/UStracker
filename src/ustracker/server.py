from __future__ import annotations

import hashlib
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

from .auth import AuthService, Session
from .attachments import list_attachments, load_attachment, store_attachment, store_link
from .codes import resolve_entity_ref
from .backup import create_backup, maybe_automatic_backup, prune_backups, restore_backup, verify_backup
from .branding import asset_dir, store_brand_asset
from .billing import client_payment_options, register_subscription_payment, subscription_payment_status
from .catalog import list_catalog, remove_catalog_item
from .cloud import CloudError, CloudSync, apply_pending_restore, restore_from_cloud
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


def create_app(root: Path | str) -> FastAPI:
    paths = ProductPaths.from_root(root)
    root = paths.app_root
    root.mkdir(parents=True, exist_ok=True)
    paths.ensure_runtime_directories()
    repository = LocalRepository(root)
    product_version = read_version(root)
    auth = AuthService(root)
    app = FastAPI(title='UStracker', version=product_version, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.root = root
    app.state.auth = auth
    app.state.server = None
    read_public(root)

    def get_db(session: Session) -> Database:
        return repository.database(session.environment, session.db_key)

    cloud = CloudSync(root, auth)
    app.state.cloud = cloud

    @app.middleware('http')
    async def security_headers(request: Request, call_next):
        correlation = request.headers.get('X-Correlation-ID', '').strip()
        if not correlation or len(correlation) > 128:
            correlation = str(uuid.uuid4())
        request.state.correlation_id = correlation
        host = request.headers.get('host', '').split(':')[0].lower()
        if host not in {'127.0.0.1', 'localhost', 'testserver'}:
            return JSONResponse({'error': 'INVALID_HOST', 'correlation_id': correlation}, status_code=400)
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            origin = request.headers.get('origin')
            if origin and not (
                origin.startswith('http://127.0.0.1:')
                or origin.startswith('http://localhost:')
                or origin.startswith('http://testserver')
            ):
                return JSONResponse({'error': 'INVALID_ORIGIN', 'correlation_id': correlation}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Correlation-ID'] = correlation
        return response

    def _err(request: Request, code: str, detail: str):
        return {'error': code, 'detail': detail, 'correlation_id': getattr(request.state, 'correlation_id', '')}

    @app.exception_handler(ValueError)
    async def value_error(request: Request, exc: ValueError):
        return JSONResponse(_err(request, 'VALIDATION', str(exc)), status_code=422)

    @app.exception_handler(KeyError)
    async def key_error(request: Request, exc: KeyError):
        return JSONResponse(_err(request, 'NOT_FOUND', str(exc)), status_code=404)

    @app.exception_handler(PermissionError)
    async def permission_error(request: Request, exc: PermissionError):
        return JSONResponse(_err(request, 'FORBIDDEN', str(exc)), status_code=403)

    @app.exception_handler(RuntimeError)
    async def runtime_error(request: Request, exc: RuntimeError):
        status = 409 if 'pending from a previous interrupted attempt' in str(exc) else 500
        return JSONResponse(_err(request, 'CONFLICT' if status == 409 else 'RUNTIME', str(exc)), status_code=status)

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

    def mutation(request: Request, session: Session, route: str, payload, fn, *, writer: bool = True):
        csrf_required(request, session)
        db = get_db(session)
        if writer and session.environment == 'production':
            require_writer(root, db)
        operation_id = request.headers.get('X-Operation-ID', '')
        result = run_idempotent(db, session.slot, route, operation_id, payload, lambda: fn(db))
        if session.environment == 'production':
            cloud.mark_dirty()
        return result

    def authorize_file_mutation(request: Request, session: Session, *, writer: bool = True) -> Database:
        csrf_required(request, session)
        db = get_db(session)
        if writer and session.environment == 'production':
            require_writer(root, db)
            cloud.mark_dirty()
        return db

    @app.get('/api/v1/health')
    def health():
        return {'status': 'ok', 'product': 'UStracker', 'version': product_version}

    @app.get('/api/v1/public')
    def public():
        return read_public(root)

    @app.get('/api/v1/auth/setup-status')
    def setup_status():
        return auth.setup_status()

    @app.get('/api/v1/auth/csrf')
    def csrf(response: Response):
        token = secrets.token_urlsafe(24)
        response.set_cookie('us_csrf', token, httponly=False, samesite='strict', secure=False)
        return {'csrf': token}

    @app.post('/api/v1/auth/bootstrap')
    def bootstrap(request: Request, p: dict = Body(...)):
        csrf_required(request)
        return auth.bootstrap(p.get('name', ''), p.get('password', ''))

    @app.post('/api/v1/auth/enroll')
    def enroll(request: Request, p: dict = Body(...)):
        csrf_required(request)
        return auth.enroll(p.get('ticket', ''), p.get('name', ''), p.get('password', ''))

    @app.post('/api/v1/auth/login')
    def login(request: Request, response: Response, p: dict = Body(...)):
        csrf_required(request)
        session = auth.login(p.get('name', ''), p.get('password', ''), p.get('environment', 'production'))
        response.set_cookie('us_session', session.token, httponly=True, samesite='strict', secure=False, max_age=43200)
        response.set_cookie('us_csrf', session.csrf, httponly=False, samesite='strict', secure=False, max_age=43200)
        db = get_db(session)
        cloud_restore = None
        if session.environment == 'production':
            cloud_restore = apply_pending_restore(root, db, session, cloud)
            if cloud_restore:
                db = get_db(session)
        station = ensure_station(root, db) if session.environment == 'production' else None
        if session.environment == 'production':
            cloud.attach(session)
            try:
                cloud.purge_trash(session)
            except Exception:
                pass
            cloud.start()
        media_recovery = recover_media_journals(root, db)
        if session.environment == 'production':
            rebuild_public(root, db)
        settings = {r['key']: r['value'] for r in db.query('SELECT key,value FROM settings')}
        backup_info = None
        backup_warning = None
        try:
            created = maybe_automatic_backup(root, db, session.vrk, retention=int(settings.get('backup_retention', 14)))
            backup_info = created.name if created else None
        except Exception as exc:
            backup_warning = str(exc)
        return {
            'slot': session.slot,
            'name': session.name,
            'environment': session.environment,
            'csrf': session.csrf,
            'station': station,
            'cloud_restore': cloud_restore,
            'media_recovery': media_recovery,
            'automatic_backup': backup_info,
            'backup_warning': backup_warning,
        }

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
        return {'slot': session.slot, 'name': session.name, 'environment': session.environment, 'setup': auth.setup_status(), 'station': station}

    @app.post('/api/v1/auth/change-password')
    def change_password(request: Request, response: Response, p: dict = Body(...)):
        session = session_required(request, True)
        csrf_required(request, session)
        auth.change_password(session, p.get('current_password', ''), p.get('new_password', ''))
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
        return {'items': list_clients(get_db(session_required(request, True)), limit=500)}

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
        def action(db):
            rec = update_client(db, session.slot, cid, p)
            if session.environment == 'production': rebuild_public(root, db)
            return rec
        return mutation(request, session, f'PATCH /clients/{cid}', p, action)

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
        return {'items': list_table(get_db(session_required(request, True)), 'vehicles', limit=500)}

    @app.post('/api/v1/vehicles', status_code=201)
    def vehicles_create(request: Request, p: dict = Body(...)):
        session = session_required(request, True)
        return mutation(request, session, 'POST /vehicles', p, lambda db: create_vehicle(db, session.slot, p))

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
        return finance_snapshot(get_db(session_required(request, True)))

    @app.post('/api/v1/fiscal/{fiscal_id}/ensure-expense')
    def fiscal_ensure_expense(fiscal_id: str, request: Request):
        session = session_required(request, True); db = get_db(session)
        payload = {'fiscal_id': fiscal_id}
        return mutation(request, session, f'POST /fiscal/{fiscal_id}/ensure-expense', payload, lambda db: ensure_fiscal_expense(db, session.slot, fiscal_id))

    @app.get('/api/v1/commercial')
    def commercial(request: Request):
        return commercial_snapshot(get_db(session_required(request, True)))

    @app.post('/api/v1/commercial/coverage', status_code=201)
    def commercial_coverage(request: Request, p: dict = Body(...)):
        session = session_required(request, True); db = get_db(session)
        return mutation(request, session, 'POST /commercial/coverage', p, lambda db: create_coverage(db, session.slot, p))

    @app.get('/api/v1/catalog')
    def catalog(request: Request):
        return {'items': list_catalog(get_db(session_required(request, True)))}

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
        db = get_db(session_required(request, True))
        return {**dashboard(db, year=year), **dashboard_extended(db), 'client_activity': client_activity_overview(db, q)}

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
            require_writer(root, get_db(session))
        cloud.attach(session)
        return session

    def cloud_call(fn):
        try:
            return fn()
        except CloudError as exc:
            raise HTTPException(409 if exc.code in ('CONFLICT', 'READ_ONLY') else 502,
                                detail={'code': f'CLOUD_{exc.code}', 'detail': exc.detail}) from exc

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
        """C-05 — before login, on a new or wiped machine."""
        csrf_required(request)
        if p.get('confirm') != 'RESTAURAR DA NUVEM':
            raise ValueError('confirmation RESTAURAR DA NUVEM required')
        out = cloud_call(lambda: restore_from_cloud(root, p.get('url', ''), p.get('secret', '')))
        auth.clear_sessions()
        cloud.state = type(cloud.state)(root)
        cloud.pending_secret = str(p.get('secret', '')).strip()
        return out

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


def run(root: Path | str):
    paths = ProductPaths.from_root(root); paths.ensure_runtime_directories(); root = paths.app_root; state_dir = paths.state_root; port_file = state_dir/'backend.json'
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM); sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); sock.bind(('127.0.0.1', 0)); sock.listen(2048); port = sock.getsockname()[1]
    app = create_app(root); config = uvicorn.Config(app, host='127.0.0.1', port=port, log_level='info', access_log=False, log_config=None); server = uvicorn.Server(config); app.state.server = server
    tmp = port_file.with_suffix('.tmp'); tmp.write_text(json.dumps({'port':port,'pid':os.getpid(),'version':app.version}), encoding='utf-8'); tmp.replace(port_file)
    try: server.run(sockets=[sock])
    finally: port_file.unlink(missing_ok=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument('--root', default=os.getcwd()); args = parser.parse_args(); run(args.root)
