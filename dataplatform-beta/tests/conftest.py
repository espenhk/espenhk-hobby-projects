import os
import sys

_project_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_src_dir = os.path.join(_project_dir, "src")
_tests_dir = os.path.dirname(__file__)

for _path in (_src_dir, _tests_dir):
    if _path not in sys.path:
        sys.path.insert(0, _path)