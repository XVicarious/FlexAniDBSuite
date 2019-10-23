from flexget.manager import manager
from flexget.utils.requests import Session as Requests
from sqlalchemy import orm as sa_orm


class FadbsSession:

    _session: sa_orm.Session

    @property
    def requests(self) -> Requests:
        """Return a requests session for FADBS."""
        return manager.task_queue.current_task.requests

    @property
    def session(self) -> sa_orm.Session:
        """Return a database session for FADBS."""
        if not self._session:
            session = sa_orm.sessionmaker(class_=sa_orm.Session)
            session.configure(bind=manager.engine, expire_on_commit=False)
            self._session = session()
        return self._session
