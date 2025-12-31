# note: usual max toot length is 500
# url length is 23
# https://docs.joinmastodon.org/user/posting/

MAX_TOOT_LENGTH = 5000
url_len = 23
url_margin = 2

# arXiv API rate limits  2020-06-16
# no more than 1 request every 3 seconds,
# a single connection at a time.
# https://arxiv.org/help/api/tou
arxiv_call_limit = 1
arxiv_call_period = 5

arxiv_max_trial = 2
arxiv_call_sleep = 2 * 60

# 300 for 5mins per account/ip
# https://docs.joinmastodon.org/api/rate-limits/
# toXiv uses ratelimit library, assuming that different arXiv
# categories use different user accounts.
mstdn_time_period = 5 * 60
post_updates = 300
mstdn_sleep = 5

# overall posting limit independent to specific categories
overall_mstdn_limit_call = 1
overall_mstdn_limit_period = 10

# rag_toXiv specific variables
DATA_DIR = "./data"
LOG_DIR = "./logs"
MASTODON_INSTANCE = "mastoxiv.page"
USERNAME = "ragtoXiv"
DEFAULT_CATEGORY = "cs.LG"
CAT_MAX_FILES = 1
SKIP_EMPTY = True
CONTEXT_MODE = "first_sentence"
# LLM_MODEL = "google/gemini-2.0-flash-exp:free"
LLM_MODEL = "xiaomi/mimo-v2-flash:free"
POLL_INTERVAL = 60

PROMPT_TEMPLATE = """You are an arXiv paper assistant bot on Mastodon.
Answer the user's question based only on recent {category} papers.
Beconcise and helpful. Keep response under 4000 characters.

Important: Format paper references as clickable links: https://arxiv.org/abs/ID

Example: Instead of just 2512.21450, write https://arxiv.org/abs/2512.21450

Recent {category} papers:
{context}

User question: {question}

If the question is about the papers above, answer it. If not, politely decline and explain your purpose."""

HELP_MESSAGE_TEMPLATE = """
I'm an arXiv paper assistant. I can help you explore recent arXiv papers.

Things I can help with:
- "summarize today's papers"
- "any papers on transformers?"
- "find papers about diffusion models"
- "explain what paper 2512.xxxxx is about"

Available categories: {cat_list}"""
