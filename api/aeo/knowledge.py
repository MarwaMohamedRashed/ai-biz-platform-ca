"""
Knowledge base loader for FAQ generation and AI Coach.

Each entry is a markdown file under `api/knowledge/` with YAML frontmatter:

    ---
    key: homestars
    applies_to: recommendation        # 'recommendation' | 'faq'
    match_titles:                     # exact (case-insensitive) match against
      - Claim your HomeStars profile  # rec.title from generate_recommendations
    last_updated: 2026-05-09
    ---
    # Markdown body — platform-specific knowledge, common stuck points,
    # owner-friendly explanations of jargon, etc.

The loader runs at module import; entries are read once and held in memory.
Updates require an API restart.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"


@dataclass
class KnowledgeEntry:
    key: str
    applies_to: str                # 'recommendation' | 'faq'
    match_titles: list[str] = field(default_factory=list)
    body: str = ""

    def matches_title(self, title: str | None) -> bool:
        if not title or not self.match_titles:
            return False
        t = title.strip().lower()
        return any(m.strip().lower() == t for m in self.match_titles)


def _parse_frontmatter(raw: str) -> tuple[dict, str]:
    """Tiny YAML-ish frontmatter parser. Same shape as lib/blog.ts on the FE."""
    m = re.match(r"^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$", raw)
    if not m:
        return {}, raw

    meta: dict = {}
    pending_list_key: str | None = None
    for line in m.group(1).split("\n"):
        line = line.rstrip()
        if not line.strip():
            pending_list_key = None
            continue
        # YAML-style list items '  - foo'
        if pending_list_key and line.lstrip().startswith("- "):
            val = line.lstrip()[2:].strip().strip('"').strip("'")
            meta.setdefault(pending_list_key, []).append(val)
            continue
        kv = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not kv:
            continue
        key, value = kv.group(1).strip(), kv.group(2).strip()
        # Inline list `[a, b]`
        if value.startswith("[") and value.endswith("]"):
            items = value[1:-1].split(",")
            meta[key] = [s.strip().strip('"').strip("'") for s in items if s.strip()]
        elif value == "":
            # Multi-line list follows
            meta[key] = []
            pending_list_key = key
        else:
            # Strip surrounding quotes
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            meta[key] = value
    return meta, m.group(2)


def _load_all() -> list[KnowledgeEntry]:
    """Read every *.md file under api/knowledge/ and parse into entries."""
    out: list[KnowledgeEntry] = []
    if not KNOWLEDGE_DIR.exists():
        logger.warning(f"[KB] {KNOWLEDGE_DIR} does not exist; no knowledge loaded")
        return out

    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        try:
            raw = path.read_text(encoding="utf-8")
            meta, body = _parse_frontmatter(raw)
            key = str(meta.get("key") or path.stem)
            applies_to = str(meta.get("applies_to") or "recommendation")
            match_titles = meta.get("match_titles") or []
            if not isinstance(match_titles, list):
                match_titles = [str(match_titles)]
            out.append(KnowledgeEntry(
                key=key,
                applies_to=applies_to,
                match_titles=[str(t) for t in match_titles],
                body=body.strip(),
            ))
        except Exception as e:
            logger.warning(f"[KB] failed to load {path.name}: {e}")
    return out


# Loaded once at import. Restart the API to pick up edits.
_ENTRIES = _load_all()
logger.info(f"[KB] Loaded {len(_ENTRIES)} knowledge entries from {KNOWLEDGE_DIR}")


# ─── Public API ───────────────────────────────────────────────────────────
def for_faq() -> str | None:
    """Return the FAQ-generation guidelines body (or None if not present)."""
    for e in _ENTRIES:
        if e.applies_to == "faq":
            return e.body
    return None


def for_recommendation(title: str | None) -> str | None:
    """Return the body of the knowledge entry whose match_titles include
    `title` (case-insensitive exact match). None if no match."""
    if not title:
        return None
    for e in _ENTRIES:
        if e.applies_to == "recommendation" and e.matches_title(title):
            return e.body
    return None


def all_keys() -> list[str]:
    """Diagnostic helper -- list every loaded entry key."""
    return [e.key for e in _ENTRIES]
