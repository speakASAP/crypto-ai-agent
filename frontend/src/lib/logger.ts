/**
 * Centralized logging utility for frontend
 * All logs are sent to the backend API for centralized logging
 * Console output is only used in development (DEBUG=true) for local debugging
 */

const isDebug = process.env.NEXT_PUBLIC_DEBUG === 'true' || process.env.NEXT_PUBLIC_DEBUG === '1';
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class Logger {
  private isDebugMode: boolean;
  private logQueue: Array<{ level: string; message: string; context?: string; metadata?: any }> = [];

  constructor() {
    this.isDebugMode = isDebug;
    
    // Note: We use fetch directly instead of API client to avoid circular dependencies
    // API client is not needed since we're just sending logs via fetch
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

  private async sendToBackend(level: string, message: string, context?: string, metadata?: any): Promise<void> {
    // Only send logs in browser environment
    if (typeof window === 'undefined') {
      return;
    }

    // Don't block on log sending - fire and forget
    try {
      const logEntry = {
        level,
        message,
        context: context || 'frontend',
        metadata: metadata || {},
        timestamp: new Date().toISOString(),
        url: window.location.href,
        user_agent: navigator.userAgent,
      };

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

  private log(level: string, context: string, ...args: any[]): void {
    const message = this.formatMessage(args);
    
    // Always send to backend (centralized logging)
    this.sendToBackend(level, message, context);

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
    this.log('log', 'app', ...args);
  }

  error(...args: any[]): void {
    this.log('error', 'app', ...args);
  }

  warn(...args: any[]): void {
    this.log('warn', 'app', ...args);
  }

  info(...args: any[]): void {
    this.log('info', 'app', ...args);
  }

  debug(...args: any[]): void {
    this.log('debug', 'app', ...args);
  }

  // Context-aware logging methods
  withContext(context: string) {
    return {
      log: (...args: any[]) => this.log('log', context, ...args),
      error: (...args: any[]) => this.log('error', context, ...args),
      warn: (...args: any[]) => this.log('warn', context, ...args),
      info: (...args: any[]) => this.log('info', context, ...args),
      debug: (...args: any[]) => this.log('debug', context, ...args),
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

