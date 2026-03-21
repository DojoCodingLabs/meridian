"""Meridian - Product Profitability Prediction Engine."""

__version__ = "0.1.0"

# Lazy imports to avoid requiring heavy dependencies (torch, etc.)
# for lightweight usage like economic behavior and segment generation.


def __getattr__(name):
    """Lazy-load heavy modules only when accessed."""
    _lazy_map = {
        "LLMAction": "meridian.environment.env_action",
        "ManualAction": "meridian.environment.env_action",
        "make": "meridian.environment.make",
        "SocialAgent": "meridian.market_agent.agent",
        "AgentGraph": "meridian.market_agent.agent_graph",
        "UserInfo": "meridian.market_platform.config",
        "Platform": "meridian.market_platform.platform",
        "ActionType": "meridian.market_platform.typing",
        "DefaultPlatformType": "meridian.market_platform.typing",
    }
    if name in _lazy_map:
        import importlib
        module = importlib.import_module(_lazy_map[name])
        return getattr(module, name)
    raise AttributeError(f"module 'meridian' has no attribute {name!r}")


__all__ = [
    "make", "Platform", "ActionType", "DefaultPlatformType", "ManualAction",
    "LLMAction", "AgentGraph", "SocialAgent", "UserInfo",
]
