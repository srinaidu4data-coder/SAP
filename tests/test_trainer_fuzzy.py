from __future__ import annotations

from sapilot.autobot.trainer import (
    BotTrainer,
    ControlHit,
    ScreenTraining,
    TrainingStore,
    find_fuzzy_match,
    tail_field,
)


def test_tail_field_strips_widget_prefix_and_container_path():
    assert tail_field("wnd[0]/usr/ctxtRF02K-LIFNR") == "RF02K-LIFNR"
    assert tail_field("wnd[0]/usr/subScreen:OLD:0100/ctxtRF02K-LIFNR") == "RF02K-LIFNR"
    assert tail_field("wnd[0]/usr/subScreen:NEW:0200/txtRF02K-LIFNR") == "RF02K-LIFNR"


def test_find_fuzzy_match_recovers_field_across_different_container_path():
    recorded_cid = "wnd[0]/usr/subScreen:OLD:0100/ctxtRF02K-LIFNR"
    live_controls = [
        ControlHit(
            id="wnd[0]/usr/subScreen:NEW:0200/ctxtRF02K-LIFNR",
            name="RF02K-LIFNR",
            type="GuiCTextField",
            changeable=True,
        ),
        ControlHit(id="wnd[0]/usr/ctxtRF02K-BUKRS", name="RF02K-BUKRS", changeable=True),
    ]
    match = find_fuzzy_match(recorded_cid, live_controls)
    assert match is not None
    control, score = match
    assert control.id == "wnd[0]/usr/subScreen:NEW:0200/ctxtRF02K-LIFNR"
    assert score >= 0.9


def test_find_fuzzy_match_never_targets_readonly_control():
    recorded_cid = "wnd[0]/usr/ctxtRF02K-LIFNR"
    live_controls = [
        ControlHit(id="wnd[0]/usr/lblRF02K-LIFNR", name="RF02K-LIFNR", changeable=False),
    ]
    assert find_fuzzy_match(recorded_cid, live_controls) is None


def test_find_fuzzy_match_returns_none_below_threshold():
    recorded_cid = "wnd[0]/usr/ctxtRF02K-LIFNR"
    live_controls = [ControlHit(id="wnd[0]/usr/ctxtCOMPLETELY-UNRELATED", name="X", changeable=True)]
    assert find_fuzzy_match(recorded_cid, live_controls) is None


# -- End-to-end replay with a fake SAP COM session ---------------------------


class _FakeChildren:
    def __init__(self, items):
        self._items = items

    @property
    def Count(self):
        return len(self._items)

    def __call__(self, i):
        return self._items[i]


class _FakeControl:
    def __init__(self, id_, name="", text="", type_="GuiCTextField", changeable=False, children=None):
        self.Id = id_
        self.Name = name
        self.Text = text
        self.Type = type_
        self.Changeable = changeable
        self.ScreenLeft = 100
        self.ScreenTop = 200
        self.Width = 40
        self.Height = 20
        self.Children = _FakeChildren(children or [])

    def __setattr__(self, key, value):
        object.__setattr__(self, key, value)


class _FakeSession:
    """Simulates a SAP version bump: the recorded control_id's container
    path no longer exists, but a control with the same trailing field name
    exists at a different path."""

    def __init__(self, live_control_id: str):
        self.live_control_id = live_control_id
        self._live_control = _FakeControl(
            live_control_id, name="RF02K-LIFNR", changeable=True
        )
        self._root = _FakeControl("wnd[0]", children=[self._live_control])

    def StartTransaction(self, Transaction: str):
        return None

    def FindById(self, control_id: str):
        if control_id == "wnd[0]":
            return self._root
        if control_id == self.live_control_id:
            return self._live_control
        raise Exception(f"element not found: {control_id}")


def test_apply_training_to_navigator_falls_back_to_fuzzy_match(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "sapilot.connect.mouse.click_sap_component",
        lambda el: None,
        raising=False,
    )

    recorded_cid = "wnd[0]/usr/subScreen:OLD:0100/ctxtRF02K-LIFNR"
    live_cid = "wnd[0]/usr/subScreen:NEW:0200/ctxtRF02K-LIFNR"

    store = TrainingStore(path=tmp_path / "training.json")
    store.upsert_screen(
        ScreenTraining(
            tcode="XK03",
            title="Display Vendor",
            labels={"LIFNR": recorded_cid},
            fill_order=[{"label": "LIFNR", "control_id": recorded_cid, "example_value": ""}],
        )
    )

    bt = BotTrainer()
    bt.store = store

    session = _FakeSession(live_cid)
    result = bt.apply_training_to_navigator("XK03", session, {"LIFNR": "0000100001"})

    assert result["ok"] is True
    step = result["results"][0]
    assert step["fuzzy_matched"] is True
    assert step["id"] == live_cid
    assert step["recorded_id"] == recorded_cid
    assert step["fuzzy_score"] >= 0.9
    # The value was actually written to the live (re-grounded) control.
    assert session._live_control.Text == "0000100001"


def test_apply_training_to_navigator_exact_match_skips_fuzzy_path(tmp_path, monkeypatch):
    """When the recorded id still matches live, no fuzzy fallback should
    fire (and no live-tree walk is needed) — this is the common case."""
    monkeypatch.setattr(
        "sapilot.connect.mouse.click_sap_component",
        lambda el: None,
        raising=False,
    )

    cid = "wnd[0]/usr/ctxtRF02K-LIFNR"
    store = TrainingStore(path=tmp_path / "training2.json")
    store.upsert_screen(
        ScreenTraining(
            tcode="XK03",
            labels={"LIFNR": cid},
            fill_order=[{"label": "LIFNR", "control_id": cid, "example_value": ""}],
        )
    )
    bt = BotTrainer()
    bt.store = store

    session = _FakeSession(cid)  # live control IS at the recorded id
    result = bt.apply_training_to_navigator("XK03", session, {"LIFNR": "0000100001"})

    assert result["ok"] is True
    step = result["results"][0]
    assert "fuzzy_matched" not in step
    assert step["id"] == cid
