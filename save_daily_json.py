#!/usr/bin/env python3
# save_daily_json.py

import json
import os
import glob
from datetime import datetime, timezone, timedelta
from dateutil.parser import parse

from rag_arXiv_daily_feed import daily_entries
from rag_toXiv_variables import DATA_DIR, DEFAULT_CATEGORY, CAT_MAX_FILES, SKIP_EMPTY


def save_feed_json(category: str, aliases: dict = None, dry_run: bool = False):
    """Fetch via toXiv_daily_feed and save as JSON."""
    os.makedirs(DATA_DIR, exist_ok=True)

    feed = daily_entries(category, aliases or {})

    data = {
        "category": category,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "feed_updated": feed.updated,
        "stats": {
            "new_submissions": feed.num_newsubmissions,
            "cross_lists": feed.num_crosslists,
            "replacements": feed.num_replacements,
            "total": feed.total,
        },
        "papers": [],
    }

    for entry in feed.newsubmissions + feed.crosslists:
        data["papers"].append(
            {
                "id": entry["id"],
                "title": entry["title"],
                "authors": entry["authors"],
                "abstract": entry["abstract"],
                "primary_subject": entry["primary_subject"],
                "label": entry["label"],
                "abs_url": entry["abs_url"],
                "pdf_url": entry["pdf_url"],
                "html_url": entry["html_url"],
            }
        )

    # Use feed update date instead of fetch date
    feed_date = parse(feed.updated)
    date_str = feed_date.strftime("%Y-%m-%d")
    filename = f"{date_str}_{category.replace('.', '_')}.json"
    filepath = os.path.join(DATA_DIR, filename)

    if dry_run:
        print(f"Would save {len(data['papers'])} papers to {filepath}")
    else:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(data['papers'])} papers to {filepath}")
    return filepath


def is_empty_file(filepath: str) -> bool:
    """Check if a JSON file has no papers."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return len(data.get("papers", [])) == 0
    except (json.JSONDecodeError, IOError):
        return False


def cleanup_old_files(days: int, category: str = None, dry_run: bool = False):
    """Delete JSON files older than n days.

    Args:
        days: Delete files older than this many days
        category: If specified, only delete files for this category
        dry_run: If True, only print what would be deleted
    """
    if not os.path.exists(DATA_DIR):
        print(f"Data directory {DATA_DIR} does not exist")
        return 0

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d")

    if category:
        pattern = os.path.join(DATA_DIR, f"*_{category.replace('.', '_')}.json")
    else:
        pattern = os.path.join(DATA_DIR, "*.json")

    files = glob.glob(pattern)
    deleted_count = 0

    for filepath in files:
        filename = os.path.basename(filepath)
        # Extract date from filename (YYYY-MM-DD_category.json)
        try:
            file_date_str = filename[:10]
            file_date = datetime.strptime(file_date_str, "%Y-%m-%d")
            file_date = file_date.replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"Skipping file with invalid date format: {filename}")
            continue

        if file_date.date() < cutoff_date.date():
            if dry_run:
                print(f"Would delete: {filename}")
            else:
                os.remove(filepath)
                print(f"Deleted: {filename}")
            deleted_count += 1

    action = "Would delete" if dry_run else "Deleted"
    print(
        f"\n{action} {deleted_count} file(s) older than {days} days (before {cutoff_str})"
    )
    return deleted_count


def cleanup_by_cat_max_files(
    max_files: int, category: str = None, skip_empty: bool = SKIP_EMPTY, dry_run: bool = False
):
    """Keep only the most recent n files per category, delete the rest.

    Args:
        max_files: Number of (non-empty if skip_empty) files to keep per category
        category: If specified, only cleanup this category
        skip_empty: If True, don't count empty files toward the limit (but don't delete them either)
        dry_run: If True, only print what would be deleted
    """
    if not os.path.exists(DATA_DIR):
        print(f"Data directory {DATA_DIR} does not exist")
        return 0

    # Get all categories or just the specified one
    if category:
        categories = [category]
    else:
        # Find all unique categories from filenames
        files = glob.glob(os.path.join(DATA_DIR, "*.json"))
        categories = set()
        for f in files:
            basename = os.path.basename(f)
            parts = basename.split("_", 1)
            if len(parts) == 2:
                cat = parts[1].replace("_", ".").replace(".json", "")
                categories.add(cat)
        categories = sorted(categories)

    total_deleted = 0

    for cat in categories:
        pattern = os.path.join(DATA_DIR, f"*_{cat.replace('.', '_')}.json")
        file_list = sorted(glob.glob(pattern), reverse=True)  # newest first

        kept_count = 0
        files_to_delete = []

        for filepath in file_list:
            filename = os.path.basename(filepath)
            empty = is_empty_file(filepath)

            if skip_empty and empty:
                # Skip empty files entirely - don't count, don't delete
                continue

            if kept_count < max_files:
                kept_count += 1
            else:
                files_to_delete.append((filepath, filename))

        if files_to_delete:
            print(f"\n--- {cat} ---")
            for filepath, filename in files_to_delete:
                if dry_run:
                    print(f"Would delete: {filename}")
                else:
                    os.remove(filepath)
                    print(f"Deleted: {filename}")
                total_deleted += 1

    action = "Would delete" if dry_run else "Deleted"
    print(f"\n{action} {total_deleted} file(s) total (keeping {max_files} per category)")
    return total_deleted


def list_files(category: str = None):
    """List all JSON files in data directory."""
    if not os.path.exists(DATA_DIR):
        print(f"Data directory {DATA_DIR} does not exist")
        return

    if category:
        pattern = os.path.join(DATA_DIR, f"*_{category.replace('.', '_')}.json")
    else:
        pattern = os.path.join(DATA_DIR, "*.json")

    files = sorted(glob.glob(pattern))

    if not files:
        print("No data files found")
        return

    print(f"Data files in {DATA_DIR}:")
    for filepath in files:
        filename = os.path.basename(filepath)
        size = os.path.getsize(filepath)
        empty_marker = " (empty)" if is_empty_file(filepath) else ""
        print(f"  {filename} ({size:,} bytes){empty_marker}")

    print(f"\nTotal: {len(files)} file(s)")


if __name__ == "__main__":
    import sys

    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: python save_daily_json.py [categories...] [options]")
        print("")
        print("Commands:")
        print("  <category> [category2...]  Fetch and save today's feed for categories")
        print("  --cleanup <days>           Delete files older than n days")
        print("  --cleanup-by-cat-max-files <n>  Keep only n files per category")
        print("  --list                     List all data files")
        print("")
        print("Options:")
        print("  --category <cat>        Specify category for cleanup/list")
        print("  --skip-empty=1          Skip empty files when counting (default)")
        print("  --skip-empty=0          Count empty files toward limit")
        print("  --dry-run               Show what would be saved/deleted without doing it")
        print("")
        print("Examples:")
        print("  python save_daily_json.py cs.LG")
        print("  python save_daily_json.py cs.LG --dry-run")
        print("  python save_daily_json.py cs.AI cs.LG math.CT")
        print("  python save_daily_json.py --cleanup 30")
        print("  python save_daily_json.py --cleanup 30 --category cs.LG")
        print("  python save_daily_json.py --cleanup 30 --dry-run")
        print("  python save_daily_json.py --cleanup-by-cat-max-files 7")
        print("  python save_daily_json.py --cleanup-by-cat-max-files 7 --skip-empty=0")
        print("  python save_daily_json.py --cleanup-by-cat-max-files 7 --category cs.LG --dry-run")
        print("  python save_daily_json.py --list")
        print("  python save_daily_json.py --list --category cs.LG")
        sys.exit(0)

    dry_run = "--dry-run" in sys.argv

    # Parse --skip-empty option
    skip_empty = SKIP_EMPTY  # default from variables
    for arg in sys.argv:
        if arg == "--skip-empty=1":
            skip_empty = True
        elif arg == "--skip-empty=0":
            skip_empty = False

    # Get category if specified with --category flag
    category = None
    if "--category" in sys.argv:
        idx = sys.argv.index("--category")
        if idx + 1 < len(sys.argv):
            category = sys.argv[idx + 1]

    # List files
    if "--list" in sys.argv:
        list_files(category=category)
        sys.exit(0)

    # Cleanup by cat-max-files
    if "--cleanup-by-cat-max-files" in sys.argv:
        idx = sys.argv.index("--cleanup-by-cat-max-files")
        if idx + 1 < len(sys.argv):
            try:
                max_files = int(sys.argv[idx + 1])
                cleanup_by_cat_max_files(
                    max_files, category=category, skip_empty=skip_empty, dry_run=dry_run
                )
            except ValueError:
                print("Error: --cleanup-by-cat-max-files requires a number")
                sys.exit(1)
        else:
            print("Error: --cleanup-by-cat-max-files requires a number")
            sys.exit(1)
        sys.exit(0)

    # Cleanup old files by days
    if "--cleanup" in sys.argv:
        idx = sys.argv.index("--cleanup")
        if idx + 1 < len(sys.argv):
            try:
                days = int(sys.argv[idx + 1])
                cleanup_old_files(days, category=category, dry_run=dry_run)
            except ValueError:
                print("Error: --cleanup requires a number of days")
                sys.exit(1)
        else:
            print("Error: --cleanup requires a number of days")
            sys.exit(1)
        sys.exit(0)

    # Default: fetch and save
    # Filter out option values
    clean_args = []
    skip_next = False
    for i, arg in enumerate(sys.argv[1:]):
        if skip_next:
            skip_next = False
            continue
        if arg.startswith("--"):
            if arg in ["--category", "--cleanup", "--cleanup-by-cat-max-files"]:
                skip_next = True
            continue
        clean_args.append(arg)

    categories = clean_args if clean_args else [DEFAULT_CATEGORY]

    aliases = {}
    for cat in categories:
        print(f"\n--- Fetching {cat}  [{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}] ---")
        save_feed_json(cat, aliases, dry_run=dry_run)
