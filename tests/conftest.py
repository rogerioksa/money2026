import pytest

from gnc_lite.db.repository import Repository
from gnc_lite.db.session import connect, init_db, make_session
from gnc_lite.services.ledger import Ledger


@pytest.fixture
def session():
    engine = connect(":memory:")
    init_db(engine)
    factory = make_session(engine)
    with factory() as db_session:
        yield db_session


@pytest.fixture
def repo(session):
    return Repository(session)


@pytest.fixture
def ledger(repo):
    return Ledger(repo)
