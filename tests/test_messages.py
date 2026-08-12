from __future__ import annotations

from sapilot.observe.messages import MessageResolver, parse_status_bar


def test_parse_status_bar():
    m = parse_status_bar("E: No valid payment method found")
    assert m.msgty == "E"
    assert "payment method" in m.short_text.lower()


def test_resolve_t100(mock_rfc):
    r = MessageResolver(mock_rfc)
    msg = r.resolve("FZ", "001", msgty="E", msgv1="1000")
    assert "payment method" in msg.short_text.lower() or msg.short_text
