import sys
import os

# Add the parent directory (backend) to the Python path
# This allows 'import app' to work correctly without ModuleNotFoundError
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.main import app
