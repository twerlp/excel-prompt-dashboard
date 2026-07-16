#!/usr/bin/env python3
"""
Prompt evaluation dashboard — CLI for querying the knowledge base.

Usage:
  python eval_dashboard.py --summary
  python eval_dashboard.py --story US-001
  python eval_dashboard.py --best-prompt frs --domain Banking
  python eval_dashboard.py --compare frs_few_shot frs_cot
  python eval_dashboard.py --human-review US-001

Configuration is read from config.yaml.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from evaluation_kb import KnowledgeBase


def load_config() -> Dict[str, Any]:
    config_path = Path(__file__).resolve().parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def cmd_summary(kb: KnowledgeBase) -> None:
    """Print KB summary statistics."""
    stories = kb.list_stories()
    print(f"Stories: {len(stories)}")
    domains = {}
    for s in stories:
        domains[s.get("domain", "Unknown")] = domains.get(s.get("domain", "Unknown"), 0) + 1
    for d, c in sorted(domains.items()):
        print(f"  {d}: {c}")

    # Count experiments
    exp_count = kb.conn.execute(
        "SELECT category, COUNT(*) as cnt FROM experiments GROUP BY category"
    ).fetchall()
    print(f"\nExperiments:")
    for row in exp_count:
        print(f"  {row['category']}: {row['cnt']}")

    # Avg scores
    avg = kb.conn.execute(
        """SELECT prompt_name, category, tier,
                  AVG(completeness) as avg_comp,
                  AVG(tc_completeness) as avg_tc
           FROM experiments
           WHERE completeness IS NOT NULL OR tc_completeness IS NOT NULL
           GROUP BY prompt_name, category, tier
           ORDER BY category, tier, prompt_name"""
    ).fetchall()
    if avg:
        print(f"\nAvg scores by prompt/tier:")
        for row in avg:
            score = row["avg_comp"] or row["avg_tc"]
            print(f"  {row['category']} | {row['prompt_name']} | tier-{row['tier']} | {score:.3f}" if score else "")


def cmd_story(kb: KnowledgeBase, story_id: str) -> None:
    """Show details for a specific story and its experiments."""
    story = kb.get_story(story_id)
    if not story:
        print(f"Story {story_id} not found")
        return

    print(f"Story: {story['story_id']} - {story['title']}")
    print(f"  Domain: {story['domain']}  Priority: {story['priority']}")
    print(f"  Status: {story['status']}  Points: {story['story_points']}")
    print(f"  Dependencies: {story['dependencies']}")
    print(f"\nUser Story:\n  {story['user_story']}\n")
    print(f"Acceptance Criteria:\n{story['acceptance_criteria']}\n")

    # Ground truth
    frs = kb.get_ground_truth_frs(story_id)
    tcs = kb.get_ground_truth_tcs(story_id)
    print(f"Ground Truth: {len(frs)} FRs, {len(tcs)} TCs")

    # Experiments
    exps = kb.get_experiments_by_story(story_id)
    if exps:
        print(f"\nExperiments ({len(exps)}):")
        for exp in exps:
            comp = exp.get("completeness")
            tc_comp = exp.get("tc_completeness")
            try:
                score = float(comp) if comp else float(tc_comp) if tc_comp else 0.0
            except (ValueError, TypeError):
                score = 0.0
            print(f"  {exp['prompt_name']} [{exp['category']}] tier-{int(exp['tier'])} "
                  f"({exp['backend']}/{exp['model']}) score={score:.3f}")
    else:
        print("\nNo experiments yet.")


def cmd_best_prompt(kb: KnowledgeBase, category: str, domain: Optional[str] = None) -> None:
    """Show best-performing prompts."""
    metric = "completeness" if category == "frs" else "tc_completeness"
    results = kb.query_best_prompt(
        category=category,
        domain=domain,
        metric=metric,
    )
    if not results:
        print(f"No experiments found for {category}" + (f" in {domain}" if domain else ""))
        return

    print(f"Best prompts for {category}" + (f" in {domain}" if domain else "") + ":")
    for name, score in results:
        print(f"  {name}: {score:.3f}")


def cmd_compare(kb: KnowledgeBase, prompt_a: str, prompt_b: str,
                category: Optional[str] = None) -> None:
    """Compare two prompts across all stories."""
    queries = {
        "frs": (
            "SELECT prompt_name, AVG(completeness) as avg_score, COUNT(*) as n "
            "FROM experiments WHERE category='frs' AND completeness IS NOT NULL "
            "GROUP BY prompt_name"
        ),
        "test_case": (
            "SELECT prompt_name, AVG(tc_completeness) as avg_score, COUNT(*) as n "
            "FROM experiments WHERE category='test_case' AND tc_completeness IS NOT NULL "
            "GROUP BY prompt_name"
        ),
    }

    for cat, query in queries.items():
        if category and cat != category:
            continue
        rows = kb.conn.execute(query).fetchall()
        scores = {r["prompt_name"]: r["avg_score"] for r in rows if r["prompt_name"] in (prompt_a, prompt_b)}
        if prompt_a in scores and prompt_b in scores:
            diff = scores[prompt_a] - scores[prompt_b]
            winner = prompt_a if diff > 0 else prompt_b
            print(f"{cat}: {prompt_a}={scores[prompt_a]:.3f}  {prompt_b}={scores[prompt_b]:.3f}  "
                  f"delta={diff:+.3f}  winner={winner}")
        else:
            print(f"{cat}: insufficient data for comparison")


def cmd_human_review(kb: KnowledgeBase, story_id: Optional[str] = None) -> None:
    """List experiments pending human review, or review a specific one."""
    if story_id:
        exps = kb.get_experiments_by_story(story_id)
    else:
        rows = kb.conn.execute(
            """SELECT e.id, e.story_id, e.category, e.prompt_name, e.tier,
                      e.completeness, e.tc_completeness, e.generated_content
               FROM experiments e
               LEFT JOIN human_reviews hr ON e.id = hr.experiment_id
               WHERE hr.experiment_id IS NULL
                 AND (e.completeness IS NOT NULL OR e.tc_completeness IS NOT NULL)
               LIMIT 10"""
        ).fetchall()
        for row in rows:
            score = row["completeness"] or row["tc_completeness"]
            print(f"  {row['story_id']} | {row['prompt_name']} [{row['category']}] "
                  f"tier-{row['tier']} score={score:.3f}")

        if rows:
            print(f"\n{len(rows)} experiments pending review.")
            print("Use --story <id> to review a specific story's experiments.")
        else:
            print("No experiments pending review.")
        return

    # Interactive review
    exps = kb.get_experiments_by_story(story_id) if story_id else []

    for exp in exps:
        score = exp.get("completeness") or exp.get("tc_completeness") or 0
        content = exp.get("generated_content", "")
        print(f"\n{'='*60}")
        print(f"Experiment: {exp['id'][:8]}...  {exp['prompt_name']} [{exp['category']}] tier-{exp['tier']}")
        print(f"Auto-score: {score:.3f}")
        print(f"\nGenerated content (first 500 chars):")
        print(content[:500])

        try:
            score_str = input(f"\nEnter score (1-5, or Enter to skip): ").strip()
            if score_str:
                score_val = int(score_str)
                if 1 <= score_val <= 5:
                    notes = input("Notes (optional): ").strip()
                    kb.upsert_human_review(
                        experiment_id=exp["id"],
                        reviewer="cli",
                        score_frs=score_val if exp["category"] == "frs" else 0,
                        score_tc=score_val if exp["category"] == "test_case" else 0,
                        notes=notes,
                    )
                    print("Review saved.")
        except (ValueError, EOFError):
            pass

    kb.close()


def main():
    parser = argparse.ArgumentParser(
        description="Prompt evaluation dashboard"
    )
    parser.add_argument("--summary", action="store_true", help="Show KB summary")
    parser.add_argument("--story", type=str, help="Show story details and experiments")
    parser.add_argument("--best-prompt", type=str, metavar="CATEGORY",
                        help="Show best prompt for frs or test_case")
    parser.add_argument("--domain", type=str, default=None,
                        help="Filter by domain (with --best-prompt)")
    parser.add_argument("--compare", nargs=2, metavar=("PROMPT_A", "PROMPT_B"),
                        help="Compare two prompts")
    parser.add_argument("--human-review", nargs="?", const="", metavar="STORY_ID",
                        help="List or review experiments pending human review")
    parser.add_argument("--db", type=str, default="kb.sqlite")

    args = parser.parse_args()
    config = load_config()
    db_path = config.get("database", {}).get("sqlite_path", args.db)

    kb = KnowledgeBase(db_path)
    kb.initialize()

    try:
        if args.summary:
            cmd_summary(kb)
        elif args.story:
            cmd_story(kb, args.story)
        elif args.best_prompt:
            cmd_best_prompt(kb, args.best_prompt, args.domain)
        elif args.compare:
            cmd_compare(kb, args.compare[0], args.compare[1])
        elif args.human_review is not None:
            story = args.human_review if args.human_review else None
            cmd_human_review(kb, story)
        else:
            cmd_summary(kb)
    finally:
        kb.close()


if __name__ == "__main__":
    main()
