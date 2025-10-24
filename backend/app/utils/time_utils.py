"""
Common time utility functions for consistent timestamp handling
Used across currency rates and crypto prices
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any


def format_timestamp(timestamp: Optional[datetime]) -> str:
    """Format timestamp for display (e.g., '2025-10-24 19:22:09 UTC')"""
    if not timestamp:
        return "Never updated"
    
    try:
        # Ensure timestamp is timezone-aware
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        
        return timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return "Invalid timestamp"


def get_iso_timestamp(timestamp: Optional[datetime] = None) -> str:
    """Get ISO format timestamp for API responses"""
    if timestamp:
        # Ensure timestamp is timezone-aware
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.isoformat()
    else:
        return datetime.now(timezone.utc).isoformat()


def get_current_timestamp() -> datetime:
    """Get current timestamp in UTC"""
    return datetime.now(timezone.utc)


def is_valid_timestamp(timestamp: Any) -> bool:
    """Check if timestamp is valid"""
    if not timestamp:
        return False
    
    try:
        if isinstance(timestamp, datetime):
            return True
        elif isinstance(timestamp, str):
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return True
        return False
    except (ValueError, TypeError):
        return False


def get_timestamp_display_info(timestamp: Optional[datetime]) -> Dict[str, str]:
    """Get comprehensive timestamp display information"""
    if not timestamp:
        return {
            "formatted": "Never updated",
            "iso": "",
            "relative": "Unknown"
        }
    
    return {
        "formatted": format_timestamp(timestamp),
        "iso": get_iso_timestamp(timestamp),
        "relative": get_relative_time(timestamp)
    }


def get_relative_time(timestamp: datetime) -> str:
    """Get relative time string (e.g., '2h ago', '30s ago')"""
    try:
        now = datetime.now(timezone.utc)
        
        # Ensure timestamp is timezone-aware
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        
        diff = now - timestamp
        total_seconds = int(diff.total_seconds())
        
        if total_seconds < 60:
            return f"{total_seconds}s ago"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes}m ago"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            return f"{hours}h ago"
        else:
            days = total_seconds // 86400
            return f"{days}d ago"
    except Exception:
        return "Invalid time"


def get_data_freshness(timestamp: Optional[datetime]) -> str:
    """Get data freshness status based on timestamp age"""
    if not timestamp:
        return "stale"
    
    try:
        now = datetime.now(timezone.utc)
        
        # Ensure timestamp is timezone-aware
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        
        diff = now - timestamp
        diff_minutes = int(diff.total_seconds() / 60)
        
        if diff_minutes < 1:
            return "fresh"
        elif diff_minutes < 5:
            return "recent"
        else:
            return "stale"
    except Exception:
        return "stale"
