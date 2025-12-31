#!/usr/bin/env python3
# rag_toXiv_reply_bot.py

import os
import json
import glob
import time
import re
from datetime import datetime, timezone
from html import unescape

from dotenv import load_dotenv

load_dotenv()

from mastodon import Mastodon
from openai import OpenAI

from rag_toXiv_variables import (
    DATA_DIR,
    LOG_DIR,
    MASTODON_INSTANCE,
    USERNAME,
    DEFAULT_CATEGORY,
    CAT_MAX_FILES,
    SKIP_EMPTY,
    LLM_MODEL,
    POLL_INTERVAL,
    PROMPT_TEMPLATE,
    CONTEXT_MODE,
    MAX_TOOT_LENGTH,
    HELP_MESSAGE_TEMPLATE,
)

# === Config ===
MASTODON_ACCESS_TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# OpenRouter
openrouter = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# Files
processed_file = os.path.join(LOG_DIR, "processed_notifications.json")
log_file = os.path.join(LOG_DIR, "bot_interactions.log")


def ensure_log_dir():
    """Ensure log directory exists."""
    os.makedirs(LOG_DIR, exist_ok=True)


def log_interaction(account: str, question: str, category: str, reply_len: int):
    """Log bot interactions for debugging."""
    ensure_log_dir()
    with open(log_file, "a", encoding="utf-8") as f:
        timestamp = datetime.now(timezone.utc).isoformat()
        f.write(f"{timestamp}|{account}|{category}|{len(question)}|{reply_len}\n")


def load_processed() -> set:
    """Load set of processed notification IDs."""
    if os.path.exists(processed_file):
        with open(processed_file, "r") as f:
            return set(json.load(f))
    return set()


def save_processed(processed: set):
    """Save processed notification IDs."""
    ensure_log_dir()
    with open(processed_file, "w") as f:
        json.dump(list(processed), f)


def load_feeds(category: str, files: int = CAT_MAX_FILES, skip_empty: bool = SKIP_EMPTY) -> list:
    """Load recent JSON feeds.
    
    Args:
        category: arXiv category (e.g., cs.LG)
        files: Maximum number of (non-empty) files to load
        skip_empty: If True, don't count empty files toward the limit
    """
    pattern = os.path.join(DATA_DIR, f"*_{category.replace('.', '_')}.json")
    file_list = sorted(glob.glob(pattern), reverse=True)

    all_papers = []
    loaded_count = 0
    
    for fpath in file_list:
        if loaded_count >= files:
            break
            
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            papers = data.get("papers", [])
            
            if not papers and skip_empty:
                continue  # Skip empty files without counting
                
            all_papers.extend(papers)
            loaded_count += 1
            
    return all_papers


def get_available_categories() -> list:
    """Get list of categories with available data."""
    files = glob.glob(os.path.join(DATA_DIR, "*.json"))
    categories = set()
    for f in files:
        basename = os.path.basename(f)
        parts = basename.split("_", 1)
        if len(parts) == 2:
            cat = parts[1].replace("_", ".").replace(".json", "")
            categories.add(cat)
    return sorted(categories)


def first_sentence(text: str) -> str:
    """Extract first sentence from text."""
    for end in [". ", ".\n", ".\t"]:
        if end in text:
            return text.split(end)[0] + "."
    return text[:200] + "..."


def build_context(papers: list, mode: str = "first_sentence") -> str:
    """Build context string for LLM.

    Args:
        papers: List of paper dictionaries
        mode: One of "title", "first_sentence", or "full_abstract"
    """
    lines = []
    for p in papers:
        if mode == "title":
            lines.append(f"[{p['id']}] {p['title']}")
        elif mode == "first_sentence":
            lines.append(
                f"[{p['id']}] {p['title']}\n"
                f"Abstract: {first_sentence(p['abstract'])}"
            )
        elif mode == "full_abstract":
            lines.append(f"[{p['id']}] {p['title']}\n" f"Abstract: {p['abstract']}")
        else:
            raise ValueError(f"Unknown mode: {mode}")

    separator = "\n" if mode == "title" else "\n\n"
    return separator.join(lines)


def get_help_message() -> str:
    """Return help message."""
    categories = get_available_categories()
    cat_list = ", ".join(categories) if categories else "none fetched yet"

    return HELP_MESSAGE_TEMPLATE.format(cat_list=cat_list)


def generate_reply(
    question: str, category: str, papers: list, mode: str = "first_sentence"
) -> str:
    """Generate LLM reply based on papers."""
    context = build_context(papers, mode=mode)

    prompt = PROMPT_TEMPLATE.format(
        category=category,
        context=context,
        question=question,
    )

    response = openrouter.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.choices[0].message.content.strip()


def generate_reply_streaming(
    question: str, category: str, papers: list, mode: str = "first_sentence"
) -> str:
    """Generate LLM reply with streaming output."""
    context = build_context(papers, mode=mode)

    prompt = PROMPT_TEMPLATE.format(
        category=category,
        context=context,
        question=question,
    )

    response = openrouter.chat.completions.create(
        model=LLM_MODEL, messages=[{"role": "user", "content": prompt}], stream=True
    )

    reply_text = ""
    for chunk in response:
        if chunk.choices[0].delta.content:
            text = chunk.choices[0].delta.content
            print(text, end="", flush=True)
            reply_text += text

    print()
    return reply_text


def extract_category_from_message(text: str) -> str:
    """Extract category if mentioned, else default."""
    match = re.search(r"\b([a-z]{2,4}\.[A-Z]{2})\b", text)
    if match:
        return match.group(1)
    return DEFAULT_CATEGORY


def strip_mentions(text: str) -> str:
    """Remove @mentions from text."""
    return re.sub(r"@\S+", "", text).strip()


def is_help_request(text: str) -> bool:
    """Check if user is asking for help."""
    text_lower = text.lower().strip()
    help_triggers = [
        "help",
        "?",
        "how do i use",
        "what can you do",
        "commands",
        "usage",
    ]
    return any(trigger in text_lower for trigger in help_triggers)


def run_cli(mode: str = "first_sentence", category: str = None, files: int = CAT_MAX_FILES):
    """Interactive command-line mode."""
    current_category = category or DEFAULT_CATEGORY
    current_files = files

    print("=" * 60)
    print("arXiv Paper Assistant - CLI Mode")
    print("=" * 60)
    print(f"Context mode: {mode}")
    print(f"Current category: {current_category}")
    print(f"Files to load: {current_files}")
    print(f"LLM model: {LLM_MODEL}")
    print(f"Available categories: {', '.join(get_available_categories()) or 'none'}")
    print()
    print("Commands:")
    print("  /cat <category>  - Change category (e.g., /cat math.CO)")
    print("  /mode <mode>     - Change mode (title, first_sentence, full_abstract)")
    print("  /files <n>       - Change files to load (e.g., /files 3)")
    print("  /list            - List available categories")
    print("  /help            - Show help message")
    print("  /quit            - Exit")
    print("=" * 60)
    print()

    while True:
        try:
            question = input(f"[{current_category}] >>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not question:
            continue

        if question.lower() in ["/quit", "/exit", "/bye"]:
            print("Goodbye!")
            break

        if question.lower().startswith("/cat "):
            new_cat = question[5:].strip()
            available = get_available_categories()
            if new_cat in available:
                current_category = new_cat
                papers = load_feeds(current_category, files=current_files)
                print(f"Switched to {current_category} ({len(papers)} papers loaded)")
            else:
                print(
                    f"Category '{new_cat}' not available. Available: {', '.join(available)}"
                )
            continue

        if question.lower().startswith("/mode "):
            new_mode = question[6:].strip()
            if new_mode in ["title", "first_sentence", "full_abstract"]:
                mode = new_mode
                print(f"Context mode changed to: {mode}")
            else:
                print("Invalid mode. Choose: title, first_sentence, full_abstract")
            continue

        if question.lower().startswith("/files "):
            try:
                new_files = int(question[7:].strip())
                if new_files < 1:
                    print("Files must be at least 1")
                else:
                    current_files = new_files
                    papers = load_feeds(current_category, files=current_files)
                    print(f"Files changed to {current_files} ({len(papers)} papers loaded)")
            except ValueError:
                print("Invalid number. Usage: /files 3")
            continue

        if question.lower() == "/list":
            available = get_available_categories()
            print(f"Available categories: {', '.join(available) or 'none'}")
            continue

        if question.lower() == "/help":
            print(get_help_message())
            continue

        detected_cat = extract_category_from_message(question)
        if detected_cat != DEFAULT_CATEGORY and detected_cat != current_category:
            available = get_available_categories()
            if detected_cat in available:
                current_category = detected_cat
                print(f"(Detected category: {current_category})")

        papers = load_feeds(current_category, files=current_files)

        if not papers:
            available = get_available_categories()
            print(
                f"No papers found for {current_category}. Available: {', '.join(available) or 'none'}"
            )
            continue

        print(f"\n({len(papers)} papers, generating response...)\n")

        try:
            generate_reply_streaming(question, current_category, papers, mode=mode)
            print()
        except Exception as e:
            print(f"Error: {e}")


def run_reply_bot(dry_run: bool = False, mode: str = "first_sentence", files: int = CAT_MAX_FILES):
    """Main bot loop."""
    if not MASTODON_ACCESS_TOKEN:
        print("Error: MASTODON_ACCESS_TOKEN not set in .env file")
        return

    mastodon = Mastodon(
        access_token=MASTODON_ACCESS_TOKEN,
        api_base_url=f"https://{MASTODON_INSTANCE}",
    )

    processed = load_processed()

    print(f"Bot started. Polling every {POLL_INTERVAL}s...")
    print(f"Instance: {MASTODON_INSTANCE}")
    print(f"Username: {USERNAME}")
    print(f"LLM model: {LLM_MODEL}")
    print(f"Context mode: {mode}")
    print(f"Responding to: public and unlisted mentions only")
    print(f"Reply visibility: unlisted")
    print(f"Already processed: {len(processed)} notifications")

    while True:
        try:
            notifications = mastodon.notifications(types=["mention"])

            for notif in notifications:
                notif_id = str(notif["id"])

                if notif_id in processed:
                    continue

                status = notif["status"]
                account = notif["account"]

                if status["visibility"] not in ["public", "unlisted"]:
                    print(
                        f"Skipping {status['visibility']} mention from @{account['acct']}"
                    )
                    processed.add(notif_id)
                    save_processed(processed)
                    continue

                content = re.sub(r"<[^>]+>", "", status["content"])
                content = unescape(content)
                question = strip_mentions(content)

                print(
                    f"\n--- New mention from @{account['acct']} ({status['visibility']}) ---"
                )
                print(f"Question: {question}")

                if not question:
                    print("Empty question, skipping")
                    processed.add(notif_id)
                    save_processed(processed)
                    continue

                if is_help_request(question):
                    reply_text = get_help_message()
                    category = "help"
                else:
                    category = extract_category_from_message(content)
                    print(f"Category: {category}")

                    papers = load_feeds(category, files=files)

                    if not papers:
                        available = get_available_categories()
                        reply_text = f"Sorry, I don't have recent data for {category}. Available categories: {', '.join(available) if available else 'none yet'}."
                    else:
                        print(
                            f"Loaded {len(papers)} papers, generating reply (mode={mode})..."
                        )
                        reply_text = generate_reply(
                            question, category, papers, mode=mode
                        )

                if len(reply_text) > MAX_TOOT_LENGTH - 100:
                    reply_text = reply_text[: MAX_TOOT_LENGTH - 103] + "..."

                print(f"\n--- Reply ({len(reply_text)} chars) ---")
                print(reply_text)
                print("---")

                if dry_run:
                    print("[Dry run - not posting]")
                else:
                    mastodon.status_reply(
                        to_status=status,
                        status=reply_text,
                        visibility="unlisted",
                    )
                    print(f"Replied to @{account['acct']}")

                log_interaction(account["acct"], question, category, len(reply_text))

                processed.add(notif_id)
                save_processed(processed)

                time.sleep(5)

        except Exception as e:
            print(f"Error: {e}")

        time.sleep(POLL_INTERVAL)


def run_once(dry_run: bool = False, mode: str = "first_sentence", files: int = CAT_MAX_FILES):
    """Process mentions once and exit."""
    if not MASTODON_ACCESS_TOKEN:
        print("Error: MASTODON_ACCESS_TOKEN not set in .env file")
        return

    mastodon = Mastodon(
        access_token=MASTODON_ACCESS_TOKEN,
        api_base_url=f"https://{MASTODON_INSTANCE}",
    )

    processed = load_processed()

    print(f"Checking for new mentions (mode={mode}, public/unlisted only)...")

    notifications = mastodon.notifications(types=["mention"])
    new_count = 0

    for notif in notifications:
        notif_id = str(notif["id"])

        if notif_id in processed:
            continue

        status = notif["status"]
        account = notif["account"]

        if status["visibility"] not in ["public", "unlisted"]:
            print(f"Skipping {status['visibility']} mention from @{account['acct']}")
            processed.add(notif_id)
            continue

        new_count += 1

        content = re.sub(r"<[^>]+>", "", status["content"])
        content = unescape(content)
        question = strip_mentions(content)

        print(f"\n--- Mention from @{account['acct']} ({status['visibility']}) ---")
        print(f"Question: {question}")

        if not question:
            print("Empty question, skipping")
            processed.add(notif_id)
            continue

        if is_help_request(question):
            reply_text = get_help_message()
            category = "help"
        else:
            category = extract_category_from_message(content)
            print(f"Category: {category}")

            papers = load_feeds(category, files=files)

            if not papers:
                available = get_available_categories()
                reply_text = f"Sorry, I don't have recent data for {category}. Available categories: {', '.join(available) if available else 'none yet'}."
            else:
                print(f"Loaded {len(papers)} papers, generating reply (mode={mode})...")
                reply_text = generate_reply(question, category, papers, mode=mode)

        if len(reply_text) > MAX_TOOT_LENGTH - 100:
            reply_text = reply_text[: MAX_TOOT_LENGTH - 103] + "..."

        print(f"\n--- Reply ({len(reply_text)} chars) ---")
        print(reply_text)
        print("---")

        if dry_run:
            print("[Dry run - not posting]")
        else:
            mastodon.status_reply(
                to_status=status,
                status=reply_text,
                visibility="unlisted",
            )
            print(f"Replied to @{account['acct']}")

        log_interaction(account["acct"], question, category, len(reply_text))

        processed.add(notif_id)
        time.sleep(5)

    save_processed(processed)
    print(f"\nProcessed {new_count} new mentions")


if __name__ == "__main__":
    import sys

    if "--help" in sys.argv:
        print("Usage: python rag_toXiv_reply_bot.py [options]")
        print("")
        print("Modes:")
        print("  --cli             Interactive command-line mode")
        print("  --daemon          Run Mastodon bot continuously")
        print("  --once            Process Mastodon mentions once and exit (default)")
        print("")
        print("Options:")
        print("  --dry-run         Don't actually post replies (Mastodon modes)")
        print(
            "  --category <cat>  Set initial category (CLI mode, e.g., --category math.CO)"
        )
        print("  --cat-max-files <n>  Number of data files to load per category (default: 1)")
        print("")
        print("Context modes (choose one):")
        print("  --title           Use paper titles only")
        print("  --first-sentence  Use titles + first sentence of abstract (default)")
        print("  --full-abstract   Use titles + full abstracts")
        print("")
        print("Examples:")
        print("  python rag_toXiv_reply_bot.py --cli")
        print("  python rag_toXiv_reply_bot.py --cli --full-abstract --category cs.AI")
        print("  python rag_toXiv_reply_bot.py --cli --cat-max-files 3")
        print("  python rag_toXiv_reply_bot.py --once --dry-run")
        print("  python rag_toXiv_reply_bot.py --daemon --full-abstract --cat-max-files 7")
        print("")
        print("CLI commands:")
        print("  /cat <category>  - Change category")
        print("  /mode <mode>     - Change context mode")
        print("  /files <n>       - Change number of files to load")
        print("  /list            - List available categories")
        print("  /help            - Show help")
        print("  /quit            - Exit")
        print("")
        print(f"Config from rag_toXiv_variables.py:")
        print(f"  Instance: {MASTODON_INSTANCE}")
        print(f"  Username: {USERNAME}")
        print(f"  Default category: {DEFAULT_CATEGORY}")
        print(f"  LLM model: {LLM_MODEL}")
        print("")
        print("Environment variables (from .env):")
        print(
            f"  MASTODON_ACCESS_TOKEN: {'set' if MASTODON_ACCESS_TOKEN else 'NOT SET'}"
        )
        print(f"  OPENROUTER_API_KEY: {'set' if OPENROUTER_API_KEY else 'NOT SET'}")
        sys.exit(0)

    dry_run = "--dry-run" in sys.argv

    if "--title" in sys.argv:
        mode = "title"
    elif "--full-abstract" in sys.argv:
        mode = "full_abstract"
    else:
        mode = "first_sentence"

    category = None
    if "--category" in sys.argv:
        idx = sys.argv.index("--category")
        if idx + 1 < len(sys.argv):
            category = sys.argv[idx + 1]

    files = CAT_MAX_FILES
    if "--cat-max-files" in sys.argv:
        idx = sys.argv.index("--cat-max-files")
        if idx + 1 < len(sys.argv):
            try:
                files = int(sys.argv[idx + 1])
            except ValueError:
                print("Error: --cat-max-files requires a number")
                sys.exit(1)

    if "--cli" in sys.argv:
        run_cli(mode=mode, category=category, files=files)
    elif "--daemon" in sys.argv:
        run_reply_bot(dry_run=dry_run, mode=mode, files=files)
    else:
        run_once(dry_run=dry_run, mode=mode, files=files)
