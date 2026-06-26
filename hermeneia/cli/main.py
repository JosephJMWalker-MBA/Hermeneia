#!/usr/bin/env python3
"""
herm — Hermeneia inspection CLI

Usage:
    herm stats  <bundle.herm | hermeneia.db>
    herm search <query>   [--db <path>] [--limit N]
    herm neighbors <OBS-N>  [--db <path>]
    herm provenance <OBS-N>  [--db <path>]
    herm concept <term>  [--db <path>] [--limit N]
    herm trace <OBS-N>  [--db <path>]
"""
import argparse
import sys

from hermeneia.cli.inspector import (
    cmd_concept,
    cmd_neighbors,
    cmd_provenance,
    cmd_search,
    cmd_stats,
    cmd_trace,
)
from hermeneia.cli.interpreter import cmd_interpret_create, cmd_interpret_view
from hermeneia.cli.comparer import cmd_compare
from hermeneia.cli.blueprinter import cmd_blueprint_view, cmd_blueprint_create, cmd_blueprint_list
from hermeneia.cli.health import cmd_health
from hermeneia.cli.architect_cmd import cmd_architect
from hermeneia.cli.artist_cmd import cmd_artist
from hermeneia.cli.profile_cmd import cmd_profile_list, cmd_profile_view, cmd_profile_create
from hermeneia.cli.critic_cmd import cmd_critic
from hermeneia.cli.bootstrap_cmd import cmd_bootstrap
from hermeneia.cli.extract_cmd import cmd_extract
from hermeneia.cli.explorer_cmd import cmd_explorer_discover


def main() -> None:
    parser = argparse.ArgumentParser(prog="herm", description="Hermeneia inspection CLI")
    parser.add_argument("--db", default=None, help="Path to hermeneia.db")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="Epistemic pipeline confidence dashboard")

    p_stats = sub.add_parser("stats", help="Corpus summary")
    p_stats.add_argument("bundle", help=".herm bundle dir or hermeneia.db path")

    p_search = sub.add_parser("search", help="Full-text search")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=10)

    p_neighbors = sub.add_parser("neighbors", help="Adjacency chain")
    p_neighbors.add_argument("obs", help="e.g. OBS-312")

    p_prov = sub.add_parser("provenance", help="Full provenance record")
    p_prov.add_argument("obs", help="e.g. OBS-312")

    p_concept = sub.add_parser("concept", help="Field v0.1: observations containing term")
    p_concept.add_argument("term")
    p_concept.add_argument("--limit", type=int, default=20)

    p_trace = sub.add_parser("trace", help="Full pipeline trace for an observation")
    p_trace.add_argument("obs", help="e.g. OBS-312")

    p_bp = sub.add_parser("blueprint", help="View or create Narrative Blueprints")
    p_bp.add_argument(
        "bp_args", nargs="*", metavar="ARG",
        help="OBS-N (view), 'create' (new blueprint), 'list' (all blueprints)",
    )

    p_architect = sub.add_parser("architect", help="Appoint Architect for the blueprint citing OBS-N")
    p_architect.add_argument("obs", help="e.g. OBS-312")

    p_artist = sub.add_parser("artist", help="Render prose from an ArchitectPlan")
    p_artist.add_argument("obs", help="e.g. OBS-312")
    p_artist.add_argument("--provider", default="null",
                          help="null | anthropic | openai | gemini | grok  (default: null)")
    p_artist.add_argument("--model", default=None,
                          help="Override default model (e.g. gpt-4o, claude-opus-4-8, grok-3)")
    p_artist.add_argument("--profile", default=None, dest="profile",
                          help="Expression profile slug (e.g. literary-en, historical-en)")
    p_artist.add_argument("--theme", default=None, dest="theme_legacy",
                          help=argparse.SUPPRESS)  # backwards-compat alias for --profile
    p_artist.add_argument("--show-prompt", action="store_true", help="Print the generated prompt")
    p_artist.add_argument("--all-profiles", action="store_true",
                          help="Render with every available Expression Profile")
    p_artist.add_argument("--recursive", action="store_true",
                          help="Recursive protocol: Reconstruction → Draft → Self-Critique → Revision")

    p_profile = sub.add_parser("profile", help="Browse and create Expression Profiles")
    p_profile.add_argument(
        "profile_args", nargs="*", metavar="ARG",
        help="'list', 'create', or SLUG to view",
    )

    p_critic = sub.add_parser("critic", help="Run the Critic on a Rendered Narrative")
    p_critic.add_argument("obs", help="e.g. OBS-312")
    p_critic.add_argument("--narrative-id", default=None, help="Target a specific Rendered Narrative ID")

    p_compare = sub.add_parser("compare", help="Structural comparison of all interpretations")
    p_compare.add_argument("obs", help="e.g. OBS-312")

    sub.add_parser("bootstrap", help="Seed minimum viable pipeline content for first provider render")

    p_explorer = sub.add_parser("explorer", help="Explorer discovery: bucket observations and generate speculative interpretations")
    explorer_sub = p_explorer.add_subparsers(dest="explorer_command", required=True)
    p_discover = explorer_sub.add_parser("discover", help="Run bucketing pass and generate speculative interpretations")
    p_discover.add_argument("obs_refs", nargs="*", metavar="OBS-N",
                            help="Specific observations (e.g. OBS-1 OBS-7); omit to use --limit most recent")
    p_discover.add_argument("--limit", type=int, default=30,
                            help="Max observations to consider when no OBS-N given (default: 30)")
    p_discover.add_argument("--provider", default="null",
                            help="LLM provider: null | anthropic | openai | gemini | grok (default: null)")
    p_discover.add_argument("--model", default=None, help="Override model")
    p_discover.add_argument("--perspective", default="Literary",
                            help="Investigative perspective label (default: Literary)")

    p_extract = sub.add_parser("extract", help="Extract a Blueprint Intent Hypothesis from an existing document")
    p_extract.add_argument("input", nargs="?", default=None, help="Path to input file (or omit with --stdin)")
    p_extract.add_argument("--stdin", action="store_true", help="Read document text from stdin")
    p_extract.add_argument("--provider", default="null",
                           help="LLM provider: null | anthropic | openai | gemini | grok  (default: null)")
    p_extract.add_argument("--model", default=None, help="Override model (e.g. claude-sonnet-4-6)")
    p_extract.add_argument("--api-key", default=None, dest="api_key", help="Provider API key")
    p_extract.add_argument("--no-architect", action="store_true",
                           help="Store Blueprint only, skip Architect compilation")

    p_interp = sub.add_parser("interpret", help="View or create interpretations")
    p_interp.add_argument(
        "obs_args", nargs="+", metavar="OBS",
        help="OBS-N (view) or 'create OBS-N' (interactive creation)",
    )

    args = parser.parse_args()
    db = args.db or "build/hermeneia.db"

    if args.command == "health":
        cmd_health(bundle_or_db=db)
    elif args.command == "stats":
        cmd_stats(args.bundle)
    elif args.command == "search":
        cmd_search(args.query, bundle_or_db=db, limit=args.limit)
    elif args.command == "neighbors":
        cmd_neighbors(args.obs, bundle_or_db=db)
    elif args.command == "provenance":
        cmd_provenance(args.obs, bundle_or_db=db)
    elif args.command == "concept":
        cmd_concept(args.term, bundle_or_db=db, limit=args.limit)
    elif args.command == "blueprint":
        bp_args = args.bp_args
        if not bp_args or bp_args[0].lower() == "list":
            cmd_blueprint_list(bundle_or_db=db)
        elif bp_args[0].lower() == "create":
            cmd_blueprint_create(bundle_or_db=db)
        else:
            cmd_blueprint_view(bp_args[0], bundle_or_db=db)
    elif args.command == "architect":
        cmd_architect(args.obs, bundle_or_db=db)
    elif args.command == "artist":
        profile_slug = args.profile or getattr(args, "theme_legacy", None)
        cmd_artist(args.obs, provider_name=args.provider, theme_slug=profile_slug,
                   show_prompt=args.show_prompt, bundle_or_db=db,
                   model=getattr(args, "model", None),
                   all_profiles=getattr(args, "all_profiles", False),
                   recursive=getattr(args, "recursive", False))
    elif args.command == "profile":
        profile_args = args.profile_args
        if not profile_args or profile_args[0].lower() == "list":
            cmd_profile_list(bundle_or_db=db)
        elif profile_args[0].lower() == "create":
            cmd_profile_create(bundle_or_db=db)
        else:
            cmd_profile_view(profile_args[0], bundle_or_db=db)
    elif args.command == "critic":
        cmd_critic(args.obs, narrative_id=args.narrative_id, bundle_or_db=db)
    elif args.command == "compare":
        cmd_compare(args.obs, bundle_or_db=db)
    elif args.command == "trace":
        cmd_trace(args.obs, bundle_or_db=db)
    elif args.command == "bootstrap":
        cmd_bootstrap(bundle_or_db=db)
    elif args.command == "explorer":
        if args.explorer_command == "discover":
            cmd_explorer_discover(
                obs_refs=args.obs_refs,
                limit=args.limit,
                provider_name=args.provider,
                model=args.model,
                perspective=args.perspective,
                bundle_or_db=db,
            )
    elif args.command == "extract":
        cmd_extract(
            args.input,
            from_stdin=args.stdin,
            provider_name=args.provider,
            model=args.model,
            api_key=args.api_key,
            bundle_or_db=db,
            run_architect=not args.no_architect,
        )
    elif args.command == "interpret":
        obs_args = args.obs_args
        if obs_args[0].lower() == "create":
            if len(obs_args) < 2:
                print("Usage: herm interpret create OBS-N")
                sys.exit(1)
            cmd_interpret_create(obs_args[1], bundle_or_db=db)
        else:
            cmd_interpret_view(obs_args[0], bundle_or_db=db)


if __name__ == "__main__":
    main()
