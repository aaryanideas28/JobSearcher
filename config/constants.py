# File: config/constants.py
"""Centralized constants and regex patterns for ATS scoring penalties and document formatting."""

import re
from typing import Dict, List, Set

# Weak/passive verb phrases that lack strong impact
WEAK_ACTION_VERBS: List[str] = [
    "assisted",
    "assisted with",
    "helped",
    "helped to",
    "worked on",
    "worked with",
    "responsible for",
    "duties included",
    "handled",
    "tasked with",
    "participated in",
    "served as",
    "contributed to",
    "involved in",
    "managed to",
    "attempted to",
    "supported",
    "aided",
    "was part of",
    "took part in",
    "dealt with",
]

# Compiled Regex pattern for weak action verbs (word boundary, case-insensitive)
WEAK_VERBS_REGEX: re.Pattern = re.compile(
    r"\b(?:" + "|".join(re.escape(verb) for verb in WEAK_ACTION_VERBS) + r")\b",
    re.IGNORECASE,
)

# Regex pattern for detecting metrics, percentages, currency, and multipliers (e.g. 2x, $50k, 30%, 100+)
METRIC_PATTERNS_REGEX: re.Pattern = re.compile(
    r"(\b\d+(?:\.\d+)?\s*[%$xXkKMB\+]|\$\s*\d+(?:\.\d+)?\b|\b\d+\+\b|\b\d+x\b|\bincreased\s+by\s+\d+|\bimproved\s+by\s+\d+|\breduced\s+by\s+\d+|\bsaved\s+\$?\d+)",
    re.IGNORECASE,
)

# Formatting artifact patterns (tables, images, columns)
FORMATTING_ARTIFACT_PATTERNS: Dict[str, re.Pattern] = {
    "table_pipes": re.compile(r"\|.*\|.*\|"),
    "html_tables": re.compile(r"<table[^>]*>|<tr>|<td>", re.IGNORECASE),
    "html_images": re.compile(r"<img[^>]*>|!\[.*?\]\(.*?\)", re.IGNORECASE),
    "multi_column_tabs": re.compile(r"\t{2,}"),
}

# Penalty weights (points deducted)
PENALTY_WEIGHTS: Dict[str, int] = {
    "weak_verb_per_occurrence": 3,
    "max_weak_verb_penalty": 15,
    "table_penalty": 15,
    "image_column_penalty": 15,
    "max_formatting_penalty": 25,
    "low_bullet_count_penalty": 15,
    "invalid_bullet_length_penalty": 2,
    "max_brevity_penalty": 15,
    "low_metric_ratio_penalty": 15,
}
