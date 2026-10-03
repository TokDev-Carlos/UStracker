from __future__ import annotations

import calendar
from datetime import date

from .db import Database
from .money import parse_money_api
from .services import audit, now, uid, list_direct_sales, list_subscriptions
from .vehicle_types import annotate_vehicle


def add_months(value:date, months:int)->date:
    if months < 0: raise ValueError('months cannot be negative')
    index=(value.year*12 + value.month-1)+months
    year,month=divmod(index,12); month+=1
    day=min(value.day,calendar.monthrange(year,month)[1])
    return date(year,month,day)


def _subscription_total(con, subscription_id:str)->int:
    row=con.execute('SELECT COALESCE(SUM(quantity*unit_price_cents),0) AS total FROM subscription_items WHERE subscription_id=?',(subscription_id,)).fetchone()
    return int(row['total'] or 0)


def create_coverage(db:Database,actor:int,p:dict)->dict:
    subscription_id=str(p.get('subscription_id') or '').strip(); payment_id=str(p.get('origin_payment_id') or '').strip()
    cycles=int(p.get('cycles') or 0)
    if not subscription_id or not payment_id or cycles<=0: raise ValueError('subscription_id, origin_payment_id and positive cycles required')
    with db.transaction() as con:
        sub=con.execute('SELECT * FROM subscriptions WHERE id=?',(subscription_id,)).fetchone()
        pay=con.execute('SELECT * FROM payments WHERE id=?',(payment_id,)).fetchone()
        if not sub or not pay: raise ValueError('subscription/payment not found')
        if sub['client_id']!=pay['client_id']: raise ValueError('payment and subscription client mismatch')
        if pay['reversed_at']: raise ValueError('reversed payment cannot create coverage')
        start=date.fromisoformat(str(p.get('start_on') or pay['paid_on']))
        # Coverage follows calendar months; plans with annual billing still express purchased cycles explicitly.
        end=add_months(start,cycles)
        applied=int(pay['amount_cents']) if p.get('value') is None else parse_money_api(p['value'])
        if applied<0 or applied>int(pay['amount_cents']): raise ValueError('applied coverage value exceeds payment')
        rec={'id':uid(),'client_id':sub['client_id'],'subscription_id':subscription_id,'origin_payment_id':payment_id,
             'start_on':start.isoformat(),'end_on':end.isoformat(),'cycles':cycles,'applied_value_cents':applied,'created_at':now()}
        con.execute('''INSERT INTO service_coverage_periods(id,client_id,subscription_id,origin_payment_id,start_on,end_on,cycles,applied_value_cents,created_at)
                       VALUES(:id,:client_id,:subscription_id,:origin_payment_id,:start_on,:end_on,:cycles,:applied_value_cents,:created_at)''',rec)
        audit(con,actor,'SERVICE_COVERAGE_CREATE','service_coverage',rec['id'],None,rec)
        return rec


def commercial_snapshot(db:Database)->dict:
    subscriptions=list_subscriptions(db)
    for rec in subscriptions:
        rec['total_cents']=rec['effective_total_cents']
        rec['vehicles']=[{
            'id':target['vehicle_id'],'code':target['vehicle_code'],'type':target['vehicle_type'],
            'category':target.get('vehicle_category'),'category_label':target.get('vehicle_category_label'),
            'brand':target['vehicle_brand'],'model':target['vehicle_model'],
            'plate':target['vehicle_plate'],'fleet_id':target['vehicle_fleet_id'],
        } for target in rec['targets'] if target['target_type']=='VEHICLE']
        rec['plans']=[{
            'id':item['catalog_id'],'name':item['plan_name'],'code':item['plan_code'],
            'quantity':item['quantity'],'unit_price_cents':item['unit_price_cents'],
        } for item in rec['items']]
    coverages=[dict(r) for r in db.query('''SELECT sc.*,c.legal_name AS client_name,s.code AS subscription_code FROM service_coverage_periods sc LEFT JOIN subscriptions s ON s.id=sc.subscription_id
                                            JOIN clients c ON c.id=sc.client_id ORDER BY sc.end_on DESC,sc.created_at DESC''')]
    return {
        'subscriptions':subscriptions,
        'direct_sales':list_direct_sales(db),
        'credits':[dict(r) for r in db.query('SELECT cr.*,c.legal_name AS client_name,c.code AS client_code FROM credits cr LEFT JOIN clients c ON c.id=cr.client_id ORDER BY cr.created_at DESC')],
        'coverage_periods':coverages,
        'catalog_avulsa':[dict(r) for r in db.query("SELECT * FROM catalog WHERE active=1 AND category='AVULSA' ORDER BY name")],
        'catalog_mensal':[dict(r) for r in db.query("SELECT * FROM catalog WHERE active=1 AND category='MENSAL' ORDER BY name")],
        'payments':[dict(r) for r in db.query('SELECT * FROM payments WHERE reversed_at IS NULL ORDER BY paid_on DESC,created_at DESC')],
        'vehicles':[annotate_vehicle(dict(r)) for r in db.query('SELECT id,code,client_id,plate,type,brand,model,fleet_id FROM vehicles WHERE archived=0 ORDER BY plate')],
        'fleets':[dict(r) for r in db.query('SELECT id,code,client_id,client_company_id,name FROM fleets WHERE archived=0 ORDER BY name')],
    }
