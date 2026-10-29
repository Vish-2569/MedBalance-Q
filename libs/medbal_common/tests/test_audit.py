from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from medbal_common.audit import CREATE_AUDIT_TABLE, append, verify


def _setup():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text(CREATE_AUDIT_TABLE))
        conn.commit()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return engine, factory


def test_audit_chain_ok():
    _engine, factory = _setup()
    session = factory()
    append(session, "user1", "create", "lot", "L001", {"qty": 100})
    append(session, "user1", "update", "lot", "L001", {"qty": 90})
    append(session, "user2", "approve", "order", "O001", {"status": "approved"})
    session.commit()

    result = verify(session)
    assert result["ok"] is True
    assert result["entries"] == 3
    assert result["first_bad_seq"] is None
    session.close()


def test_audit_detects_tamper():
    _engine, factory = _setup()
    session = factory()
    append(session, "user1", "create", "lot", "L001", {"qty": 100})
    append(session, "user1", "update", "lot", "L001", {"qty": 90})
    append(session, "user2", "approve", "order", "O001", {"status": "approved"})
    session.commit()

    session.execute(
        text("UPDATE audit_log SET payload = :payload WHERE seq = :seq"),
        {"payload": '{"qty":999}', "seq": 2},
    )
    session.commit()

    result = verify(session)
    assert result["ok"] is False
    assert result["first_bad_seq"] == 2
    session.close()


def test_audit_empty():
    _engine, factory = _setup()
    session = factory()
    result = verify(session)
    assert result["ok"] is True
    assert result["entries"] == 0
    session.close()
