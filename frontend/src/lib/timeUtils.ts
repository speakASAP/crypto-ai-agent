/**
 * Common time utility functions for consistent timestamp handling
 * Used across currency rates and crypto prices
 */

export type DataFreshness = 'fresh' | 'recent' | 'stale';

export interface TimestampDisplay {
  formatted: string;
  relative: string;
  freshness: DataFreshness;
  iso: string;
}

/**
 * Get relative time string (e.g., "2h ago", "30s ago")
 */
export const getRelativeTime = (timestamp: string): string => {
  if (!timestamp) return 'Unknown';
  
  try {
    const now = new Date();
    const time = new Date(timestamp);
    const diffMs = now.getTime() - time.getTime();
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    const diffSeconds = Math.floor(diffMs / 1000);
    
    if (diffSeconds < 60) {
      return `${diffSeconds}s ago`;
    } else if (diffMinutes < 60) {
      return `${diffMinutes}m ago`;
    } else if (diffMinutes < 1440) {
      const hours = Math.floor(diffMinutes / 60);
      return `${hours}h ago`;
    } else {
      const days = Math.floor(diffMinutes / 1440);
      return `${days}d ago`;
    }
  } catch (error) {
    return 'Invalid time';
  }
};

/**
 * Get data freshness status based on timestamp age
 */
export const getDataFreshness = (timestamp: string): DataFreshness => {
  if (!timestamp) return 'stale';
  
  try {
    const now = new Date();
    const time = new Date(timestamp);
    const diffMs = now.getTime() - time.getTime();
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    
    if (diffMinutes < 1) return 'fresh';
    if (diffMinutes < 5) return 'recent';
    return 'stale';
  } catch (error) {
    return 'stale';
  }
};

/**
 * Format timestamp for display (e.g., "2025-10-24 19:22:09 UTC")
 */
export const formatTimestamp = (timestamp: string): string => {
  if (!timestamp) return 'Never updated';
  
  try {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZone: 'UTC',
      timeZoneName: 'short'
    });
  } catch (error) {
    return 'Invalid timestamp';
  }
};

/**
 * Get comprehensive timestamp display information
 */
export const getTimestampDisplay = (timestamp: string): TimestampDisplay => {
  return {
    formatted: formatTimestamp(timestamp),
    relative: getRelativeTime(timestamp),
    freshness: getDataFreshness(timestamp),
    iso: timestamp
  };
};

/**
 * Get freshness color class for UI
 */
export const getFreshnessColorClass = (freshness: DataFreshness): string => {
  switch (freshness) {
    case 'fresh':
      return 'bg-green-500';
    case 'recent':
      return 'bg-yellow-500';
    case 'stale':
      return 'bg-red-500';
    default:
      return 'bg-gray-500';
  }
};

/**
 * Check if timestamp is valid
 */
export const isValidTimestamp = (timestamp: string): boolean => {
  if (!timestamp) return false;
  try {
    const date = new Date(timestamp);
    return !isNaN(date.getTime());
  } catch (error) {
    return false;
  }
};

/**
 * Get current timestamp in ISO format
 */
export const getCurrentTimestamp = (): string => {
  return new Date().toISOString();
};
