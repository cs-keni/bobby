#!/usr/bin/env python3
"""
Bobby gbrain Recall@5 evaluation.

Runs each query in golden_queries.yaml against gbrain and checks whether
expected_slug appears in the top-5 results. Writes results to eval_results.yaml.

Usage:
    python evals/run_eval.py
    python evals/run_eval.py --limit 5 --category bobby
"""
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add repo root to path so we can import config
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import yaml
except ImportError:
    print("pip install pyyaml", file=sys.stderr)
    sys.exit(1)

GBRAIN_BIN = str(Path.home() / ".bun" / "bin" / "gbrain")
QUERIES_FILE = Path(__file__).parent / "golden_queries.yaml"
RESULTS_FILE = Path(__file__).parent / "eval_results.yaml"
RECALL_K = 5

# Build subprocess env with VOYAGE_API_KEY so gbrain uses hybrid vector+keyword search
_CONFIG_FILE = Path(__file__).parent.parent / "config.yaml"
_VOYAGE_KEY = ""
if _CONFIG_FILE.exists():
    _cfg = yaml.safe_load(_CONFIG_FILE.read_text()) or {}
    _VOYAGE_KEY = _cfg.get("gbrain", {}).get("voyage_api_key", "")
_SUBPROCESS_ENV = {**__import__("os").environ}
if _VOYAGE_KEY:
    _SUBPROCESS_ENV["VOYAGE_API_KEY"] = _VOYAGE_KEY


def run_query(query: str) -> list[str]:
    """Return top-K slugs from gbrain query. Returns [] on any error."""
    try:
        result = subprocess.run(
            [GBRAIN_BIN, "query", query, "--limit", str(RECALL_K), "--source-id", "__all__"],
            capture_output=True,
            text=True,
            timeout=20,
            env=_SUBPROCESS_ENV,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []

        slugs = []
        for line in result.stdout.strip().splitlines():
            # Format: "[score] slug -- chunk_text..."
            if " -- " in line and line.startswith("["):
                header = line.split(" -- ")[0]
                slug = header.split("] ", 1)[-1].strip() if "] " in header else ""
                if slug:
                    slugs.append(slug)
        return slugs
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Bobby gbrain Recall@5 eval")
    parser.add_argument("--category", help="Only run queries in this category")
    args = parser.parse_args()

    data = yaml.safe_load(QUERIES_FILE.read_text())
    queries = data.get("queries", [])

    if args.category:
        queries = [q for q in queries if q.get("category") == args.category]

    print(f"\nBobby gbrain Recall@{RECALL_K} Evaluation")
    print(f"Queries: {len(queries)}  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    print(f"{'#':<4} {'Category':<14} {'Pass':<5} {'Query'}")
    print("-" * 70)

    results = []
    passed = 0

    for i, q in enumerate(queries, 1):
        query = q["query"]
        expected = q["expected_slug"]
        category = q.get("category", "?")
        confidence = q.get("confidence", "medium")

        returned_slugs = run_query(query)
        hit = expected in returned_slugs
        if hit:
            passed += 1

        status = "✓" if hit else "✗"
        print(f"{i:<4} {category:<14} {status:<5} {query[:50]}")
        if not hit:
            print(f"     expected: {expected}")
            if returned_slugs:
                print(f"     got:      {returned_slugs[0]}")
            else:
                print(f"     got:      (no results)")

        results.append({
            "query": query,
            "expected_slug": expected,
            "category": category,
            "confidence": confidence,
            "returned_slugs": returned_slugs,
            "hit": hit,
        })

    recall = passed / len(queries) if queries else 0
    print("-" * 70)
    print(f"\nRecall@{RECALL_K}: {passed}/{len(queries)} = {recall:.0%}")

    by_category: dict[str, list[bool]] = {}
    for r in results:
        by_category.setdefault(r["category"], []).append(r["hit"])
    print("\nBy category:")
    for cat, hits in sorted(by_category.items()):
        n = len(hits)
        p = sum(hits)
        print(f"  {cat:<14} {p}/{n}  ({p/n:.0%})")

    output = {
        "run_date": datetime.now().isoformat(),
        "recall_k": RECALL_K,
        "total": len(queries),
        "passed": passed,
        "recall": round(recall, 4),
        "results": results,
    }
    RESULTS_FILE.write_text(yaml.dump(output, allow_unicode=True, default_flow_style=False))
    print(f"\nResults saved → evals/eval_results.yaml")


if __name__ == "__main__":
    main()
