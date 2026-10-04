"""R23 — bulk subscription summaries are identical to the per-row reference implementation."""
import os, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['USTRACKER_DEV_PLAINTEXT'] = '1'
from ustracker.db import Database
from ustracker.mobility import _active_subscription_summaries, _subscription_summaries_bulk, create_fleet, create_vehicle, list_mobility
from ustracker.services import create_catalog, create_client, create_client_company, create_subscription


class BulkSummaryTests(unittest.TestCase):
    def test_bulk_equals_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp), 'test', b'0' * 32)
            plan = create_catalog(db, 1, {'description': 'P', 'category': 'Mensal', 'price': '10,00'})
            vids, fids = [], []
            for i in range(4):
                c = create_client(db, 1, {'legal_name': f'C{i}', 'email': f'{i}@x.test', 'documents': [{'type': 'RG', 'number': f'RG-BULK-{i}', 'is_primary': True}]})
                co = create_client_company(db, 1, c['id'], {'legal_name': f'E{i}', 'is_primary': True})
                f = create_fleet(db, 1, {'client_id': c['id'], 'client_company_id': co['id'], 'name': f'F{i}'}); fids.append(f['id'])
                vs = [create_vehicle(db, 1, {'client_id': c['id'], 'fleet_id': f['id'] if j else None, 'plate': f'B{i}{j}', 'type': 'Carro', 'brand': 'x', 'model': 'y', 'year': 2024})['id'] for j in range(3)]
                vids += vs
                create_subscription(db, 1, {'client_id': c['id'], 'start_on': '2026-01-01', 'target_vehicle_ids': [vs[1]], 'items': [{'catalog_id': plan['id']}]})
                if i % 2: create_subscription(db, 1, {'client_id': c['id'], 'start_on': '2026-02-01', 'target_fleet_ids': [f['id']], 'target_vehicle_ids': [vs[2]], 'items': [{'catalog_id': plan['id'], 'quantity': 2}]})
                create_subscription(db, 1, {'client_id': c['id'], 'start_on': '2026-03-01', 'items': [{'catalog_id': plan['id'], 'vehicle_id': vs[0]}]})
            by_v, by_f = _subscription_summaries_bulk(db)
            for v in vids:
                self.assertEqual(by_v.get(v, []), _active_subscription_summaries(db, vehicle_id=v), v)
            for f in fids:
                self.assertEqual(by_f.get(f, []), _active_subscription_summaries(db, fleet_id=f), f)
            data = list_mobility(db)
            self.assertEqual(sum(x['subscriptions_count'] for x in data['fleets']), sum(len(_active_subscription_summaries(db, fleet_id=f)) for f in fids))


if __name__ == '__main__':
    unittest.main()
