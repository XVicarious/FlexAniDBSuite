"""FADBS."""
import pathlib

from flexget.manager import manager

BASE_PATH = pathlib.Path(manager.config_base, '.fadbs')
if not BASE_PATH.exists():
    BASE_PATH.mkdir()
