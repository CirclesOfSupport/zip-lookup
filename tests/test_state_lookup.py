"""State lookup: a complete, real five-digit zip or no state at all.

Run: pip install flask pytest && python -m pytest tests
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import main  # noqa: E402


def post(client, zipcode):
    return client.post("/", json={"zipcode": zipcode}).get_json()


@pytest.fixture
def client():
    main.app.config["TESTING"] = True
    return main.app.test_client()


@pytest.mark.parametrize("zipcode,state", [
    ("02809", "RI"),        # Bristol RI, with its leading zero
    ("00745", "PR"),        # Rio Grande PR (territory file)
    ("00802", "VI"),
    ("96929", "GU"),
    ("96799", "AS"),
    ("96950", "MP"),
    ("83414", "WY"),        # Alta WY sits in a prefix that is otherwise Idaho
    ("30310.0", "GA"),      # a number written out as text still has five digits
    ("12345-6789", "NY"),   # zip+4
    ("09226", "AE"),        # military mail
    ("34030", "AA"),
    ("96311", "AP"),
    ("28090", "NC"),        # a real zip stays what it is
])
def test_real_zip_resolves(client, zipcode, state):
    assert post(client, zipcode)["state"] == state


@pytest.mark.parametrize("zipcode", [
    "2809",      # 02809 that lost its zero; the old prefix rule said NC
    "2809.0",
    "745",       # 00745; the old prefix rule said OK
    "6010",      # 06010; the old prefix rule said IL
    "28850",     # five digits but not a zip
    "99999",
    "abc",
    "",
])
def test_anything_else_has_no_state(client, zipcode):
    assert post(client, zipcode)["state"] == ""


def test_vamc_still_uses_the_prefix(client):
    assert post(client, "02809")["vamc_presumed"] == "650"
    assert post(client, "2809")["vamc_presumed"] == main.lookup_vamc("280")
