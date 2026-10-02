from __future__ import annotations
from .db import Database

STABLE_TABLES=(
    'clients','fleets','vehicles','ownerships','catalog','subscriptions','direct_sales',
    'charges','payments','credits','expenses','fiscal_obligations','media','attachments',
)

def _table_exists(db:Database, table:str)->bool:
    return db.one("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)) is not None

def snapshot_counts(db:Database)->dict:
    counts={}
    for table in STABLE_TABLES:
        counts[table]=int(db.one(f'SELECT COUNT(*) FROM {table}')[0]) if _table_exists(db,table) else 0
    schema=db.one("SELECT value FROM meta WHERE key='schema_version'")
    return {'schema_version':int(schema[0]) if schema else 0,'counts':counts}

def reconcile_snapshots(before:dict,after:dict)->dict:
    differences={}
    before_counts=before.get('counts',{}); after_counts=after.get('counts',{})
    for table in STABLE_TABLES:
        b=int(before_counts.get(table,0)); a=int(after_counts.get(table,0))
        if a!=b: differences[table]={'before':b,'after':a,'delta':a-b}
    return {'ok':not differences,'before_schema':before.get('schema_version'),'after_schema':after.get('schema_version'),'differences':differences}

def inspect_invariants(db:Database)->dict:
    checks={
      'multiple_current_ownerships':int(db.one('''SELECT COUNT(*) FROM (
          SELECT vehicle_id FROM ownerships WHERE effective_to IS NULL GROUP BY vehicle_id HAVING COUNT(*)>1
      )''')[0]),
      'orphan_vehicle_clients':int(db.one('''SELECT COUNT(*) FROM vehicles v LEFT JOIN clients c ON c.id=v.client_id WHERE c.id IS NULL''')[0]),
      'orphan_fleet_companies':int(db.one('''SELECT COUNT(*) FROM fleets f LEFT JOIN client_companies cc ON cc.id=f.client_company_id
          WHERE f.client_company_id IS NOT NULL AND cc.id IS NULL''')[0]),
      'duplicate_catalog_codes':int(db.one('''SELECT COUNT(*) FROM (SELECT code FROM catalog GROUP BY code HAVING COUNT(*)>1)''')[0]),
      'invalid_attachment_origins':int(db.one("SELECT COUNT(*) FROM attachments WHERE origin NOT IN ('LOCAL','LINK')")[0]),
      'pending_transfer_duplicates':int(db.one("""SELECT COUNT(*) FROM (
          SELECT vehicle_id FROM vehicle_transfer_cases WHERE status='PENDING' GROUP BY vehicle_id HAVING COUNT(*)>1
      )""")[0]),
    }
    return {'ok':all(value==0 for value in checks.values()),'checks':checks,'snapshot':snapshot_counts(db)}
