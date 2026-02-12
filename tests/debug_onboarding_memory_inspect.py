import pytest
from src.models.database import SessionLocal, init_db
from src.services.dialogue_engine import DialogueEngine
from tests.utils import create_test_user
from src.memories import MemoryManager


@pytest.mark.asyncio
async def test_debug_onboarding_memories():
    db = SessionLocal()
    try:
        init_db()
        user_id = create_test_user(db, 'dbg_onboard_user')
        dialogue = DialogueEngine(db)
        mm = MemoryManager(db)

        resp1 = await dialogue.process_message(user_id, 'Hi', db)
        print('RESP1:', resp1)
        print('MEM after resp1:', mm.get_memory(user_id))

        resp2 = await dialogue.process_message(user_id, 'My name is Alex', db)
        print('RESP2:', resp2)
        print('MEM after resp2:', mm.get_memory(user_id))

        resp3 = await dialogue.process_message(user_id, 'Yes', db)
        print('RESP3:', resp3)
        print('MEM after resp3:', mm.get_memory(user_id))
    finally:
        db.close()
