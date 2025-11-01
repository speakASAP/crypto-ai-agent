/**
 * Centralized logging utility for frontend
 * Respects DEBUG flag - only logs to console in development (DEBUG=true)
 * In production (DEBUG=false), NO console output at all - everything goes to logs only
 */

const isDebug = process.env.NEXT_PUBLIC_DEBUG === 'true' || process.env.NEXT_PUBLIC_DEBUG === '1';

class Logger {
  private isDebugMode: boolean;

  constructor() {
    this.isDebugMode = isDebug;
  }

  private shouldLog(): boolean {
    // Only log to console if DEBUG is enabled
    // In production, NO console output - all logs go to server logs only
    return this.isDebugMode;
  }

  log(...args: any[]): void {
    if (this.shouldLog()) {
      console.log(...args);
    }
  }

  error(...args: any[]): void {
    if (this.shouldLog()) {
      console.error(...args);
    }
  }

  warn(...args: any[]): void {
    if (this.shouldLog()) {
      console.warn(...args);
    }
  }

  info(...args: any[]): void {
    if (this.shouldLog()) {
      console.info(...args);
    }
  }

  debug(...args: any[]): void {
    if (this.shouldLog()) {
      console.debug(...args);
    }
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

