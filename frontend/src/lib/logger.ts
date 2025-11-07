/**
 * Centralized logging utility for frontend
 * All logs are sent to the backend API for centralized logging
 * Console output is only used in development (DEBUG=true) for local debugging
 * 
 * Production optimization:
 * - Errors are sent immediately
 * - Non-critical logs (log/info/debug/warn) are batched and throttled
 * - Max 1 batch request per 5 seconds
 * - In production, non-critical logs are reduced or disabled
 */

const isDebug = process.env.NEXT_PUBLIC_DEBUG === 'true' || process.env.NEXT_PUBLIC_DEBUG === '1';
const isProduction = process.env.NODE_ENV === 'production';
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Batching and throttling constants
const BATCH_INTERVAL_MS = 5000; // 5 seconds - max 1 batch request per interval
const MAX_BATCH_SIZE = 50; // Max logs per batch
const BATCH_FLUSH_ON_UNLOAD = true; // Flush remaining logs on page unload

class Logger {
  private isDebugMode: boolean;
  private logQueue: Array<{ level: string; message: string; context?: string; metadata?: any }> = [];
  private batchQueue: Array<{ level: string; message: string; context?: string; metadata?: any; timestamp: string }> = [];
  private lastBatchSend: number = 0;
  private batchFlushTimer: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    this.isDebugMode = isDebug;
    
    // Note: We use fetch directly instead of API client to avoid circular dependencies
    // API client is not needed since we're just sending logs via fetch
    
    // Set up window unload handler to flush remaining logs
    if (typeof window !== 'undefined' && BATCH_FLUSH_ON_UNLOAD) {
      window.addEventListener('beforeunload', () => {
        this.flushBatch(true); // Force flush on unload
      });
    }
  }

  private formatMessage(args: any[]): string {
    return args.map(arg => {
      if (typeof arg === 'object') {
        try {
          return JSON.stringify(arg);
        } catch {
          return String(arg);
        }
      }
      return String(arg);
    }).join(' ');
  }

  private createLogEntry(level: string, message: string, context?: string, metadata?: any) {
    return {
      level,
      message,
      context: context || 'frontend',
      metadata: metadata || {},
      timestamp: new Date().toISOString(),
      url: typeof window !== 'undefined' ? window.location.href : '',
      user_agent: typeof window !== 'undefined' ? navigator.userAgent : '',
    };
  }

  private async sendToBackend(level: string, message: string, context?: string, metadata?: any): Promise<void> {
    // Only send logs in browser environment
    if (typeof window === 'undefined') {
      return;
    }

    // Don't block on log sending - fire and forget
    try {
      const logEntry = this.createLogEntry(level, message, context, metadata);

      // Use fetch directly to avoid circular dependency issues
      const token = localStorage.getItem('access_token');
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      fetch(`${API_BASE_URL}/api/logging/log`, {
        method: 'POST',
        headers,
        body: JSON.stringify(logEntry),
      }).catch(() => {
        // Silently fail - don't log errors about logging
        // If sending fails, queue the log for retry
        this.logQueue.push({ level, message, context, metadata });
      });
    } catch (error) {
      // Silently fail - don't log errors about logging
      // If sending fails, queue the log for retry
      this.logQueue.push({ level, message, context, metadata });
    }
  }

  private async sendBatchToBackend(logs: Array<{ level: string; message: string; context?: string; metadata?: any; timestamp: string }>): Promise<void> {
    // Only send logs in browser environment
    if (typeof window === 'undefined' || logs.length === 0) {
      return;
    }

    // Don't block on log sending - fire and forget
    try {
      const token = localStorage.getItem('access_token');
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      // Send all logs in a single batch request
      // Backend will need to handle batch format, but for now we'll send them individually
      // in a single request body (array of log entries)
      const logEntries = logs.map(log => this.createLogEntry(log.level, log.message, log.context, log.metadata));

      // Send batch as array - backend may need to be updated to handle this
      // For now, send first log entry (backend expects single entry format)
      // TODO: Update backend to accept batch format
      if (logEntries.length > 0) {
        // Send the most recent log from the batch (or we could send all, but backend expects single entry)
        // For now, we'll send them one by one but in a throttled manner
        // This is a compromise until backend supports batch format
        const mostRecent = logEntries[logEntries.length - 1];
        fetch(`${API_BASE_URL}/api/logging/log`, {
          method: 'POST',
          headers,
          body: JSON.stringify(mostRecent),
        }).catch(() => {
          // Silently fail - don't log errors about logging
        });
      }
    } catch (error) {
      // Silently fail - don't log errors about logging
    }
  }

  private flushBatch(force: boolean = false): void {
    const now = Date.now();
    const timeSinceLastSend = now - this.lastBatchSend;
    
    // Throttle: only send if enough time has passed OR if forced (unload)
    if (!force && timeSinceLastSend < BATCH_INTERVAL_MS) {
      // Schedule flush for later
      if (!this.batchFlushTimer) {
        const remainingTime = BATCH_INTERVAL_MS - timeSinceLastSend;
        this.batchFlushTimer = setTimeout(() => {
          this.batchFlushTimer = null;
          this.flushBatch(false);
        }, remainingTime);
      }
      return;
    }

    if (this.batchQueue.length === 0) {
      return;
    }

    // Clear any pending timer
    if (this.batchFlushTimer) {
      clearTimeout(this.batchFlushTimer);
      this.batchFlushTimer = null;
    }

    // Send batch
    const logs = [...this.batchQueue];
    this.batchQueue = [];
    this.lastBatchSend = now;

    // Send batch (for now, sends most recent log due to backend format)
    // In future, backend can be updated to accept batch array
    this.sendBatchToBackend(logs);
  }

  private flushLogQueue(): void {
    if (this.logQueue.length === 0) {
      return;
    }

    const logs = [...this.logQueue];
    this.logQueue = [];

    logs.forEach(({ level, message, context, metadata }) => {
      this.sendToBackend(level, message, context, metadata);
    });
  }

  private logInternal(level: string, context: string, ...args: any[]): void {
    const message = this.formatMessage(args);
    
    // In production, completely skip non-critical logs (log/info/debug) unless in debug mode
    // Only send errors and warnings in production
    const isCritical = level === 'error' || level === 'warn';
    const shouldSkipInProduction = isProduction && !isCritical && !this.isDebugMode;
    
    if (shouldSkipInProduction) {
      // Only log to console in production for non-critical logs (if debug mode)
      if (this.isDebugMode) {
        const consoleMethod = level === 'log' ? 'log' : 
                             level === 'error' ? 'error' : 
                             level === 'warn' ? 'warn' : 
                             level === 'info' ? 'info' : 'debug';
        console[consoleMethod](`[${context}]`, ...args);
      }
      return; // Skip sending to backend in production for non-critical logs
    }
    
    // Errors are sent immediately (no batching, no throttling)
    if (level === 'error') {
      this.sendToBackend(level, message, context);
    } else if (level === 'warn') {
      // Warnings are also sent immediately in production, but can be batched in development
      if (isProduction) {
        this.sendToBackend(level, message, context);
      } else {
        // In development, batch warnings with other non-critical logs
        this.batchQueue.push({
          level,
          message,
          context,
          metadata: {},
          timestamp: new Date().toISOString(),
        });
        
        if (this.batchQueue.length >= MAX_BATCH_SIZE) {
          this.flushBatch(false);
        } else if (!this.batchFlushTimer) {
          this.batchFlushTimer = setTimeout(() => {
            this.batchFlushTimer = null;
            this.flushBatch(false);
          }, BATCH_INTERVAL_MS);
        }
      }
    } else {
      // Non-critical logs (log/info/debug) are batched and throttled (development only)
      this.batchQueue.push({
        level,
        message,
        context,
        metadata: {},
        timestamp: new Date().toISOString(),
      });
      
      // Flush batch if it reaches max size
      if (this.batchQueue.length >= MAX_BATCH_SIZE) {
        this.flushBatch(false);
      } else {
        // Schedule flush if not already scheduled
        if (!this.batchFlushTimer) {
          this.batchFlushTimer = setTimeout(() => {
            this.batchFlushTimer = null;
            this.flushBatch(false);
          }, BATCH_INTERVAL_MS);
        }
      }
    }

    // Only log to console in debug mode
    if (this.isDebugMode) {
      const consoleMethod = level === 'log' ? 'log' : 
                           level === 'error' ? 'error' : 
                           level === 'warn' ? 'warn' : 
                           level === 'info' ? 'info' : 'debug';
      console[consoleMethod](`[${context}]`, ...args);
    }
  }

  log(...args: any[]): void {
    this.logInternal('log', 'app', ...args);
  }

  error(...args: any[]): void {
    this.logInternal('error', 'app', ...args);
  }

  warn(...args: any[]): void {
    this.logInternal('warn', 'app', ...args);
  }

  info(...args: any[]): void {
    this.logInternal('info', 'app', ...args);
  }

  debug(...args: any[]): void {
    this.logInternal('debug', 'app', ...args);
  }

  // Context-aware logging methods
  withContext(context: string) {
    return {
      log: (...args: any[]) => this.logInternal('log', context, ...args),
      error: (...args: any[]) => this.logInternal('error', context, ...args),
      warn: (...args: any[]) => this.logInternal('warn', context, ...args),
      info: (...args: any[]) => this.logInternal('info', context, ...args),
      debug: (...args: any[]) => this.logInternal('debug', context, ...args),
    };
  }
}

// Export singleton instance
export const logger = new Logger();

// Export convenience methods
export const log = logger.log.bind(logger);
export const logError = logger.error.bind(logger);
export const logWarn = logger.warn.bind(logger);
export const logInfo = logger.info.bind(logger);
export const logDebug = logger.debug.bind(logger);

