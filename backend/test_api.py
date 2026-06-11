"""API-level test for the FastAPI app. Run: python backend/test_api.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient

import app as app_module
from telecom_ai.loaders import TelecomDB


def main() -> None:
    # TelecomDB constructed from the master file path must still see devices/.
    db = TelecomDB(str(Path(__file__).resolve().parent / "data" / "telecom_master_db.json"))
    assert len(db.devices) == 7, f"expected 7 devices, got {len(db.devices)}"
    print(f"TelecomDB(file path) OK: {len(db.devices)} devices merged")

    client = TestClient(app_module.app)

    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["devices"] == 7, r.text
    print("GET /api/health OK:", r.json())

    for query, expect in [
        ("Does the S23 support n77+n78 CA?", "supports n77+n78"),
        ("ARFCN 620000 n78", "3300.0 MHz"),
        ("Is n48 licensed by the FCC?", "unlicensed"),
    ]:
        r = client.post("/ask", json={"query": query})
        assert r.status_code == 200, r.text
        answer = r.json()["answer"]
        assert expect in answer, f"{query!r}: expected {expect!r} in {answer!r}"
        print(f"POST /ask OK: {query!r} -> {answer[:80]}...")

    r = client.get("/api/devices")
    assert r.status_code == 200 and len(r.json()) == 7
    r = client.get("/api/bands")
    assert r.status_code == 200 and "n78" in r.json()["nr_bands"]
    print("GET /api/devices, /api/bands OK")

    r = client.post("/ask", json={"query": "what is prach?", "trace": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "PRACH" in body["answer"]
    assert body.get("steps"), body
    print("POST /ask trace OK:", body["steps"])

    print("All API tests passed.")


if __name__ == "__main__":
    main()
