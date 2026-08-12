"""Typed accessors for FBZP config, vendor master, payment run tables."""

from __future__ import annotations

from typing import Any

from sapilot.connect.rfc import RfcClientBase


class KnowledgeTables:
    """Always uses KNOWLEDGE channel (RFC/SQL) — never GUI scrape for reads."""

    def __init__(self, rfc: RfcClientBase):
        self.rfc = rfc

    # --- Client / tier ---
    def read_t000(self, mandt: str | None = None) -> list[dict[str, str]]:
        opts = [f"MANDT = '{mandt}'"] if mandt else None
        return self.rfc.read_table(
            "T000",
            fields=["MANDT", "MTEXT", "ORT01", "CCCATEGORY", "CCCORACTIV"],
            options=opts,
        )

    # --- FBZP chain ---
    def t042(self, bukrs: str | None = None) -> list[dict[str, str]]:
        opts = [f"BUKRS = '{bukrs}'"] if bukrs else None
        return self.rfc.read_table("T042", options=opts)

    def t042b(self, zbukr: str | None = None) -> list[dict[str, str]]:
        opts = [f"ZBUKR = '{zbukr}'"] if zbukr else None
        return self.rfc.read_table("T042B", options=opts)

    def t042z(self, land1: str | None = None, zlsch: str | None = None) -> list[dict[str, str]]:
        opts = []
        if land1:
            opts.append(f"LAND1 = '{land1}'")
        if zlsch:
            opts.append(f"AND ZLSCH = '{zlsch}'" if opts else f"ZLSCH = '{zlsch}'")
        return self.rfc.read_table("T042Z", options=opts or None)

    def t042e(self, bukrs: str | None = None, zlsch: str | None = None) -> list[dict[str, str]]:
        opts = []
        if bukrs:
            opts.append(f"ZBUKR = '{bukrs}'")
        if zlsch:
            opts.append(f"AND ZLSCH = '{zlsch}'" if opts else f"ZLSCH = '{zlsch}'")
        return self.rfc.read_table(
            "T042E",
            fields=[
                "ZBUKR",
                "ZLSCH",
                "XBKKT",
                "XEOSC",
                "XELGB",
                "VONBT",
                "BISBT",
                "WAERS",
            ],
            options=opts or None,
        )

    def t042i(self, zbukr: str | None = None, zlsch: str | None = None) -> list[dict[str, str]]:
        opts = []
        if zbukr:
            opts.append(f"ZBUKR = '{zbukr}'")
        if zlsch:
            opts.append(f"AND ZLSCH = '{zlsch}'" if opts else f"ZLSCH = '{zlsch}'")
        return self.rfc.read_table("T042I", options=opts or None)

    def t042a(self, zbukr: str | None = None) -> list[dict[str, str]]:
        opts = [f"ZBUKR = '{zbukr}'"] if zbukr else None
        return self.rfc.read_table("T042A", options=opts)

    def t042y(self, zbukr: str | None = None) -> list[dict[str, str]]:
        opts = [f"ZBUKR = '{zbukr}'"] if zbukr else None
        return self.rfc.read_table("T042Y", options=opts)

    def t012(self, bukrs: str | None = None, hbkid: str | None = None) -> list[dict[str, str]]:
        opts = []
        if bukrs:
            opts.append(f"BUKRS = '{bukrs}'")
        if hbkid:
            opts.append(f"AND HBKID = '{hbkid}'" if opts else f"HBKID = '{hbkid}'")
        return self.rfc.read_table("T012", options=opts or None)

    def t012k(self, bukrs: str | None = None, hbkid: str | None = None) -> list[dict[str, str]]:
        opts = []
        if bukrs:
            opts.append(f"BUKRS = '{bukrs}'")
        if hbkid:
            opts.append(f"AND HBKID = '{hbkid}'" if opts else f"HBKID = '{hbkid}'")
        return self.rfc.read_table("T012K", options=opts or None)

    # --- Vendor master ---
    def lfa1(self, lifnr: str) -> list[dict[str, str]]:
        return self.rfc.read_table(
            "LFA1",
            fields=["LIFNR", "NAME1", "LAND1", "SPERR", "SPERM", "LOEVM"],
            options=[f"LIFNR = '{lifnr.zfill(10)}'"],
        )

    def lfb1(self, lifnr: str, bukrs: str) -> list[dict[str, str]]:
        return self.rfc.read_table(
            "LFB1",
            fields=[
                "LIFNR",
                "BUKRS",
                "ZWELS",
                "ZTERM",
                "ZAHLS",
                "HBKID",
                "ZINDT",
                "SPERR",
            ],
            options=[f"LIFNR = '{lifnr.zfill(10)}'", f"AND BUKRS = '{bukrs}'"],
        )

    def lfbk(self, lifnr: str) -> list[dict[str, str]]:
        return self.rfc.read_table(
            "LFBK",
            fields=["LIFNR", "BANKS", "BANKL", "BANKN", "BVTYP", "KOINH"],
            options=[f"LIFNR = '{lifnr.zfill(10)}'"],
        )

    def bnka(self, banks: str, bankl: str) -> list[dict[str, str]]:
        return self.rfc.read_table(
            "BNKA",
            fields=["BANKS", "BANKL", "BANKA", "ORT01"],
            options=[f"BANKS = '{banks}'", f"AND BANKL = '{bankl}'"],
        )

    # --- Open items ---
    def bsik(
        self,
        bukrs: str,
        lifnr: str | None = None,
        rowcount: int = 200,
    ) -> list[dict[str, str]]:
        opts = [f"BUKRS = '{bukrs}'"]
        if lifnr:
            opts.append(f"AND LIFNR = '{lifnr.zfill(10)}'")
        return self.rfc.read_table(
            "BSIK",
            fields=[
                "BUKRS",
                "LIFNR",
                "BELNR",
                "GJAHR",
                "BUZEI",
                "WRBTR",
                "WAERS",
                "ZFBDT",
                "ZTERM",
                "ZLSPR",
                "ZLSCH",
                "SHKZG",
            ],
            options=opts,
            rowcount=rowcount,
        )

    # --- Payment run results ---
    def reguv(self, laufd: str, laufi: str) -> list[dict[str, str]]:
        return self.rfc.read_table(
            "REGUV",
            fields=["LAUFD", "LAUFI", "XVORL", "XBUKR", "ANZPO", "STATU"],
            options=[f"LAUFD = '{laufd}'", f"AND LAUFI = '{laufi}'"],
        )

    def regup(self, laufd: str, laufi: str, rowcount: int = 500) -> list[dict[str, str]]:
        return self.rfc.read_table(
            "REGUP",
            fields=["LAUFD", "LAUFI", "VBLNR", "BUKRS", "LIFNR", "BELNR", "WRBTR", "WAERS"],
            options=[f"LAUFD = '{laufd}'", f"AND LAUFI = '{laufi}'"],
            rowcount=rowcount,
        )

    def reguh(self, laufd: str, laufi: str, rowcount: int = 200) -> list[dict[str, str]]:
        return self.rfc.read_table(
            "REGUH",
            fields=["LAUFD", "LAUFI", "VBLNR", "ZBUKR", "LIFNR", "RWBTR", "WAERS", "RZAWE"],
            options=[f"LAUFD = '{laufd}'", f"AND LAUFI = '{laufi}'"],
            rowcount=rowcount,
        )

    def fbzp_chain_snapshot(self, bukrs: str, zlsch: str, land1: str = "US") -> dict[str, Any]:
        return {
            "T042": self.t042(bukrs),
            "T042B": self.t042b(bukrs),
            "T042Z": self.t042z(land1, zlsch),
            "T042E": self.t042e(bukrs, zlsch),
            "T042I": self.t042i(bukrs, zlsch),
            "T042A": self.t042a(bukrs),
            "T042Y": self.t042y(bukrs),
            "T012": self.t012(bukrs),
            "T012K": self.t012k(bukrs),
        }
