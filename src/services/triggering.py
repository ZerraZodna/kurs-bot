import json
import logging
from typing import Optional, Dict, Any

from src.services.trigger_matcher import get_trigger_matcher
from src.services.trigger_dispatcher import get_trigger_dispatcher
from src.config import settings

logger = logging.getLogger(__name__)


async def handle_triggers(
    response: str,
    original_text: str,
    session,
    memory_manager,
    user_id: int,
) -> None:
    """Run trigger dispatching for a dialogue turn.

    This will prefer structured intent from the assistant response, and
    otherwise run semantic trigger matching against both the user's original
    text and the assistant response. Matches that meet their threshold are
    dispatched.
    """
    try:
        try:
            print(f"[DEBUG triggering] handle_triggers entry user={user_id} ts={__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}")
        except Exception:
            pass

        # Prefer structured intent from LLM if present
        intent = None
        try:
            parsed = json.loads(response)
            if isinstance(parsed, dict) and parsed.get("intent"):
                intent = parsed.get("intent")
        except Exception:
            intent = None

        dispatcher = get_trigger_dispatcher(session, memory_manager)
        # Track dispatched action_types per dialogue turn to avoid duplicate handling
        dispatched_actions: set = set()

        if intent:
            logger.info(f"Triggering via structured intent for user={user_id} intent={intent}")
            try:
                print(f"[DEBUG triggering] structured intent for user={user_id} intent_name={intent.get('name')} action_type={intent.get('action_type')} ts={__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}")
            except Exception:
                pass
            match = {
                "trigger_id": None,
                "name": intent.get("name"),
                "action_type": intent.get("action_type") or intent.get("name"),
                "score": 1.0,
                "threshold": settings.TRIGGER_SIMILARITY_THRESHOLD,
            }
            action = match.get("action_type")
            # dispatch and record action
            result = dispatcher.dispatch(match, {"user_id": user_id, "intent": intent, "original_text": original_text})
            if result and result.get("ok"):
                dispatched_actions.add(action)
            return

        matcher = get_trigger_matcher()
        try:
            # Match on original user text
            matches = await matcher.match_triggers(original_text)
            for m in matches:
                if m.get("score", 0.0) >= m.get("threshold", settings.TRIGGER_SIMILARITY_THRESHOLD):
                    action = m.get("action_type")
                    # Skip if this action was already dispatched in this dialogue turn
                    if action in dispatched_actions:
                        try:
                            print(f"[DEBUG triggering] skipping duplicate original_text action={action} for user={user_id} match={m}")
                        except Exception:
                            pass
                        continue
                    try:
                        print(f"[DEBUG triggering] dispatching from original_text user={user_id} action={action} match={m} ts={__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}")
                    except Exception:
                        pass
                    logger.info(f"Dispatching match from original_text: {m}")
                    res = dispatcher.dispatch(m, {"user_id": user_id, "original_text": original_text})
                    if res and res.get("ok"):
                        dispatched_actions.add(action)

            # Also attempt matching on the assistant response text
            try:
                # Normalize assistant response to a concise form before matching
                def _normalize_response(text: str) -> str:
                    import re
                    # Try to extract explicit confirmation like "your daily reminder at 15:00"
                    m = re.search(r"your\s+daily\s+reminder\s+(?:at\s+)?(\d{1,2}(?::\d{2})?)", text, re.IGNORECASE)
                    if m:
                        t = m.group(1)
                        if ":" not in t:
                            t = f"{int(t):02d}:00"
                        return f"Your daily reminder at {t} is now set"

                    # Otherwise, pick the shortest sentence that contains 'remind'/'reminder'/'daily'
                    sents = re.split(r"(?<=[.!?])\s+", text)
                    for s in sents:
                        if re.search(r"\b(remind|reminder|daily|set)\b", s, re.IGNORECASE):
                            return s.strip()

                    # Fallback to full text
                    return text

                condensed = _normalize_response(response)
                resp_matches = await matcher.match_triggers(condensed)
                for m in resp_matches:
                    action = m.get("action_type")
                    # Skip if this action was already dispatched for original_text
                    if action in dispatched_actions:
                        try:
                            print(f"[DEBUG triggering] skipping action {action} because already dispatched in this turn for user={user_id}")
                        except Exception:
                            pass
                        continue
                    if m.get("score", 0.0) >= m.get("threshold", settings.TRIGGER_SIMILARITY_THRESHOLD):
                        try:
                            print(f"[DEBUG triggering] dispatching from assistant_response user={user_id} action={action} match={m} ts={__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}")
                        except Exception:
                            pass
                        logger.info(f"Dispatching match from assistant response: {m}")
                        res = dispatcher.dispatch(m, {"user_id": user_id, "original_text": original_text, "assistant_response": response})
                        if res and res.get("ok"):
                            dispatched_actions.add(action)
            except Exception as e:
                logger.warning(f"Response matching failed: {e}")
        except Exception as e:
            logger.warning(f"Trigger matcher error: {e}")

    except Exception as e:
        logger.warning(f"Triggers failed: {e}")
