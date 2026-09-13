from pathlib import Path
from fastapi.testclient import TestClient
from ustracker.server import create_app


def _csrf(client: TestClient):
    r=client.get('/api/v1/auth/csrf'); assert r.status_code==200
    return r.json()['csrf']


def test_bootstrap_login_and_client_crud(tmp_path: Path):
    app=create_app(tmp_path)
    c=TestClient(app)
    csrf=_csrf(c)
    r=c.post('/api/v1/auth/bootstrap',json={'name':'Carlos','password':'StrongPass!123'},headers={'X-CSRF-Token':csrf})
    assert r.status_code==200
    tickets=r.json()['tickets']
    for i,t in enumerate(tickets,2):
        csrf=_csrf(c)
        r=c.post('/api/v1/auth/enroll',json={'ticket':t,'name':f'Admin {i}','password':f'StrongPass!{i}xx'},headers={'X-CSRF-Token':csrf})
        assert r.status_code==200
    csrf=_csrf(c)
    r=c.post('/api/v1/auth/login',json={'name':'Carlos','password':'StrongPass!123'},headers={'X-CSRF-Token':csrf})
    assert r.status_code==200
    csrf=r.json()['csrf']
    r=c.post('/api/v1/clients',json={'legal_name':'Cliente A','public_name':'Cliente Público','status':'ACTIVE'},headers={'X-CSRF-Token':csrf,'X-Operation-ID':'client-create-0001'})
    assert r.status_code==201, r.text
    cid=r.json()['id']
    r=c.get('/api/v1/clients'); assert len(r.json()['items'])==1
    r=c.get('/api/v1/dashboard'); assert r.status_code==200 and r.json()['active_clients']==1
    r=c.get('/api/v1/public'); assert r.status_code==200
    assert any(x['public_name']=='Cliente Público' for x in r.json()['clients'])
    r=c.patch(f'/api/v1/clients/{cid}',json={'trade_name':'Fantasia','expected_revision':1},headers={'X-CSRF-Token':csrf,'X-Operation-ID':'client-update-0001'})
    assert r.status_code==200
