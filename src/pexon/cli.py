"""Pexon command line interface."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

try:
    import typer as _typer
except ImportError:  # the checked-in launcher must work before installation
    _typer = None  # type: ignore[assignment]

from pexon.adapters import registry
from pexon.config.settings import Settings, get_settings
from pexon.main import build_runtime
from pexon.models.topic import Topic
from pexon.observability.logging import configure_logging, set_trace_id

logger = logging.getLogger(__name__)
_ANALYTICS_COLUMNS = ["article_id", "clicks", "impressions", "position", "measured_at", "page_url"]
_LEAD_COLUMNS = [
    "lead_id",
    "created_at",
    "article_id",
    "source",
    "medium",
    "campaign",
    "page_url",
    "status",
    "company",
    "annual_value",
    "currency",
    "client",
    "won_value",
    "crm_url",
]
_KEYWORD_COLUMNS = ["keyword", "volume", "difficulty", "cpc", "intent", "funnel_stage", "cluster"]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pexon", description="Four-frame AI content engine")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run the four-frame graph for one topic")
    run.add_argument("--topic", required=True)
    run.add_argument("--wait", type=int, default=0, help="seconds before measuring analytics")
    run.add_argument("--max-iterations", type=int, default=None)
    run.add_argument("--llm", choices=["openai-compatible", "anthropic", "gemini"], default=None)
    run.add_argument("--search", choices=["duckduckgo", "tavily", "brave", "serpapi"], default=None)
    run.add_argument("--analytics", choices=["csv", "gsc", "plausible", "matomo"], default=None)
    run.add_argument("--base-url", default=None)
    run.add_argument("--model", default=None)
    run.add_argument("--segment", default="universalbank")
    run.add_argument("--target-keyword", default="")
    run.add_argument("--cluster", default="")
    run.add_argument("--funnel-stage", default="middle")

    batch = sub.add_parser("run-batch", help="run topics from a YAML file")
    batch.add_argument("--topics-file", required=True)
    batch.add_argument("--wait", type=int, default=0)
    batch.add_argument("--max-iterations", type=int, default=None)

    replay = sub.add_parser("replay", help="resume a checkpointed run")
    replay.add_argument("--run-id", required=True)

    inspect = sub.add_parser("inspect", help="inspect runtime state")
    inspect_sub = inspect.add_subparsers(dest="inspect_command", required=True)
    inspect_sub.add_parser("weights")
    features = inspect_sub.add_parser("features")
    features.add_argument("--article-id", required=True)
    inspect_sub.add_parser("providers")
    inspect_sub.add_parser("settings")

    seed = sub.add_parser("seed-analytics", help="import an analytics CSV")
    seed.add_argument("--csv", required=True)
    seed.add_argument("--append", action="store_true")

    evaluate = sub.add_parser("evaluate", help="prediction error since a date")
    evaluate.add_argument("--since", required=True)

    plan = sub.add_parser("plan", help="build a demand-aware content plan")
    plan.add_argument("--seeds", nargs="*", default=[])
    plan.add_argument("--limit", type=int, default=None)
    plan.add_argument("--write", default="")

    geo = sub.add_parser("geo", help="measure real AI-answer visibility")
    geo.add_argument("--topic", required=True)
    geo.add_argument("--topic-id", default="cli-geo")

    report = sub.add_parser("report", help="show funnel and unit economics")
    report.add_argument("--since", default="")
    report.add_argument("--until", default="")

    approve = sub.add_parser("approve", help="approve a staged article")
    approve.add_argument("--article-id", required=True)
    approve.add_argument("--reviewer", required=True)
    approve.add_argument("--notes", default="")

    measure = sub.add_parser("measure", help="collect analytics and GEO for an approved article")
    measure.add_argument("--article-id", required=True)
    measure.add_argument("--wait", type=int, default=0)

    for name, help_text in (
        ("seed-leads", "import a lead CSV"),
        ("seed-keywords", "import a keyword-demand CSV"),
    ):
        seed_cmd = sub.add_parser(name, help=help_text)
        seed_cmd.add_argument("--csv", required=True)

    sub.add_parser("doctor", help="probe every active adapter with a real call")
    return parser


def _settings_from_args(args: argparse.Namespace) -> Settings:
    settings = get_settings()
    updates: dict[str, Any] = {}
    if getattr(args, "llm", None):
        updates["llm_provider"] = args.llm
    if getattr(args, "search", None):
        updates["search_provider"] = args.search
    if getattr(args, "analytics", None):
        updates["analytics_provider"] = args.analytics
    if getattr(args, "base_url", None):
        updates["llm_base_url"] = args.base_url
    if getattr(args, "model", None):
        updates["llm_model"] = args.model
    return settings.with_cli_overrides(**updates) if updates else settings


def _inside_workspace(path: Path, settings: Settings) -> Path:
    resolved = path.resolve()
    root = settings.project_root.resolve()
    if root not in resolved.parents and resolved != root:
        raise SystemExit(f"path outside workspace is not allowed: {resolved}")
    return resolved


def _run_one(runtime, topic: Topic, args) -> dict[str, Any]:
    state = runtime.graph.initial_state(
        topic, wait_seconds=args.wait, max_iterations=getattr(args, "max_iterations", None)
    )
    set_trace_id(state["trace_id"])
    runtime.storage.setup()
    runtime.audit.emit(
        state["run_id"],
        "run_started",
        {
            "topic": topic.name_de,
            "provider_config": runtime.settings.provider_config,
        },
    )
    if not runtime.settings.judge_is_separate:
        runtime.audit.emit(
            state["run_id"],
            "judge_same_provider",
            {
                "warning": "judge and generator share provider/model",
                "judge": runtime.settings.judge_provider_name,
                "model": runtime.settings.effective_judge_model,
            },
        )
    print(
        f"[run]       trace_id={state['trace_id'][:8]}… "
        f"providers={{llm:{runtime.settings.llm_provider_name}, "
        f"search:{runtime.settings.search_provider}, analytics:{runtime.settings.analytics_provider}, "
        f"crm:{runtime.settings.crm_provider}, geo:{runtime.settings.geo_provider}, "
        f"publishing:{runtime.settings.publishing_provider}}}"
    )
    try:
        for chunk in runtime.graph.stream(state):
            for node, update in chunk.items():
                _print_update(node, update)
    except Exception as exc:
        logger.exception("run failed")
        runtime.audit.emit(
            state["run_id"],
            "run_error",
            {
                "error": f"{type(exc).__name__}: {exc}",
            },
        )
        print(f"[error]     {type(exc).__name__}: {exc}")
        return {"decision": "failed", "error": str(exc)}
    final = runtime.graph.final_state(state["run_id"])
    _print_final(final)
    print(f"[metrics]   {runtime.metrics.render()}")
    print("DONE")
    return final


def _print_update(node: str, update: dict[str, Any]) -> None:
    if not isinstance(update, dict):
        return
    if node == "research" and update.get("snapshot"):
        snapshot = update["snapshot"]
        verified = sum(1 for f in snapshot.facts if f.verified)
        print(
            f"[research]  sources={len(snapshot.sources)} facts={verified} "
            f"hash={snapshot.snapshot_hash[:8]}"
        )
    elif node == "intelligence":
        pages = update.get("competitor_pages") or []
        insights = update.get("insights")
        report = update.get("training_report")
        print(
            f"[features]  pages={len(pages)} insights={len(insights.insights_de) if insights else 0}"
        )
        if report is not None:
            print(
                f"[rank]      weights={report.version or 'prior-v1'} trained={report.trained} "
                f"rows={report.row_count} metrics={report.metrics}"
            )
    elif node == "generation":
        ranked = update.get("ranked") or []
        gates = update.get("gates")
        if ranked:
            summary = " | ".join(
                f"{item.draft.angle or item.draft.id}=p={item.expected_clicks:.0f} "
                f"ci=[{item.clicks_ci_low:.0f},{item.clicks_ci_high:.0f}]"
                for item in ranked[:5]
            )
            print(f"[samples]   ranked={len(ranked)} {summary}")
        if gates:
            for result in gates.results:
                marker = "pass" if result.passed else "FAIL"
                print(f"[gate:{result.name}] {marker} {result.reason}".rstrip())
            print(f"[gate]      passed={gates.passed} reasons={','.join(gates.reasons) or '-'}")
        print(f"[generate]  decision={update.get('decision', '-')}")
    elif node == "retry_direction":
        print(f"[retry]     attempt={update.get('retries')} reasons={update.get('retry_reasons')}")
    elif node == "publish":
        print(
            f"[publish]   article_id={update.get('article_id')} path={update.get('article_path')}"
        )
    elif node == "measure":
        performance = update.get("performance")
        if performance:
            print(
                f"[measure]   clicks={performance.clicks:.0f} impressions={performance.impressions:.0f}"
            )
        else:
            print("[measure]   pending_measure")
    elif node == "reflection":
        print(
            f"[reflect]   iterations={update.get('iterations')} "
            f"update={update.get('reflection_update')}"
        )
    elif node == "report":
        geo_report = update.get("geo_report")
        funnel = update.get("funnel_report")
        if geo_report is not None:
            print(
                f"[geo]       provider={geo_report.provider} queries={len(geo_report.results)} "
                f"mention_rate={geo_report.mention_rate:.2f} citation_rate={geo_report.citation_rate:.2f}"
            )
        else:
            print("[geo]       no report (GEO_PROVIDER=none or measurement failed)")
        if funnel is not None:
            print(
                f"[funnel]    clicks={funnel.clicks:.0f} leads={funnel.leads} "
                f"attributed={funnel.attributed_leads} qualified={funnel.qualified_leads} "
                f"clients={funnel.clients} pipeline={funnel.pipeline_value:.2f} "
                f"{funnel.economics.cost.currency}"
            )
            econ = funnel.economics
            print(
                f"[economics] cost={econ.cost.total_cost:.4f} {econ.cost.currency} "
                f"cost_per_lead={econ.cost_per_lead:.2f} cost_per_client={econ.cost_per_client:.2f}"
            )
    elif node == "failed":
        print("[failed]    quality gate exhausted retries")


def _print_final(state: dict[str, Any]) -> None:
    if state.get("article_path"):
        print(f"[done]      decision={state.get('decision')} article={state.get('article_id')}")
        print(f"[done]      path={state.get('article_path')}")
    elif state.get("decision") == "failed":
        print("[done]      decision=failed")
    if state.get("pending_measure"):
        print("[done]      pending_measure=true")
    if state.get("decision") == "pending_review":
        print("[done]      pending_review=true")


def _cmd_run(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    configure_logging(settings.log_level, settings.log_format)
    runtime = build_runtime(settings)
    topic = Topic.from_name(
        args.topic,
        bank_segment=args.segment,
        target_keyword=args.target_keyword,
        cluster=args.cluster,
        funnel_stage=args.funnel_stage,
    )
    final = _run_one(runtime, topic, args)
    return 0 if final.get("decision") in {"published", "publish", "pending_review"} else 1


def _cmd_batch(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    configure_logging(settings.log_level, settings.log_format)
    path = _inside_workspace(Path(args.topics_file), settings)
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    entries = payload.get("topics", []) if isinstance(payload, dict) else payload
    runtime = build_runtime(settings)
    failures = 0
    for entry in entries:
        if isinstance(entry, str):
            topic = Topic.from_name(entry)
        else:
            topic = Topic.from_name(
                entry.get("name", ""),
                bank_segment=entry.get("segment", "universalbank"),
                target_keyword=entry.get("target_keyword", ""),
                cluster=entry.get("cluster", ""),
                funnel_stage=entry.get("funnel_stage", "middle"),
            )
        print(f"\n=== {topic.name_de} ===")
        final = _run_one(runtime, topic, args)
        if final.get("decision") not in {"published", "publish", "pending_review"}:
            failures += 1
    return 0 if failures == 0 else 1


def _cmd_replay(args: argparse.Namespace) -> int:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    runtime = build_runtime(settings)
    set_trace_id(args.run_id)
    try:
        for chunk in runtime.graph.replay(args.run_id):
            for node, update in chunk.items():
                _print_update(node, update)
    except ValueError as exc:
        print(f"[replay]    {exc}")
        return 1
    final = runtime.graph.final_state(args.run_id)
    print(f"[replay]    loaded run_id={args.run_id} decision={final.get('decision')}")
    _print_final(final)
    return 0


def _storage(settings: Settings):
    storage = registry.build("storage", settings.storage_provider, settings)
    storage.setup()
    return storage


def _cmd_inspect(args: argparse.Namespace) -> int:
    settings = get_settings()
    if args.inspect_command == "settings":
        _print_settings(settings)
        return 0
    if args.inspect_command == "providers":
        _print_providers(settings)
        return 0
    storage = _storage(settings)
    if args.inspect_command == "weights":
        weights = storage.latest("weights", order_by="trained_at")
        if not weights:
            print("weights=prior-v1 trained=false")
            print(
                "reason=no measured (features, outcome) pairs yet; run with analytics data to train"
            )
            return 0
        cards = storage.find("model_cards", version=weights.get("version"))
        card = cards[0] if cards else {}
        print(
            f"version={weights.get('version')} backend={weights.get('backend')} "
            f"trained_at={weights.get('trained_at')} rows={weights.get('row_count')}"
        )
        print(f"metrics={json.dumps(weights.get('metrics_json') or {}, ensure_ascii=False)}")
        print("known_limits=" + str(card.get("known_limits", "")))
        print(
            f"provider_config={json.dumps(card.get('provider_config_json') or weights.get('provider_config_json') or {}, ensure_ascii=False, indent=2)}"
        )
        importances = weights.get("values_json") or {}
        for name, value in sorted(importances.items(), key=lambda pair: pair[1], reverse=True):
            print(f"importance.{name}={value}")
        return 0
    if args.inspect_command == "features":
        rows = storage.find("features", article_id=args.article_id)
        if not rows:
            print(f"no features for article_id={args.article_id}")
            return 1
        print(json.dumps(rows[0].get("features_json") or {}, ensure_ascii=False, indent=2))
        return 0
    print("unknown inspect command")
    return 1


def _print_settings(settings: Settings) -> None:
    print(f"{'field':38} {'source':8} value")
    for name, _field in Settings.model_fields.items():
        value = getattr(settings, name)
        secret_name = name.endswith(("api_key", "secret", "password")) or (
            name.endswith("token") and name != "pii_redaction_token"
        )
        if secret_name:
            raw = value.get_secret_value() if hasattr(value, "get_secret_value") else value
            value = "***" if raw else ""
        source = settings.source_for(name)
        print(f"{name:38} {source:8} {value}")


def _print_providers(settings: Settings) -> None:
    for port in registry.REGISTRY:
        active = registry.active_provider(port, settings)
        print(f"\n{port} (active={active})")
        for name, spec in registry.providers(port).items():
            marker = "*" if name == active else " "
            state = "available" if spec.available else f"unavailable ({spec.reason})"
            print(f" {marker} {name:22} {state}")


def _cmd_seed(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings.ensure_directories()
    source = _inside_workspace(Path(args.csv), settings)
    if not source.exists():
        print(f"[seed]      missing source: {source}")
        return 1
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [
            column for column in _ANALYTICS_COLUMNS[:5] if column not in (reader.fieldnames or [])
        ]
        if missing:
            print(f"[seed]      missing columns: {missing}")
            return 1
        rows = list(reader)
    target = settings.analytics_file
    mode = "a" if args.append else "w"
    with target.open(mode, newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_ANALYTICS_COLUMNS)
        if mode == "w" or target.stat().st_size == 0:
            writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in _ANALYTICS_COLUMNS})
    print(f"[seed]      rows={len(rows)} path={target}")
    return 0


def _cmd_evaluate(args: argparse.Namespace) -> int:
    settings = get_settings()
    storage = _storage(settings)
    try:
        since = datetime.fromisoformat(args.since).replace(tzinfo=UTC)
    except ValueError:
        print("[evaluate]  --since must be YYYY-MM-DD")
        return 1
    predictions = {row["article_id"]: row for row in storage.find("predictions")}
    actuals: dict[str, dict[str, float]] = {}
    for row in storage.find("performance"):
        measured = str(row.get("measured_at", ""))
        try:
            stamp = datetime.fromisoformat(measured.replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=UTC)
        except ValueError:
            continue
        if stamp < since:
            continue
        current = actuals.setdefault(row["article_id"], {"clicks": 0.0, "impressions": 0.0})
        current["clicks"] += float(row["clicks"])
        current["impressions"] += float(row["impressions"])
    pairs = [(predictions[aid], actual) for aid, actual in actuals.items() if aid in predictions]
    if not pairs:
        print("[evaluate]  n=0 (no measured predictions in window)")
        return 0
    mae_clicks = sum(abs(p["clicks"] - a["clicks"]) for p, a in pairs) / len(pairs)
    mae_impressions = sum(abs(p["impressions"] - a["impressions"]) for p, a in pairs) / len(pairs)
    print(
        f"[evaluate]  n={len(pairs)} mae_clicks={mae_clicks:.2f} mae_impressions={mae_impressions:.2f}"
    )
    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    runtime = build_runtime(settings)
    seeds = [
        part.strip() for value in (args.seeds or []) for part in value.split(",") if part.strip()
    ]
    try:
        plan = runtime.portfolio.build_plan(seeds, args.limit)
    except Exception as exc:
        print(f"[plan]      failed: {exc}")
        return 1
    payload = plan.model_dump(mode="json")
    payload["topics"] = [
        {
            "name": candidate.topic_name_de,
            "target_keyword": candidate.keyword,
            "cluster": candidate.cluster,
            "funnel_stage": candidate.funnel_stage,
        }
        for candidate in plan.selected
    ]
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    print(text)
    if args.write:
        path = _inside_workspace(Path(args.write), settings)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"[plan]      wrote {path}")
    return 0


def _cmd_geo(args: argparse.Namespace) -> int:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    runtime = build_runtime(settings)
    report = runtime.geo_service.measure_topic(
        args.topic_id, args.topic, f"geo-{uuid.uuid4().hex[:10]}"
    )
    if report is None:
        print("[geo]       no report: set GEO_PROVIDER or inspect events for the failure")
        return 2
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    runtime = build_runtime(settings)
    try:
        since = _parse_cli_date(args.since)
        until = _parse_cli_date(args.until, end=True)
    except ValueError:
        print("[report]    dates must be ISO-8601 (YYYY-MM-DD)")
        return 1
    try:
        report = runtime.attribution.build_report(
            f"report-{uuid.uuid4().hex[:10]}", since=since, until=until
        )
    except Exception as exc:
        print(f"[report]    failed: {exc}")
        return 1
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


def _cmd_approve(args: argparse.Namespace) -> int:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    runtime = build_runtime(settings)
    try:
        status, path = runtime.reflection.approve(
            args.article_id,
            args.reviewer,
            args.notes,
            f"approve-{uuid.uuid4().hex[:10]}",
        )
    except ValueError as exc:
        print(f"[approve]   {exc}")
        return 1
    print(f"[approve]   article_id={args.article_id} status={status} path={path}")
    return 0 if status == "published" else 1


def _cmd_measure(args: argparse.Namespace) -> int:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    runtime = build_runtime(settings)
    article = runtime.storage.read("articles", args.article_id)
    if not article:
        print(f"[measure]   unknown article: {args.article_id}")
        return 1
    if article.get("status") not in {"published", "publish"}:
        print(f"[measure]   article is not public: {article.get('status')}")
        return 1
    run_id = f"measure-{uuid.uuid4().hex[:10]}"
    bundle = runtime.reflection.collect_metrics(args.article_id, run_id, args.wait)
    print("[measure]   pending" if bundle is None else f"[measure]   clicks={bundle.clicks:.0f}")
    topic = runtime.storage.read("topics", str(article.get("topic_id", ""))) or {}
    geo = runtime.geo_service.measure_topic(
        str(article.get("topic_id", "")),
        str(topic.get("name_de", article.get("title_de", ""))),
        run_id,
        args.article_id,
    )
    print(
        "[geo]       pending"
        if geo is None
        else f"[geo]       mention_rate={geo.mention_rate:.2f} citation_rate={geo.citation_rate:.2f}"
    )
    funnel = runtime.attribution.build_report(run_id)
    print(
        f"[funnel]    leads={funnel.leads} attributed={funnel.attributed_leads} "
        f"qualified={funnel.qualified_leads} clients={funnel.clients}"
    )
    return 0


def _cmd_seed_named(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings.ensure_directories()
    source = _inside_workspace(Path(args.csv), settings)
    if not source.exists():
        print(f"[seed]      missing source: {source}")
        return 1
    target = settings.leads_path if args.command == "seed-leads" else settings.keyword_path
    columns = _LEAD_COLUMNS if args.command == "seed-leads" else _KEYWORD_COLUMNS
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in columns if column not in (reader.fieldnames or [])]
        if missing:
            print(f"[seed]      missing columns: {missing}")
            return 1
        rows = list(reader)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
    print(f"[seed]      rows={len(rows)} path={target}")
    return 0


def _parse_cli_date(value: str, *, end: bool = False) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    if end and parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0:
        parsed += timedelta(days=1) - timedelta(microseconds=1)
    return parsed


def _probe(port_name: str, provider: str, settings: Settings) -> tuple[Any, bool, str]:
    try:
        adapter = registry.build(port_name, provider, settings)
        if port_name == "storage":
            adapter.setup()
        ok = bool(adapter.probe())
        return adapter, ok, ""
    except Exception as exc:
        return None, False, str(exc)


def _cmd_doctor(_: argparse.Namespace) -> int:
    settings = get_settings()
    failures: list[str] = []
    descriptions: list[str] = []

    def line(label: str, port: str, provider: str, detail: str, probe_settings: Settings) -> None:
        adapter, ok, error = _probe(port, provider, probe_settings)
        status = "ok" if ok else f"FAIL: {error}"
        descriptions.append(f"[doctor]    {label}={provider}{detail} → {status}")
        if not ok:
            failures.append(f"{label}:{provider}")

    line(
        "llm",
        "llm",
        settings.llm_provider,
        f" @ {settings.effective_llm_base_url} ({settings.effective_llm_model})",
        settings,
    )
    judge_settings = settings.judge_settings()
    warning = "" if settings.judge_is_separate else " (WARNING: same provider as generator)"
    line(
        "judge",
        "llm",
        settings.judge_provider_name,
        f" @ {settings.effective_judge_base_url} ({settings.effective_judge_model}){warning}",
        judge_settings,
    )
    line("search", "search", settings.search_provider, "", settings)
    line("fetch", "fetch", settings.fetch_provider, "", settings)
    line(
        "embeddings",
        "embeddings",
        settings.embeddings_provider,
        f" @ {settings.effective_embeddings_base_url} ({settings.embeddings_model})",
        settings,
    )
    if settings.analytics_provider == "csv":
        rows = 0
        if settings.analytics_file.exists():
            with settings.analytics_file.open(encoding="utf-8") as handle:
                rows = max(0, sum(1 for _ in handle) - 1)
        analytics_detail = f" ({settings.analytics_file}, {rows} rows)"
    else:
        analytics_detail = ""
    line("analytics", "analytics", settings.analytics_provider, analytics_detail, settings)
    leads_detail = f" ({settings.leads_path})" if settings.crm_provider == "csv" else ""
    line("crm", "crm", settings.crm_provider, leads_detail, settings)
    geo_detail = (
        f" (brand={settings.geo_brand_name}, domain={settings.effective_geo_domain})"
        if settings.geo_enabled
        else " (measuring disabled)"
    )
    line("geo", "geo", settings.geo_provider, geo_detail, settings)
    keywords_detail = f" ({settings.keyword_path})" if settings.keyword_provider == "csv" else ""
    line("keywords", "keywords", settings.keyword_provider, keywords_detail, settings)
    line("publishing", "publishing", settings.publishing_provider, "", settings)
    line(
        "storage",
        "storage",
        settings.storage_provider,
        f" ({settings.sqlite_path})" if settings.storage_provider == "sqlite" else "",
        settings,
    )
    line("cache", "cache", settings.cache_provider, f" ({settings.cache_path})", settings)
    line("tracing", "tracing", settings.effective_tracing_provider, "", settings)
    for text in descriptions:
        print(text)
    if failures:
        print("[doctor]    FAILED: " + ", ".join(failures))
        return 1
    print("[doctor]    OK")
    return 0


def _typer_app():
    """Build the Typer front end used by the packaged console script."""
    if _typer is None:
        raise RuntimeError("typer is not installed")
    app = _typer.Typer(no_args_is_help=True, add_completion=False)

    @app.command("run")
    def run_command(
        topic: str = _typer.Option(..., "--topic"),
        wait: int = _typer.Option(0, "--wait"),
        max_iterations: int | None = _typer.Option(None, "--max-iterations"),
        llm: str | None = _typer.Option(None, "--llm"),
        search: str | None = _typer.Option(None, "--search"),
        analytics: str | None = _typer.Option(None, "--analytics"),
        base_url: str | None = _typer.Option(None, "--base-url"),
        model: str | None = _typer.Option(None, "--model"),
        segment: str = _typer.Option("universalbank", "--segment"),
        target_keyword: str = _typer.Option("", "--target-keyword"),
        cluster: str = _typer.Option("", "--cluster"),
        funnel_stage: str = _typer.Option("middle", "--funnel-stage"),
    ) -> None:
        args = argparse.Namespace(
            command="run",
            topic=topic,
            wait=wait,
            max_iterations=max_iterations,
            llm=llm,
            search=search,
            analytics=analytics,
            base_url=base_url,
            model=model,
            segment=segment,
            target_keyword=target_keyword,
            cluster=cluster,
            funnel_stage=funnel_stage,
        )
        raise _typer.Exit(_cmd_run(args))

    @app.command("run-batch")
    def batch_command(
        topics_file: str = _typer.Option(..., "--topics-file"),
        wait: int = _typer.Option(0, "--wait"),
        max_iterations: int | None = _typer.Option(None, "--max-iterations"),
    ) -> None:
        args = argparse.Namespace(
            command="run-batch", topics_file=topics_file, wait=wait, max_iterations=max_iterations
        )
        raise _typer.Exit(_cmd_batch(args))

    @app.command("replay")
    def replay_command(run_id: str = _typer.Option(..., "--run-id")) -> None:
        raise _typer.Exit(_cmd_replay(argparse.Namespace(command="replay", run_id=run_id)))

    inspect_app = _typer.Typer(no_args_is_help=True, add_completion=False)

    @inspect_app.command("weights")
    def inspect_weights() -> None:
        raise _typer.Exit(
            _cmd_inspect(argparse.Namespace(command="inspect", inspect_command="weights"))
        )

    @inspect_app.command("features")
    def inspect_features(article_id: str = _typer.Option(..., "--article-id")) -> None:
        raise _typer.Exit(
            _cmd_inspect(
                argparse.Namespace(
                    command="inspect", inspect_command="features", article_id=article_id
                )
            )
        )

    @inspect_app.command("providers")
    def inspect_providers() -> None:
        raise _typer.Exit(
            _cmd_inspect(argparse.Namespace(command="inspect", inspect_command="providers"))
        )

    @inspect_app.command("settings")
    def inspect_settings() -> None:
        raise _typer.Exit(
            _cmd_inspect(argparse.Namespace(command="inspect", inspect_command="settings"))
        )

    app.add_typer(inspect_app, name="inspect")

    @app.command("seed-analytics")
    def seed_command(
        csv_path: str = _typer.Option(..., "--csv"), append: bool = _typer.Option(False, "--append")
    ) -> None:
        raise _typer.Exit(
            _cmd_seed(argparse.Namespace(command="seed-analytics", csv=csv_path, append=append))
        )

    @app.command("evaluate")
    def evaluate_command(since: str = _typer.Option(..., "--since")) -> None:
        raise _typer.Exit(_cmd_evaluate(argparse.Namespace(command="evaluate", since=since)))

    @app.command("plan")
    def plan_command(
        seeds: str = _typer.Option("", "--seeds"),
        limit: int | None = _typer.Option(None, "--limit"),
        write: str = _typer.Option("", "--write"),
    ) -> None:
        args = argparse.Namespace(
            command="plan",
            seeds=[s.strip() for s in seeds.split(",") if s.strip()],
            limit=limit,
            write=write,
        )
        raise _typer.Exit(_cmd_plan(args))

    @app.command("geo")
    def geo_command(
        topic: str = _typer.Option(..., "--topic"),
        topic_id: str = _typer.Option("cli-geo", "--topic-id"),
    ) -> None:
        raise _typer.Exit(
            _cmd_geo(argparse.Namespace(command="geo", topic=topic, topic_id=topic_id))
        )

    @app.command("report")
    def report_command(
        since: str = _typer.Option("", "--since"), until: str = _typer.Option("", "--until")
    ) -> None:
        raise _typer.Exit(
            _cmd_report(argparse.Namespace(command="report", since=since, until=until))
        )

    @app.command("approve")
    def approve_command(
        article_id: str = _typer.Option(..., "--article-id"),
        reviewer: str = _typer.Option(..., "--reviewer"),
        notes: str = _typer.Option("", "--notes"),
    ) -> None:
        raise _typer.Exit(
            _cmd_approve(
                argparse.Namespace(
                    command="approve", article_id=article_id, reviewer=reviewer, notes=notes
                )
            )
        )

    @app.command("measure")
    def measure_command(
        article_id: str = _typer.Option(..., "--article-id"),
        wait: int = _typer.Option(0, "--wait"),
    ) -> None:
        raise _typer.Exit(
            _cmd_measure(argparse.Namespace(command="measure", article_id=article_id, wait=wait))
        )

    @app.command("seed-leads")
    def seed_leads(csv_path: str = _typer.Option(..., "--csv")) -> None:
        raise _typer.Exit(_cmd_seed_named(argparse.Namespace(command="seed-leads", csv=csv_path)))

    @app.command("seed-keywords")
    def seed_keywords(csv_path: str = _typer.Option(..., "--csv")) -> None:
        raise _typer.Exit(
            _cmd_seed_named(argparse.Namespace(command="seed-keywords", csv=csv_path))
        )

    @app.command("doctor")
    def doctor_command() -> None:
        raise _typer.Exit(_cmd_doctor(argparse.Namespace(command="doctor")))

    return app


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: Typer when installed, argparse for the pre-install path."""
    if argv is None and _typer is not None:
        _typer_app()()
        return 0
    args = _parser().parse_args(argv)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "run-batch":
        return _cmd_batch(args)
    if args.command == "replay":
        return _cmd_replay(args)
    if args.command == "inspect":
        return _cmd_inspect(args)
    if args.command == "seed-analytics":
        return _cmd_seed(args)
    if args.command == "evaluate":
        return _cmd_evaluate(args)
    if args.command == "plan":
        return _cmd_plan(args)
    if args.command == "geo":
        return _cmd_geo(args)
    if args.command == "report":
        return _cmd_report(args)
    if args.command == "approve":
        return _cmd_approve(args)
    if args.command == "measure":
        return _cmd_measure(args)
    if args.command in {"seed-leads", "seed-keywords"}:
        return _cmd_seed_named(args)
    if args.command == "doctor":
        return _cmd_doctor(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
