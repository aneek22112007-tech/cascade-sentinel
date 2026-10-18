"""Backtest CLI: day-one data only. Held-out outcomes sealed until close."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sentinel import config
from sentinel.agents.orchestrator import run_season
from sentinel.db import delete_graph, node_edge_counts, query_stats, reset_query_log
from sentinel.seed.loader import load_tenant
from sentinel.tools.episodes import close_episode
from sentinel.tools.registry import call_tool

console = Console()

PITCH = "Existing science models how cascades could unfold. Sentinel remembers how they actually unfolded, which interventions actually worked, and refuses to act without precedent."


def _fmt_path(sig: str, width: int = 88) -> str:
    s = str(sig)
    return s if len(s) <= width else s[: width - 1] + "…"


def _status_style(status: str) -> str:
    return {
        "accepted": "bold green",
        "defeated": "bold red",
        "proposed": "yellow",
        "contested": "yellow",
    }.get(status, "")


def print_banner() -> None:
    console.print(
        Panel.fit(
            Text.from_markup(
                "[bold]Cascade Sentinel[/bold]: the climate-crisis agent that refuses to act without precedent.\n"
                f"[dim]{PITCH}[/dim]\n\n"
                "[bold cyan]Day-1 data only. Held-out outcomes sealed.[/bold cyan]"
            ),
            border_style="orange1",
        )
    )


def _path_table(title: str, rows: list[dict[str, Any]]) -> Table:
    paths = Table(title=title, show_lines=False)
    paths.add_column("#", justify="right")
    paths.add_column("path")
    paths.add_column("score", justify="right")
    paths.add_column("lag_d", justify="right")
    paths.add_column("T", justify="right")
    for p in rows:
        paths.add_row(
            str(p.get("rank") or ""),
            _fmt_path(p["signature"]),
            f"{p['score']:.3f}",
            str(p["lag_days"]),
            f"{p['timing']:.1f}",
        )
    return paths


def print_season(bundle: dict[str, Any], title: str) -> None:
    console.rule(f"[bold]{title}[/bold]")
    console.print(_path_table("Top cascade paths (3+ hops)", bundle["paths"]))
    direct = bundle.get("direct_exposure") or []
    if direct:
        console.print(_path_table("Direct exposure (1–2 hops)", direct))

    hyps = Table(title="Hypotheses (adjudicated)", show_lines=False)
    hyps.add_column("agent")
    hyps.add_column("path")
    hyps.add_column("eff", justify="right")
    hyps.add_column("status")
    hyps.add_column("reason")
    for h in bundle["hypotheses"]:
        st = h["status"] if h["status"] != "proposed" else "contested"
        hyps.add_row(
            h["agent_id"],
            _fmt_path(h["path_signature"], 56),
            f"{h['eff_confidence']:.2f}",
            Text(st, style=_status_style(st)),
            (h.get("reason") or "")[:80],
        )
    console.print(hyps)

    recs = Table(title="Recommendations", show_lines=True)
    recs.add_column("kind")
    recs.add_column("intervention / message")
    recs.add_column("P", justify="right")
    recs.add_column("score", justify="right")
    recs.add_column("path")
    for r in bundle["recommendations"]:
        kind = r["kind"]
        if kind == "act":
            kind_t = Text("ACT", style="bold green")
            name = r.get("intervention_name") or r.get("intervention_id")
        elif kind == "defeated_precedent":
            kind_t = Text("DEFEATED", style="dim")
            name = Text(str(r.get("intervention_name") or r.get("intervention_id")), style="strike dim")
        elif kind == "weak_analog":
            kind_t = Text("WEAK ANALOG", style="bold yellow")
            name = r.get("message") or "weak analog"
        else:
            kind_t = Text("ESCALATE", style="bold white on grey39")
            name = r.get("message") or "UNPRECEDENTED"
        pval = "" if r.get("precedent_weight") is None else f"{r['precedent_weight']:.2f}"
        recs.add_row(kind_t, name, pval, f"{r['score']:.3f}", _fmt_path(r["path_signature"], 56))
    console.print(recs)
    if bundle.get("rationale"):
        console.print(Panel(bundle["rationale"], title="Rationale (prose only)", border_style="dim"))


def print_writeback(closed: dict[str, Any]) -> None:
    console.rule("[bold]Write-back (close_episode)[/bold]")
    iv = Table(title="Intervention P before → after")
    iv.add_column("id")
    iv.add_column("P before", justify="right")
    iv.add_column("P after", justify="right")
    iv.add_column("trials")
    for iid, pair in closed["interventions"].items():
        b, a = pair["before"], pair["after"]
        iv.add_row(
            iid,
            f"{b['precedent_weight']:.3f}",
            f"{a['precedent_weight']:.3f}",
            f"{b['trials']}/{b['successes']} → {a['trials']}/{a['successes']}",
        )
    console.print(iv)
    ag = Table(title="Agent credibility before → after")
    ag.add_column("agent")
    ag.add_column("verdict")
    ag.add_column("C before", justify="right")
    ag.add_column("C after", justify="right")
    ag.add_column("hits/misses")
    for aid, pair in closed["agents"].items():
        b, a = pair["before"], pair["after"]
        ag.add_row(
            aid,
            pair["verdict"],
            f"{b['credibility']:.3f}",
            f"{a['credibility']:.3f}",
            f"{b['hits']}/{b['misses']} → {a['hits']}/{a['misses']}",
        )
    console.print(ag)
    j = closed["reconstruction_jaccard"]
    flag = "PASS" if closed["reconstruction_pass"] else "FAIL"
    style = "bold green" if closed["reconstruction_pass"] else "bold red"
    console.print(Text(f"Path reconstruction Jaccard={j:.3f}  {flag} ≥ 0.6", style=style))


def diff_seasons(a: dict[str, Any], b: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    a_h = {(h["agent_id"], h["path_signature"]): h for h in a["hypotheses"]}
    b_h = {(h["agent_id"], h["path_signature"]): h for h in b["hypotheses"]}
    for key in sorted(set(a_h) | set(b_h)):
        ha, hb = a_h.get(key), b_h.get(key)
        sa = (ha["status"] if ha and ha["status"] != "proposed" else "contested") if ha else "—"
        sb = (hb["status"] if hb and hb["status"] != "proposed" else "contested") if hb else "—"
        if sa != sb:
            rows.append(
                {
                    "what": f"hyp {key[0]} {_fmt_path(key[1], 48)}",
                    "n_minus_1": sa,
                    "n": sb,
                }
            )
    a_r = {(r["kind"], r.get("intervention_id"), r["path_signature"]) for r in a["recommendations"]}
    b_r = {(r["kind"], r.get("intervention_id"), r["path_signature"]) for r in b["recommendations"]}
    lost = a_r - b_r
    gained = b_r - a_r
    for kind, iid, sig in sorted(gained, key=str):
        rows.append({"what": f"+ {kind} {iid or kind} {_fmt_path(sig, 40)}", "n_minus_1": "—", "n": kind})
    for kind, iid, sig in sorted(lost, key=str):
        rows.append({"what": f"- {kind} {iid or kind} {_fmt_path(sig, 40)}", "n_minus_1": kind, "n": "—"})
    return rows


def print_diff(rows: list[dict[str, str]]) -> None:
    console.rule("[bold]What changed because of memory[/bold]")
    t = Table()
    t.add_column("change")
    t.add_column("2024")
    t.add_column("2025")
    for r in rows:
        t.add_row(r["what"], r["n_minus_1"], r["n"])
    console.print(t)
    console.print(f"[bold]{len(rows)} diffs[/bold]")


def print_footer(tenant: str) -> None:
    nodes, edges = node_edge_counts(tenant)
    stats = query_stats()
    console.print(
        Text(
            f"Graph: {nodes} nodes, {edges} edges, 3 memory layers, "
            f"{stats['count']} Cypher queries, total {stats['total_ms']:.0f} ms.",
            style="bold cyan",
        )
    )


_STRIP_KEYS = {
    "created_at",
    "opened_at",
    "closed_at",
    "ms",
    "cypher",
    "step_events",
    "steps",
    "payload",
}


def jsonable(bundle: dict[str, Any]) -> dict[str, Any]:
    def strip(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: strip(v) for k, v in obj.items() if k not in _STRIP_KEYS}
        if isinstance(obj, list):
            return [strip(x) for x in obj]
        if isinstance(obj, float):
            return round(obj, 8)
        return obj

    return strip(bundle)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Cascade Sentinel backtest")
    p.add_argument("--tenant", default=config.DEFAULT_TENANT)
    p.add_argument("--season", type=int, default=None)
    p.add_argument("--double-run", action="store_true")
    p.add_argument("--json", dest="json_out", default=None)
    args = p.parse_args(argv)

    reset_query_log()
    print_banner()

    if args.double_run:
        delete_graph(args.tenant)
        load_tenant(args.tenant)
        s2024 = run_season(args.tenant, 2024)
        print_season(s2024, "Season N-1 (2024)")
        closed = close_episode(args.tenant, s2024["episode_id"])["result"]
        print_writeback(closed)
        s2025 = run_season(args.tenant, 2025)
        print_season(s2025, "Season N (2025)")
        diffs = diff_seasons(s2024, s2025)
        print_diff(diffs)
        payload = jsonable(
            {
                "season_2024": s2024,
                "close_2024": closed,
                "season_2025": s2025,
                "diffs": diffs,
            }
        )
        print_footer(args.tenant)
        if args.json_out:
            with open(args.json_out, "w") as f:
                json.dump(payload, f, indent=2, sort_keys=True)
                f.write("\n")
        return 0

    year = args.season or 2024
    bundle = run_season(args.tenant, year)
    print_season(bundle, f"Season {year}")
    print_footer(args.tenant)
    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(jsonable(bundle), f, indent=2, sort_keys=True)
            f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
