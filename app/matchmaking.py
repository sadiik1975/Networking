import math
import re
from dataclasses import dataclass
from collections import Counter
from typing import Sequence

from app.company_models import CompanyProfile

_TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class CompanyMatch:
    company: CompanyProfile
    score: float
    tags: list[str]


def _terms(text: str) -> Counter[str]:
    return Counter(_TOKEN.findall(text.lower()))


def _cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    dot_product = sum(count * right.get(term, 0) for term, count in left.items())
    left_norm = math.sqrt(sum(count * count for count in left.values()))
    right_norm = math.sqrt(sum(count * count for count in right.values()))
    return dot_product / (left_norm * right_norm)


def find_matches(
    query: str,
    companies: Sequence[CompanyProfile],
    min_score: float = 0.3,
) -> list[CompanyMatch]:
    query_terms = _terms(query)
    matches = []
    for company in companies:
        searchable_text = " ".join(
            [
                company.description,
                *company.capabilities,
                *company.certifications,
                *company.demographic_tags,
                *company.target_global_markets,
                company.naics_code or "",
            ]
        )
        score = _cosine_similarity(query_terms, _terms(searchable_text))
        if score > min_score:
            tags = list(dict.fromkeys([*company.certifications, *company.demographic_tags]))
            matches.append(CompanyMatch(company=company, score=score, tags=tags))
    return sorted(matches, key=lambda match: match.score, reverse=True)
