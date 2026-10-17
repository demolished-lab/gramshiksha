from fastapi.testclient import TestClient

import app.main as main
from app.main import app


class _SuccessfulSession:
    def __init__(self, _engine):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def exec(self, _statement):
        return None


class _FailingSession:
    def __init__(self, _engine):
        pass

    def __enter__(self):
        raise RuntimeError("database unavailable")

    def __exit__(self, *_args):
        return False


def test_readiness_endpoints_return_200_when_db_probe_succeeds(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setattr(main, "Session", _SuccessfulSession)
        for path in ("/ready", "/api/ready"):
            response = client.get(path)
            assert response.status_code == 200
            assert response.json() == {"status": "ready"}


def test_readiness_endpoints_return_503_when_db_probe_fails(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setattr(main, "Session", _FailingSession)
        for path in ("/ready", "/api/ready"):
            response = client.get(path)
            assert response.status_code == 503
            assert response.json() == {
                "status": "degraded",
                "reason": "db_unreachable",
            }
