"""
Advanced prompt optimization utilities for token and context management.
Provides tools for pruning, summarizing, and optimizing prompts.
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
import re


class PromptOptimizer:
    """Advanced prompt optimization strategies."""
    
    @staticmethod
    def estimate_gpt_tokens(text: str) -> int:
        """
        Estimate token count for GPT-style models.
        More accurate than simple char division.
        """
        # Rough estimation: ~4 chars = 1 token for English
        # But words with punctuation count differently
        words = text.split()
        # Average: ~1.3 tokens per word for English
        return int(len(words) * 1.3)
    
    @staticmethod
    def prioritize_memories(
        memories: List[Dict],
        max_count: int = 5,
        weights: Optional[Dict[str, float]] = None
    ) -> List[Dict]:
        """
        Rank and select top memories by relevance.
        
        Args:
            memories: List of memory dicts
            max_count: Maximum memories to include
            weights: Custom weights for scoring
                - 'confidence': Weight for confidence score (default 0.5)
                - 'recency': Weight for recentness (default 0.3)
                - 'importance': Weight for importance tag (default 0.2)
        
        Returns:
            Top N memories sorted by score
        """
        if not memories:
            return []
        
        if weights is None:
            weights = {'confidence': 0.5, 'recency': 0.3, 'importance': 0.2}
        
        # Score each memory
        scored = []
        for memory in memories:
            score = 0.0
            
            # Confidence score
            confidence = memory.get('confidence', 1.0)
            score += confidence * weights.get('confidence', 0.5)
            
            # Recency score (newer = higher)
            if 'created_at' in memory:
                created = memory['created_at']
                if isinstance(created, str):
                    created = datetime.fromisoformat(created.replace('Z', '+00:00'))
                # Handle both naive and timezone-aware datetimes
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
                # Decay: full score if < 1 day, 0.5 if 1 week, 0 if 30+ days
                recency = max(0, 1 - (age_hours / 720))  # 30 days = 720 hours
                score += recency * weights.get('recency', 0.3)
            
            # Importance score (if tagged)
            if memory.get('important', False):
                score += weights.get('importance', 0.2)
            
            scored.append((score, memory))
        
        # Sort by score and return top N
        sorted_memories = sorted(scored, key=lambda x: x[0], reverse=True)
        return [m for _, m in sorted_memories[:max_count]]
    
    @staticmethod
    def truncate_context_sections(
        sections: Dict[str, str],
        total_budget: int = 2000,
        priority_order: List[str] = None
    ) -> Dict[str, str]:
        """
        Intelligently truncate context sections to fit token budget.
        
        Args:
            sections: Dict of section_name -> section_text
            total_budget: Max tokens for all sections
            priority_order: Order to preserve sections (highest priority first)
        
        Returns:
            Truncated sections fitting within budget
        """
        if priority_order is None:
            priority_order = list(sections.keys())
        
        result = {}
        used_tokens = 0
        
        # Allocate tokens by priority
        for section in priority_order:
            if section not in sections:
                continue
            
            section_text = sections[section]
            section_tokens = PromptOptimizer.estimate_gpt_tokens(section_text)
            
            if used_tokens + section_tokens <= total_budget:
                # Full section fits
                result[section] = section_text
                used_tokens += section_tokens
            else:
                # Partial section
                remaining = total_budget - used_tokens
                if remaining > 100:  # Only include if > 100 tokens left
                    truncated = PromptOptimizer.truncate_by_tokens(
                        section_text,
                        remaining - 50  # Leave buffer
                    )
                    result[section] = truncated
                    used_tokens = total_budget
                break
        
        return result
    
    @staticmethod
    def truncate_by_tokens(text: str, max_tokens: int) -> str:
        """Truncate text to approximately max tokens."""
        estimated_chars = max_tokens * 4
        if len(text) <= estimated_chars:
            return text
        
        # Truncate and break at word boundary
        truncated = text[:estimated_chars]
        last_space = truncated.rfind(' ')
        if last_space > 0:
            truncated = truncated[:last_space]
        return truncated + "..."
    
    @staticmethod
    def deduplicate_memories(memories: List[Dict]) -> List[Dict]:
        """Remove duplicate or highly similar memories."""
        seen = {}
        unique = []
        
        for memory in memories:
            key = (memory.get('key'), memory.get('category'))
            
            if key not in seen:
                seen[key] = memory
                unique.append(memory)
            else:
                # If duplicate has higher confidence, replace
                if memory.get('confidence', 0) > seen[key].get('confidence', 0):
                    unique.remove(seen[key])
                    unique.append(memory)
                    seen[key] = memory
        
        return unique
    
    @staticmethod
    def compress_conversation_history(
        turns: List[Tuple[str, str]],
        max_turns: int = 4,
        strategy: str = "recent"
    ) -> List[Tuple[str, str]]:
        """
        Compress conversation history to fit token budget.
        
        Args:
            turns: List of (user_msg, assistant_msg) tuples
            max_turns: Maximum turns to keep
            strategy: 'recent' (keep last N), 'important' (keep key turns), 'summary' (summarize old)
        
        Returns:
            Compressed conversation
        """
        if len(turns) <= max_turns:
            return turns
        
        if strategy == "recent":
            return turns[-max_turns:]
        
        elif strategy == "important":
            # Keep turns with questions or context shifts
            important_turns = []
            for user_msg, asst_msg in turns:
                if any(q in user_msg.lower() for q in ['?', 'how', 'what', 'why', 'explain']):
                    important_turns.append((user_msg, asst_msg))
            
            # If we have enough important ones, use them
            if len(important_turns) >= max_turns:
                return important_turns[:max_turns]
            # Otherwise, fill with recent turns
            return turns[-max_turns:]
        
        elif strategy == "summary":
            # Keep first 2 and last N-2 (summarize middle)
            if max_turns < 2:
                return turns[-max_turns:]
            
            result = turns[:2]  # First exchange for context
            result.extend(turns[-(max_turns - 2):])  # Recent exchanges
            return result
        
        return turns[-max_turns:]
    
    @staticmethod
    def format_with_budget(
        system_prompt: str,
        context_dict: Dict[str, str],
        user_input: str,
        total_budget: int = 2000
    ) -> str:
        """
        Format complete prompt respecting token budget.
        
        Args:
            system_prompt: System role
            context_dict: Named context sections
            user_input: Current user input
            total_budget: Total token limit
        
        Returns:
            Formatted prompt within budget
        """
        system_tokens = PromptOptimizer.estimate_gpt_tokens(system_prompt)
        user_tokens = PromptOptimizer.estimate_gpt_tokens(user_input)
        
        # Reserve tokens for system and user input
        context_budget = total_budget - system_tokens - user_tokens - 100  # 100 token buffer
        
        # Truncate context sections
        truncated = PromptOptimizer.truncate_context_sections(
            context_dict,
            context_budget,
            priority_order=['profile', 'goals', 'preferences', 'history']
        )
        
        # Assemble prompt
        parts = [system_prompt]
        for section, text in truncated.items():
            if text.strip():
                parts.append(f"\n### {section.title()}\n{text}")
        
        parts.append(f"\nUser: {user_input}\n\nAssistant:")
        
        return "".join(parts)


class ConversationSummarizer:
    """Summarize conversations when they exceed token limits."""
    
    @staticmethod
    def extract_topics(turns: List[Tuple[str, str]]) -> List[str]:
        """Extract main topics from conversation."""
        topics = []
        keywords = {}
        
        for user_msg, asst_msg in turns:
            # Simple keyword extraction
            words = (user_msg + " " + asst_msg).lower().split()
            # Remove common words
            common = {'the', 'a', 'and', 'or', 'is', 'are', 'in', 'on', 'at', 'to', 'for'}
            important_words = [w for w in words if w not in common and len(w) > 3]
            
            for word in important_words:
                keywords[word] = keywords.get(word, 0) + 1
        
        # Get top keywords as topics
        sorted_keywords = sorted(keywords.items(), key=lambda x: x[1], reverse=True)
        topics = [word for word, _ in sorted_keywords[:5]]
        
        return topics
    
    @staticmethod
    def summarize_history(
        turns: List[Tuple[str, str]],
        max_length: int = 200
    ) -> str:
        """Create concise summary of conversation history."""
        if not turns:
            return ""
        
        topics = ConversationSummarizer.extract_topics(turns)
        
        # Count key message types
        questions = sum(1 for user_msg, _ in turns if '?' in user_msg)
        explanations = sum(1 for _, asst_msg in turns if len(asst_msg) > 100)
        
        summary = f"Conversation summary: {len(turns)} exchanges covering {', '.join(topics[:3])}. "
        if questions > 0:
            summary += f"User asked {questions} question(s). "
        if explanations > 0:
            summary += f"Received {explanations} detailed explanation(s). "
        
        return summary[:max_length]


class MemoryFilter:
    """Filter memories for relevant context."""
    
    @staticmethod
    def filter_by_relevance(
        memories: List[Dict],
        user_input: str,
        threshold: float = 0.3
    ) -> List[Dict]:
        """
        Filter memories by relevance to user input.
        Simple keyword matching.
        """
        input_words = set(user_input.lower().split())
        relevant = []
        
        for memory in memories:
            value = memory.get('value', '').lower()
            value_words = set(value.split())
            
            # Jaccard similarity
            if value_words:
                overlap = len(input_words & value_words)
                similarity = overlap / len(input_words | value_words)
                
                if similarity >= threshold:
                    relevant.append(memory)
        
        return relevant
    
    @staticmethod
    def filter_active_only(memories: List[Dict]) -> List[Dict]:
        """Keep only active (non-archived) memories."""
        return [m for m in memories if m.get('is_active', True)]
    
    @staticmethod
    def filter_non_expired(memories: List[Dict]) -> List[Dict]:
        """Filter out expired (TTL) memories."""
        now = datetime.now(timezone.utc)
        non_expired = []
        
        for memory in memories:
            if 'ttl_expires_at' not in memory:
                non_expired.append(memory)
            else:
                expires = memory['ttl_expires_at']
                if isinstance(expires, str):
                    expires = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                if expires > now:
                    non_expired.append(memory)
        
        return non_expired
