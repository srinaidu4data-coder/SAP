"""DDIC lookup: DD02L / DD03L / DD04T — field semantics."""

from __future__ import annotations

from sapilot.connect.rfc import RfcClientBase


class DdicIntrospector:
    def __init__(self, rfc: RfcClientBase, ddlanguage: str = "E"):
        self.rfc = rfc
        self.ddlanguage = ddlanguage

    def table_exists(self, tabname: str) -> bool:
        rows = self.rfc.read_table(
            "DD02L",
            fields=["TABNAME", "TABCLASS"],
            options=[f"TABNAME = '{tabname.upper()}'"],
            rowcount=1,
        )
        return bool(rows)

    def fields(self, tabname: str) -> list[dict[str, str]]:
        return self.rfc.read_table(
            "DD03L",
            fields=["TABNAME", "FIELDNAME", "POSITION", "ROLLNAME", "DATATYPE", "LENG", "KEYFLAG"],
            options=[f"TABNAME = '{tabname.upper()}'"],
        )

    def field_texts(self, rollname: str) -> list[dict[str, str]]:
        return self.rfc.read_table(
            "DD04T",
            fields=["ROLLNAME", "DDLANGUAGE", "DDTEXT", "REPTEXT"],
            options=[f"ROLLNAME = '{rollname.upper()}'", f"AND DDLANGUAGE = '{self.ddlanguage}'"],
        )
