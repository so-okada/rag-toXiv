#!/usr/bin/env python3
# written by So Okada so.okada@gmail.com
# a part of rag-toXiv for retrival of arXiv rss feeds
# by arXiv_feed_parser.py
# https://github.com/so-okada/rag-toXiv/

import time
from datetime import datetime, timezone
from ratelimit import limits, sleep_and_retry, rate_limited

from rag_toXiv_variables import *
import arXiv_feed_parser as afpa


# overall limit
@sleep_and_retry
@limits(calls=arxiv_call_limit, period=arxiv_call_period)
def daily_entries(cat, aliases):
    trial_num = 0
    while trial_num < arxiv_max_trial:
        feed = afpa.retrieve(cat, aliases)
        if feed.bozo:
            print(str(trial_num + 1) + "th feed parse error for " + cat)
        if trial_num < arxiv_max_trial - 1:
            if len(feed.entries) > 0:
                return feed
            else:
                print("empty feed entries for " + cat)
        else:
            return feed
        trial_num += 1
        if trial_num < arxiv_max_trial:
            print("sleep and retry for " + cat)
            time.sleep(arxiv_call_sleep)
        else:
            raise Exception("fatal parse error for " + cat)
