#!/usr/bin/env python3
# pyright: reportUnusedCallResult=false
"""Inspect and manage project-level SonarCloud or SonarQube resources."""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING, Any

from sonar_manage_api import (
    DEFAULT_AUTH_SCHEME,
    DEFAULT_HOTSPOT_STATUS,
    DEFAULT_ISSUE_STATUSES,
    DEFAULT_PAGE_SIZE,
    DEFAULT_SUMMARY_METRICS,
    SonarCliError,
    resolve_context,
)
from sonar_manage_common import (
    parse_name_value_pairs,
    resolve_csv_values,
    resolve_tag_values,
)
from sonar_manage_diagnostics import (
    DEFAULT_PROJECT_ANALYSES_PAGE_SIZE,
    fetch_ce_component,
    fetch_ce_task,
    fetch_project_analyses,
    investigate_tsconfig_warning,
)
from sonar_manage_issues import (
    add_issue_comment,
    assign_issue,
    fetch_hotspot_detail,
    fetch_hotspots,
    fetch_issue_changelog,
    fetch_issues,
    review_hotspots,
    set_issue_tags,
    transition_issues,
)
from sonar_manage_project import (
    build_summary,
    direct_api_call,
    fetch_measure_history,
    fetch_measures,
    fetch_project_component_info,
    fetch_project_quality_gate,
    fetch_quality_gate_status,
    fetch_quality_profile_changelog,
    fetch_settings_definitions,
    fetch_settings_values,
    list_quality_gates,
    list_quality_profiles,
    reset_setting_value,
    search_project_tags,
    set_project_tags,
    set_quality_gate,
    set_quality_profile,
    set_setting_value,
    unset_quality_gate,
    unset_quality_profile,
)
from sonar_manage_render import emit_output

if TYPE_CHECKING:
    from sonar_manage_api import ProjectContext

HELP_COMPONENT_KEY_OVERRIDE = "Optional component key override. Defaults to the project key."
HELP_DRY_RUN = "Print the intended mutation without sending it."
HELP_ISSUE_KEY = "Issue key."
HELP_PROJECT_KEY_OVERRIDE = "Optional project key override."
HELP_QUALITY_PROFILE_KEY = "Quality profile key."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect and manage project-level SonarCloud or SonarQube resources using an environment-variable token."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Path inside the target repository or project checkout.",
    )
    parser.add_argument(
        "--project-key",
        default=None,
        help=(
            "Explicit Sonar project key. If omitted, the script tries to read "
            "sonar.projectKey from sonar-project.properties."
        ),
    )
    parser.add_argument(
        "--organization",
        default=None,
        help=(
            "Explicit Sonar organization key. If omitted, the script tries to read "
            "sonar.organization from sonar-project.properties."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help=("Sonar base URL. Defaults to sonar.host.url from sonar-project.properties or SonarCloud."),
    )
    parser.add_argument(
        "--token-env",
        action="append",
        dest="token_envs",
        default=None,
        help=("Environment variable name that may contain the Sonar token. Repeat to provide fallbacks."),
    )
    parser.add_argument(
        "--auth-scheme",
        choices=("auto", "bearer", "basic"),
        default=DEFAULT_AUTH_SCHEME,
        help=(
            "Authentication scheme to use. 'auto' tries Bearer first, then Basic "
            "for compatibility with older endpoints."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of text output.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    summary_parser = subparsers.add_parser(
        "summary",
        help="Fetch a summary of issues, hotspots, quality gate, and measures.",
    )
    add_issue_listing_args(summary_parser, include_page=False)
    summary_parser.add_argument(
        "--hotspot-status",
        default=DEFAULT_HOTSPOT_STATUS,
        help="Hotspot lifecycle status to query.",
    )
    summary_parser.add_argument(
        "--sample-size",
        type=int,
        default=5,
        help="Number of issue and hotspot samples to include.",
    )
    summary_parser.add_argument(
        "--metrics",
        default=DEFAULT_SUMMARY_METRICS,
        help="Comma-separated metric keys to include in the summary.",
    )

    list_issues_parser = subparsers.add_parser(
        "list-issues",
        help="List Sonar issues for the resolved project.",
    )
    add_issue_listing_args(list_issues_parser, include_page=True)

    issue_changelog_parser = subparsers.add_parser(
        "issue-changelog",
        help="Fetch the changelog/activity for one issue.",
    )
    issue_changelog_parser.add_argument("--issue", required=True, help=HELP_ISSUE_KEY)

    issue_comment_parser = subparsers.add_parser(
        "comment-issue",
        help="Add a comment to one issue.",
    )
    issue_comment_parser.add_argument("--issue", required=True, help=HELP_ISSUE_KEY)
    issue_comment_parser.add_argument("--text", required=True, help="Comment text.")
    issue_comment_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=HELP_DRY_RUN,
    )

    issue_assign_parser = subparsers.add_parser(
        "assign-issue",
        help="Assign or unassign one issue.",
    )
    issue_assign_parser.add_argument("--issue", required=True, help=HELP_ISSUE_KEY)
    issue_assign_parser.add_argument(
        "--assignee",
        required=True,
        help="Assignee login. Use an empty string to unassign.",
    )
    issue_assign_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=HELP_DRY_RUN,
    )

    issue_tags_parser = subparsers.add_parser(
        "set-issue-tags",
        help="Replace the tags on one issue.",
    )
    issue_tags_parser.add_argument("--issue", required=True, help=HELP_ISSUE_KEY)
    issue_tags_parser.add_argument(
        "--tag",
        action="append",
        dest="tags",
        default=None,
        help="Tag to apply. Repeat or pass comma-separated values.",
    )
    issue_tags_parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear all tags instead of setting tags.",
    )
    issue_tags_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=HELP_DRY_RUN,
    )

    transition_issue_parser = subparsers.add_parser(
        "transition-issue",
        help="Apply a workflow transition to one or more Sonar issues.",
    )
    transition_issue_parser.add_argument(
        "--issue",
        action="append",
        dest="issues",
        required=True,
        help="Issue key to transition. Repeat for multiple issues.",
    )
    transition_issue_parser.add_argument(
        "--transition",
        required=True,
        help="Issue transition such as resolve, wontfix, falsepositive, or accept.",
    )
    transition_issue_parser.add_argument(
        "--comment",
        default=None,
        help="Optional comment to add alongside the issue transition.",
    )
    transition_issue_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=HELP_DRY_RUN,
    )

    list_hotspots_parser = subparsers.add_parser(
        "list-hotspots",
        help="List security hotspots for the resolved project.",
    )
    add_hotspot_listing_args(list_hotspots_parser)
    list_hotspots_parser.add_argument(
        "--page",
        type=int,
        default=1,
        help="Hotspot search page number.",
    )
    list_hotspots_parser.add_argument(
        "--include-details",
        action="store_true",
        help="Fetch api/hotspots/show for each returned hotspot.",
    )

    show_hotspot_parser = subparsers.add_parser(
        "show-hotspot",
        help="Show one security hotspot, including its activity fields.",
    )
    show_hotspot_parser.add_argument(
        "--hotspot",
        required=True,
        help="Hotspot key.",
    )

    review_hotspot_parser = subparsers.add_parser(
        "review-hotspot",
        help="Change the review status of one or more security hotspots.",
    )
    review_hotspot_parser.add_argument(
        "--hotspot",
        action="append",
        dest="hotspots",
        required=True,
        help="Hotspot key to update. Repeat for multiple hotspots.",
    )
    review_hotspot_parser.add_argument(
        "--status",
        required=True,
        help="Target hotspot status value, for example REVIEWED.",
    )
    review_hotspot_parser.add_argument(
        "--resolution",
        required=True,
        help="Target hotspot resolution, for example SAFE or FIXED.",
    )
    review_hotspot_parser.add_argument(
        "--comment",
        default=None,
        help="Optional comment to add alongside the hotspot review.",
    )
    review_hotspot_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=HELP_DRY_RUN,
    )

    measures_parser = subparsers.add_parser(
        "measures",
        help="Fetch current metric values for a component or project.",
    )
    measures_parser.add_argument(
        "--metric",
        action="append",
        dest="metrics",
        default=None,
        help="Metric key to fetch. Repeat or pass comma-separated values.",
    )
    measures_parser.add_argument(
        "--component",
        default=None,
        help="Component key. Defaults to the resolved project key.",
    )

    measures_history_parser = subparsers.add_parser(
        "measures-history",
        help="Fetch metric history for a component or project.",
    )
    measures_history_parser.add_argument(
        "--metric",
        action="append",
        dest="metrics",
        required=True,
        help="Metric key to fetch. Repeat or pass comma-separated values.",
    )
    measures_history_parser.add_argument(
        "--component",
        default=None,
        help="Component key. Defaults to the resolved project key.",
    )
    measures_history_parser.add_argument(
        "--from-date",
        default=None,
        help="Optional start date filter accepted by Sonar, for example 2026-03-01.",
    )
    measures_history_parser.add_argument(
        "--to-date",
        default=None,
        help="Optional end date filter accepted by Sonar, for example 2026-03-22.",
    )

    project_info_parser = subparsers.add_parser(
        "project-info",
        help="Show the resolved project component details.",
    )
    project_info_parser.add_argument(
        "--component",
        default=None,
        help="Optional component key. Defaults to the resolved project key.",
    )

    ce_component_parser = subparsers.add_parser(
        "ce-component",
        help="Show Compute Engine task information for the project/component.",
    )
    ce_component_parser.add_argument(
        "--component",
        default=None,
        help="Optional component key. Defaults to the resolved project key.",
    )

    ce_task_parser = subparsers.add_parser(
        "ce-task",
        help="Show details for one Compute Engine task id.",
    )
    ce_task_parser.add_argument(
        "--task-id",
        required=True,
        help="Compute Engine task id.",
    )

    project_analyses_parser = subparsers.add_parser(
        "project-analyses",
        help="List recent project analyses and attached events.",
    )
    project_analyses_parser.add_argument(
        "--project",
        default=None,
        help=HELP_PROJECT_KEY_OVERRIDE,
    )
    project_analyses_parser.add_argument(
        "--page",
        type=int,
        default=1,
        help="Project analyses page number.",
    )
    project_analyses_parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PROJECT_ANALYSES_PAGE_SIZE,
        help="Maximum number of analyses to fetch.",
    )

    subparsers.add_parser(
        "tsconfig-warning-check",
        help=(
            "Investigate the common Sonar TypeScript tsconfig warning using "
            "project settings, CE metadata, and the local tsconfig graph."
        ),
    )

    quality_gate_status_parser = subparsers.add_parser(
        "quality-gate-status",
        help="Fetch the current quality gate status for the project.",
    )
    quality_gate_status_parser.add_argument(
        "--project",
        default=None,
        help=HELP_PROJECT_KEY_OVERRIDE,
    )

    subparsers.add_parser(
        "list-quality-gates",
        help="List available quality gates.",
    )

    get_quality_gate_parser = subparsers.add_parser(
        "get-quality-gate",
        help="Show the quality gate currently associated with the project.",
    )
    get_quality_gate_parser.add_argument(
        "--project",
        default=None,
        help=HELP_PROJECT_KEY_OVERRIDE,
    )

    set_quality_gate_parser = subparsers.add_parser(
        "set-quality-gate",
        help="Associate the project with a quality gate.",
    )
    gate_group = set_quality_gate_parser.add_mutually_exclusive_group(required=True)
    gate_group.add_argument(
        "--gate-id",
        default=None,
        help="Quality gate id.",
    )
    gate_group.add_argument(
        "--gate-name",
        default=None,
        help="Quality gate name. The script resolves the id automatically.",
    )
    set_quality_gate_parser.add_argument(
        "--project",
        default=None,
        help=HELP_PROJECT_KEY_OVERRIDE,
    )
    set_quality_gate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=HELP_DRY_RUN,
    )

    unset_quality_gate_parser = subparsers.add_parser(
        "unset-quality-gate",
        help="Remove the project's explicit quality gate association.",
    )
    unset_quality_gate_parser.add_argument(
        "--project",
        default=None,
        help=HELP_PROJECT_KEY_OVERRIDE,
    )
    unset_quality_gate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=HELP_DRY_RUN,
    )

    list_quality_profiles_parser = subparsers.add_parser(
        "list-quality-profiles",
        help="List quality profiles relevant to the project.",
    )
    list_quality_profiles_parser.add_argument(
        "--project",
        default=None,
        help=HELP_PROJECT_KEY_OVERRIDE,
    )
    list_quality_profiles_parser.add_argument(
        "--language",
        default=None,
        help="Optional language filter, for example ts or js.",
    )
    list_quality_profiles_parser.add_argument(
        "--quality-profile",
        default=None,
        help="Optional exact quality profile key filter.",
    )

    quality_profile_changelog_parser = subparsers.add_parser(
        "quality-profile-changelog",
        help="Fetch the changelog for one quality profile.",
    )
    quality_profile_changelog_parser.add_argument(
        "--quality-profile",
        required=True,
        help=HELP_QUALITY_PROFILE_KEY,
    )

    set_quality_profile_parser = subparsers.add_parser(
        "set-quality-profile",
        help="Associate the project with a quality profile.",
    )
    set_quality_profile_parser.add_argument(
        "--quality-profile",
        required=True,
        help=HELP_QUALITY_PROFILE_KEY,
    )
    set_quality_profile_parser.add_argument(
        "--project",
        default=None,
        help=HELP_PROJECT_KEY_OVERRIDE,
    )
    set_quality_profile_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=HELP_DRY_RUN,
    )

    unset_quality_profile_parser = subparsers.add_parser(
        "unset-quality-profile",
        help="Remove the project association from a quality profile.",
    )
    unset_quality_profile_parser.add_argument(
        "--quality-profile",
        required=True,
        help=HELP_QUALITY_PROFILE_KEY,
    )
    unset_quality_profile_parser.add_argument(
        "--project",
        default=None,
        help=HELP_PROJECT_KEY_OVERRIDE,
    )
    unset_quality_profile_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=HELP_DRY_RUN,
    )

    settings_values_parser = subparsers.add_parser(
        "settings-values",
        help="List project settings values.",
    )
    settings_values_parser.add_argument(
        "--key",
        action="append",
        dest="keys",
        default=None,
        help="Setting key to fetch. Repeat or pass comma-separated values.",
    )
    settings_values_parser.add_argument(
        "--component",
        default=None,
        help=HELP_COMPONENT_KEY_OVERRIDE,
    )

    settings_definitions_parser = subparsers.add_parser(
        "settings-definitions",
        help="List setting definitions for a project.",
    )
    settings_definitions_parser.add_argument(
        "--key",
        action="append",
        dest="keys",
        default=None,
        help="Setting key to fetch. Repeat or pass comma-separated values.",
    )
    settings_definitions_parser.add_argument(
        "--component",
        default=None,
        help=HELP_COMPONENT_KEY_OVERRIDE,
    )

    settings_set_parser = subparsers.add_parser(
        "settings-set",
        help="Set a project setting value.",
    )
    settings_set_parser.add_argument("--key", required=True, help="Setting key.")
    setting_values_group = settings_set_parser.add_mutually_exclusive_group(required=True)
    setting_values_group.add_argument(
        "--value",
        default=None,
        help="Single setting value.",
    )
    setting_values_group.add_argument(
        "--values",
        nargs="+",
        default=None,
        help="Multiple setting values. These are sent as a comma-separated list.",
    )
    settings_set_parser.add_argument(
        "--component",
        default=None,
        help=HELP_COMPONENT_KEY_OVERRIDE,
    )
    settings_set_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=HELP_DRY_RUN,
    )

    settings_reset_parser = subparsers.add_parser(
        "settings-reset",
        help="Reset a project setting to its inherited/default value.",
    )
    settings_reset_parser.add_argument("--key", required=True, help="Setting key.")
    settings_reset_parser.add_argument(
        "--component",
        default=None,
        help=HELP_COMPONENT_KEY_OVERRIDE,
    )
    settings_reset_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=HELP_DRY_RUN,
    )

    search_project_tags_parser = subparsers.add_parser(
        "search-project-tags",
        help="Search available project tags.",
    )
    search_project_tags_parser.add_argument(
        "--query-text",
        default=None,
        help="Optional search text.",
    )
    search_project_tags_parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help="Maximum number of tags to fetch.",
    )

    set_project_tags_parser = subparsers.add_parser(
        "set-project-tags",
        help="Replace the tags on the current project.",
    )
    set_project_tags_parser.add_argument(
        "--project",
        default=None,
        help=HELP_PROJECT_KEY_OVERRIDE,
    )
    set_project_tags_parser.add_argument(
        "--tag",
        action="append",
        dest="tags",
        default=None,
        help="Tag to apply. Repeat or pass comma-separated values.",
    )
    set_project_tags_parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear all project tags instead of setting tags.",
    )
    set_project_tags_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=HELP_DRY_RUN,
    )

    api_call_parser = subparsers.add_parser(
        "api-call",
        help="Call any Sonar API endpoint directly as an escape hatch.",
    )
    api_call_parser.add_argument(
        "--endpoint",
        required=True,
        help=(
            "API endpoint path such as /api/issues/search. Absolute URLs are "
            "allowed only when their origin matches --base-url."
        ),
    )
    api_call_parser.add_argument(
        "--method",
        choices=("GET", "POST"),
        default="GET",
        help="HTTP method.",
    )
    api_call_parser.add_argument(
        "--query-param",
        action="append",
        dest="query_params",
        default=None,
        help="Query parameter in key=value form. Repeat as needed.",
    )
    api_call_parser.add_argument(
        "--form-param",
        action="append",
        dest="form_params",
        default=None,
        help="Form parameter in key=value form. Repeat as needed.",
    )
    api_call_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the intended request without sending it.",
    )

    return parser.parse_args(normalize_global_args(sys.argv[1:]))


def normalize_global_args(argv: list[str]) -> list[str]:
    flags_with_values = {
        "--repo",
        "--project-key",
        "--organization",
        "--base-url",
        "--token-env",
        "--auth-scheme",
    }
    flags_without_values = {"--json"}

    global_args: list[str] = []
    other_args: list[str] = []
    index = 0
    while index < len(argv):
        argument = argv[index]

        if argument in flags_without_values:
            global_args.append(argument)
            index += 1
            continue

        if argument in flags_with_values:
            next_index = index + 1
            if next_index >= len(argv):
                raise SonarCliError(f"Missing value for global argument: {argument}")

            global_args.extend((argument, argv[next_index]))
            index += 2
            continue

        other_args.append(argument)
        index += 1

    return [*global_args, *other_args]


def add_issue_listing_args(parser: argparse.ArgumentParser, *, include_page: bool) -> None:
    parser.add_argument(
        "--issue-statuses",
        default=DEFAULT_ISSUE_STATUSES,
        help="Comma-separated Sonar issue statuses to query.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help="Maximum number of issues to fetch in one page.",
    )
    if include_page:
        parser.add_argument(
            "--page",
            type=int,
            default=1,
            help="Issue search page number.",
        )
    parser.add_argument(
        "--extra-query",
        action="append",
        dest="extra_query",
        default=None,
        help="Extra api/issues/search parameter in key=value form. Repeat as needed.",
    )


def add_hotspot_listing_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--hotspot-status",
        default=DEFAULT_HOTSPOT_STATUS,
        help="Hotspot lifecycle status to query.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help="Maximum number of hotspots to fetch in one page.",
    )
    parser.add_argument(
        "--extra-query",
        action="append",
        dest="extra_query",
        default=None,
        help="Extra api/hotspots/search parameter in key=value form. Repeat as needed.",
    )


def main() -> int:
    try:
        args = parse_args()
        context = resolve_context(args)
        payload = dispatch_command(args, context)
        emit_output(payload, as_json=args.json)
    except SonarCliError as error_message:
        sys.stderr.write(f"Error: {error_message}\n")
        return 1
    else:
        return 0


def dispatch_command(args: argparse.Namespace, context: ProjectContext) -> Any:
    handlers = {
        "summary": lambda: build_summary(args, context),
        "list-issues": lambda: command_list_issues(args, context),
        "issue-changelog": lambda: fetch_issue_changelog(context=context, issue_key=args.issue),
        "comment-issue": lambda: add_issue_comment(
            context=context,
            issue_key=args.issue,
            text=args.text,
            dry_run=args.dry_run,
        ),
        "assign-issue": lambda: assign_issue(
            context=context,
            issue_key=args.issue,
            assignee=args.assignee,
            dry_run=args.dry_run,
        ),
        "set-issue-tags": lambda: set_issue_tags(
            context=context,
            issue_key=args.issue,
            tags=resolve_tag_values(args.tags, clear=args.clear, argument_name="tag"),
            dry_run=args.dry_run,
        ),
        "transition-issue": lambda: transition_issues(
            context=context,
            issue_keys=args.issues,
            transition=args.transition,
            comment=args.comment,
            dry_run=args.dry_run,
        ),
        "list-hotspots": lambda: command_list_hotspots(args, context),
        "show-hotspot": lambda: fetch_hotspot_detail(context=context, hotspot_key=args.hotspot),
        "review-hotspot": lambda: review_hotspots(
            context=context,
            hotspot_keys=args.hotspots,
            status=args.status,
            resolution=args.resolution,
            comment=args.comment,
            dry_run=args.dry_run,
        ),
        "measures": lambda: command_measures(args, context),
        "measures-history": lambda: fetch_measure_history(
            context=context,
            component=args.component or context.project_key,
            metrics=resolve_csv_values(args.metrics, argument_name="metric"),
            from_date=args.from_date,
            to_date=args.to_date,
        ),
        "project-info": lambda: fetch_project_component_info(
            context=context,
            component=args.component or context.project_key,
        ),
        "ce-component": lambda: fetch_ce_component(
            context=context,
            component=args.component or context.project_key,
        ),
        "ce-task": lambda: fetch_ce_task(context=context, task_id=args.task_id),
        "project-analyses": lambda: fetch_project_analyses(
            context=context,
            project_key=args.project or context.project_key,
            page=args.page,
            page_size=args.page_size,
        ),
        "tsconfig-warning-check": lambda: investigate_tsconfig_warning(context=context),
        "quality-gate-status": lambda: fetch_quality_gate_status(
            context=context,
            project_key=args.project or context.project_key,
        ),
        "list-quality-gates": lambda: list_quality_gates(context=context),
        "get-quality-gate": lambda: fetch_project_quality_gate(
            context=context,
            project_key=args.project or context.project_key,
        ),
        "set-quality-gate": lambda: set_quality_gate(
            context=context,
            project_key=args.project or context.project_key,
            gate_id=args.gate_id,
            gate_name=args.gate_name,
            dry_run=args.dry_run,
        ),
        "unset-quality-gate": lambda: unset_quality_gate(
            context=context,
            project_key=args.project or context.project_key,
            dry_run=args.dry_run,
        ),
        "list-quality-profiles": lambda: list_quality_profiles(
            context=context,
            project_key=args.project or context.project_key,
            language=args.language,
            quality_profile=args.quality_profile,
        ),
        "quality-profile-changelog": lambda: fetch_quality_profile_changelog(
            context=context,
            quality_profile_key=args.quality_profile,
        ),
        "set-quality-profile": lambda: set_quality_profile(
            context=context,
            project_key=args.project or context.project_key,
            quality_profile_key=args.quality_profile,
            dry_run=args.dry_run,
        ),
        "unset-quality-profile": lambda: unset_quality_profile(
            context=context,
            project_key=args.project or context.project_key,
            quality_profile_key=args.quality_profile,
            dry_run=args.dry_run,
        ),
        "settings-values": lambda: command_settings_values(args, context),
        "settings-definitions": lambda: command_settings_definitions(args, context),
        "settings-set": lambda: set_setting_value(
            context=context,
            component=args.component or context.project_key,
            key=args.key,
            value=args.value,
            values=args.values,
            dry_run=args.dry_run,
        ),
        "settings-reset": lambda: reset_setting_value(
            context=context,
            component=args.component or context.project_key,
            key=args.key,
            dry_run=args.dry_run,
        ),
        "search-project-tags": lambda: search_project_tags(
            context=context,
            query_text=args.query_text,
            page_size=args.page_size,
        ),
        "set-project-tags": lambda: set_project_tags(
            context=context,
            project_key=args.project or context.project_key,
            tags=resolve_tag_values(args.tags, clear=args.clear, argument_name="tag"),
            dry_run=args.dry_run,
        ),
        "api-call": lambda: command_api_call(args, context),
    }

    try:
        return handlers[args.command]()
    except KeyError as error:
        raise SonarCliError(f"Unsupported command: {args.command}") from error


def command_list_issues(args: argparse.Namespace, context: ProjectContext) -> dict[str, Any]:
    return fetch_issues(
        context=context,
        issue_statuses=args.issue_statuses,
        page=args.page,
        page_size=args.page_size,
        extra_query=parse_name_value_pairs(args.extra_query, argument_name="extra-query"),
    )


def command_list_hotspots(args: argparse.Namespace, context: ProjectContext) -> dict[str, Any]:
    return fetch_hotspots(
        context=context,
        hotspot_status=args.hotspot_status,
        page=args.page,
        page_size=args.page_size,
        include_details=args.include_details,
        extra_query=parse_name_value_pairs(args.extra_query, argument_name="extra-query"),
    )


def command_measures(args: argparse.Namespace, context: ProjectContext) -> dict[str, Any]:
    metrics = resolve_csv_values(args.metrics, argument_name="metric")
    default_metrics = resolve_csv_values([DEFAULT_SUMMARY_METRICS], argument_name="metric")
    return fetch_measures(
        context=context,
        component=args.component or context.project_key,
        metrics=metrics or default_metrics,
    )


def command_settings_values(args: argparse.Namespace, context: ProjectContext) -> dict[str, Any]:
    return fetch_settings_values(
        context=context,
        component=args.component or context.project_key,
        keys=resolve_csv_values(args.keys, argument_name="key"),
    )


def command_settings_definitions(args: argparse.Namespace, context: ProjectContext) -> dict[str, Any]:
    return fetch_settings_definitions(
        context=context,
        component=args.component or context.project_key,
        keys=resolve_csv_values(args.keys, argument_name="key"),
    )


def command_api_call(args: argparse.Namespace, context: ProjectContext) -> dict[str, Any]:
    return direct_api_call(
        context=context,
        endpoint=args.endpoint,
        method=args.method,
        query=parse_name_value_pairs(args.query_params, argument_name="query-param"),
        form=parse_name_value_pairs(args.form_params, argument_name="form-param"),
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
