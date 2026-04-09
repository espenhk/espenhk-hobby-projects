import os
import sys

_skate_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _skate_dir not in sys.path:
    sys.path.insert(0, _skate_dir)
