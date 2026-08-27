"""Token and request accounting for the agent.

Free-tier Gemini quotas are per-model and per-day, and a single audit fans out
across four sub agents and twenty-odd tool calls. Without measurement, "I ran
out of quota" carries no information about which part of the run was expensive.

`UsageTrackerPlugin` records one line per model call -- agent, model, token
counts, latency -- into a JSONL file. Nothing is aggregated at write time, so a
run that crashes still leaves usable data.

Registered application-wide in `agent.py`, so it sees every sub agent without
each one having to opt in.

Read it back with:

    python -m gtm_agent.usage              # summary of every run
    python -m gtm_agent.usage --last       # the most recent run only
    python -m gtm_agent.usage --json       # machine-readable
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin

from .config import PROJECT_ROOT
from .config import settings

logger = logging.getLogger(__name__)

DEFAULT_LOG_PATH = PROJECT_ROOT / "usage" / "model_calls.jsonl"


class UsageTrackerPlugin(BasePlugin):
    """Append one JSONL record per model call."""

    def __init__(self, log_path: Optional[Path] = None, name: str = "usage_tracker"):
        super().__init__(name=name)
        self.log_path = Path(log_path or os.getenv("GTM_USAGE_LOG") or DEFAULT_LOG_PATH)
        #: Groups the calls of one process together, so a report can separate
        #: "today's testing" from "the run that blew the quota".
        self.run_id = uuid.uuid4().hex[:12]

    async def before_model_callback(self, *, callback_context, llm_request):
        # Latency is measured per call because sub agents interleave.
        setattr(callback_context, "_usage_started_at", time.time())
        return None

    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> None:
        usage = getattr(llm_response, "usage_metadata", None)
        started = getattr(callback_context, "_usage_started_at", None)
        total = getattr(usage, "total_token_count", None)

        # A streamed response emits many partial chunks and one final chunk;
        # only the final one carries usage. Counting the partials would inflate
        # the request count several-fold, which is the number that matters
        # against a requests-per-day quota.
        if bool(getattr(llm_response, "partial", False)) and total is None:
            return None

        record = {
            "ts": time.time(),
            "run_id": self.run_id,
            "agent": getattr(callback_context, "agent_name", None),
            "invocation_id": getattr(callback_context, "invocation_id", None),
            "model": self._model_name(callback_context),
            "provider": settings.model_provider,
            "latency_s": round(time.time() - started, 3) if started else None,
            "prompt_tokens": getattr(usage, "prompt_token_count", None),
            "output_tokens": getattr(usage, "candidates_token_count", None),
            "thoughts_tokens": getattr(usage, "thoughts_token_count", None),
            "cached_tokens": getattr(usage, "cached_content_token_count", None),
            "total_tokens": total,
            "error": getattr(llm_response, "error_code", None),
        }

        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")
        except OSError:  # pragma: no cover - never break a run over telemetry
            logger.warning("Could not write usage record to %s", self.log_path)
        return None

    @staticmethod
    def _model_name(callback_context: CallbackContext) -> Optional[str]:
        try:
            model = callback_context._invocation_context.agent.canonical_model
        except Exception:  # pragma: no cover
            return None
        return getattr(model, "model", None) or str(model)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

_TOKEN_FIELDS = (
    "prompt_tokens",
    "output_tokens",
    "thoughts_tokens",
    "cached_tokens",
    "total_tokens",
)


def load_records(log_path: Optional[Path] = None) -> list[dict[str, Any]]:
    """Read the JSONL log, skipping any line a crash left half-written."""
    path = Path(log_path or os.getenv("GTM_USAGE_LOG") or DEFAULT_LOG_PATH)
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _blank() -> dict[str, Any]:
    bucket = {field: 0 for field in _TOKEN_FIELDS}
    bucket.update({"requests": 0, "errors": 0, "latency_s": 0.0})
    return bucket


def _add(bucket: dict[str, Any], record: dict[str, Any]) -> None:
    bucket["requests"] += 1
    for field in _TOKEN_FIELDS:
        bucket[field] += record.get(field) or 0
    bucket["latency_s"] += record.get("latency_s") or 0.0
    if record.get("error"):
        bucket["errors"] += 1


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate records by run, by agent and by model."""
    overall = _blank()
    by_run: dict[str, dict[str, Any]] = defaultdict(_blank)
    by_agent: dict[str, dict[str, Any]] = defaultdict(_blank)
    by_model: dict[str, dict[str, Any]] = defaultdict(_blank)

    for record in records:
        _add(overall, record)
        _add(by_run[record.get("run_id", "?")], record)
        _add(by_agent[record.get("agent") or "?"], record)
        _add(by_model[record.get("model") or "?"], record)

    for run_id, bucket in by_run.items():
        stamps = [r["ts"] for r in records if r.get("run_id") == run_id and r.get("ts")]
        bucket["started"] = min(stamps) if stamps else None
        bucket["ended"] = max(stamps) if stamps else None

    return {
        "overall": overall,
        "by_run": dict(by_run),
        "by_agent": dict(by_agent),
        "by_model": dict(by_model),
    }


def _table(title: str, rows: dict[str, dict[str, Any]], key_header: str) -> list[str]:
    if not rows:
        return []
    width = max([len(key_header)] + [len(str(k)) for k in rows])
    header = (
        "  {:<{w}}  {:>5}  {:>9}  {:>8}  {:>8}  {:>9}  {:>8}  {:>4}".format(
            key_header, "reqs", "prompt", "output", "cached", "total", "avg/req",
            "errs", w=width,
        )
    )
    lines = ["", title, header]
    for key, bucket in sorted(rows.items(), key=lambda kv: -kv[1]["total_tokens"]):
        avg = bucket["total_tokens"] / bucket["requests"] if bucket["requests"] else 0
        lines.append(
            "  {:<{w}}  {:>5}  {:>9,}  {:>8,}  {:>8,}  {:>9,}  {:>8,.0f}  {:>4}".format(
                str(key), bucket["requests"], bucket["prompt_tokens"],
                bucket["output_tokens"], bucket["cached_tokens"],
                bucket["total_tokens"], avg, bucket["errors"], w=width,
            )
        )
    return lines


def render_report(records: list[dict[str, Any]]) -> str:
    """A text report of requests and tokens, ready to paste into an issue."""
    if not records:
        path = Path(os.getenv("GTM_USAGE_LOG") or DEFAULT_LOG_PATH)
        return (
            "No usage recorded yet.\n\n"
            f"The tracker writes to {path}\n"
            "Run the agent once (adk web, or adk run gtm_agent), then try again."
        )

    summary = summarize(records)
    overall = summary["overall"]
    runs = summary["by_run"]

    lines = [
        "GTM Auto Tagging - model usage",
        "=" * 62,
        f"  runs recorded      {len(runs)}",
        f"  model requests     {overall['requests']:,}",
        f"  prompt tokens      {overall['prompt_tokens']:,}",
        f"  output tokens      {overall['output_tokens']:,}",
        f"  cached tokens      {overall['cached_tokens']:,}",
        f"  total tokens       {overall['total_tokens']:,}",
        f"  failed calls       {overall['errors']:,}",
    ]
    if overall["requests"]:
        lines += [
            f"  avg tokens/request {overall['total_tokens'] / overall['requests']:,.0f}",
            f"  avg latency        {overall['latency_s'] / overall['requests']:.1f}s",
        ]
    if runs:
        lines += [
            "",
            f"  requests per run   {overall['requests'] / len(runs):,.1f}"
            "   <- what a requests-per-day quota is spent on",
        ]

    lines += _table("By agent", summary["by_agent"], "agent")
    lines += _table("By model", summary["by_model"], "model")

    recent = sorted(runs.items(), key=lambda kv: kv[1].get("started") or 0)[-5:]
    if recent:
        lines += ["", "Last runs"]
        for run_id, bucket in recent:
            started = bucket.get("started")
            when = (
                time.strftime("%Y-%m-%d %H:%M", time.localtime(started))
                if started
                else "?"
            )
            duration = (bucket.get("ended") or 0) - (started or 0)
            lines.append(
                f"  {when}  run {run_id}  {bucket['requests']:>3} reqs"
                f"  {bucket['total_tokens']:>8,} tokens  {duration:>5.0f}s"
            )

    lines += [
        "",
        "Reading this against a free-tier quota",
        "  - Requests-per-day is spent by the 'model requests' number, not by",
        "    tokens. One user turn costs several requests: every sub agent",
        "    transfer and every tool round trip is its own call.",
        "  - 'By agent' shows where a cheaper model would help. An agent making",
        "    many small calls and one making few large ones want different",
        "    models - see GTM_MODEL_FAST and GTM_MODEL_REASONING.",
        "  - High prompt tokens with few requests means instructions and tool",
        "    declarations dominate. Trimming an agent's toolset saves more than",
        "    shortening its replies, because the declarations are resent on",
        "    every call of that agent.",
    ]
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m gtm_agent.usage",
        description="Report model token and request usage for this agent.",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--last", action="store_true", help="only the most recent run")
    parser.add_argument("--path", type=Path, default=None, help="usage log location")
    args = parser.parse_args(argv)

    records = load_records(args.path)
    if args.last and records:
        latest = max(records, key=lambda r: r.get("ts", 0)).get("run_id")
        records = [r for r in records if r.get("run_id") == latest]

    if args.json:
        print(json.dumps(summarize(records), indent=2))
    else:
        print(render_report(records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
