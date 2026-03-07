"""Lesson parser.

Parses normalized text into structured lesson objects with
IDs, titles, and content.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator, Optional


@dataclass
class Lesson:
    """A parsed lesson."""
    lesson_id: int
    title: str
    content: str


class LessonHeaderDetector:
    """Detects lesson headers in text.
    
    Recognizes patterns like:
    - "Lesson 1"
    - "Lesson 1 to 5"
    - "Lesson 1 <content>" (content may follow on same line)
    - "LESSON 1"
    - "L E S S O N  1" (spaced)
    """
    
    # Normalized header pattern - content may follow on same line
    HEADER_PATTERN = re.compile(
        r'(?i)^(?:l\s*e\s*s\s*s\s*o\s*n|lesson)\s+(\d{1,3})(?:\s*(?:to|-|–)\s*(\d{1,3}))?(\s|$)'
    )
    
    # Spaced letter pattern - content may follow on same line
    SPACED_PATTERN = re.compile(
        r'^(?:l\s*e\s*s\s*s\s*o\s*n)\s*(\d{1,3})(\s|$)',
        re.IGNORECASE
    )
    
    # Pattern for compact text (no spaces) - content may follow
    COMPACT_PATTERN = re.compile(r'^lesson(\d{1,3})(\s|$)', re.IGNORECASE)
    
    def detect_header(self, line: str) -> Optional[tuple[int, Optional[int]]]:
        """Detect if a line is a lesson header.
        
        Args:
            line: Text line to check.
            
        Returns:
            Tuple of (start_id, end_id) if header found, None otherwise.
            end_id is None for single lessons.
        """
        stripped = line.strip()
        if not stripped:
            return None
        
        # Try standard pattern
        match = self.HEADER_PATTERN.match(stripped)
        if match:
            start = int(match.group(1))
            end = match.group(2)
            if end:
                return (start, int(end))
            return (start, None)
        
        # Try spaced letter pattern
        match = self.SPACED_PATTERN.match(stripped)
        if match:
            return (int(match.group(1)), None)
        
        # Try compact pattern
        match = self.COMPACT_PATTERN.match(stripped)
        if match:
            return (int(match.group(1)), None)
        
        return None


class TitleExtractor:
    """Extracts lesson titles from lesson content.
    
    Title extraction strategies:
    1. Quoted title (most common in ACIM)
    2. First sentence after header
    3. Fallback to "Lesson N"
    """
    
    # Pattern for quoted text (with optional formatting)
    QUOTED_PATTERN = re.compile(
        r'^((?:<[a-z]+>)*["](?:[^"]|["][^"])*["](?:</[a-z]+>)*)'
    )
    
    def extract(self, content: str) -> str:
        """Extract title from lesson content.
        
        Args:
            content: Full lesson content.
            
        Returns:
            Extracted title (truncated to 128 chars).
        """
        if not content:
            return "Lesson"
        
        # Join lines for analysis
        text = ' '.join(content.split('\n'))
        
        # Strip HTML tags for analysis
        clean = re.sub(r'</?[a-z]+>', '', text, flags=re.IGNORECASE)
        
        # Try to find quoted title
        match = self.QUOTED_PATTERN.match(clean)
        if match:
            title = match.group(1).strip()
            if len(title) > 5:
                # Remove leading "lesson N" if present
                title = re.sub(r'^lesson\s+\d+\s+', '', title, flags=re.I)
                # Remove leading quotes
                title = re.sub(r'^["""]+', '', title)
                return title[:128]
        
        # Try first sentence
        sentence_match = re.match(r'^([^.!?]+[.!?])', clean)
        if sentence_match:
            title = sentence_match.group(1).strip()
            if len(title) > 5:
                title = re.sub(r'^lesson\s+\d+\s+', '', title, flags=re.I)
                title = re.sub(r'^["""]+', '', title)
                return title[:128]
        
        return "Lesson"


class LessonParser:
    """Parses normalized text into structured lessons."""
    
    def __init__(self):
        self.header_detector = LessonHeaderDetector()
        self.title_extractor = TitleExtractor()
    
    def parse(self, text: str) -> list[Lesson]:
        """Parse lessons from normalized text.
        
        Args:
            text: Normalized text containing lessons.
            
        Returns:
            List of parsed Lesson objects.
        """
        if not text:
            return []
        
        lines = text.split('\n')
        
        # Find all lesson headers
        headers: list[tuple[int, int]] = []  # (line_index, lesson_id)
        
        for i, line in enumerate(lines):
            result = self.header_detector.detect_header(line)
            if result:
                lesson_id = result[0]
                headers.append((i, lesson_id))
        
        if not headers:
            return []
        
        # Extract lessons between headers
        lessons: list[Lesson] = []
        
        for idx, (header_idx, lesson_id) in enumerate(headers):
            # Determine end of this lesson
            if idx + 1 < len(headers):
                end_idx = headers[idx + 1][0]
            else:
                end_idx = len(lines)
            
            # Extract content
            lesson_lines = lines[header_idx:end_idx]
            content = '\n'.join(lesson_lines).strip()
            
            # Skip if too short
            if len(content) < 60:
                continue
            
            # Extract title
            title = self.title_extractor.extract(content)
            
            # Handle lesson ranges (e.g., "Lesson 1 to 5")
            # For now, just use the first lesson ID
            
            lessons.append(Lesson(
                lesson_id=lesson_id,
                title=title,
                content=content,
            ))
        
        return lessons
    
    def parse_with_intro(
        self, 
        text: str, 
        intro_min_length: int = 80
    ) -> list[Lesson]:
        """Parse lessons with optional introduction.
        
        Args:
            text: Normalized text.
            intro_min_length: Minimum length for intro content.
            
        Returns:
            List of lessons including intro as lesson_id=0 if found.
        """
        lessons = self.parse(text)
        
        if not lessons:
            return []
        
        # Check for intro content before first lesson
        first_lesson_idx = lessons[0].lesson_id
        
        if first_lesson_idx > 1:
            # There's content before lesson 1 that might be intro
            lines = text.split('\n')
            header_line_idx = None
            
            for i, line in enumerate(lines):
                result = self.header_detector.detect_header(line)
                if result and result[0] == lessons[0].lesson_id:
                    header_line_idx = i
                    break
            
            if header_line_idx and header_line_idx > 0:
                intro_lines = lines[:header_line_idx]
                intro_text = '\n'.join(l.strip() for l in intro_lines if l.strip())
                
                if len(intro_text) >= intro_min_length:
                    # Prepend intro as lesson 0
                    lessons.insert(0, Lesson(
                        lesson_id=0,
                        title="Introduction",
                        content=intro_text,
                    ))
        
        return lessons


def parse_lessons(text: str) -> list[Lesson]:
    """Convenience function to parse lessons from text.
    
    Args:
        text: Normalized text containing lessons.
        
    Returns:
        List of parsed Lesson objects as (id, title, content) tuples.
    """
    parser = LessonParser()
    lessons = parser.parse_with_intro(text)
    
    # Convert to tuple format for compatibility
    return [
        (lesson.lesson_id, lesson.title, lesson.content)
        for lesson in lessons
    ]
