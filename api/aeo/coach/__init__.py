"""AI execution coach — Pro-only chat that helps owners execute recommendations.

Split from api/aeo/router.py. This package owns:

- handler.py  the /recommendation-help endpoint + input validation + LLM call
- prompts.py  _build_coach_system_prompt (EN + FR) and the knowledge-base
              integration that grounds the coach in Canadian platform specifics
"""
