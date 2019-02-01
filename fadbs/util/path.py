"""Things that were missing from pathlib.Path."""
import pathlib
from datetime import datetime


class Path(type(pathlib.Path())):
    """Path, but doesn't feed you raw things."""

    def modified(self) -> datetime:
        """Return a datetime object of the last time this file was modified."""
        return datetime.fromtimestamp(self.stat().st_mtime)
