"""
Vercel Python entry point — exposes the FastAPI app to Vercel's runtime.
Ensures the project root is on sys.path so engine/generator packages are importable.
"""
import sys
from pathlib import Path

# Ensure project root is on sys.path for engine/generator imports.
# Vercel runs api/index.py with api/ on sys.path, but engine/ and generator/
# live at the project root level, which may not be on sys.path.
API_DIR = str(Path(__file__).resolve().parent)
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from server import app
