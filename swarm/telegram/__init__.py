"""
Telegram Bot Module for Swarm Human-in-the-Loop System

This module provides the integration between the swarm workflow and the Telegram approval bot.
"""

from .integration import (
    SwarmTelegramIntegration,
    integration,
    request_approval,
    hook_request_prompt_approval,
    hook_request_final_approval,
    hook_send_swarm_complete_notification,
    hook_register_authorization,
    register_swarm_authorization,
)
from .telegram_swarm_polling import (
    state_manager,
    ApprovalRequest,
)

__all__ = [
    "SwarmTelegramIntegration",
    "integration",
    "request_approval",
    "hook_request_prompt_approval",
    "hook_request_final_approval",
    "hook_send_swarm_complete_notification",
    "hook_register_authorization",
    "state_manager",
    "ApprovalRequest",
    "register_swarm_authorization",
]
