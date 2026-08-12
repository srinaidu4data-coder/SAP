"""OData / IWFND CDS reads — knowledge ladder rung 1."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import requests
from requests.auth import HTTPBasicAuth

log = logging.getLogger(__name__)


class ODataClient:
    def __init__(
        self,
        base_url: str,
        user: str,
        password: str,
        client: str | None = None,
        verify_ssl: bool = True,
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/") + "/"
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(user, password)
        self.session.verify = verify_ssl
        self.session.headers.update({"Accept": "application/json"})
        if client:
            self.session.headers["sap-client"] = client
        self.timeout = timeout

    def get_entity_set(
        self,
        service: str,
        entity_set: str,
        *,
        filter_expr: str | None = None,
        select: list[str] | None = None,
        top: int | None = None,
    ) -> list[dict[str, Any]]:
        path = f"{service.strip('/')}/{entity_set}"
        url = urljoin(self.base_url, path)
        params: dict[str, str] = {"$format": "json"}
        if filter_expr:
            params["$filter"] = filter_expr
        if select:
            params["$select"] = ",".join(select)
        if top is not None:
            params["$top"] = str(top)
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        # OData V2 vs V4
        if "d" in data and "results" in data["d"]:
            return list(data["d"]["results"])
        if "value" in data:
            return list(data["value"])
        return [data]

    def available(self) -> bool:
        try:
            resp = self.session.get(self.base_url, timeout=5)
            return resp.status_code < 500
        except Exception:
            return False


class MockODataClient(ODataClient):
    def __init__(self, entities: dict[str, list[dict[str, Any]]] | None = None):
        self._entities = entities or {}
        self.base_url = "mock://"
        self.timeout = 1.0

    def get_entity_set(self, service: str, entity_set: str, **kwargs: Any) -> list[dict[str, Any]]:
        key = f"{service}/{entity_set}"
        return list(self._entities.get(key, self._entities.get(entity_set, [])))

    def available(self) -> bool:
        return True
