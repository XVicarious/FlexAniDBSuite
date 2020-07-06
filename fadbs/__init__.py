"""FADBS."""
import pathlib

BASE_PATH = pathlib.Path('.fadbs')
if not BASE_PATH.exists():
    BASE_PATH.mkdir()
