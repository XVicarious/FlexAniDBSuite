"""Configuration for certain FADBS features."""
from datetime import datetime, timedelta

from yaml import dump, load

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


class Config:
    """Track session downloads for metadata and ban status."""

    max_session = 15
    last_session = 0
    last_time: datetime
    banned: datetime = datetime.utcnow()

    def __init__(self, max_session=15, last_session=0, last_time=datetime.utcnow()):
        """Initalize the variables required for operation.

        max_session -- maximum number of metadata items to download in a single session (default 15)
        last_session -- how many metadata items were downloaded last session (default 0)
        last_time -- the last time a piece of metadata was downloaded (default: None)
        """
        self.max_session = max_session
        self.last_session = last_session
        self.last_time = last_time

    def update_session(self):
        """Update the session time."""
        self.last_time = datetime.utcnow()
        self.flush()

    def inc_session(self):
        """Increment the number of metadata downloaded within the session."""
        self.last_session += 1
        self.flush()

    def set_banned(self):
        """Set being banned from AniDB."""
        self.banned = datetime.utcnow()
        self.flush()

    def is_banned(self) -> bool:
        """Check if we are banned from AniDB based on stored ban time."""
        return not datetime.utcnow() - self.banned < timedelta(days=1)

    def can_request(self) -> bool:
        """Check if we can request new metadata from the server based off session limits."""
        return not (
            self.last_session >= self.max_session
            and self.last_time
            and datetime.utcnow() - self.last_time >= timedelta(hours=4)
        )

    def flush(self):
        """Flush settings to disk."""
        with open('fadbs.yml', 'w') as cfg:
            dump(self, cfg, Dumper=Dumper)


def open_config() -> Config:
    """Load and return the configuration, create a new one if needed."""
    try:
        with open('fadbs.yml') as cfg:
            return load(cfg, Loader=Loader)
    except FileNotFoundError:
        newcfg = Config()
        newcfg.flush()
        return newcfg


CONFIG = open_config()
