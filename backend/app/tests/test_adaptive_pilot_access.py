"""Private network integration must fail closed; these are software checks."""
import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient


def test_pilot_requires_private_key_and_does_not_publish_missing_configuration(tmp_path,monkeypatch):
    path=Path(__file__).resolve().parents[3]/'research/tilapia_growth_meta_20261021/pilot_service.py'
    spec=importlib.util.spec_from_file_location('experimental_pilot_access',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    key=tmp_path/'key'
    monkeypatch.setenv('TILAPIA_GROWTH_API_KEY_FILE',str(key))
    client=TestClient(module.app)
    assert client.get('/api/v1/models/tilapia-growth-adaptive/status').status_code==503
    key.write_text('test-private-key')
    assert client.get('/api/v1/models/tilapia-growth-adaptive/status').status_code==401
    assert client.get('/api/v1/models/tilapia-growth-adaptive/status',headers={'Authorization':'Bearer wrong'}).status_code==401
    # Middleware accepted the key, but there is no configured artifact at this fixture path.
    monkeypatch.setenv('TILAPIA_GROWTH_ADAPTIVE_ARTIFACT',str(tmp_path/'absent.json'))
    r=client.get('/api/v1/models/tilapia-growth-adaptive/status',headers={'Authorization':'Bearer test-private-key'})
    assert r.status_code==503 and r.json()['detail']=='Adaptive ML artifact cannot be loaded'
