"""Stable command-line interface for the Test Platform."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from test_platform import __version__
from test_platform.contracts import (
    EvidenceClass,
    ExecutionTrustClass,
    QualityResult,
)
from test_platform.doctor import run_doctor
from test_platform.guidance import generate_agent_guidance
from test_platform.operator import (
    actions_report,
    analyze_gaps_from_context,
    build_repository_inventory,
    evaluate_from_context,
    load_repository_context,
    parse_behavior_evidence,
    parse_behavior_links,
    parse_gap_findings,
    parse_quality_assessment,
    parse_receipt_ids,
    parse_rule_states,
    parse_test_inventory,
    parse_waivers,
    parse_workflow_observations,
)
from test_platform.planning import (
    ExecutionEvent,
    PlanningContext,
    compile_execution_plan,
)
from test_platform.reporting import (
    build_quality_export,
    command_envelope,
    load_json_file,
    public_safe_value,
    render_markdown,
    serialize_json,
)


def _add_output_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the complete versioned machine-readable JSON payload.",
    )
    parser.add_argument(
        "--public-safe",
        action="store_true",
        help="Redact absolute/private paths and explicitly sensitive fields.",
    )


def _add_repository(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path("."),
        help="Explicit repository root. Defaults to the current directory.",
    )


def _add_identity(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repository", required=True, help="Canonical repository identity.")
    parser.add_argument("--sha", required=True, help="Full exact repository SHA.")


def build_parser() -> argparse.ArgumentParser:
    """Build the stable V1 top-level parser."""
    parser = argparse.ArgumentParser(
        prog="test-platform",
        description="Behavioral verification and quality-evidence platform.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser(
        "doctor",
        help="Run bounded credential-free environment diagnostics.",
    )
    _add_output_flags(doctor)

    validate = subparsers.add_parser(
        "validate",
        help="Validate the manifest, profile binding, and behavior declarations.",
    )
    _add_repository(validate)
    _add_output_flags(validate)

    inventory = subparsers.add_parser(
        "inventory",
        help="Discover supported frameworks and build a normalized test inventory.",
    )
    _add_repository(inventory)
    _add_identity(inventory)
    inventory.add_argument("--behavior-links", type=Path)
    _add_output_flags(inventory)

    behaviors = subparsers.add_parser(
        "behaviors",
        help="Render declared behaviors and critical journeys.",
    )
    _add_repository(behaviors)
    _add_output_flags(behaviors)

    audit = subparsers.add_parser(
        "audit",
        help="Run a bounded offline repository declaration/discovery audit.",
    )
    _add_repository(audit)
    _add_identity(audit)
    audit.add_argument("--behavior-links", type=Path)
    _add_output_flags(audit)

    gaps = subparsers.add_parser(
        "gaps",
        help="Evaluate behavior and journey evidence gaps for an exact SHA.",
    )
    _add_repository(gaps)
    gaps.add_argument("--sha", required=True)
    gaps.add_argument("--evidence", type=Path, required=True)
    _add_output_flags(gaps)

    plan = subparsers.add_parser(
        "plan",
        help="Compile an exact-SHA deterministic ExecutionPlan.",
    )
    _add_repository(plan)
    _add_identity(plan)
    plan.add_argument(
        "--trust",
        required=True,
        choices=[item.value for item in ExecutionTrustClass],
    )
    plan.add_argument(
        "--event",
        required=True,
        choices=[item.value for item in ExecutionEvent],
    )
    plan.add_argument("--policy-version", default="1")
    plan.add_argument(
        "--behavior-evidence-class",
        action="append",
        default=[],
        choices=[item.value for item in EvidenceClass],
    )
    plan.add_argument("--conditional-rule", action="append", default=[])
    plan.add_argument("--additional-suite", action="append", default=[])
    plan.add_argument("--live-target")
    plan.add_argument("--owner-approved", action="store_true")
    _add_output_flags(plan)

    evaluate = subparsers.add_parser(
        "evaluate",
        help="Evaluate deterministic quality policy from explicit evidence states.",
    )
    _add_repository(evaluate)
    _add_identity(evaluate)
    evaluate.add_argument("--rule-states", type=Path, required=True)
    evaluate.add_argument("--gaps", type=Path)
    evaluate.add_argument("--waivers", type=Path)
    evaluate.add_argument("--conditional-rule", action="append", default=[])
    evaluate.add_argument("--blocked-reason", action="append", default=[])
    evaluate.add_argument(
        "--now",
        required=True,
        help="Explicit ISO-8601 evaluation time for deterministic waiver expiry.",
    )
    _add_output_flags(evaluate)

    actions = subparsers.add_parser(
        "actions",
        help="Analyze sanitized GitHub Actions observations for execution placement.",
    )
    actions.add_argument("--input", type=Path, required=True)
    _add_output_flags(actions)

    migration = subparsers.add_parser(
        "migration-plan",
        help="Render safe Actions migration candidates without mutating workflows.",
    )
    migration.add_argument("--input", type=Path, required=True)
    _add_output_flags(migration)

    report = subparsers.add_parser(
        "report",
        help="Render a bounded repository quality/context report.",
    )
    _add_repository(report)
    _add_identity(report)
    report.add_argument("--behavior-links", type=Path)
    report.add_argument("--assessment", type=Path)
    _add_output_flags(report)

    export = subparsers.add_parser(
        "portfolio-export",
        help="Build a complete versioned QualityExport for Portfolio Graph.",
    )
    _add_repository(export)
    export.add_argument("--assessment", type=Path, required=True)
    export.add_argument("--receipt-ids", type=Path)
    export.add_argument("--generated-at", required=True)
    _add_output_flags(export)

    guide = subparsers.add_parser(
        "guide",
        help="Generate deterministic behavior-focused testing guidance for an agent.",
    )
    _add_repository(guide)
    guide.add_argument("--inventory", type=Path, required=True)
    guide.add_argument("--gaps", type=Path, required=True)
    guide.add_argument(
        "--affected-behavior",
        action="append",
        required=True,
    )
    _add_output_flags(guide)

    return parser


def _iso_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO-8601 timestamp: {value}") from exc


def _emit(command: str, payload: dict[str, Any], args: argparse.Namespace) -> int:
    envelope = command_envelope(
        command,
        payload,
        public_safe=bool(args.public_safe),
    )
    if args.json:
        print(serialize_json(envelope))
    else:
        rendered_payload = cast(dict[str, Any], envelope["payload"])
        print(render_markdown(command, rendered_payload), end="")
    return 0


def _optional_json(path: Path | None) -> Any:
    return load_json_file(path) if path is not None else None


def _context_payload(args: argparse.Namespace) -> dict[str, Any]:
    context = load_repository_context(args.repo)
    return {
        "validation": "pass",
        "manifest": context.manifest.model_dump(mode="json"),
        "profile": context.profile.model_dump(mode="json"),
        "behaviors": context.behaviors.model_dump(mode="json"),
    }


def _inventory_payload(args: argparse.Namespace) -> dict[str, Any]:
    context = load_repository_context(args.repo)
    links = parse_behavior_links(_optional_json(args.behavior_links))
    discovery, result = build_repository_inventory(
        context,
        repository=args.repository,
        sha=args.sha,
        behavior_links=links,
    )
    return {
        "repository": args.repository,
        "sha": args.sha,
        "profile": context.manifest.profile.model_dump(mode="json"),
        "discovery": discovery.model_dump(mode="json"),
        "inventory": result.inventory.model_dump(mode="json"),
        "diagnostics": [
            {
                "code": item.code,
                "message": item.message,
                "test_ids": list(item.test_ids),
            }
            for item in result.diagnostics
        ],
    }


def _dispatch(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    if args.command == "doctor":
        report = run_doctor()
        payload = report.as_dict()
        return (0 if report.overall == "PASS" else 1), payload

    if args.command == "validate":
        return 0, _context_payload(args)

    if args.command == "inventory":
        return 0, _inventory_payload(args)

    if args.command == "behaviors":
        context = load_repository_context(args.repo)
        return 0, {
            "profile": context.manifest.profile.model_dump(mode="json"),
            "behaviors": context.behaviors.model_dump(mode="json"),
        }

    if args.command == "audit":
        payload = _inventory_payload(args)
        payload["audit_state"] = "not-evaluable"
        payload["audit_reason"] = (
            "offline audit does not synthesize execution or live qualification evidence"
        )
        return 0, payload

    if args.command == "gaps":
        context = load_repository_context(args.repo)
        observations = parse_behavior_evidence(load_json_file(args.evidence))
        findings = analyze_gaps_from_context(
            context,
            observations,
            sha=args.sha,
        )
        return 0, {
            "sha": args.sha,
            "profile": context.manifest.profile.model_dump(mode="json"),
            "gaps": [item.model_dump(mode="json") for item in findings],
        }

    if args.command == "plan":
        context = load_repository_context(args.repo)
        compiled = compile_execution_plan(
            repository=args.repository,
            sha=args.sha,
            profile=context.profile,
            manifest=context.manifest,
            trust=ExecutionTrustClass(args.trust),
            policy_version=args.policy_version,
            context=PlanningContext(
                event=ExecutionEvent(args.event),
                live_target=args.live_target,
                owner_approved=bool(args.owner_approved),
            ),
            behavior_evidence_classes=tuple(
                EvidenceClass(item) for item in args.behavior_evidence_class
            ),
            applicable_conditional_rules=frozenset(args.conditional_rule),
            additional_suite_ids=frozenset(args.additional_suite),
        )
        return 0, {
            "plan": compiled.plan.model_dump(mode="json"),
            "context": {
                "event": compiled.context.event.value,
                "live_target": compiled.context.live_target,
                "owner_approved": compiled.context.owner_approved,
            },
        }

    if args.command == "evaluate":
        context = load_repository_context(args.repo)
        assessment = evaluate_from_context(
            context,
            repository=args.repository,
            sha=args.sha,
            rule_states=parse_rule_states(load_json_file(args.rule_states)),
            gaps=parse_gap_findings(_optional_json(args.gaps)),
            waivers=parse_waivers(_optional_json(args.waivers)),
            applicable_conditional_rules=frozenset(args.conditional_rule),
            blocked_reasons=tuple(args.blocked_reason),
            now=_iso_datetime(args.now),
        )
        exit_code = 0 if assessment.result is QualityResult.PASS else 1
        return exit_code, {
            "assessment": assessment.model_dump(mode="json"),
        }

    if args.command in {"actions", "migration-plan"}:
        observations = parse_workflow_observations(load_json_file(args.input))
        report = actions_report(observations)
        decisions = [
            item.model_dump(mode="json")
            for item in report.decisions
        ]
        payload: dict[str, Any] = {
            "decisions": decisions,
            "hosted_verification_minutes": report.hosted_verification_minutes,
            "hosted_deployment_minutes": report.hosted_deployment_minutes,
            "candidate_moved_minutes": report.candidate_moved_minutes,
        }
        if args.command == "migration-plan":
            payload["migration_candidates"] = [
                item
                for item in decisions
                if item["placement"] in {
                    "move-to-jenkins",
                    "remove-duplicate",
                }
            ]
            payload["mutation_performed"] = False
        return 0, payload

    if args.command == "report":
        payload = _inventory_payload(args)
        raw_assessment = _optional_json(args.assessment)
        if raw_assessment is None:
            payload["quality"] = {
                "result": "not-evaluable",
                "reason": "no QualityAssessment was supplied",
            }
        else:
            assessment = parse_quality_assessment(raw_assessment)
            if assessment.repository != args.repository or assessment.sha != args.sha:
                raise ValueError("assessment repository/SHA does not match report target")
            payload["quality"] = assessment.model_dump(mode="json")
        return 0, payload

    if args.command == "portfolio-export":
        context = load_repository_context(args.repo)
        assessment = parse_quality_assessment(load_json_file(args.assessment))
        receipt_ids = parse_receipt_ids(_optional_json(args.receipt_ids))
        export = build_quality_export(
            assessment,
            context.behaviors,
            receipt_ids=receipt_ids,
            generated_at=_iso_datetime(args.generated_at),
        )
        return 0, {"quality_export": export.model_dump(mode="json")}

    if args.command == "guide":
        context = load_repository_context(args.repo)
        inventory = parse_test_inventory(load_json_file(args.inventory))
        gaps = parse_gap_findings(load_json_file(args.gaps))
        guidance = generate_agent_guidance(
            manifest=context.manifest,
            profile=context.profile,
            behaviors=context.behaviors,
            inventory=inventory,
            affected_behavior_ids=tuple(args.affected_behavior),
            gap_findings=gaps,
        )
        return 0, {"guidance": guidance.model_dump(mode="json")}

    raise ValueError(f"unsupported command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a stable process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        exit_code, payload = _dispatch(args)
        _emit(args.command, payload, args)
        return exit_code
    except (OSError, ValueError) as exc:
        safe_message = public_safe_value(str(exc), key="error")
        print(f"test-platform: {safe_message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
