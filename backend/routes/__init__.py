"""
Routes package
"""

from .auth import router as auth_router
from .nodes import router as nodes_router
from .honeypot import router as honeypot_router
from .agent import router as agent_router
from .alerts import router as alerts_router

__all__ = ["auth_router", "nodes_router", "honeypot_router", "agent_router", "alerts_router"]
