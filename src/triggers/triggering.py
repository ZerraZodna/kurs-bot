import json
import logging
from typing import Optional, Dict, Any

from src.triggers.trigger_matcher import get_trigger_matcher
from src.triggers.trigger_dispatcher import get_trigger_dispatcher
from src.config import settings

logger = logging.getLogger(__name__)


def _decision_from_matches(
    source: str,
    matches: Optional[list],
    fallback_path_used: bool = False,
) -> Dict[str, Any]:
    top = (matches or [None])[0]
    threshold = float(
        top.get("threshold", settings.TRIGGER_SIMILARITY_THRESHOLD)
    ) if top else float(settings.TRIGGER_SIMILARITY_THRESHOLD)
    score = float(top.get("score", 0.0)) if top else 0.0
    matched = bool(top) and score >= threshold
    return {
        "source": source,
        "matched": matched,
        "matched_action": top.get("action_type") if matched else None,
        "score": score,
        "threshold": threshold,
        "fallback_path_used": bool(fallback_path_used or (top and top.get("fallback_path_used"))),
        "match_source": top.get("match_source") if top else "none",
        "top_candidate_action": top.get("action_type") if top else None,
    }


def _log_trigger_decision(user_id: int, decision: Dict[str, Any]) -> None:
    logger.info(
        "trigger_decision user=%s payload=%s",
        user_id,
        json.dumps(decision, ensure_ascii=False, sort_keys=True),
    )


async def handle_triggers(
    response: str,
    original_text: str,
    session,
    memory_manager,
    user_id: int,
    original_text_embedding=None,
) -> Dict[str, Any]:
    """Run trigger dispatching for a dialogue turn.

    This will prefer structured intent from the assistant response, and
    otherwise run semantic trigger matching against both the user's original
    text and the assistant response. Matches that meet their threshold are
    dispatched.
    """
    diagnostics: Dict[str, Any] = {
        "structured_intent_used": False,
        "original_text_decision": None,
        "assistant_response_decision": None,
        "dispatched_actions": [],
    }

    try:
        # Guard: if response is None, skip matching
        if response is None:
            logger.warning("Assistant response is None; skipping trigger matching")
            diagnostics["original_text_decision"] = {
                "source": "original_text",
                "matched": False,
                "matched_action": None,
                "score": 0.0,
                "threshold": float(settings.TRIGGER_SIMILARITY_THRESHOLD),
                "fallback_path_used": False,
                "match_source": "none",
                "top_candidate_action": None,
            }
            return diagnostics

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

        # No ad-hoc heuristics here — rely on structured intent or trigger matching.

        if intent:
            logger.info(f"Triggering via structured intent for user={user_id} intent={intent}")
            print(f"[DEBUG triggering] structured intent for user={user_id} intent_name={intent.get('name')} action_type={intent.get('action_type')} ts={__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}")
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
            decision = {
                "source": "structured_intent",
                "matched": True,
                "matched_action": action,
                "score": 1.0,
                "threshold": float(settings.TRIGGER_SIMILARITY_THRESHOLD),
                "fallback_path_used": False,
                "match_source": "structured_intent",
                "top_candidate_action": action,
            }
            diagnostics["structured_intent_used"] = True
            diagnostics["original_text_decision"] = decision
            diagnostics["dispatched_actions"] = sorted(dispatched_actions)
            _log_trigger_decision(user_id, decision)
            return diagnostics

        matcher = get_trigger_matcher()
        try:
            # Match on original user text
            matches = await matcher.match_triggers(original_text, precomputed_embedding=original_text_embedding)
            original_decision = _decision_from_matches("original_text", matches)
            diagnostics["original_text_decision"] = original_decision
            _log_trigger_decision(user_id, original_decision)
            for m in matches:
                if m.get("score", 0.0) >= m.get("threshold", settings.TRIGGER_SIMILARITY_THRESHOLD):
                    action = m.get("action_type")
                    # Skip if this action was already dispatched in this dialogue turn
                    if action in dispatched_actions:
                        print(f"[DEBUG triggering] skipping duplicate original_text action={action} for user={user_id} match={m}")
                        continue
                    print(f"[DEBUG triggering] dispatching from original_text user={user_id} action={action} match={m} ts={__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}")
                    logger.info(f"Dispatching match from original_text: {m}")
                    res = dispatcher.dispatch(m, {"user_id": user_id, "original_text": original_text})
                    if res and res.get("ok"):
                        dispatched_actions.add(action)
            # If any actions were dispatched from the original text, skip matching
            # on the assistant response to avoid computing an extra embedding.
            if dispatched_actions:
                logger.info(f"Skipping assistant-response trigger matching; actions already dispatched for user={user_id}: {dispatched_actions}")
                diagnostics["dispatched_actions"] = sorted(dispatched_actions)
                return diagnostics

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
                response_decision = _decision_from_matches(
                    "assistant_response",
                    resp_matches,
                    fallback_path_used=True,
                )
                diagnostics["assistant_response_decision"] = response_decision
                _log_trigger_decision(user_id, response_decision)
                for m in resp_matches:
                    action = m.get("action_type")
                    # Skip if this action was already dispatched for original_text
                    if action in dispatched_actions:
                        print(f"[DEBUG triggering] skipping action {action} because already dispatched in this turn for user={user_id}")
                        continue
                    if m.get("score", 0.0) >= m.get("threshold", settings.TRIGGER_SIMILARITY_THRESHOLD):
                        print(f"[DEBUG triggering] dispatching from assistant_response user={user_id} action={action} match={m} ts={__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}")
                        logger.info(f"Dispatching match from assistant response: {m}")
                        res = dispatcher.dispatch(m, {"user_id": user_id, "original_text": original_text, "assistant_response": response})
                        if res and res.get("ok"):
                            dispatched_actions.add(action)
            except Exception as e:
                logger.warning(f"Response matching failed: {e}")
                decision = {
                    "source": "assistant_response",
                    "matched": False,
                    "matched_action": None,
                    "score": 0.0,
                    "threshold": float(settings.TRIGGER_SIMILARITY_THRESHOLD),
                    "fallback_path_used": True,
                    "match_source": "error",
                    "top_candidate_action": None,
                    "error": str(e),
                }
                diagnostics["assistant_response_decision"] = decision
                _log_trigger_decision(user_id, decision)
        except Exception as e:
            logger.warning(f"Trigger matcher error: {e}")
            if diagnostics.get("original_text_decision") is None:
                diagnostics["original_text_decision"] = {
                    "source": "original_text",
                    "matched": False,
                    "matched_action": None,
                    "score": 0.0,
                    "threshold": float(settings.TRIGGER_SIMILARITY_THRESHOLD),
                    "fallback_path_used": False,
                    "match_source": "error",
                    "top_candidate_action": None,
                    "error": str(e),
                }
                _log_trigger_decision(user_id, diagnostics["original_text_decision"])

    except Exception as e:
        logger.warning(f"Triggers failed: {e}")
        if diagnostics.get("original_text_decision") is None:
            diagnostics["original_text_decision"] = {
                "source": "original_text",
                "matched": False,
                "matched_action": None,
                "score": 0.0,
                "threshold": float(settings.TRIGGER_SIMILARITY_THRESHOLD),
                "fallback_path_used": False,
                "match_source": "error",
                "top_candidate_action": None,
                "error": str(e),
            }
            _log_trigger_decision(user_id, diagnostics["original_text_decision"])

    diagnostics["dispatched_actions"] = sorted(dispatched_actions) if "dispatched_actions" in locals() else []
    return diagnostics
