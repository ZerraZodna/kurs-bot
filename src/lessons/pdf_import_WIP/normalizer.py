"""Text normalization pipeline.

Provides a modular normalization pipeline that processes extracted
text through multiple stages to fix common PDF artifacts and prepare
text for lesson parsing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


# Type alias for normalization functions
NormalizerFn = Callable[[str], str]


@dataclass
class NormalizationStage:
    """A single stage in the normalization pipeline."""
    name: str
    func: NormalizerFn
    description: str


class ParagraphJoiner:
    """Joins fragmented paragraphs caused by PDF line breaks.
    
    Uses heuristics to determine when lines should be joined vs.
    when paragraph breaks should be preserved.
    """
    
    def normalize(self, text: str) -> str:
        """Join fragmented paragraphs.
        
        Args:
            text: Input text with line breaks.
            
        Returns:
            Text with proper paragraph structure.
        """
        if not text:
            return text
        
        # Replace \r\n with \n
        text = text.replace('\r\n', '\n')
        
        # Collapse excessive blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Split into lines
        lines = text.split('\n')
        
        paragraphs: list[str] = []
        current: list[str] = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Empty line = paragraph break
            if not stripped:
                if current:
                    paragraphs.append(' '.join(current))
                    current = []
                continue
            
            # Check if current paragraph should end
            if current:
                prev = current[-1]
                
                # Hyphenation at end of line = join
                if prev.endswith('-'):
                    current[-1] = prev[:-1] + stripped
                    continue
                
                # Check for explicit paragraph breaks
                ends_sentence = bool(re.search(r'[\.\!\?\:\;\"\)\]]$', prev))
                next_is_header = bool(re.match(r'(?i)^(lesson\s+\d|intro|part|workbook)', stripped))
                
                # If previous ends with sentence AND next is a header or looks like new paragraph
                if ends_sentence and (next_is_header or self._looks_like_new_paragraph(stripped)):
                    paragraphs.append(' '.join(current))
                    current = [stripped]
                    continue
            
            # Default: continue current paragraph
            current.append(stripped)
        
        # Don't forget last paragraph
        if current:
            paragraphs.append(' '.join(current))
        
        return '\n\n'.join(paragraphs)
    
    def _looks_like_new_paragraph(self, text: str) -> bool:
        """Heuristic: does this look like start of new paragraph?"""
        # Starts with capital and is reasonably long
        if text[0].isupper() and len(text) > 60:
            return True
        
        # Starts with opening quote
        if text.startswith('"') or text.startswith('"') or text.startswith('"'):
            return True
        
        return False


class LessonHeaderSeparator:
    """Ensures each lesson header is on its own line with blank lines around it.
    
    This is critical for the parser to find lesson boundaries.
    The PDF often has "Lesson N <content>" on the same line, which needs
    to be split so "Lesson N" is alone on its line.
    """
    
    def normalize(self, text: str) -> str:
        """Separate lesson headers onto their own lines.
        
        Args:
            text: Input text.
            
        Returns:
            Text with lesson headers on separate lines.
        """
        if not text:
            return text
        
        # First ensure each lesson header starts a new paragraph
        # Pattern: "lesson N" (anywhere in text) -> "\n\nlesson N\n\n"
        # This handles cases like "Lesson 141 ... Lesson 142 ..."
        text = re.sub(
            r'(?mi)(lesson\s+\d{1,3}\b)',
            r'\n\n\1\n\n',
            text
        )
        
        # Clean up: ensure no more than 2 newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Also fix lesson headers that might have content on same line
        # e.g., "Lesson 1 <b>text" -> "Lesson 1\n\n<b>text"
        lines = text.split('\n')
        result_lines = []
        
        for line in lines:
            # Check if line starts with "Lesson N" and has more content
            match = re.match(r'^(lesson\s+\d{1,3})\b(.+)$', line, re.IGNORECASE)
            if match:
                # Split into header and content
                header = match.group(1)
                content = match.group(2).strip()
                # Capitalize properly
                header = header.capitalize() if header.lower().startswith('lesson') else header
                result_lines.append(header)
                if content:
                    result_lines.append(content)
            else:
                result_lines.append(line)
        
        # Join with proper paragraph breaks
        text = '\n'.join(result_lines)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text


class HyphenationFixer:
    """Fixes hyphenation at line breaks.
    
    Example: " continu-\ning" -> "continuing"
    """
    
    def normalize(self, text: str) -> str:
        """Remove hyphenation breaks.
        
        Args:
            text: Input text with hyphenated line breaks.
            
        Returns:
            Text with hyphenation fixed.
        """
        # Pattern: word followed by hyphen at end of line
        # followed by lowercase word start
        text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
        text = re.sub(r'(\w)-\n\s+(\w)', r'\1\2', text)
        
        return text


class SpacingFixer:
    """Fixes common spacing issues in extracted text."""
    
    # Fix missing space after punctuation
    PUNCT_PATTERN = re.compile(r'([\.,!?])(?=[A-Za-z""])')
    
    # Fix missing space after closing quotes
    QUOTE_PATTERN = re.compile(r'([''"])(?=[A-Za-z])')
    
    # Fix multiple spaces
    MULTI_SPACE_PATTERN = re.compile(r' {2,}')
    
    def normalize(self, text: str) -> str:
        """Fix spacing issues.
        
        Args:
            text: Input text.
            
        Returns:
            Text with normalized spacing.
        """
        text = self.PUNCT_PATTERN.sub(r'\1 ', text)
        text = self.QUOTE_PATTERN.sub(r'\1 ', text)
        text = self.MULTI_SPACE_PATTERN.sub(' ', text)
        
        return text


class LessonHeaderNormalizer:
    """Normalizes lesson headers to consistent format.
    
    Converts variants like:
    - "lesson 14"
    - "LESSON 14"  
    - "Lesson 14"
    To canonical "Lesson 14"
    """
    
    def __init__(self, target_lesson_id: int | None = None):
        """Initialize normalizer.
        
        Args:
            target_lesson_id: If provided, normalize all headers to this ID.
        """
        self.target_lesson_id = target_lesson_id
    
    def normalize(self, text: str) -> str:
        """Normalize lesson headers.
        
        Args:
            text: Input text.
            
        Returns:
            Text with normalized headers.
        """
        if self.target_lesson_id is not None:
            # Replace any lesson header with target ID
            pattern = r'(?i)^\s*lesson\s+\d{1,3}\b'
            text = re.sub(pattern, f'Lesson {self.target_lesson_id}', text, count=1)
        
        # Standardize "Lesson N" capitalization
        text = re.sub(r'(?i)(lesson)\s+(\d)', r'Lesson \2', text)
        
        # Fix spaced numbers in ranges like "Lesson 1 to 5"
        text = re.sub(r'(\d)\s+to\s+(\d)', r'\1 to \2', text)
        
        return text


class FormattingFixer:
    """Fixes formatting artifacts from PDF extraction."""
    
    # Fix </em></b>  -> </em></b>\n
    CLOSE_PATTERN = re.compile(r'(</[biuems]+>)\s+(biuems]+>)')
    
    # Fix .?=<[T -> . T (PDF keystoning issue)
    KEYSTONE_PATTERN = re.compile(r'\.T\b')
    
    def normalize(self, text: str) -> str:
        """Fix formatting artifacts.
        
        Args:
            text: Input text with formatting issues.
            
        Returns:
            Text with formatting fixed.
        """
        # Add newlines between styled blocks
        text = self.CLOSE_PATTERN.sub(r'\1\n', text)
        
        # Fix keystoning
        text = self.KEYSTONE_PATTERN.sub('. T', text)
        
        return text


class NormalizationPipeline:
    """A pipeline of normalization stages.
    
    Applies multiple normalization functions in sequence,
    allowing for easy debugging and extension.
    """
    
    def __init__(self):
        self._stages: list[NormalizationStage] = []
    
    def add_stage(
        self, 
        name: str, 
        func: NormalizerFn, 
        description: str = ""
    ) -> 'NormalizationPipeline':
        """Add a normalization stage to the pipeline.
        
        Args:
            name: Name of the stage.
            func: Normalization function.
            description: What this stage does.
            
        Returns:
            Self for chaining.
        """
        self._stages.append(NormalizationStage(
            name=name,
            func=func,
            description=description,
        ))
        return self
    
    def normalize(self, text: str, debug: bool = False) -> str:
        """Apply all normalization stages.
        
        Args:
            text: Input text.
            debug: If True, return debug info about stages.
            
        Returns:
            Normalized text.
        """
        result = text
        
        for stage in self._stages:
            result = stage.func(result)
        
        return result
    
    @property
    def stages(self) -> list[NormalizationStage]:
        """Return list of stages."""
        return self._stages.copy()
    
    @classmethod
    def default_pipeline(cls) -> 'NormalizationPipeline':
        """Create the default normalization pipeline.
        
        Returns:
            Configured pipeline with standard stages.
        """
        pipeline = cls()
        
        # Stage 1: Basic fixes
        pipeline.add_stage(
            "hyphenation",
            HyphenationFixer().normalize,
            "Fix hyphenation at line breaks"
        )
        
        # Stage 2: Paragraph joining
        pipeline.add_stage(
            "paragraphs",
            ParagraphJoiner().normalize,
            "Join fragmented paragraphs"
        )
        
        # Stage 3: CRITICAL - Separate lesson headers onto their own lines
        pipeline.add_stage(
            "lesson_headers",
            LessonHeaderSeparator().normalize,
            "Ensure lesson headers are on separate lines"
        )
        
        # Stage 4: Spacing fixes
        pipeline.add_stage(
            "spacing",
            SpacingFixer().normalize,
            "Fix spacing after punctuation and quotes"
        )
        
        # Stage 5: Formatting fixes
        pipeline.add_stage(
            "formatting",
            FormattingFixer().normalize,
            "Fix PDF formatting artifacts"
        )
        
        # Stage 6: Lesson header normalization
        pipeline.add_stage(
            "headers",
            LessonHeaderNormalizer().normalize,
            "Normalize lesson headers"
        )
        
        return pipeline


def normalize_text(text: str) -> str:
    """Convenience function to normalize text.
    
    Args:
        text: Input text from PDF extraction.
        
    Returns:
        Normalized text ready for parsing.
    """
    pipeline = NormalizationPipeline.default_pipeline()
    return pipeline.normalize(text)


def normalize_for_dump(text: str) -> str:
    """Normalize text specifically for dump file output.
    
    This applies stricter normalization suitable for
    inspection/dump files.
    
    Args:
        text: Input text.
        
    Returns:
        Normalized text for dumps.
    """
    # Use default pipeline plus additional fixes
    pipeline = NormalizationPipeline.default_pipeline()
    
    # Add extra cleanup stage
    def final_cleanup(t: str) -> str:
        t = re.sub(r'\n{3,}', '\n\n', t)
        t = t.strip()
        return t
    
    pipeline.add_stage("cleanup", final_cleanup, "Final cleanup")
    
    return pipeline.normalize(text)
