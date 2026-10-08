import json
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from prabhat.ledger import Ledger


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import prabhat.api.app as appmod

    appmod.ledger = Ledger(tmp_path_factory.mktemp("ledger") / "ledger.jsonl")
    with TestClient(appmod.app) as c:
        yield c


def test_cases_and_tube_routes(client):
    cases = client.get("/v1/cases").json()
    assert {c["hazard"] for c in cases} == {"cyclone", "extreme_rain", "heatwave", "coldwave"}
    tube = client.get("/v1/tubes", params={"case": cases[0]["id"]}).json()[0]
    tid = tube["tube_id"]
    gate = client.get(f"/v1/tubes/{tid}/gate").json()
    assert gate["verdict"] in {"PASS", "DEGRADE", "SUPPRESS"}
    raster = client.get(f"/v1/tubes/{tid}/exceedance").json()
    assert len(raster["values"]) == len(raster["lead_hours"])
    assert len(raster["values"][0]) == len(raster["lat"])
    assert client.get(f"/v1/tubes/{tid}/efi").json()["is_synthetic_baseline"] is True
    assert client.get(f"/v1/tubes/{tid}/analogues").status_code == 200


def test_status_admits_synthetic_input(client):
    for s in client.get("/v1/status").json():
        assert s["is_synthetic"] is True
        assert any(d.startswith("S0 input") for d in s["degradations"])


def test_alerts_filter_and_cap(client):
    alerts = client.get("/v1/alerts", params={"case": "bay_of_bengal_cyclone",
                                              "user_class": "district_dm"}).json()
    assert alerts and all(a["user_class"] == "district_dm" for a in alerts)
    r = client.get(f"/v1/cap/{alerts[0]['alert_id']}.xml")
    assert r.status_code == 200
    ns = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}
    root = ET.fromstring(r.content)
    assert root.find("cap:status", ns).text == "Exercise"


def test_unknown_ids_are_404(client):
    assert client.get("/v1/tubes", params={"case": "nope"}).status_code == 404
    assert client.get("/v1/tubes/nope-T1/gate").status_code == 404
    assert client.get("/v1/cap/nope.xml").status_code == 404


def test_ledger_is_seeded_and_tamper_evident(client):
    import prabhat.api.app as appmod

    s = client.get("/v1/ledger/summary").json()
    assert s["n_scored"] > 0 and s["chain_valid"]
    assert s["brier_skill_score"] > 0

    path = appmod.ledger.path
    lines = path.read_text().splitlines()
    first = json.loads(lines[0])
    first["forecasts"][0] = 0.999
    lines[0] = json.dumps(first, sort_keys=True)
    path.write_text("\n".join(lines) + "\n")
    assert client.get("/v1/ledger/summary").json()["chain_valid"] is False
