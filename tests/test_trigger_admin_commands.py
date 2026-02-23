import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base, User, TriggerEmbedding
from src.services.dialogue.admin_handler import handle_trigger_admin_commands


class DummyEmbedSvc:
    async def generate_embedding(self, text: str):
        return [0.1, 0.2, 0.3, 0.4]

    def embedding_to_bytes(self, emb):
        import numpy as np

        return np.array(emb, dtype="float32").tobytes()


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _seed_users_and_action(session):
    admin_user = User(external_id="111", channel="telegram", opted_in=True)
    other_user = User(external_id="222", channel="telegram", opted_in=True)
    session.add(admin_user)
    session.add(other_user)
    session.add(
        TriggerEmbedding(
            name="create_schedule_seed",
            action_type="create_schedule",
            embedding=DummyEmbedSvc().embedding_to_bytes([1.0, 0.0, 0.0, 0.0]),
            threshold=0.75,
        )
    )
    session.commit()
    return admin_user.user_id, other_user.user_id


@pytest.mark.asyncio
async def test_trigger_add_requires_admin(monkeypatch, db_session):
    admin_user_id, other_user_id = _seed_users_and_action(db_session)
    monkeypatch.setattr(
        "src.services.dialogue.admin_handler.get_admin_chat_id",
        lambda: 111,
    )
    monkeypatch.setattr(
        "src.services.dialogue.admin_handler.get_embedding_service",
        lambda: DummyEmbedSvc(),
    )

    out = await handle_trigger_admin_commands(
        text="trigger_add create_schedule | remind me daily | 0.6",
        session=db_session,
        user_id=other_user_id,
    )
    assert out == "This command is admin-only."

    rows = (
        db_session.query(TriggerEmbedding)
        .filter(TriggerEmbedding.action_type == "create_schedule")
        .all()
    )
    assert len(rows) == 1

    # sanity: admin user should still be recognized
    out_admin = await handle_trigger_admin_commands(
        text="trigger_add create_schedule | remind me daily | 0.6",
        session=db_session,
        user_id=admin_user_id,
    )
    assert "Added trigger id=" in out_admin


@pytest.mark.asyncio
async def test_trigger_add_list_delete_roundtrip(monkeypatch, db_session):
    admin_user_id, _ = _seed_users_and_action(db_session)
    monkeypatch.setattr(
        "src.services.dialogue.admin_handler.get_admin_chat_id",
        lambda: 111,
    )
    monkeypatch.setattr(
        "src.services.dialogue.admin_handler.get_embedding_service",
        lambda: DummyEmbedSvc(),
    )

    add_out = await handle_trigger_admin_commands(
        text="trigger_add create_schedule | remind me after lunch | 0.66",
        session=db_session,
        user_id=admin_user_id,
    )
    assert "Added trigger id=" in add_out
    assert "threshold=0.66" in add_out

    list_out = await handle_trigger_admin_commands(
        text="trigger_list create_schedule",
        session=db_session,
        user_id=admin_user_id,
    )
    assert list_out is not None
    assert "Trigger embeddings" in list_out
    assert "action=create_schedule" in list_out
    assert "remind me after lunch" in list_out

    latest = (
        db_session.query(TriggerEmbedding)
        .filter(TriggerEmbedding.action_type == "create_schedule")
        .order_by(TriggerEmbedding.id.desc())
        .first()
    )
    assert latest is not None

    del_out = await handle_trigger_admin_commands(
        text=f"trigger_delete {latest.id}",
        session=db_session,
        user_id=admin_user_id,
    )
    assert del_out == f"Deleted trigger id={latest.id} action_type=create_schedule."

    deleted = (
        db_session.query(TriggerEmbedding)
        .filter(TriggerEmbedding.id == latest.id)
        .first()
    )
    assert deleted is None
