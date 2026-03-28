"""
Workflow Coordinator for Swarm Telegram Approval System

Manages synchronization between the swarm workflow execution and the Telegram approval requests.

Key responsibilities:
- Tracking active approval request sessions for workflows
- Providing blocking mechanisms for workflow nodes that need to wait for approval
- Resuming blocked workflows when approval responses arrive
- Managing lifecycle of workflow sessions

This solves the critical issue where workflows request approval but never know when it's received.
"""

import asyncio
import logging
from typing import Dict, Callable, Awaitable, Any
from dataclasses import dataclass, field
from enum import Enum


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"
    RETRY = "retry"


@dataclass
class WorkflowApprovalSession:
    """
    Tracks a single approval request session.
    """

    request_id: str
    workflow_instance: Any  # The actual workflow instance that's waiting
    approval_callback: Callable[[str], Awaitable[None]]  # Function to call when approval received
    timeout: float | None = 300.0  # 5 minutes default timeout
    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    updated_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    status: ApprovalStatus = ApprovalStatus.PENDING
    timeout_task: asyncio.Task | None = None
    resume_condition: asyncio.Event | None = None  # Event that unblocks waiting workflow
    retry_feedback: str | None = None


class WorkflowCoordinator:
    """
    Singleton coordinator that manages workflow approval sessions.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.sessions: Dict[str, WorkflowApprovalSession] = {}
        self.logger = logging.getLogger(__name__)
        self._lock = asyncio.Lock()
        self._initialized = True

    async def create_session(
        self,
        request_id: str,
        workflow_instance: Any,
        approval_callback: Callable[[str], Awaitable[None]],
        timeout: float | None = 300.0,
    ) -> WorkflowApprovalSession:
        """
        Create a new approval request session that will block until approval is received.

        Args:
            request_id: Unique identifier for this approval request
            workflow_instance: Reference to the workflow that is waiting
            approval_callback: Function to call when approval is received
            timeout: Max time to wait before marking as expired (seconds)

        Returns:
            WorkflowApprovalSession that blocks until approval is received
        """
        async with self._lock:
            # Create the resume condition event that will block the workflow
            resume_condition = asyncio.Event()

            session = WorkflowApprovalSession(
                request_id=request_id,
                workflow_instance=workflow_instance,
                approval_callback=approval_callback,
                timeout=timeout,
                resume_condition=resume_condition,
            )

            self.sessions[request_id] = session
            self.logger.info(f"[workflow-coordinator] Created session {request_id}")

            # Set up timeout mechanism
            if timeout:
                session.timeout_task = asyncio.create_task(self._handle_timeout(request_id, timeout))

            return session

    async def wait_for_approval(self, request_id: str) -> ApprovalStatus:
        """
        Block the calling workflow until approval is received for the given request.

        Args:
            request_id: The ID of the approval request to wait for

        Returns:
            ApprovalStatus indicating the outcome
        """
        session = self.sessions.get(request_id)
        if not session:
            self.logger.warning(f"[workflow-coordinator] No session found for {request_id}")
            return ApprovalStatus.DECLINED  # Default to declined if session not found

        # Wait for the resume condition to be signaled
        await session.resume_condition.wait()

        # Return the final status
        return session.status

    async def approve_request(self, request_id: str) -> bool:
        """
        Mark an approval request as approved, thus resuming the waiting workflow.

        Args:
            request_id: ID of the request to approve

        Returns:
            True if successfully approved, False otherwise
        """
        async with self._lock:
            session = self.sessions.get(request_id)
            if not session:
                self.logger.warning(f"[workflow-coordinator] No session found for approve {request_id}")
                return False

            # Cancel any timeout task
            if session.timeout_task:
                session.timeout_task.cancel()

            # Update status and resume the blocked workflow
            session.status = ApprovalStatus.APPROVED
            session.updated_at = asyncio.get_event_loop().time()

            # Call the callback function to update workflow state
            try:
                await session.approval_callback(ApprovalStatus.APPROVED.value)
            except Exception as e:
                self.logger.error(f"[workflow-coordinator] Callback error in approve_request: {e}")
            session.resume_condition.set()  # Wake up the waiting workflow!

            self.logger.info(f"[workflow-coordinator] Approved request {request_id}")
            return True

    async def decline_request(self, request_id: str) -> bool:
        """
        Mark an approval request as declined, thus resuming the waiting workflow.

        Args:
            request_id: ID of the request to decline

        Returns:
            True if successfully declined, False otherwise
        """
        async with self._lock:
            session = self.sessions.get(request_id)
            if not session:
                self.logger.warning(f"[workflow-coordinator] No session found for decline {request_id}")
                return False

            # Cancel timeout
            if session.timeout_task:
                session.timeout_task.cancel()

            # Update status and resume workflow
            session.status = ApprovalStatus.DECLINED
            session.updated_at = asyncio.get_event_loop().time()

            # Call the callback to update workflow state
            try:
                await session.approval_callback(ApprovalStatus.DECLINED.value)
            except Exception as e:
                self.logger.error(f"[workflow-coordinator] Callback error in decline_request: {e}")
            session.resume_condition.set()

            self.logger.info(f"[workflow-coordinator] Declined request {request_id}")
            return True

    async def retry_request(self, request_id: str, feedback: str) -> bool:
        """
        Mark an approval request for retry with feedback.

        Args:
            request_id: ID of the request to retry
            feedback: Feedback from user for adjustment

        Returns:
            True if successfully set to retry, False otherwise
        """
        async with self._lock:
            session = self.sessions.get(request_id)
            if not session:
                self.logger.warning(f"[workflow-coordinator] No session found for retry {request_id}")
                return False

            # Cancel timeout
            if session.timeout_task:
                session.timeout_task.cancel()

            # Store feedback and update status
            session.retry_feedback = feedback
            session.status = ApprovalStatus.RETRY
            session.updated_at = asyncio.get_event_loop().time()

            # Call the callback to update workflow state with feedback
            try:
                await session.approval_callback(ApprovalStatus.RETRY.value)
            except Exception as e:
                self.logger.error(f"[workflow-coordinator] Callback error in retry_request: {e}")
            session.resume_condition.set()

            self.logger.info(
                f"[workflow-coordinator] Retry requested for {request_id} with feedback: {feedback[:100]}..."
            )
            return True

    async def _handle_timeout(self, request_id: str, timeout: float):
        """
        Private method to handle session timeouts.
        """
        try:
            await asyncio.sleep(timeout)

            async with self._lock:
                session = self.sessions.get(request_id)
                if session and session.status == ApprovalStatus.PENDING:
                    # Time is up, force resolution (default to decline)
                    session.status = ApprovalStatus.DECLINED

                # Call the callback to notify of timeout
                try:
                    await session.approval_callback(ApprovalStatus.DECLINED.value)
                except Exception as e:
                    self.logger.error(f"[workflow-coordinator] Timeout callback error: {e}")
                if session.resume_condition:
                    session.resume_condition.set()

                self.logger.warning(f"[workflow-coordinator] Request {request_id} timed out, defaulted to declined")

        except asyncio.CancelledError:
            self.logger.debug(f"[workflow-coordinator] Timeout task cancelled for {request_id}")
        except Exception as e:
            self.logger.error(f"[workflow-coordinator] Error handling timeout for {request_id}: {e}")

    async def cleanup_expired_sessions(self, max_age_hours: float = 24.0):
        """
        Remove expired sessions to prevent memory leaks.
        """
        now = asyncio.get_event_loop().time()
        expired_ids = []

        async with self._lock:
            for req_id, session in self.sessions.items():
                if now - session.created_at > (max_age_hours * 3600):
                    expired_ids.append(req_id)

            for req_id in expired_ids:
                session = self.sessions.pop(req_id, None)
                if session and session.timeout_task:
                    session.timeout_task.cancel()
                self.logger.info(f"[workflow-coordinator] Cleaned up expired session {req_id}")

        return len(expired_ids)

    async def cleanup_expired_sessions_coroutine(self, max_age_hours: float = 24.0) -> int:
        """
        Async version of cleanup_expired_sessions.

        Args:
            max_age_hours: Maximum age of sessions to keep (default: 24 hours)

        Returns:
            Number of sessions cleaned up
        """
        now = asyncio.get_event_loop().time()
        expired_ids = []

        async with self._lock:
            for req_id, session in self.sessions.items():
                if now - session.created_at > (max_age_hours * 3600):
                    expired_ids.append(req_id)

            for req_id in expired_ids:
                session = self.sessions.pop(req_id, None)
                if session and session.timeout_task:
                    session.timeout_task.cancel()
                self.logger.info(f"[workflow-coordinator] Cleaned up expired session {req_id}")

        return len(expired_ids)

    async def get_session_status(self, request_id: str) -> ApprovalStatus | None:
        """
        Get the status of a particular request.
        """
        session = self.sessions.get(request_id)
        return session.status if session else None


# Global coordinator instance
coordinator = WorkflowCoordinator()
