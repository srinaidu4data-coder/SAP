"""ABAP Development Tools REST — external breakpoints (T1 only)."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import requests
from requests.auth import HTTPBasicAuth

log = logging.getLogger(__name__)


class AdtClient:
    """
    Minimal ADT debugger client.
    Field-value replacement is intentionally NOT implemented.
    """

    def __init__(
        self,
        base_url: str,
        user: str,
        password: str,
        client: str,
        verify_ssl: bool = True,
    ):
        self.base_url = base_url.rstrip("/") + "/"
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(user, password)
        self.session.verify = verify_ssl
        self.session.headers.update(
            {
                "Accept": "application/xml",
                "X-CSRF-Token": "Fetch",
                "sap-client": client,
            }
        )

    def fetch_csrf(self) -> str:
        url = urljoin(self.base_url, "sap/bc/adt/discovery")
        resp = self.session.get(url, timeout=30)
        token = resp.headers.get("X-CSRF-Token") or resp.headers.get("x-csrf-token") or ""
        if token:
            self.session.headers["X-CSRF-Token"] = token
        return token

    def set_external_breakpoint(
        self,
        object_name: str,
        include: str,
        line: int,
        user: str,
    ) -> dict[str, Any]:
        """
        Set external breakpoint. Exact ADT payload varies by backend version;
        this posts a documented-style request and returns status for the agent.
        """
        self.fetch_csrf()
        # ADT debugger endpoint family
        path = "sap/bc/adt/debugger/breakpoints"
        url = urljoin(self.base_url, path)
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<dbg:breakpoints xmlns:dbg="http://www.sap.com/adt/debugger">
  <dbg:breakpoint kind="line" object="{object_name}" include="{include}" line="{line}" user="{user}"/>
</dbg:breakpoints>"""
        resp = self.session.post(
            url,
            data=body.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=30,
        )
        return {"status_code": resp.status_code, "text": resp.text[:2000]}

    def read_variables(self, debuggee_id: str) -> dict[str, Any]:
        """Pull variable stack as structured data — never supports replace."""
        path = f"sap/bc/adt/debugger/debuggees/{debuggee_id}/variables"
        url = urljoin(self.base_url, path)
        resp = self.session.get(url, timeout=30)
        return {"status_code": resp.status_code, "body": resp.text[:50000]}
