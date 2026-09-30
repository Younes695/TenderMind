"""Stage 6 — tender team: similar-task grouping and department vote summaries."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List

VOTES = ("APPROVE", "REJECT", "ABSTAIN")
OUTCOMES = ("WON", "LOST", "SUBMITTED", "NOT_SUBMITTED")
_STOP = {"the", "a", "an", "for", "of", "to", "and", "in", "on", "with", "from", "by", "at", "get", "prepare",
         "send", "request", "ask", "make", "do", "tender", "new"}
SIMILARITY = 0.6


def _tokens(title: str) -> set:
    words = re.findall(r"[a-z0-9؀-ۿ]+", (title or "").lower())
    return {w[:-1] if len(w) > 4 and w.endswith("s") else w for w in words if w not in _STOP}


def similar_groups(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group open tasks whose titles share >= 60% of their meaningful words.
    Only groups that save work are returned: 2+ tasks. Single-link clustering."""
    items = [t for t in tasks if (t.get("status") or "OPEN") == "OPEN"]
    toks = [_tokens(t["title"]) for t in items]
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = toks[i], toks[j]
            if a and b and len(a & b) / len(a | b) >= SIMILARITY:
                parent[find(i)] = find(j)
    groups = defaultdict(list)
    for i, t in enumerate(items):
        groups[find(i)].append(t)
    out = []
    for g in groups.values():
        if len(g) < 2:
            continue
        g.sort(key=lambda t: (t.get("due_date") or "9999", t["title"]))
        out.append({"title": g[0]["title"], "count": len(g), "tenders": sorted({t["tender_id"] for t in g}),
                    "tasks": g})
    out.sort(key=lambda g: (-g["count"], g["title"].lower()))
    return out


def vote_summary(votes: List[Dict[str, Any]]) -> Dict[str, Any]:
    def block(vs):
        c = {v: sum(1 for x in vs if x["vote"] == v) for v in VOTES}
        decided = c["APPROVE"] + c["REJECT"]
        return {"approve": c["APPROVE"], "reject": c["REJECT"], "abstain": c["ABSTAIN"], "total": len(vs),
                "approve_pct": round(100 * c["APPROVE"] / decided) if decided else None}
    by_dep = defaultdict(list)
    for v in votes:
        by_dep[v["department"]].append(v)
    return {"overall": block(votes),
            "by_department": [dict(department=d, **block(vs)) for d, vs in sorted(by_dep.items())]}
