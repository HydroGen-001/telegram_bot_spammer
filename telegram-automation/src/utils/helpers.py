"""
Helper utilities
"""

from typing import Any, Dict, Optional
from datetime import timedelta


def format_duration(seconds: int) -> str:
    """
    Format duration in human-readable format
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        Formatted string (e.g., "2h 30m 15s")
    """
    if seconds < 60:
        return f"{seconds}s"
    
    if seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    return f"{hours}h {minutes}m {secs}s"


def format_number(num: int) -> str:
    """
    Format number with thousands separator
    
    Args:
        num: Number to format
    
    Returns:
        Formatted string (e.g., "1,234")
    """
    return f"{num:,}"


def safe_get(
    data: Dict[str, Any],
    path: str,
    default: Any = None
) -> Any:
    """
    Safely get nested dictionary value
    
    Args:
        data: Dictionary
        path: Dot-separated path (e.g., "user.name")
        default: Default value if not found
    
    Returns:
        Value or default
    """
    keys = path.split('.')
    value = data
    
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    
    return value


def truncate_text(text: str, max_length: int = 50) -> str:
    """
    Truncate text to max length with ellipsis
    
    Args:
        text: Text to truncate
        max_length: Maximum length
    
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + "..."


def parse_chat_id(chat_input: str) -> str:
    """
    Parse chat input to proper format
    
    Args:
        chat_input: Chat ID or username
    
    Returns:
        Normalized chat ID string
    """
    chat_input = chat_input.strip()
    
    # Remove @ prefix if present
    if chat_input.startswith('@'):
        return chat_input[1:]
    
    return chat_input


async def retry_async(
    coro_func,
    max_retries: int = 3,
    delay_seconds: float = 1.0,
    backoff_multiplier: float = 2.0
):
    """
    Retry async function with exponential backoff
    
    Args:
        coro_func: Async function to retry
        max_retries: Maximum retry attempts
        delay_seconds: Initial delay
        backoff_multiplier: Delay multiplier
    
    Returns:
        Function result
    
    Raises:
        Last exception if all retries failed
    """
    import asyncio
    
    last_exception = None
    delay = delay_seconds
    
    for attempt in range(max_retries):
        try:
            return await coro_func()
        except Exception as e:
            last_exception = e
            
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
                delay *= backoff_multiplier
    
    raise last_exception
