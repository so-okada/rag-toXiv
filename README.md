# App Info

rag-toXiv is a RAG (Retrieval-Augmented Generation) system for arXiv papers.
It fetches daily arXiv RSS feeds, stores them as JSON, and provides an 
interactive Mastodon reply bot that answers questions about recent papers,
using LLM-based summarization.  We use python3 scripts, arXiv RSS feeds, 
and OpenRouter API.  rag-toXiv is not affiliated with arXiv.


## Setup

* Install required packages.

	```
	% pip install Mastodon.py feedparser ratelimit python-dotenv openai python-dateutil
	```

* Put the following python scripts in the same directory.

	- rag_toXiv_reply_bot.py
	- rag_toXiv_variables.py
	- rag_arXiv_daily_feed.py
	- arXiv_feed_parser.py
	- save_daily_json.py

* Create a .env file with your API keys.

	```
	MASTODON_ACCESS_TOKEN=your_mastodon_access_token
	OPENROUTER_API_KEY=your_openrouter_api_key
	```

* Configure rag_toXiv_variables.py for your settings.

	- DATA_DIR: Directory for storing daily JSON feeds (default: ./data)
	- LOG_DIR: Directory for log files (default: ./logs)
	- MASTODON_INSTANCE: Your Mastodon instance (default: mastoxiv.page)
	- USERNAME: Your bot username
	- DEFAULT_CATEGORY: Default arXiv category (default: cs.LG)
	- CAT_MAX_FILES: Number of JSON files to load per category (default: 1)
	- SKIP_EMPTY: Skip empty JSON files when loading (default: True)
	- LLM_MODEL: OpenRouter model to use (default: xiaomi/mimo-v2-flash:free)
	- CONTEXT_MODE: How much context to include (title, first_sentence, full_abstract)
	- POLL_INTERVAL: Seconds between polling for mentions (default: 60)
	- PROMPT_TEMPLATE: LLM prompt template


## Notes

* Outputs of save_daily_json.py can differ from arXiv new submission web
  pages.  First, this can be due to bugs in scripts or
  instance connection errors.  Second, items of arXiv RSS feeds are not
  necessarily the same as those of arXiv new submission web
  pages (see the second item of https://github.com/so-okada/twXiv?tab=readme-ov-file#notes)

* arXiv does not publish new submissions on weekends.  Schedule
  your cron jobs accordingly (Monday through Friday).

* The reply bot responds only to public and unlisted mentions.  Direct
  messages and followers-only posts are ignored for privacy.  All
  replies are posted as unlisted to avoid flooding public timelines.

* On the use of metadata of arXiv articles, there is the web page of
  [Terms of Use for arXiv APIs](https://arxiv.org/help/api/tou).
  This says that "You are free to use
  descriptive metadata about arXiv e-prints under the terms of the
  Creative Commons Universal (CC0 1.0) Public Domain Declaration." and
  "Descriptive metadata includes information for discovery and
  identification purposes, and includes fields such as title,
  abstract, authors, identifiers, and classification terms."

* Context modes affect LLM token usage and response quality:
	- title: titles only
	- first_sentence: titles and first sentences of abstracts (default)
	- full_abstract: titles and full abstracts

* JSON files are named by feed update date (not fetch date), e.g., 
  `2025-01-07_cs_LG.json` corresponds to the arXiv feed updated on 
  January 7, 2025.

* Empty JSON files (0 papers) are skipped when loading data by default.
  This can be configured with the SKIP_EMPTY variable.


## Usage

### Collecting Daily Feeds

```
% python save_daily_json.py -h
Usage: python save_daily_json.py [categories...] [options]
....

Examples:
  python save_daily_json.py cs.LG
  python save_daily_json.py --cleanup-by-cat-max-files 7
  python save_daily_json.py --list
```


### Reply Bot

```
% python rag_toXiv_reply_bot.py --help

....

Examples:
  python rag_toXiv_reply_bot.py --cli
  python rag_toXiv_reply_bot.py --daemon --full-abstract 
```

### Collecting and Running

	```
	% python save_daily_json.py cs.LG cs.AI
	% python rag_toXiv_reply_bot.py --daemon
	```

## Sample Interactions

* CLI mode interaction:

	```
	% python rag_toXiv_reply_bot.py --cli

	....
	
	[cs.LG] >>> any papers on transformers?
	Based on today's cs.LG submissions, here are papers related to 
	transformers:

	1. https://arxiv.org/abs/2512.xxxxx - "yyyyyyyyy"
	   This paper proposes a novel attention mechanism...
	```

* Mastodon interaction:

	```
	User: @ragtoXiv any interesting papers on graph neural networks today?
	
	Bot: Based on recent cs.LG papers, here are submissions related 
	     to graph neural networks:
	     
	     1. https://arxiv.org/abs/2512.xxxxx - "yyyyyyyyyy..."
	        This paper introduces...
	```

## Directory Structure

```
rag-toXiv/
├── rag_toXiv_reply_bot.py    # Main reply bot
├── rag_toXiv_variables.py    # Configuration
├── rag_arXiv_daily_feed.py   # Feed retrieval with rate limiting
├── arXiv_feed_parser.py      # RSS feed parser (from twXiv/toXiv)
├── save_daily_json.py        # Daily feed collection script
├── .env                      # API keys (not in repo)
├── data/                     # Daily JSON feeds
│   ├── xxxx_cs_LG.json ...
└── logs/                     # Bot logs
    ├── processed_notifications.json
    └── bot_interactions.log
```
## Example

https://mastoxiv.page/@ragtoXiv

## Related Projects

- [toXiv](https://github.com/so-okada/toXiv): arXiv daily new submissions 
on Mastodon 
- [twXiv](https://github.com/so-okada/twXiv): arXiv daily new submissions 
on x.com 
- [bXiv](https://github.com/so-okada/bXiv): arXiv daily new submissions 
on bluesky 


## Author
So Okada, so.okada@gmail.com, https://so-okada.github.io/


## Acknowledgments
Developed with AI assistance including Claude (Anthropic).


## Contributing

Pull requests are welcome. For major changes, please open an
issue first to discuss what you would like to change.


## License

[AGPLv3](https://www.gnu.org/licenses/agpl-3.0.en.html)
