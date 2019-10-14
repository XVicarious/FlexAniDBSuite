from datetime import datetime, timedelta
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


class Config:

    max_session = 15
    last_session = 0
    last_time = None

    def __init__(self, max_session=15, last_session=0, last_time=None):
        self.max_session = max_session
        self.last_session = last_session
        self.last_time = last_time

    def update_session(self):
        self.last_time = datetime.utcnow()
        self.flush()

    def inc_session(self):
        self.last_session += 1
        self.flush()

    def can_request(self):
        if self.last_session >= self.max_session and self.last_time and datetime.utcnow() - self.last_time >= timedelta(hours=4):
            return False
        return True

    def flush(self):
        with open('fadbs.yml', 'w') as cfg:
            dump(self, cfg, Dumper=Dumper)


def open_config() -> Config:
    try:
        with open('fadbs.yml') as cfg:
            return load(cfg, Loader=Loader)
    except FileNotFoundError:
        cfg = Config()
        cfg.flush()
        return cfg

CONFIG = open_config()
