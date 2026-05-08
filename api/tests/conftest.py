"""
Load .env before tests collect — many modules read env vars at import time.
"""
from dotenv import load_dotenv
import os
from pathlib import Path

# Load the api/.env (parent of tests/)
load_dotenv(Path(__file__).parent.parent / ".env")
