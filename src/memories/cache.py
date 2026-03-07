"""Disk-based cache for AI Judge decisions."""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from src.config import settings

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_DIR = Path(__file__).parent.parent.parent / "src" / "data"
CACHE_FILE = CACHE_DIR / "ai_judge_cache.json"
CACHE_LOCK = threading.Lock()
# Cache entries older than this will be considered stale (7 days)
CACHE_TTL_DAYS = 7


def _load_disk_cache() -> Dict[str, Any]:
    """Load cache from disk. Returns empty dict if file doesn't exist or is invalid."""
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.debug(f"Loaded {len(data.get('entries', {}))} cache entries from disk")
                return data
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to load disk cache: {e}")
    return {"entries": {}, "version": 1}


def _save_disk_cache(cache_data: Dict[str, Any]) -> None:
    """Save cache to disk atomically."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # Write to temp file first, then rename for atomicity
        temp_file = CACHE_FILE.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, default=str)
        temp_file.replace(CACHE_FILE)
        logger.debug(f"Saved {len(cache_data.get('entries', {}))} cache entries to disk")
    except IOError as e:
        logger.error(f"Failed to save disk cache: {e}")


def is_cache_entry_fresh(entry: Dict[str, Any]) -> bool:
    """Check if a cache entry is still fresh (not expired)."""
    created_at = entry.get("created_at")
    if not created_at:
        return False
    try:
        # Handle both ISO string and datetime objects
        if isinstance(created_at, str):
            created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        else:
            created = created_at
        now = datetime.now(timezone.utc)
        age_days = (now - created).total_seconds() / 86400
        return age_days < CACHE_TTL_DAYS
    except (ValueError, TypeError):
        return False


class DecisionCache:
    """Persistent cache for AI judge storage decisions."""
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._disk_cache_loaded = False
    
    def ensure_loaded(self) -> None:
        """Lazy load cache from disk on first access."""
        if not self._disk_cache_loaded:
            disk_data = _load_disk_cache()
            # Only keep fresh entries
            for key, entry in list(disk_data.get("entries", {}).items()):
                if is_cache_entry_fresh(entry):
                    self._cache[key] = entry.get("decision", {})
                else:
                    # Remove stale entry
                    del disk_data["entries"][key]
            # Save if we cleaned stale entries
            if len(disk_data.get("entries", {})) != len(self._cache):
                _save_disk_cache(disk_data)
            self._disk_cache_loaded = True
            logger.info(f"Loaded {len(self._cache)} fresh cache entries from disk")
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached decision by key."""
        self.ensure_loaded()
        return self._cache.get(key)
    
    def set(self, key: str, decision: Dict[str, Any]) -> None:
        """Cache a decision."""
        self.ensure_loaded()
        self._cache[key] = decision
        # Persist to disk
        cache_data = {"entries": {}, "version": 1}
        for k, v in self._cache.items():
            cache_data["entries"][k] = {
                "decision": v,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        _save_disk_cache(cache_data)
    
    def invalidate_for_key(self, user_id: int, key: str) -> None:
        """Invalidate all cache entries for a specific user and key."""
        self.ensure_loaded()
        keys_to_remove = [k for k in self._cache if k.startswith(f"{user_id}:{key}:")]
        for k in keys_to_remove:
            del self._cache[k]
        if keys_to_remove:
            # Save updated cache to disk
            cache_data = {"entries": {}, "version": 1}
            for k, v in self._cache.items():
                cache_data["entries"][k] = {
                    "decision": v,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            _save_disk_cache(cache_data)
            logger.info(f"Invalidated {len(keys_to_remove)} cache entries for user_id={user_id}, key={key}")
    
    def clear(self) -> None:
        """Clear all cached decisions."""
        self._cache = {}
        _save_disk_cache({"entries": {}, "version": 1})
        logger.info("Cleared AI judge cache")

