import copy
from fastapi.testclient import TestClient
from formula_lab.app import app,sessions
from formula_lab.strategies import prepare,SOURCES


def test_session_revision_and_trace():
    item=prepare(SOURCES[0],'registry');sessions['test-session']=item
    body={'session_id':'test-session','revision':'1','inputs':{'pm':{'value':'1.03','unit':'bar'},'pcd':{'value':'1','unit':'bar'}},'request_id':'42'}
    with TestClient(app) as c:
        result=c.post('/api/lab/calculate',json=body)
        assert result.status_code==200
        assert result.json()['source_hash']==SOURCES[0]['docx_sha256']
        assert result.json()['request_id']=='42'
        body['revision']='old'
        assert c.post('/api/lab/calculate',json=body).status_code==409
        body['session_id']='unknown'
        assert c.post('/api/lab/calculate',json=body).status_code==409
    sessions.pop('test-session')
