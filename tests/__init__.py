import os
import sys

# Allow `python -m unittest discover -s tests -t .` with or without PYTHONPATH=src.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
