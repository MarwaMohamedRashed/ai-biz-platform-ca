"""Content generation — descriptions / FAQ / social bio for AEO customers.

Split from api/aeo/router.py. This package owns:

- generator.py   the /generate-content endpoint + patch/verify/regenerate
- prompts.py     _build_content_prompts and the regenerate-item prompt builder
- validators.py  _clean_bio, _clean_description, _validate_content, etc.
"""
