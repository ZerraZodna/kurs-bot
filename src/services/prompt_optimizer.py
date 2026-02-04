"""
Advanced prompt optimization utilities for token and context management.
Provides tools for pruning, summarizing, and optimizing prompts.
"""

from typing import List, Dict


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
    
