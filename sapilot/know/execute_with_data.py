"""
Gather multi-table data pack → debug readiness → optionally run scenario.

This is the Co-pilot loop for "get data for scenario then execute".
"""

from __future__ import annotations

from typing import Any

from sapilot.connect.driver import GuiDriver
from sapilot.connect.rfc import RfcClientBase
from sapilot.copilot.knowledge import DataExtractor
from sapilot.copilot.scenarios import ScenarioContext, ScenarioRunner, load_scenario
from sapilot.know.gather import DataPack, ScenarioDataGatherer
from sapilot.report.journal import RunJournal


class ScenarioOrchestrator:
    def __init__(
        self,
        rfc: RfcClientBase,
        driver: GuiDriver | None = None,
        journal: RunJournal | None = None,
    ):
        self.rfc = rfc
        self.driver = driver
        self.journal = journal or RunJournal()
        self.gatherer = ScenarioDataGatherer(rfc)
        self.extractor = DataExtractor(rfc=rfc, driver=driver)

    def prepare(self, pack_or_scenario_id: str, params: dict[str, Any] | None = None) -> DataPack:
        packs = self.gatherer.packs
        pack_id = pack_or_scenario_id
        if pack_id not in packs:
            # map scenario id to pack if same name
            if pack_or_scenario_id in packs:
                pack_id = pack_or_scenario_id
            else:
                # try ptp_full_chain for unknown
                raise KeyError(pack_or_scenario_id)
        pack = self.gatherer.gather(pack_id, params)
        self.journal.append(
            "data_pack",
            {
                "pack_id": pack.pack_id,
                "ready": pack.ready,
                "summary": pack.summary,
                "findings": [f.to_dict() for f in pack.findings],
                "tables": {k: {"count": v.count, "ok": v.ok} for k, v in pack.tables.items()},
            },
        )
        return pack

    def debug(self, symptom: str, params: dict[str, Any] | None = None) -> DataPack:
        pack = self.gatherer.debug_message(symptom, params)
        self.journal.append("debug_pack", pack.to_dict())
        return pack

    def execute(
        self,
        scenario_id: str,
        params: dict[str, Any] | None = None,
        *,
        require_ready: bool = False,
        skip_gather: bool = False,
    ) -> dict[str, Any]:
        """
        1) Gather multi-table data for scenario
        2) If require_ready and blockers → stop with diagnosis
        3) Run scenario steps with knowledge channel already warm
        """
        params = dict(params or {})
        pack: DataPack | None = None
        if not skip_gather:
            try:
                pack = self.prepare(scenario_id, params)
            except KeyError:
                # no pack definition — still try scenario
                pack = None

        if pack and require_ready and not pack.ready:
            return {
                "ok": False,
                "blocked": True,
                "reason": "data pack not ready",
                "pack": pack.to_dict(),
                "journal": str(self.journal.path),
            }

        scenario = load_scenario(scenario_id)
        # Inject gathered table snapshots into scenario context vars
        ctx = ScenarioContext(
            driver=self.driver,
            extractor=self.extractor,
            journal=self.journal,
            params=params,
        )
        if pack:
            ctx.vars["data_pack"] = pack.to_dict()
            for tname, sl in pack.tables.items():
                ctx.vars[tname] = {
                    "channel": sl.channel,
                    "count": sl.count,
                    "rows": sl.rows,
                }
            if pack.fbzp:
                ctx.vars["fbzp"] = pack.fbzp

        result = ScenarioRunner(ctx).run(scenario)
        result["data_pack"] = pack.to_dict() if pack else None
        result["journal"] = str(self.journal.path)
        self.journal.append("scenario_with_data", {"id": scenario_id, "ok": result.get("ok")})
        return result
