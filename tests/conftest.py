from __future__ import annotations

import os

import pytest

os.environ.setdefault("SAPILOT_ALLOW_UNSIGNED_POLICY", "1")
os.environ.setdefault("SAPILOT_LAB", "1")
os.environ.setdefault("SAPILOT_ENV", "lab")
# Unit tests use offline data path; product runs force online GUI
os.environ.setdefault("SAPILOT_OFFLINE", "1")


@pytest.fixture
def mock_rfc():
    from sapilot.connect.rfc import MockRfcClient
    from tests.fixtures.mock_sap_data import seed_demo_tables

    rfc = MockRfcClient()
    seed_demo_tables(rfc)
    return rfc
