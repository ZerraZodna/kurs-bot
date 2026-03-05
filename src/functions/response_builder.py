"""
Response Builder for ACIM Course Bot.

Builds final responses by combining natural language text from the AI
with results from executed function calls.
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from .executor import BatchExecutionResult, ExecutionResult
from src.core.timezone import format_datetime_for_display

logger = logging.getLogger(__name__)


@dataclass
class BuiltResponse:
    """Final built response with text and metadata."""
    text: str
    has_function_results: bool = False
    successful_functions: List[str] = field(default_factory=list)
    failed_functions: List[str] = field(default_factory=list)
    follow_up_prompt: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "has_function_results": self.has_function_results,
            "successful_functions": self.successful_functions,
            "failed_functions": self.failed_functions,
            "follow_up_prompt": self.follow_up_prompt,
            "metadata": self.metadata,
        }


class ResponseBuilder:
    """Builds responses combining natural language with function results."""
    
    # Templates for different result types
    SUCCESS_TEMPLATES = {
        "create_schedule": "✓ Daily reminder set for {time}",
        "update_schedule": "✓ Schedule updated to {time}",
        "delete_schedule": "✓ Schedule removed",
        "query_schedule": "Here are your reminders:\n{details}",
        "create_one_time_reminder": "✓ One-time reminder set for {run_at}",
        "send_lesson": "📖 **Lesson {lesson_id}**: {title}\n\n{content}",
        "send_next_lesson": "📖 **Lesson {lesson_id}**: {title}\n\n{content}",
        "send_todays_lesson": "📖 **Lesson {lesson_id}**: {title}\n\n{content}",
        "mark_lesson_complete": "✓ Lesson marked complete",
        "repeat_lesson": "📖 **Lesson {lesson_id}** (repeat): {title}\n\n{content}",
        "set_lesson_preference": "✓ Lesson preference set to {preference}",
        "set_timezone": "✓ Timezone set to {timezone}",
        "set_language": "✓ Language set to {language}",
        "set_preferred_time": "✓ Preferred time set to {time}",
        "update_profile": "✓ Profile updated: {key}",
        "enter_rag": "✓ RAG mode enabled",
        "exit_rag": "✓ RAG mode disabled",
        "confirm_yes": "✓ Confirmed",
        "confirm_no": "✓ Noted",
        "extract_memory": "✓ Remembered: {key}",
    }
    
    ERROR_TEMPLATES = {
        "create_schedule": "I couldn't set up that schedule. {error}",
        "update_schedule": "I couldn't update the schedule. {error}",
        "delete_schedule": "I couldn't remove that schedule. {error}",
        "query_schedule": "I couldn't retrieve your schedules. {error}",
        "create_one_time_reminder": "I couldn't set that reminder. {error}",
        "send_lesson": "I couldn't find that lesson. {error}",
        "send_next_lesson": "I couldn't get the next lesson. {error}",
        "send_todays_lesson": "I couldn't get today's lesson. {error}",
        "mark_lesson_complete": "I couldn't mark the lesson complete. {error}",
        "repeat_lesson": "I couldn't repeat the lesson. {error}",
        "set_lesson_preference": "I couldn't set that preference. {error}",
        "set_timezone": "I couldn't set that timezone. {error}",
        "set_language": "I couldn't set that language. {error}",
        "set_preferred_time": "I couldn't set that time. {error}",
        "update_profile": "I couldn't update your profile. {error}",
        "enter_rag": "I couldn't enable RAG mode. {error}",
        "exit_rag": "I couldn't disable RAG mode. {error}",
        "confirm_yes": "",
        "confirm_no": "",
        "extract_memory": "I couldn't store that information. {error}",
    }
    
    def __init__(self):
        self.success_templates = self.SUCCESS_TEMPLATES.copy()
        self.error_templates = self.ERROR_TEMPLATES.copy()
    
    def build(
        self,
        user_text: str,
        ai_response_text: str,
        execution_result: BatchExecutionResult,
        include_function_results: bool = True,
    ) -> BuiltResponse:
        """
        Build a final response combining AI text and function results.
        
        Args:
            user_text: Original user message
            ai_response_text: Natural language response from AI
            execution_result: Results from executing functions
            include_function_results: Whether to append function result summaries
            
        Returns:
            BuiltResponse with final text and metadata
        """
        successful = execution_result.get_successful_results()
        failed = execution_result.get_failed_results()
        
        # Start with AI's natural language response
        final_text = ai_response_text.strip() if ai_response_text else ""
        
        # Build function result summaries if needed
        if include_function_results and (successful or failed):
            function_summaries = self._build_function_summaries(successful, failed)
            
            # Append to AI response if not empty
            if function_summaries:
                if final_text:
                    final_text += "\n\n"
                final_text += function_summaries
        
        # Determine follow-up prompt if needed
        follow_up = self._determine_follow_up(successful, failed, user_text)
        
        # Build metadata
        metadata = {
            "total_functions": len(execution_result.results),
            "successful_count": len(successful),
            "failed_count": len(failed),
            "execution_time_ms": execution_result.total_execution_time_ms,
        }
        
        return BuiltResponse(
            text=final_text,
            has_function_results=bool(successful or failed),
            successful_functions=[r.function_name for r in successful],
            failed_functions=[r.function_name for r in failed],
            follow_up_prompt=follow_up,
            metadata=metadata,
        )
    
    def _build_function_summaries(
        self,
        successful: List[ExecutionResult],
        failed: List[ExecutionResult],
    ) -> str:
        """Build human-readable summary of function results."""
        parts = []
        
        # Group successful results by type
        if successful:
            success_parts = []
            for result in successful:
                summary = self._format_success_result(result)
                if summary:
                    success_parts.append(summary)
            
            if success_parts:
                parts.extend(success_parts)
        
        # Add failed results
        if failed:
            for result in failed:
                summary = self._format_error_result(result)
                if summary:
                    parts.append(summary)
        
        return "\n".join(parts) if parts else ""
    
    def _format_success_result(self, result: ExecutionResult) -> Optional[str]:
        """Format a successful function result."""
        template = self.success_templates.get(result.function_name)
        if not template:
            return None
        
        # Extract relevant fields from result
        result_data = result.result or {}
        
        # Build format kwargs
        kwargs = {}
        if result.function_name in ["create_schedule", "update_schedule", "set_preferred_time"]:
            kwargs["time"] = result_data.get("time", "the specified time")
        elif result.function_name == "create_one_time_reminder":
            kwargs["run_at"] = format_datetime_for_display(result_data.get("run_at"))
        elif result.function_name in ["send_lesson", "send_next_lesson", "send_todays_lesson", "repeat_lesson"]:
            kwargs["lesson_id"] = result_data.get("lesson_id", "")
            kwargs["title"] = result_data.get("title", "ACIM Lesson")
            kwargs["content"] = result_data.get("content", "")
        elif result.function_name == "set_lesson_preference":
            kwargs["preference"] = result_data.get("preference", "custom")
        elif result.function_name == "set_timezone":
            kwargs["timezone"] = result_data.get("timezone", "the specified timezone")
        elif result.function_name == "set_language":
            kwargs["language"] = result_data.get("language", "the specified language")
        elif result.function_name == "update_profile":
            kwargs["key"] = result_data.get("key", "profile")
        elif result.function_name == "extract_memory":
            kwargs["key"] = result_data.get("key", "information")
        elif result.function_name == "query_schedule":
            # Build schedule list
            schedules = result_data.get("schedules", [])
            # Get user's timezone for display
            tz_name = result_data.get("timezone", "UTC")
            
            if schedules:
                details = []
                for s in schedules:
                    schedule_type = s.get('schedule_type', 'reminder')
                    time_display = self._format_cron_expression(
                        s.get('cron_expression', ''),
                        s.get('next_send_time'),
                        tz_name
                    )
                    
                    # Map schedule types to friendly display names
                    type_display_map = {
                        'one_time_reminder': 'Remind once',
                        'daily': 'Daily reminder',
                    }
                    type_display = type_display_map.get(schedule_type, schedule_type.replace('_', ' '))
                    
                    # For one-time reminders, show the message if available
                    if schedule_type == 'one_time_reminder':
                        message = s.get('message', '')
                        if message:
                            details.append(f"  - {type_display} at {time_display} - \"{message}\"")
                        else:
                            details.append(f"  - {type_display} at {time_display}")
                    else:
                        status = "active" if s.get("is_active") else "inactive"
                        details.append(f"  - {type_display} at {time_display} ({status})")
                
                kwargs["details"] = "\n".join(details)
            else:
                kwargs["details"] = "No active reminders found."
            
            # Add timezone to output if available
            tz_name = result_data.get("timezone", "")
            if tz_name:
                kwargs["details"] += f"\n\n(Timezone: {tz_name})"

        try:
            return template.format(**kwargs)
        except KeyError:
            # Fallback if template formatting fails
            return f"✓ {result.function_name} completed"
    
    def _format_error_result(self, result: ExecutionResult) -> Optional[str]:
        """Format a failed function result."""
        template = self.error_templates.get(result.function_name)
        if not template:
            return f"⚠ {result.function_name} failed: {result.error}"
        
        kwargs = {"error": result.error or "Unknown error"}
        
        try:
            return template.format(**kwargs)
        except KeyError:
            return f"⚠ {result.function_name} failed: {result.error}"
    
    def _format_cron_expression(self, cron_expr: str, next_send_time: Any = None, tz_name: str = "UTC") -> str:
        """Format a cron expression or special time format into human-readable time.
        
        Args:
            cron_expr: The cron expression (e.g., "0 7 * * *") or special format (e.g., "once:2024-01-15T07:00:00")
            next_send_time: Optional datetime object or ISO format datetime string for one-time reminders
            tz_name: User's timezone for local time display
            
        Returns:
            Human-readable time string (e.g., "07:00", "2024-01-15 07:00")
        """
        # Handle datetime object (passed from executor with local timezone)
        from datetime import datetime
        from src.core.timezone import format_datetime_for_display as fdfd
        
        if isinstance(next_send_time, datetime):
            # Already a datetime object - format it directly
            return fdfd(next_send_time.isoformat())
        
        if not cron_expr:
            return "unknown"
        
        # Handle one-time reminder format: "once:ISO8601"
        if cron_expr.startswith("once:"):
            return fdfd(next_send_time) if next_send_time else "one-time"
        
        # Parse standard cron expression: "M H * * *"
        parts = cron_expr.split()
        if len(parts) >= 2:
            try:
                minute = int(parts[0])
                hour = int(parts[1])
                
                # Convert UTC hour/minute to user's local timezone
                from datetime import datetime, timezone as tz
                from zoneinfo import ZoneInfo
                try:
                    tzinfo = ZoneInfo(tz_name)
                except Exception:
                    tzinfo = tz.utc
                
                # Create a datetime in UTC and convert to user's timezone
                utc_dt = datetime(2000, 1, 1, hour, minute, 0, tzinfo=tz.utc)
                local_dt = utc_dt.astimezone(tzinfo)
                return f"{local_dt.hour:02d}:{local_dt.minute:02d}"
            except (ValueError, IndexError):
                pass
        
        # Fallback: return the raw expression
        return cron_expr

    def _determine_follow_up(
        self,
        successful: List[ExecutionResult],
        failed: List[ExecutionResult],
        user_text: str,
    ) -> Optional[str]:
        """Determine if a follow-up prompt is needed."""
        # If there are failures, suggest retry or clarification
        if failed:
            critical_failures = [
                r for r in failed 
                if r.function_name in ["create_schedule", "update_schedule", "set_timezone"]
            ]
            if critical_failures:
                return "Would you like to try again with different details?"
        
        # Check for specific follow-up scenarios
        for result in successful:
            if result.function_name == "create_schedule":
                return None  # No follow-up needed for successful schedule creation
            
            if result.function_name == "set_timezone":
                # Suggest setting preferred time after timezone
                return "Would you like to set your preferred lesson time as well?"
            
            if result.function_name == "send_lesson" and "repeat" not in result.function_name:
                # Suggest marking complete after sending lesson
                return "Let me know when you've completed this lesson!"
        
        return None
    
    def build_simple_response(
        self,
        ai_response_text: str,
        function_results: Optional[BatchExecutionResult] = None,
    ) -> str:
        """
        Build a simple text response (convenience method).
        
        Args:
            ai_response_text: Natural language response from AI
            function_results: Optional function execution results
            
        Returns:
            Final response text
        """
        if not function_results:
            return ai_response_text or ""
        
        built = self.build("", ai_response_text, function_results)
        return built.text
    
    def add_custom_template(self, function_name: str, success_template: str, error_template: Optional[str] = None):
        """Add or override a template for a function."""
        self.success_templates[function_name] = success_template
        if error_template:
            self.error_templates[function_name] = error_template
    
    def build_error_response(self, error_message: str, suggestion: Optional[str] = None) -> BuiltResponse:
        """
        Build a response for when something went wrong.
        
        Args:
            error_message: The error message to display
            suggestion: Optional suggestion for the user
            
        Returns:
            BuiltResponse with error information
        """
        text = f"I encountered an issue: {error_message}"
        if suggestion:
            text += f"\n\n{suggestion}"
        
        return BuiltResponse(
            text=text,
            has_function_results=False,
            successful_functions=[],
            failed_functions=[],
            follow_up_prompt=None,
            metadata={"error": True, "error_message": error_message},
        )


# Global instance
_builder: Optional[ResponseBuilder] = None


def get_response_builder() -> ResponseBuilder:
    """Get the global response builder instance."""
    global _builder
    if _builder is None:
        _builder = ResponseBuilder()
    return _builder


def reset_builder():
    """Reset the global instance (useful for testing)."""
    global _builder
    _builder = None
