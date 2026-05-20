"""Audit engine — the AEO score pipeline.

Split from api/aeo/router.py (formerly ~4,800 lines). This package owns:

- engine.py          orchestrates _run_audit_core
- scoring.py         calculate_score, score_competitor
- recommendations.py generate_recommendations
- signals.py         _extract_text_signals, cuisine/dietary/service detection
- queries.py         build_queries
- prompts.py         audit-side LLM prompt strings

Re-exports the symbols still used by api/aeo/router.py so the routes file
doesn't need to know the internal layout. As more pieces move, the
re-export surface here grows; eventually router.py imports only what its
endpoint handlers need.
"""
