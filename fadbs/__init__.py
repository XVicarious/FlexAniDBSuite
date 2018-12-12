"""FADBS."""
import pathlib
from os.path import join as os_joinpath
from flexget.manager import manager

BASE_PATH = pathlib.Path(os_joinpath(manager.config_base, '.fadbs'))
