"""SAPILOT CLI."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

console = Console()


def _ensure_env() -> None:
    # Load .env (OPENAI_API_KEY, SAP defaults, etc.) before anything else
    from sapilot.env_load import load_dotenv

    load_dotenv()
    # Lab default: allow unsigned local policy
    os.environ.setdefault("SAPILOT_ALLOW_UNSIGNED_POLICY", "1")
    if not os.environ.get("SAPILOT_DATA"):
        os.environ["SAPILOT_DATA"] = str(Path.cwd() / "data")


@click.group()
@click.version_option(package_name="sapilot")
def main() -> None:
    """SAPILOT — Autonomous SAP Execution Agent."""
    _ensure_env()


@main.command("preflight")
@click.option("--strict", is_flag=True, help="Fail on any required check")
@click.option("--json-out", "json_out", is_flag=True)
def preflight_cmd(strict: bool, json_out: bool) -> None:
    """Verify prerequisites; refuse with remediation messages if hard-fail."""
    from sapilot.preflight import run_preflight
    from sapilot.exceptions import PreflightError

    try:
        results = run_preflight(strict=strict)
    except PreflightError as e:
        if json_out:
            click.echo(json.dumps(e.checks, indent=2))
        else:
            _print_checks(e.checks)
            console.print(f"[red]{e}[/red]")
        sys.exit(2)

    if json_out:
        click.echo(json.dumps(results, indent=2))
    else:
        _print_checks(results)
        console.print("[green]Preflight OK (hard checks passed)[/green]")


def _print_checks(results: list[dict]) -> None:
    table = Table(title="SAPILOT Preflight")
    table.add_column("ID")
    table.add_column("OK")
    table.add_column("Message")
    table.add_column("Remediation")
    for r in results:
        table.add_row(
            r.get("id", ""),
            "✓" if r.get("ok") else "✗",
            r.get("message", ""),
            (r.get("remediation") or "")[:80],
        )
    console.print(table)


@main.command("diagnose")
@click.option("--bukrs", required=True, help="Company code")
@click.option("--method", "payment_method", required=True, help="Payment method e.g. A")
@click.option("--vendor", multiple=True, help="Vendor number(s); omit to scan BSIK")
@click.option("--land1", default="US")
@click.option("--laufd", default=None, help="Payment run date YYYYMMDD")
@click.option("--laufi", default=None, help="Payment run identification")
@click.option("--mock", is_flag=True, help="Use built-in mock SAP data (offline)")
@click.option("--connection", default=None, help="Vault connection name for live RFC")
@click.option("--out", "out_path", default=None, type=click.Path(), help="HTML report path")
def diagnose_cmd(
    bukrs: str,
    payment_method: str,
    vendor: tuple[str, ...],
    land1: str,
    laufd: str | None,
    laufi: str | None,
    mock: bool,
    connection: str | None,
    out_path: str | None,
) -> None:
    """
    Diagnostic engine (the product): FBZP + vendor + open items analysis.
    No GUI, no writes, near-zero audit risk.
    """
    from sapilot.connect.rfc import MockRfcClient, RfcClient
    from sapilot.connect.logon import load_connection
    from sapilot.diagnose.engine import PaymentRunDiagnosticEngine
    from sapilot.know.tables import KnowledgeTables
    from sapilot.report.html import render_html_report
    from sapilot.report.journal import RunJournal
    from sapilot.security.redaction import RedactionGate
    from sapilot.demo_data import seed_demo_tables

    journal = RunJournal()
    redaction = RedactionGate()

    if mock or not connection:
        rfc: MockRfcClient | RfcClient = MockRfcClient()
        seed_demo_tables(rfc)
        console.print("[yellow]Using mock SAP data (--mock or no --connection)[/yellow]")
    else:
        params = load_connection(connection)
        rfc = RfcClient(params)
        rfc.connect()

    tables = KnowledgeTables(rfc)
    engine = PaymentRunDiagnosticEngine(tables)
    report = engine.diagnose(
        company_code=bukrs,
        payment_method=payment_method,
        vendors=list(vendor) if vendor else None,
        land1=land1,
        laufd=laufd,
        laufi=laufi,
    )
    journal.append("diagnosis", redaction.redact_payload(report.model_dump(mode="json")))

    console.print(f"\n[bold]{report.summary}[/bold]\n")
    table = Table(title="Findings")
    table.add_column("Sev")
    table.add_column("Symptom")
    table.add_column("Table")
    table.add_column("Remediation")
    for f in report.findings:
        table.add_row(f.severity, f.symptom[:60], f.cause_table, f.remediation[:50])
    console.print(table)

    html_path = Path(out_path) if out_path else journal.dir / "diagnosis.html"
    render_html_report(
        html_path,
        run_id=journal.run_id,
        diagnosis=report,
        journal_events=journal.read_all(),
    )
    console.print(f"[green]Report:[/green] {html_path}")
    console.print(f"[green]Journal:[/green] {journal.path}")


@main.command("vault")
@click.argument("action", type=click.Choice(["set", "list"]))
@click.argument("name", required=False)
@click.option("--ashost", default="")
@click.option("--sysnr", default="00")
@click.option("--client", default="100")
@click.option("--user", default="")
@click.option("--password", default="", hide_input=True)
@click.option("--lang", default="EN")
@click.option(
    "--system",
    "system_description",
    default="",
    help="Exact SAP Logon Pad system description (for GUI login)",
)
def vault_cmd(
    action: str,
    name: str | None,
    ashost: str,
    sysnr: str,
    client: str,
    user: str,
    password: str,
    lang: str,
    system_description: str,
) -> None:
    """Store or list DPAPI/passphrase-encrypted SAP credentials."""
    from sapilot.security.vault import CredentialVault

    v = CredentialVault()
    if action == "list":
        for n in v.list_names():
            console.print(n)
        return
    if not name:
        raise click.UsageError("name required for set")
    if not password:
        password = click.prompt("Password", hide_input=True)
    v.set(
        name,
        {
            "ashost": ashost or os.environ.get("SAPILOT_ASHOST", ""),
            "sysnr": sysnr,
            "client": client,
            "user": user or os.environ.get("SAPILOT_USER", ""),
            "passwd": password,
            "lang": lang,
            "system": system_description or name,
            "description": system_description or name,
        },
    )
    console.print(f"[green]Stored connection '{name}' in vault[/green]")
    if system_description:
        console.print(f"  Logon description: {system_description}")


@main.command("approve")
@click.option("--scope", required=True, help="Action scope e.g. f110.proposal")
def approve_cmd(scope: str) -> None:
    """Issue a short-lived T2 approval token (human-operated)."""
    from sapilot.policy.approval import ApprovalGate

    gate = ApprovalGate()
    token = gate.issue(scope)
    console.print(f"Scope: {scope}")
    console.print(f"Token: [bold]{token.token}[/bold]")
    console.print(f"Expires in {int(token.expires_at - token.issued_at)}s")
    console.print("Pass via env SAPILOT_APPROVAL_TOKEN or --approval-token on run")


@main.command("run")
@click.argument("goal")
@click.option("--mock", is_flag=True, help="Offline mock only")
@click.option("--attach", is_flag=True, help="Attach to already-open SAP GUI session")
@click.option("--connection", default=None, help="Vault connection name")
@click.option("--system", default=None, help="SAP Logon Pad system description")
@click.option("--client", default=None)
@click.option("--user", default=None)
@click.option("--password", default=None)
@click.option("--max-steps", default=20, type=int)
@click.option("--cccategory", default=None)
@click.option("--approval-token", default=None)
def run_cmd(
    goal: str,
    mock: bool,
    attach: bool,
    connection: str | None,
    system: str | None,
    client: str | None,
    user: str | None,
    password: str | None,
    max_steps: int,
    cccategory: str | None,
    approval_token: str | None,
) -> None:
    """NL Co-pilot on REAL SAP GUI (prefer `sapilot copilot goal`)."""
    cp = _copilot_from_opts(
        mock=mock,
        attach=attach,
        connection=connection,
        system=system,
        client=client,
        user=user,
        password=password,
        cccategory=cccategory or ("D" if mock else None),
        no_rfc=False,
    )
    cp.approval_token = approval_token or cp.approval_token
    try:
        outcome = cp.run_goal(goal, max_steps=max_steps)
        console.print(f"Tier: [bold]{cp.tier_ctx.tier.value if cp.tier_ctx else '?'}[/bold]")
        console.print(f"Outcome: [bold]{outcome.value}[/bold]")
        console.print(f"Journal: {cp.journal.path}")
    finally:
        cp.disconnect()


# ---------------------------------------------------------------------------
# Co-pilot: login, click, extract tables, run scenarios
# ---------------------------------------------------------------------------


@main.group("train")
def train_grp() -> None:
    """Train the bot: where to click, which fields to fill, how to debug."""


@train_grp.command("capture")
@click.option("--tcode", default="", help="Hint current tcode if Info.Transaction empty")
def train_capture(tcode: str) -> None:
    """
    Capture live SAP screen control IDs + positions (needs GUI scripting).

    1. Log into SAP and open the screen you want to train (e.g. XK03)
    2. Run this command
    3. Labels are auto-suggested (LIFNR, OK_CODE, …)
    """
    from sapilot.autobot.trainer import BotTrainer

    tr = BotTrainer()
    if not tr.bind_session():
        console.print("[red]No scriptable session. Enable scripting + log in first.[/red]")
        raise SystemExit(2)
    screen = tr.capture_screen(tcode)
    console.print(f"[green]Captured {screen.tcode}[/green] — {screen.title}")
    console.print(f"Controls: {len(screen.controls)}")
    console.print("Auto labels:")
    for k, v in screen.labels.items():
        console.print(f"  [bold]{k}[/bold] → {v}")
    console.print(f"Saved: {tr.store.path}")
    # show top changeable fields for manual labeling
    chg = [c for c in screen.controls if c.changeable][:25]
    if chg:
        table = Table(title="Changeable fields (train label these)")
        table.add_column("Id")
        table.add_column("Name")
        table.add_column("Text")
        for c in chg:
            table.add_row(c.id[-60:], c.name, c.text[:30])
        console.print(table)


@train_grp.command("label")
@click.argument("tcode")
@click.argument("label")
@click.argument("control_id")
def train_label(tcode: str, label: str, control_id: str) -> None:
    """Map a semantic label to a control id, e.g. train label XK03 LIFNR wnd[0]/usr/..."""
    from sapilot.autobot.trainer import TrainingStore

    store = TrainingStore()
    store.label(tcode, label.upper(), control_id)
    console.print(f"[green]{tcode}.{label.upper()}[/green] → {control_id}")


@train_grp.command("list")
def train_list() -> None:
    """List trained screens and labels."""
    from sapilot.autobot.trainer import TrainingStore

    store = TrainingStore()
    screens = store.list_screens()
    if not screens:
        console.print("No training yet. Open SAP screen and run: sapilot train capture")
        return
    for t in screens:
        scr = store.get_screen(t) or {}
        console.print(f"[bold]{t}[/bold] {scr.get('title', '')} ({len(scr.get('controls') or [])} controls)")
        for k, v in (scr.get("labels") or {}).items():
            console.print(f"   {k}: {v}")


@train_grp.command("import-vbs")
@click.argument("vbs_file", type=click.Path(exists=True))
@click.option("--tcode", required=True)
def train_import_vbs(vbs_file: str, tcode: str) -> None:
    """Import SAP Script Recording .vbs to learn field ids + fill order."""
    from pathlib import Path

    from sapilot.autobot.trainer import BotTrainer

    n = BotTrainer().import_vbs(Path(vbs_file), tcode)
    console.print(f"[green]Imported {n} fill steps for {tcode}[/green]")


@train_grp.command("debug")
@click.argument("symptom")
def train_debug(symptom: str) -> None:
    """How to debug a symptom (recipes + pack routing)."""
    from sapilot.autobot.trainer import BotTrainer
    from sapilot.know.gather import ScenarioDataGatherer
    from sapilot.demo_data_ptp import seed_ptp_tables
    from sapilot.connect.rfc import MockRfcClient

    tr = BotTrainer()
    recipes = tr.suggest_debug(symptom)
    console.print(f"[bold]Debug recipes for:[/bold] {symptom}")
    for r in recipes:
        console.print(f"  pack={r.get('pack_id')}  notes={r.get('notes')}")
        for c in r.get("checks") or []:
            console.print(f"    - {c}")
    # also run data gather on first pack
    if recipes:
        rfc = MockRfcClient()
        seed_ptp_tables(rfc)
        pack_id = recipes[0].get("pack_id")
        if pack_id:
            try:
                pack = ScenarioDataGatherer(rfc).gather(pack_id)
                console.print(f"\n[bold]Live pack check ({pack_id}):[/bold] {pack.summary}")
                for f in pack.findings[:8]:
                    console.print(f"  [{f.severity}] {f.table}.{f.field}: {f.message}")
            except Exception as e:
                console.print(f"pack gather: {e}")


@train_grp.command("seed-defaults")
def train_seed_defaults() -> None:
    """Seed standard PTP field labels from research catalog into training store."""
    from sapilot.autobot.nav_catalog import TCODE_SCREENS
    from sapilot.autobot.trainer import TrainingStore, ScreenTraining, ControlHit
    from datetime import datetime, timezone

    store = TrainingStore()
    n = 0
    for tcode, scr in TCODE_SCREENS.items():
        if scr.get("alias_of"):
            continue
        labels = {}
        controls = []
        for label, candidates in (scr.get("fields") or {}).items():
            if candidates:
                labels[label] = candidates[0]
                controls.append(ControlHit(id=candidates[0], name=label))
        labels["OK_CODE"] = "wnd[0]/tbar[0]/okcd"
        st = ScreenTraining(
            tcode=tcode,
            title=f"Seeded catalog {tcode}",
            captured_at=datetime.now(timezone.utc).isoformat(),
            controls=controls,
            labels=labels,
            fill_order=[{"label": lab, "control_id": cid} for lab, cid in labels.items() if lab != "OK_CODE"],
            notes="Seeded from nav_catalog research playbook",
        )
        store.upsert_screen(st)
        n += 1
    console.print(f"[green]Seeded {n} screens into {store.path}[/green]")
    console.print(store.export_markdown_report() if False else "")
    from sapilot.autobot.trainer import BotTrainer

    path = BotTrainer().export_markdown_report()
    console.print(f"Report: {path}")


@train_grp.command("apply")
@click.argument("tcode")
@click.option("--lifnr", default="0000100001")
@click.option("--bukrs", default="1000")
@click.option("--ebeln", default="4500000001")
@click.option("--matnr", default="000000000000100000")
@click.option("--banfn", default="0010000001")
def train_apply(tcode: str, lifnr: str, bukrs: str, ebeln: str, matnr: str, banfn: str) -> None:
    """
    Use training to navigate + fill the live screen correctly.
    Example: sapilot train apply XK03 --lifnr 0000100001 --bukrs 1000
    """
    from sapilot.autobot.trainer import BotTrainer

    tr = BotTrainer()
    if not tr.bind_session():
        console.print("[red]No scriptable session[/red]")
        raise SystemExit(2)
    values = {
        "LIFNR": lifnr,
        "BUKRS": bukrs,
        "EBELN": ebeln,
        "MATNR": matnr,
        "BANFN": banfn,
        "PARTNER": lifnr,
        "LAUFD": "20260812",
        "LAUFI": "PTP001",
        "GJAHR": "2026",
        "BELNR": "5105600001",
        "WERKS": "1000",
        "EKORG": "1000",
    }
    res = tr.apply_training_to_navigator(tcode, tr.session, values)
    console.print(res)


@main.group("mega")
def mega_grp() -> None:
    """Mega SAP Co-pilot — online login, multi-table extract, inject, execute."""


@mega_grp.command("ui")
@click.option("--port", default=8777, type=int)
def mega_ui(port: int) -> None:
    """Start Mega Co-pilot web UI (http://127.0.0.1:PORT)."""
    from sapilot.mega.web import main as mega_main

    mega_main(port=port)


@mega_grp.command("login")
@click.option("--system", default="Vista")
@click.option("--client", default="100")
@click.option("--user", default=None)
@click.option("--password", default=None)
@click.option("--connection", default="vista")
def mega_login(system: str, client: str, user: str | None, password: str | None, connection: str) -> None:
    """Online SAP GUI login with visible mouse + Client/User/Password."""
    from sapilot.mega.engine import MegaCopilot

    if not password and user:
        password = click.prompt("SAP password", hide_input=True)
    m = MegaCopilot(
        system=system,
        client=client,
        user=user,
        password=password,
        connection=connection,
        allow_mock=False,
        show_mouse=True,
    )
    res = m.login()
    console.print(res)
    console.print(f"Journal: {m.journal.path}")


@mega_grp.command("gather")
@click.argument("pack_id")
@click.option("--attach", is_flag=True, help="Use open SAP session for SE16N extract")
@click.option("--allow-mock", is_flag=True)
def mega_gather(pack_id: str, attach: bool, allow_mock: bool) -> None:
    """Extract multi-table pack online (RFC or live SE16N)."""
    from sapilot.mega.engine import MegaCopilot

    m = MegaCopilot(allow_mock=allow_mock, show_mouse=True)
    if attach:
        m.attach()
    elif allow_mock:
        m.extractor = __import__("sapilot.mega.extract", fromlist=["OnlineExtractor"]).OnlineExtractor(
            allow_mock=True
        )
    else:
        try:
            m.attach()
        except Exception:
            console.print("[yellow]No session — trying login from vault…[/yellow]")
            m.login()
    pack = m.gather(pack_id)
    console.print(f"[bold]{pack.get('summary')}[/bold]")
    for t, sl in (pack.get("tables") or {}).items():
        console.print(f"  {t}: {sl.get('count')} rows ok={sl.get('ok')}")
    for f in (pack.get("findings") or [])[:12]:
        console.print(f"  [{f.get('severity')}] {f.get('table')}.{f.get('field')}: {f.get('message')}")


@mega_grp.command("run")
@click.argument("scenario_id")
@click.option("--inject-table", default=None, help="Inject first row of this table into GUI before run")
@click.option("--require-ready", is_flag=True)
@click.option("--attach", is_flag=True)
def mega_run(scenario_id: str, inject_table: str | None, require_ready: bool, attach: bool) -> None:
    """Online: gather tables → inject data → execute scenario."""
    from sapilot.mega.engine import MegaCopilot

    m = MegaCopilot(allow_mock=False, show_mouse=True)
    if attach:
        m.attach()
    else:
        try:
            m.attach()
        except Exception:
            m.login()
    res = m.run_scenario(
        scenario_id,
        require_ready=require_ready,
        inject_table=inject_table,
    )
    console.print(res)
    console.print(f"Journal: {m.journal.path}")


@main.group("copilot")
def copilot_grp() -> None:
    """SAP GUI Co-pilot — REAL Logon Pad login (default), clicks, table extract."""


def _copilot_from_opts(
    mock: bool,
    attach: bool,
    connection: str | None,
    system: str | None,
    client: str | None,
    user: str | None,
    password: str | None,
    cccategory: str | None,
    no_rfc: bool,
    language: str = "EN",
) -> Any:
    """
    Build Co-pilot for REAL SAP GUI by default.
    Mock only when --mock is set. Password prompted interactively if missing.
    """
    from sapilot.copilot.engine import Copilot

    system = system or os.environ.get("SAPILOT_SYSTEM") or os.environ.get("SAPILOT_LOGON_SYSTEM")
    client = client or os.environ.get("SAPILOT_CLIENT")
    user = user or os.environ.get("SAPILOT_USER")
    password = password or os.environ.get("SAPILOT_PASSWORD")

    if mock:
        console.print("[yellow]Mock mode — not connecting to SAP GUI[/yellow]")
    elif attach:
        console.print("[cyan]Attaching to open SAP GUI session…[/cyan]")
    elif connection:
        console.print(f"[cyan]SAP Logon Pad via vault connection '{connection}'…[/cyan]")
    else:
        # Primary path: system + user + password → real Logon Pad
        if not system:
            system = click.prompt("SAP Logon system description (exact name in SAP Logon Pad)")
        if not client:
            client = click.prompt("Client", default=os.environ.get("SAPILOT_CLIENT", "100"))
        if not user:
            user = click.prompt("SAP user")
        if not password:
            password = click.prompt("SAP password", hide_input=True)
        console.print(
            f"[cyan]Opening SAP Logon Pad → system=[bold]{system}[/bold] "
            f"client={client} user={user}[/cyan]"
        )

    if not mock and not attach and connection and not password:
        # vault usually has password; if CLI override user without password, prompt
        pass
    if not mock and not attach and not connection and user and not password:
        password = click.prompt("SAP password", hide_input=True)

    return Copilot(
        mock=mock,
        attach=attach,
        connection=connection,
        system=system,
        client=client,
        user=user,
        password=password,
        language=language,
        cccategory=cccategory,
        use_rfc=not no_rfc,
    )


@copilot_grp.command("scenarios")
def copilot_scenarios() -> None:
    """List built-in transaction scenarios."""
    from sapilot.copilot.scenarios import list_scenarios

    table = Table(title="Co-pilot scenarios")
    table.add_column("ID")
    table.add_column("Title")
    table.add_column("Description")
    for s in list_scenarios():
        table.add_row(s["id"], s["title"], (s.get("description") or "")[:70])
    console.print(table)


def _rfc_for_data(mock: bool):
    """RFC/mock client for multi-table gather (no GUI required)."""
    if mock:
        from sapilot.connect.rfc import MockRfcClient
        from sapilot.demo_data_ptp import seed_ptp_tables

        rfc = MockRfcClient()
        seed_ptp_tables(rfc)
        console.print("[yellow]Using mock PTP table data[/yellow]")
        return rfc
    try:
        from sapilot.security.vault import CredentialVault
        from sapilot.connect.logon import load_connection
        from sapilot.connect.rfc import RfcClient

        params = load_connection(
            "vista", CredentialVault(passphrase=os.environ.get("SAPILOT_VAULT_PASSPHRASE", "sapilot-local"))
        )
        rfc = RfcClient(params)
        rfc.connect()
        console.print(f"[green]Live RFC[/green] {params.get('ashost')}")
        return rfc
    except Exception as e:
        console.print(f"[yellow]Live RFC failed ({e}); falling back to mock PTP data[/yellow]")
        from sapilot.connect.rfc import MockRfcClient
        from sapilot.demo_data_ptp import seed_ptp_tables

        rfc = MockRfcClient()
        seed_ptp_tables(rfc)
        return rfc


def _common_ptp_params(**kwargs: str) -> dict:
    return {
        "lifnr": kwargs.get("lifnr") or "0000100001",
        "bukrs": kwargs.get("bukrs") or "1000",
        "ekorg": kwargs.get("ekorg") or "1000",
        "werks": kwargs.get("werks") or "1000",
        "matnr": kwargs.get("matnr") or "000000000000100000",
        "banfn": kwargs.get("banfn") or "0010000001",
        "ebeln": kwargs.get("ebeln") or "4500000001",
        "belnr_inv": kwargs.get("belnr_inv") or "5105600001",
        "gjahr": kwargs.get("gjahr") or "2026",
        "method": kwargs.get("method") or "A",
        "land1": kwargs.get("land1") or "US",
        "laufd": kwargs.get("laufd") or "20260812",
        "laufi": kwargs.get("laufi") or "PTP001",
    }


@copilot_grp.command("mouse-demo")
@click.option("--off", is_flag=True, help="Disable mouse (SAPILOT_SHOW_MOUSE=0)")
def copilot_mouse_demo(off: bool) -> None:
    """
    Prove the Co-pilot can move the real mouse on the SAP window.

    Watch the cursor sweep across the open SAP Easy Access / session window.
    """
    if off:
        os.environ["SAPILOT_SHOW_MOUSE"] = "0"
    else:
        os.environ["SAPILOT_SHOW_MOUSE"] = "1"
    from sapilot.connect.mouse import demo_wiggle, mouse_enabled

    console.print(
        f"[cyan]Mouse visibility:[/cyan] {'ON' if mouse_enabled() else 'OFF'} "
        f"(SAPILOT_SHOW_MOUSE={os.environ.get('SAPILOT_SHOW_MOUSE', '1')})"
    )
    console.print("Moving cursor on SAP window — watch your screen…")
    try:
        demo_wiggle()
        console.print("[green]Done. You should have seen the cursor move.[/green]")
    except Exception as e:
        console.print(f"[red]Mouse demo failed:[/red] {e}")
        console.print("Open any SAP GUI window first, then retry.")


@copilot_grp.command("packs")
def copilot_packs() -> None:
    """List multi-table data packs (what tables each scenario loads)."""
    from sapilot.know.gather import list_packs

    table = Table(title="Data packs (multi-table)")
    table.add_column("ID")
    table.add_column("Process")
    table.add_column("Title")
    table.add_column("Tables")
    table.add_column("Params")
    for p in list_packs():
        table.add_row(p["id"], p["process"], p["title"], p["tables"], p["params"])
    console.print(table)


@copilot_grp.command("gather")
@click.argument("pack_id")
@click.option("--mock/--live", default=True, help="Mock PTP tables (default) or live RFC")
@click.option("--lifnr", default="0000100001")
@click.option("--bukrs", default="1000")
@click.option("--ekorg", default="1000")
@click.option("--werks", default="1000")
@click.option("--matnr", default="100000")
@click.option("--banfn", default="0010000001")
@click.option("--ebeln", default="4500000001")
@click.option("--belnr-inv", "belnr_inv", default="5105600001")
@click.option("--gjahr", default="2026")
@click.option("--method", default="A")
@click.option("--json-out", is_flag=True)
def copilot_gather(
    pack_id: str,
    mock: bool,
    lifnr: str,
    bukrs: str,
    ekorg: str,
    werks: str,
    matnr: str,
    banfn: str,
    ebeln: str,
    belnr_inv: str,
    gjahr: str,
    method: str,
    json_out: bool,
) -> None:
    """
    Access multiple database tables for a scenario pack and print readiness.

    Example:
      sapilot copilot gather ptp_06_purchase_order --mock
      sapilot copilot gather ptp_full_chain --mock
      sapilot copilot gather ptp_10_payment_readiness --mock
    """
    from sapilot.know.gather import ScenarioDataGatherer
    from sapilot.report.journal import RunJournal
    import json as _json

    rfc = _rfc_for_data(mock)
    params = _common_ptp_params(
        lifnr=lifnr,
        bukrs=bukrs,
        ekorg=ekorg,
        werks=werks,
        matnr=matnr,
        banfn=banfn,
        ebeln=ebeln,
        belnr_inv=belnr_inv,
        gjahr=gjahr,
        method=method,
    )
    pack = ScenarioDataGatherer(rfc).gather(pack_id, params)
    journal = RunJournal()
    journal.append("gather", pack.to_dict())

    if json_out:
        click.echo(_json.dumps(pack.to_dict(), indent=2, default=str))
        return

    console.print(f"[bold]{pack.summary}[/bold]")
    t = Table(title="Tables read")
    t.add_column("Table")
    t.add_column("Rows")
    t.add_column("OK")
    t.add_column("Note")
    for name, sl in pack.tables.items():
        t.add_row(name, str(sl.count), "✓" if sl.ok else "✗", (sl.note or "")[:50])
    console.print(t)
    if pack.findings:
        ft = Table(title="Debug findings")
        ft.add_column("Sev")
        ft.add_column("Table")
        ft.add_column("Field")
        ft.add_column("Message")
        ft.add_column("Current")
        for f in pack.findings:
            ft.add_row(f.severity, f.table, f.field, f.message[:55], str(f.current or "")[:20])
        console.print(ft)
    console.print(f"Journal: {journal.path}")
    console.print(f"Ready to execute scenario: [bold]{'YES' if pack.ready else 'NO — fix blockers first'}[/bold]")


@copilot_grp.command("debug")
@click.argument("symptom")
@click.option("--mock/--live", default=True)
@click.option("--lifnr", default="0000100001")
@click.option("--bukrs", default="1000")
@click.option("--ebeln", default="4500000001")
@click.option("--matnr", default="100000")
def copilot_debug(symptom: str, mock: bool, lifnr: str, bukrs: str, ebeln: str, matnr: str) -> None:
    """
    Debug a problem by reading the right multi-table pack for the symptom.

    Example:
      sapilot copilot debug "no goods receipt for PO" --mock
      sapilot copilot debug "payment method not found" --mock
    """
    from sapilot.know.gather import ScenarioDataGatherer
    from sapilot.report.journal import RunJournal

    rfc = _rfc_for_data(mock)
    params = _common_ptp_params(lifnr=lifnr, bukrs=bukrs, ebeln=ebeln, matnr=matnr)
    pack = ScenarioDataGatherer(rfc).debug_message(symptom, params)
    journal = RunJournal()
    journal.append("debug", pack.to_dict())
    console.print(f"[bold]{pack.summary}[/bold]")
    for f in pack.findings[:25]:
        console.print(f"  [{f.severity}] {f.table}.{f.field}: {f.message} ({f.current or ''})")
    console.print(f"Tables: {', '.join(f'{k}({v.count})' for k,v in pack.tables.items())}")
    console.print(f"Journal: {journal.path}")


@copilot_grp.command("prepare-run")
@click.argument("scenario_id")
@click.option("--mock/--live", default=True)
@click.option("--require-ready", is_flag=True, help="Abort execute if data pack has blockers")
@click.option("--lifnr", default="0000100001")
@click.option("--bukrs", default="1000")
@click.option("--ebeln", default="4500000001")
@click.option("--matnr", default="100000")
@click.option("--method", default="A")
@click.option("--laufd", default="20260812")
@click.option("--laufi", default="PTP001")
def copilot_prepare_run(
    scenario_id: str,
    mock: bool,
    require_ready: bool,
    lifnr: str,
    bukrs: str,
    ebeln: str,
    matnr: str,
    method: str,
    laufd: str,
    laufi: str,
) -> None:
    """
    Gather multi-table data for the scenario, debug readiness, then execute.

    Example:
      sapilot copilot prepare-run ptp_06_purchase_order --mock
      sapilot copilot prepare-run ptp_10_payment_readiness --mock --require-ready
    """
    from sapilot.connect.driver import GuiDriver
    from sapilot.connect.gui import MockGuiSession
    from sapilot.copilot.engine import _mock_screens
    from sapilot.know.execute_with_data import ScenarioOrchestrator
    from sapilot.report.journal import RunJournal
    from sapilot.schemas import GuiElement, ScreenSnapshot

    rfc = _rfc_for_data(mock)
    params = _common_ptp_params(
        lifnr=lifnr, bukrs=bukrs, ebeln=ebeln, matnr=matnr, method=method, laufd=laufd, laufi=laufi
    )
    gui = MockGuiSession(screens=_mock_screens(), initial="SESSION_MANAGER")

    def win(tcode: str, title: str) -> ScreenSnapshot:
        return ScreenSnapshot(
            tcode=tcode,
            title=title,
            elements=GuiElement(
                id="wnd[0]",
                type="GuiMainWindow",
                text=title,
                children=[
                    GuiElement(id="wnd[0]/tbar[0]/okcd", type="GuiOkCodeField", name="okcd", changeable=True),
                    GuiElement(id="wnd[0]/usr/ctxtRF02K-LIFNR", type="GuiCTextField", name="RF02K-LIFNR", changeable=True),
                    GuiElement(id="wnd[0]/usr/ctxtRF02K-BUKRS", type="GuiCTextField", name="RF02K-BUKRS", changeable=True),
                    GuiElement(id="wnd[0]/usr/ctxtKD_LIFNR-LOW", type="GuiCTextField", name="KD_LIFNR-LOW", changeable=True),
                    GuiElement(id="wnd[0]/usr/ctxtKD_BUKRS-LOW", type="GuiCTextField", name="KD_BUKRS-LOW", changeable=True),
                    GuiElement(id="wnd[0]/usr/txtF110V-LAUFD", type="GuiTextField", name="F110V-LAUFD", changeable=True),
                    GuiElement(id="wnd[0]/usr/txtF110V-LAUFI", type="GuiTextField", name="F110V-LAUFI", changeable=True),
                ],
            ),
        )

    for tc, title in [
        ("ME53N", "Display Purchase Requisition"),
        ("ME23N", "Display Purchase Order"),
        ("XK03", "Display Vendor"),
        ("FBL1N", "Vendor Line Items"),
        ("F110", "Automatic Payment Transactions"),
        ("SE16N", "General Table Display"),
    ]:
        gui.load_screen(tc, win(tc, title))

    orch = ScenarioOrchestrator(rfc, driver=GuiDriver(gui, settle_seconds=0.0), journal=RunJournal())
    console.print(f"[bold]1) Gather data for {scenario_id}…[/bold]")
    try:
        pack = orch.prepare(scenario_id, params)
        console.print(f"   {pack.summary}")
        for f in pack.findings[:8]:
            console.print(f"   [{f.severity}] {f.table}.{f.field}: {f.message}")
    except KeyError:
        console.print(f"[yellow]No data pack for {scenario_id}; executing scenario only[/yellow]")
        pack = None

    console.print(f"[bold]2) Execute scenario {scenario_id}…[/bold]")
    result = orch.execute(scenario_id, params, require_ready=require_ready, skip_gather=pack is None)
    if result.get("blocked"):
        console.print("[red]Blocked — fix data pack findings before execute[/red]")
        console.print(f"Journal: {result.get('journal')}")
        return
    console.print(
        f"Result: [{'green' if result.get('ok') else 'red'}]{result.get('ok')}[/] "
        f"steps={result.get('steps_run')}"
    )
    console.print(f"Journal: {result.get('journal')}")


@copilot_grp.command("login")
@click.option("--system", default=None, help="Exact SAP Logon Pad system description")
@click.option("--client", default=None)
@click.option("--user", default=None)
@click.option("--password", default=None)
@click.option("--connection", default=None, help="Or use vault connection name")
@click.option("--lang", default="EN")
@click.option("--no-rfc", is_flag=True)
def copilot_login(
    system: str | None,
    client: str | None,
    user: str | None,
    password: str | None,
    connection: str | None,
    lang: str,
    no_rfc: bool,
) -> None:
    """
    Open SAP Logon Pad and log in with username/password (REAL GUI).

    Example:
      sapilot copilot login --system "ECC Dev" --client 100 --user MYUSER
    """
    cp = _copilot_from_opts(
        mock=False,
        attach=False,
        connection=connection,
        system=system,
        client=client,
        user=user,
        password=password,
        cccategory=None,
        no_rfc=no_rfc,
        language=lang,
    )
    from sapilot.exceptions import CredentialsEnteredNoScripting
    from sapilot.connect.logon import gui_logon, gui_logon_from_vault
    from sapilot.security.vault import CredentialVault
    import os as _os

    try:
        # Direct logon path so we always fill user/password even when COM session is blocked
        if connection:
            try:
                vault = CredentialVault(passphrase=_os.environ.get("SAPILOT_VAULT_PASSPHRASE"))
            except Exception:
                vault = CredentialVault(passphrase="sapilot-local")
            try:
                gui_logon_from_vault(connection, vault)
            except CredentialsEnteredNoScripting as e:
                console.print("[green]Username and password were entered on the SAP login screen.[/green]")
                console.print(f"  {e}")
                console.print(
                    "[yellow]Scripting is off on the server — check the SAP window for login result. "
                    "Ask Basis for sapgui/user_scripting=TRUE for full Co-pilot control.[/yellow]"
                )
                return
        else:
            try:
                gui_logon(
                    system or "Vista",
                    client or "100",
                    user or "",
                    password or "",
                    lang,
                )
            except CredentialsEnteredNoScripting as e:
                console.print("[green]Username and password were entered on the SAP login screen.[/green]")
                console.print(f"  {e}")
                return

        cp.connect()
        screen = cp.screen()
        console.print("[green]Logged into real SAP GUI via Logon Pad[/green]")
        console.print(f"  System : {cp.system}")
        console.print(f"  Client : {cp.client}")
        console.print(f"  User   : {cp.user}")
        console.print(f"  Tier   : {cp.tier_ctx.tier.value if cp.tier_ctx else '?'}")
        console.print(f"  Title  : {screen.get('title')}")
        console.print(f"  TCode  : {screen.get('tcode')}")
        console.print(f"  Status : {screen.get('status_bar')}")
        console.print(f"Journal: {cp.journal.path}")
        console.print(
            "[dim]Session stays open in SAP GUI. Use --attach on later commands.[/dim]"
        )
    except CredentialsEnteredNoScripting as e:
        console.print("[green]Username and password were entered on the SAP login screen.[/green]")
        console.print(f"  {e}")
    finally:
        try:
            cp.disconnect()
        except Exception:
            pass


@copilot_grp.command("run")
@click.argument("scenario_id")
@click.option("--mock", is_flag=True, help="Offline mock only (NOT real SAP)")
@click.option("--attach", is_flag=True, help="Attach to already-open SAP GUI")
@click.option("--connection", default=None, help="Vault name (Logon Pad + optional RFC)")
@click.option("--system", default=None, help="SAP Logon Pad system description (exact name)")
@click.option("--client", default=None, help="SAP client")
@click.option("--user", default=None, help="SAP user")
@click.option("--password", default=None, help="SAP password (prompted if omitted)")
@click.option("--lang", default="EN")
@click.option("--cccategory", default=None, help="Only for mock tier override")
@click.option("--no-rfc", is_flag=True, help="GUI only — skip RFC")
@click.option("--bukrs", default="1000")
@click.option("--method", default="A")
@click.option("--lifnr", default=None, help="Vendor number. Omit to auto-discover from LFB1.")
@click.option("--laufd", default="20260812")
@click.option("--laufi", default="ACH001")
@click.option("--table", default="T042E", help="For read_table / se16_browse scenarios")
def copilot_run(
    scenario_id: str,
    mock: bool,
    attach: bool,
    connection: str | None,
    system: str | None,
    client: str | None,
    user: str | None,
    password: str | None,
    lang: str,
    cccategory: str | None,
    no_rfc: bool,
    bukrs: str,
    method: str,
    lifnr: str | None,
    laufd: str,
    laufi: str,
    table: str,
) -> None:
    """
    Run a scenario on REAL SAP GUI (Logon Pad). Use --mock only for offline tests.

    Examples:
      sapilot copilot run f110_parameters --system "ECC Dev" --client 100 --user BOT
      sapilot copilot run f110_diagnose --connection myecc
      sapilot copilot run f110_parameters --attach
      sapilot copilot run f110_diagnose --mock
      sapilot copilot run vendor_display --attach --bukrs 1000   (auto-discovers a vendor)
    """
    from sapilot.copilot.scenarios import load_scenario

    cp = _copilot_from_opts(
        mock=mock,
        attach=attach,
        connection=connection,
        system=system,
        client=client,
        user=user,
        password=password,
        cccategory=cccategory or ("D" if mock else None),
        no_rfc=no_rfc,
        language=lang,
    )
    try:
        scenario_def = load_scenario(scenario_id)
        needs_lifnr = "lifnr" in (scenario_def.get("params") or [])
        if needs_lifnr and not lifnr:
            console.print(
                f"[dim]No --lifnr given — reading LFB1 to find a vendor in company code "
                f"{bukrs} on its own…[/dim]"
            )
            lfb1 = cp.extract_table("LFB1", rowcount=25)
            rows = lfb1.get("rows", [])
            match = next(
                (r for r in rows if str(r.get("BUKRS", "")).strip() == str(bukrs).strip()),
                None,
            ) or (rows[0] if rows else None)
            if not match or not str(match.get("LIFNR", "")).strip():
                console.print(
                    "[red]Auto-discovery failed: LFB1 returned no usable rows. "
                    "Pass --lifnr explicitly.[/red]"
                )
                raise SystemExit(1)
            lifnr = str(match.get("LIFNR", "")).strip()
            found_bukrs = str(match.get("BUKRS", "")).strip() or bukrs
            if found_bukrs != bukrs:
                console.print(
                    f"[yellow]No vendor found for company code {bukrs}; using {found_bukrs} "
                    f"instead (from the row actually returned).[/yellow]"
                )
                bukrs = found_bukrs
            console.print(
                f"[green]Auto-discovered vendor:[/green] LIFNR={lifnr} BUKRS={bukrs} "
                f"(channel={lfb1.get('channel')})"
            )
        params = {
            "bukrs": bukrs,
            "method": method,
            "lifnr": lifnr or "",
            "laufd": laufd,
            "laufi": laufi,
            "table": table,
            "land1": "US",
        }
        console.print(f"[bold]Co-pilot scenario:[/bold] {scenario_id}")
        result = cp.run_scenario(scenario_id, params)
        console.print(
            f"Result: [{'green' if result.get('ok') else 'red'}]{result.get('ok')}[/] "
            f"({result.get('steps_run')} steps)"
        )
        if result.get("report"):
            console.print(f"Report: {result['report']}")
        console.print(f"Journal: {result.get('journal') or cp.journal.path}")
        # Show key extracted vars
        for key in ("fbzp", "vendor", "table_data", "bsik", "grid", "open_items"):
            if key in result.get("vars", {}):
                val = result["vars"][key]
                if isinstance(val, dict) and "count" in val:
                    console.print(f"  {key}: {val.get('count')} rows via {val.get('channel')}")
                elif isinstance(val, dict):
                    console.print(f"  {key}: keys={list(val.keys())[:12]}")
    finally:
        cp.disconnect()


@copilot_grp.command("goal")
@click.argument("goal_text")
@click.option("--mock", is_flag=True, help="Offline only — not real SAP")
@click.option("--attach", is_flag=True)
@click.option("--connection", default=None)
@click.option("--system", default=None, help="SAP Logon Pad system description")
@click.option("--client", default=None)
@click.option("--user", default=None)
@click.option("--password", default=None)
@click.option("--max-steps", default=25, type=int)
@click.option("--cccategory", default=None)
def copilot_goal(
    goal_text: str,
    mock: bool,
    attach: bool,
    connection: str | None,
    system: str | None,
    client: str | None,
    user: str | None,
    password: str | None,
    max_steps: int,
    cccategory: str | None,
) -> None:
    """Natural-language Co-pilot on REAL SAP GUI (LLM plans grounded actions)."""
    cp = _copilot_from_opts(
        mock=mock,
        attach=attach,
        connection=connection,
        system=system,
        client=client,
        user=user,
        password=password,
        cccategory=cccategory or ("D" if mock else None),
        no_rfc=False,
    )
    try:
        outcome = cp.run_goal(goal_text, max_steps=max_steps)
        console.print(f"Outcome: [bold]{outcome.value}[/bold]")
        console.print(f"Journal: {cp.journal.path}")
        if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("XAI_API_KEY")):
            console.print(
                "[dim]No OPENAI_API_KEY / XAI_API_KEY — planner uses safe stub (escalates).[/dim]"
            )
        else:
            console.print("[dim]Planner model active (OpenAI/xAI from .env).[/dim]")
    finally:
        cp.disconnect()


@copilot_grp.command("goto")
@click.argument("tcode")
@click.option("--mock/--live", default=False)
@click.option("--attach", is_flag=True, default=True)
@click.option("--connection", default=None)
def copilot_goto(tcode: str, mock: bool, attach: bool, connection: str | None) -> None:
    """Start a transaction (default: attach to open SAP GUI)."""
    cp = _copilot_from_opts(
        mock=mock,
        attach=attach and not connection and not mock,
        connection=connection,
        system=None,
        client=None,
        user=None,
        password=None,
        cccategory="D" if mock else "T",
        no_rfc=True,
    )
    try:
        info = cp.goto(tcode)
        console.print(info)
    finally:
        cp.disconnect()


@copilot_grp.command("extract")
@click.argument("table")
@click.option("--mock", is_flag=True)
@click.option("--attach", is_flag=True)
@click.option("--connection", default=None)
@click.option("--system", default=None)
@click.option("--client", default=None)
@click.option("--user", default=None)
@click.option("--password", default=None)
@click.option("--rowcount", default=50, type=int)
@click.option("--option", "options", multiple=True, help="RFC option e.g. \"BUKRS = '1000'\"")
def copilot_extract(
    table: str,
    mock: bool,
    attach: bool,
    connection: str | None,
    system: str | None,
    client: str | None,
    user: str | None,
    password: str | None,
    rowcount: int,
    options: tuple[str, ...],
) -> None:
    """Extract table rows via RFC (preferred) or SE16N GUI on real SAP."""
    cp = _copilot_from_opts(
        mock=mock,
        attach=attach,
        connection=connection,
        system=system,
        client=client,
        user=user,
        password=password,
        cccategory="D" if mock else None,
        no_rfc=False,
    )
    try:
        data = cp.extract_table(table, options=list(options) or None, rowcount=rowcount)
        console.print(
            f"[bold]{table}[/bold] via {data.get('channel')}: {data.get('count')} rows"
        )
        for row in (data.get("rows") or [])[:15]:
            console.print(row)
        if (data.get("count") or 0) > 15:
            console.print(f"... ({data['count'] - 15} more)")
        console.print(f"Journal: {cp.journal.path}")
    finally:
        cp.disconnect()


@copilot_grp.command("status")
def copilot_status() -> None:
    """Show whether SAP Logon is up and which sessions are open."""
    from sapilot.connect.gui import GuiSession

    try:
        import win32com.client  # type: ignore

        win32com.client.GetObject("SAPGUI")
        console.print("[green]SAP Logon / SAPGUI COM: available[/green]")
    except Exception as e:
        console.print(f"[red]SAP Logon not available:[/red] {e}")
        console.print("Start SAP Logon Pad, then log into a system.")
        return
    sessions = GuiSession.list_open_sessions()
    if not sessions:
        console.print(
            "[yellow]Logon is running but no logged-on sessions.[/yellow]\n"
            'Use: sapilot copilot login --system "..." --client 100 --user YOU'
        )
        return
    table = Table(title="Open SAP sessions")
    table.add_column("Conn")
    table.add_column("Ses")
    table.add_column("System")
    table.add_column("Client")
    table.add_column("User")
    table.add_column("TCode")
    for s in sessions:
        if "error" in s:
            console.print(f"[red]{s['error']}[/red]")
            continue
        table.add_row(
            str(s.get("connection")),
            str(s.get("session")),
            str(s.get("system", "")),
            str(s.get("client", "")),
            str(s.get("user", "")),
            str(s.get("tcode", "")),
        )
    console.print(table)


@copilot_grp.command("screen")
@click.option("--attach", is_flag=True, default=True)
@click.option("--mock", is_flag=True)
@click.option("--system", default=None)
@click.option("--client", default=None)
@click.option("--user", default=None)
@click.option("--password", default=None)
@click.option("--connection", default=None)
def copilot_screen(
    attach: bool,
    mock: bool,
    system: str | None,
    client: str | None,
    user: str | None,
    password: str | None,
    connection: str | None,
) -> None:
    """Dump current SAP GUI screen element tree (text-first, for grounding)."""
    # Prefer attach only if no login credentials provided
    use_attach = attach and not mock and not system and not connection and not user
    cp = _copilot_from_opts(
        mock=mock,
        attach=use_attach,
        connection=connection,
        system=system,
        client=client,
        user=user,
        password=password,
        cccategory="D" if mock else None,
        no_rfc=True,
    )
    try:
        summary = cp.screen()
        console.print(f"TCode: {summary.get('tcode')}  Title: {summary.get('title')}")
        console.print(f"Status: {summary.get('status_bar')}")
        console.print(f"Elements: {summary.get('element_count')}")
        for el in (summary.get("elements") or [])[:40]:
            console.print(
                f"  {el.get('id')}  [{el.get('type')}]  name={el.get('name')}  text={el.get('text')!r}"
            )
    finally:
        cp.disconnect()


@main.command("mission-critical")
@click.option("--no-gui", is_flag=True, help="Skip live GUI bind (table precision only)")
def mission_critical_cmd(no_gui: bool) -> None:
    """Run 10 PTP + 10 OTC with NASA/SpaceX fail-closed precision gates."""
    from sapilot.mission.critical_runner import CriticalMissionRunner

    runner = CriticalMissionRunner(use_live_gui=not no_gui, show_mouse=not no_gui)
    summary = runner.run_all()
    console.print()
    console.print("[bold]MISSION CRITICAL 20 — PRECISION BOARD[/bold]")
    for r in runner.results:
        flag = "PASS" if r.get("ok") else "FAIL"
        color = "green" if r.get("ok") else "red"
        console.print(f"  [{color}]{flag}[/{color}]  {r.get('id')}: {r.get('title')}")
    console.print(
        f"RESULT: {summary['ok_count']}/{summary['total']}  "
        f"all_pass={summary['all_pass']}  "
        f"journal_chain_valid={summary['journal_chain_valid']}  "
        f"fingerprints={summary.get('fingerprint_coverage')}"
    )
    console.print(f"Report: {summary.get('report')}")
    if not summary.get("all_pass"):
        raise SystemExit(1)


@main.command("system-status")
@click.option("--json-out", "json_out", is_flag=True)
def system_status_cmd(json_out: bool) -> None:
    """Full system readiness board: tests, missions, policy, vault, GUI."""
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    status: dict[str, Any] = {"ok": True, "checks": []}

    def add(name: str, ok: bool, detail: str = "") -> None:
        status["checks"].append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            status["ok"] = False

    # Policy guard present
    try:
        from sapilot.policy.guard import authorize_write, bind_write_context, is_lab_mode
        from sapilot.policy.tier import TierContext
        from sapilot.schemas import Tier

        bind_write_context(TierContext(Tier.T3_OBSERVE, "800", "P"), source="status")
        try:
            authorize_write("set_text", target="LIFNR", value="1")
            add("write_guard_t3_blocks", False, "T3 allowed write")
        except Exception:
            add("write_guard_t3_blocks", True, "T3 hard-blocks writes")
        add("lab_mode", True, f"lab={is_lab_mode()}")
    except Exception as e:
        add("write_guard", False, str(e))

    # Fingerprints 20/20
    try:
        from sapilot.autobot.consultant import ALL_MISSIONS
        from sapilot.mission.precision import PACK_EXACT

        cov = sum(1 for m in ALL_MISSIONS if m["pack"] in PACK_EXACT)
        add("fingerprints", cov == len(ALL_MISSIONS), f"{cov}/{len(ALL_MISSIONS)}")
    except Exception as e:
        add("fingerprints", False, str(e))

    # Mission critical artifact
    mc = Path(os.environ.get("SAPILOT_DATA", root / "data")) / "runs" / "MISSION_CRITICAL_20.json"
    if mc.exists():
        try:
            data = json.loads(mc.read_text(encoding="utf-8"))
            s = data.get("summary") or {}
            add(
                "last_mission_critical",
                bool(s.get("all_pass")),
                f"{s.get('ok_count')}/{s.get('total')} chain={s.get('journal_chain_valid')}",
            )
        except Exception as e:
            add("last_mission_critical", False, str(e))
    else:
        add("last_mission_critical", False, "not run yet — sapilot mission-critical")

    # Unit tests quick count via import
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "tests", "-q", "--tb=no"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "SAPILOT_LAB": "1", "SAPILOT_ALLOW_UNSIGNED_POLICY": "1"},
        )
        out = (r.stdout or "") + (r.stderr or "")
        add("unit_tests", r.returncode == 0, out.strip().splitlines()[-1] if out.strip() else "")
    except Exception as e:
        add("unit_tests", False, str(e))

    # SAP GUI COM
    try:
        import win32com.client  # type: ignore

        win32com.client.GetObject("SAPGUI")
        add("sapgui_com", True, "available")
    except Exception as e:
        add("sapgui_com", False, str(e)[:80])

    # Vault
    try:
        from sapilot.security.vault import CredentialVault, _dpapi_available

        v = CredentialVault(passphrase=os.environ.get("SAPILOT_VAULT_PASSPHRASE"))
        names = v.list_names()
        add("vault", True, f"dpapi={_dpapi_available()} connections={names}")
    except Exception as e:
        add("vault", False, str(e)[:100])

    # Approval portable
    try:
        from sapilot.policy.approval import ApprovalGate

        g = ApprovalGate()
        t = g.issue("gui_write")
        g2 = ApprovalGate(secret=g.secret)
        add("approval_portable", g2.verify(t.token, "gui_write"), "HMAC cross-process")
    except Exception as e:
        add("approval_portable", False, str(e))

    if json_out:
        click.echo(json.dumps(status, indent=2, default=str))
    else:
        table = Table(title="SAPILOT SYSTEM STATUS")
        table.add_column("Check")
        table.add_column("OK")
        table.add_column("Detail")
        for c in status["checks"]:
            table.add_row(c["name"], "✓" if c["ok"] else "✗", (c.get("detail") or "")[:90])
        console.print(table)
        if status["ok"]:
            console.print("[green bold]SYSTEM READY (all checks green)[/green bold]")
        else:
            console.print("[yellow]SYSTEM PARTIAL — fix failing checks[/yellow]")
            raise SystemExit(1)


@main.command("auto-20")
def auto_20_cmd() -> None:
    """Run autonomous 10 PTP + 10 OTC consultant bot (twin + optional GUI)."""
    from sapilot.autobot.consultant import ConsultantBot

    bot = ConsultantBot()
    result = bot.run_all_twenty("Autonomous 20 PTP+OTC")
    ok = result.get("ok_count") or result.get("passed") or 0
    total = result.get("total") or len(result.get("results") or []) or 20
    if isinstance(result.get("results"), list) and not result.get("ok_count"):
        ok = sum(1 for r in result["results"] if r.get("ok"))
        total = len(result["results"])
    console.print(f"AUTO-20: {ok}/{total}")
    console.print(str(result.get("outfile") or result.get("report") or "")[:200])
    if ok < total:
        raise SystemExit(1)


@main.command("online-health")
@click.option("--json-out", "json_out", is_flag=True)
def online_health_cmd(json_out: bool) -> None:
    """Probe SAP GUI scripting + vault + offline green (timeout-safe)."""
    from sapilot.autobot.online_health import probe_online_health

    h = probe_online_health()
    if json_out:
        click.echo(json.dumps(h.to_dict(), indent=2))
        return
    console.print(f"Score: [bold]{h.score}[/bold]  online_capable={h.online_capable}")
    console.print(f"COM={h.sapgui_com} scripting={h.scripting_engine} sessions={h.open_sessions}")
    console.print(f"Note: {h.scripting_note}")
    for b in h.blockers:
        console.print(f"  [yellow]block[/yellow] {b}")


@main.command("online-20")
@click.option("--no-fallback", is_flag=True, help="Fail if not true online (no offline green)")
def online_20_cmd(no_fallback: bool) -> None:
    """Run 20 scenarios with online-first cascade (GUI if scriptable)."""
    os.environ.setdefault("SAPILOT_LIVE_GUI", "1")
    os.environ.setdefault("SAPILOT_FORCE_COM_BIND", "1")
    from sapilot.autobot.online_runner import OnlineScenarioRunner

    r = OnlineScenarioRunner(allow_offline_fallback=not no_fallback)
    summary = r.run_all()
    console.print(
        f"ONLINE-20: {summary['ok_count']}/{summary['total']}  "
        f"true_online={summary['true_online']}  mode={summary['mode']}"
    )
    console.print(f"Report: {summary.get('report')}")
    for b in summary.get("blockers") or []:
        console.print(f"  blocker: {b}")
    if no_fallback and not summary.get("true_online"):
        raise SystemExit(1)
    if not summary.get("all_ok"):
        raise SystemExit(1)


@main.command("karpathy-tick")
def karpathy_tick_cmd() -> None:
    """One Karpathy improvement tick (measure → gap → auto-fix → agent prompt)."""
    from sapilot.autobot.karpathy_loop import tick

    result = tick()
    console.print(json.dumps(result, indent=2, default=str)[:2500])
    if result.get("fleet_exhausted") or result.get("perfected"):
        console.print(
            "[green bold]FLEET EXHAUSTED — 10 PTP + 10 OTC + 2 ABAP (22/22)[/green bold]"
        )
    if result.get("online", {}).get("true_online"):
        console.print("[green bold]true_online also achieved[/green bold]")


@main.command("super-bot")
@click.option(
    "--offline",
    is_flag=True,
    help="CI only: twin data path (NOT product success). Default is ONLINE GUI.",
)
@click.option("--no-mouse", is_flag=True, help="Online GUI without visible mouse")
def super_bot_cmd(offline: bool, no_mouse: bool) -> None:
    """
    Super Success Bot — ONLINE GUI first (product mode).

    Default: live SAP session + mouse + 10 PTP + 10 OTC + 2 ABAP.
    SUCCESS requires real GUI navigation — not twin skip.
    """
    if offline:
        os.environ["SAPILOT_OFFLINE"] = "1"
        os.environ["SAPILOT_LIVE_GUI"] = "0"
    else:
        os.environ.pop("SAPILOT_OFFLINE", None)
        os.environ["SAPILOT_LIVE_GUI"] = "1"
        os.environ["SAPILOT_FORCE_COM_BIND"] = "1"
        os.environ["SAPILOT_SHOW_MOUSE"] = "0" if no_mouse else "1"
    from sapilot.autobot.super_bot import SuperSuccessBot

    bot = SuperSuccessBot(
        use_live_gui=not offline,
        show_mouse=not offline and not no_mouse,
        require_gui=not offline,
    )
    summary = bot.run_all()
    console.print(
        f"[bold]SUPER BOT[/bold]: {summary['success_count']}/{summary['total']}  "
        f"gui={summary.get('gui_ok_count')}/{summary['total']}  "
        f"session={summary.get('gui_session_bound')}  "
        f"true_online={summary.get('true_online')}  "
        f"all_success={summary['all_success']}"
    )
    if summary.get("gui_bind_error"):
        console.print(f"[yellow]GUI bind:[/yellow] {summary['gui_bind_error']}")
    console.print(f"Report: {summary.get('report')}")
    if not summary.get("all_success"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

