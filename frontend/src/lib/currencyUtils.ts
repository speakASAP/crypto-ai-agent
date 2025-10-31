/**
 * Unified currency formatting utilities for consistent display across the application
 */

export type Currency = 'USD' | 'EUR' | 'CZK'

// Currency to locale mapping for proper symbol display
const currencyToLocale: Record<Currency, string> = {
  'USD': 'en-US',
  'EUR': 'de-DE', 
  'CZK': 'cs-CZ'
}

// Currency symbols for display
const currencySymbols: Record<Currency, string> = {
  'USD': '$',
  'EUR': '€',
  'CZK': 'Kč'
}

/**
 * Format a number as currency with proper locale formatting
 * Ensures negative numbers always show minus sign
 */
export function formatCurrency(amount: number, currency: Currency = 'USD'): string {
  const locale = currencyToLocale[currency]
  const formatted = new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(amount)
  
  // Ensure negative values have minus sign (some locales may use parentheses or other formats)
  if (amount < 0) {
    // Remove parentheses if present and add minus sign
    if (formatted.includes('(') && formatted.includes(')')) {
      return formatted.replace(/\(([^)]+)\)/, '-$1')
    }
    // If no minus sign is present, add it before the currency symbol or number
    if (!formatted.includes('-')) {
      // For CZK: "-123,45 Kč" format
      // For USD/EUR: "-$123.45" format
      const symbol = getCurrencySymbol(currency)
      if (symbol === '$' || symbol === '€') {
        return formatted.replace(new RegExp(`\\${symbol}`), `-${symbol}`)
      } else {
        return formatted.replace(/(\d)/, '-$1')
      }
    }
  }
  return formatted
}

/**
 * Format a number as currency with no decimal places (for whole numbers)
 * Ensures negative numbers always show minus sign
 */
export function formatCurrencyWhole(amount: number, currency: Currency = 'USD'): string {
  const locale = currencyToLocale[currency]
  const formatted = new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  }).format(amount)
  
  // Ensure negative values have minus sign (some locales may use parentheses or other formats)
  if (amount < 0) {
    // Remove parentheses if present and add minus sign
    if (formatted.includes('(') && formatted.includes(')')) {
      return formatted.replace(/\(([^)]+)\)/, '-$1')
    }
    // If no minus sign is present, add it before the currency symbol or number
    if (!formatted.includes('-')) {
      const symbol = getCurrencySymbol(currency)
      if (symbol === '$' || symbol === '€') {
        return formatted.replace(new RegExp(`\\${symbol}`), `-${symbol}`)
      } else {
        return formatted.replace(/(\d)/, '-$1')
      }
    }
  }
  return formatted
}

/**
 * Format a number as currency with spaces for thousands separators
 * This provides better readability for large numbers
 * Ensures negative numbers always show minus sign
 */
export function formatCurrencyWithSpaces(amount: number, currency: Currency = 'USD'): string {
  const locale = currencyToLocale[currency]
  const formatted = new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(amount)
  
  // Ensure negative values have minus sign (some locales may use parentheses or other formats)
  let result = formatted
  if (amount < 0) {
    // Remove parentheses if present and add minus sign
    if (result.includes('(') && result.includes(')')) {
      result = result.replace(/\(([^)]+)\)/, '-$1')
    }
    // If no minus sign is present, add it before the currency symbol or number
    if (!result.includes('-')) {
      const symbol = getCurrencySymbol(currency)
      if (symbol === '$' || symbol === '€') {
        result = result.replace(new RegExp(`\\${symbol}`), `-${symbol}`)
      } else {
        result = result.replace(/(\d)/, '-$1')
      }
    }
  }
  
  // Add spaces for better readability (replace commas with spaces for CZK, keep commas for others)
  if (currency === 'CZK') {
    return result.replace(/,/g, ' ')
  }
  return result
}

/**
 * Format a percentage with proper sign and decimal places
 * Ensures negative percentages always show minus sign
 */
export function formatPercent(percent: number | null | undefined, decimals: number = 2): string {
  if (percent === null || percent === undefined || isNaN(percent)) {
    return 'N/A'
  }
  // Always show minus sign for negative values
  const sign = percent >= 0 ? '+' : '-'
  return `${sign}${Math.abs(percent).toFixed(decimals)}%`
}

/**
 * Format a number with spaces for thousands separators (for non-currency values)
 * Ensures negative numbers always show minus sign
 */
export function formatNumberWithSpaces(amount: number, decimals: number = 2): string {
  const formatted = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  }).format(amount)
  
  // Ensure negative values have minus sign
  let result = formatted
  if (amount < 0) {
    // Remove parentheses if present and add minus sign
    if (result.includes('(') && result.includes(')')) {
      result = result.replace(/\(([^)]+)\)/, '-$1')
    }
    // If no minus sign is present, add it
    if (!result.includes('-')) {
      result = result.replace(/^(\d)/, '-$1')
    }
  }
  
  return result.replace(/,/g, ' ')
}

/**
 * Parse a formatted number string back to a number (removes spaces and commas)
 */
export function parseFormattedNumber(value: string): number {
  return parseFloat(value.replace(/[\s,]/g, '')) || 0
}

/**
 * Get currency symbol for a given currency
 */
export function getCurrencySymbol(currency: Currency): string {
  return currencySymbols[currency]
}

/**
 * Format amount with currency symbol and proper spacing
 * Ensures negative numbers always show minus sign
 */
export function formatAmountWithSymbol(amount: number, currency: Currency = 'USD'): string {
  const symbol = getCurrencySymbol(currency)
  // Use Math.abs to format the number, then add sign manually
  const absAmount = Math.abs(amount)
  const formatted = formatNumberWithSpaces(absAmount, 2)
  
  // Add minus sign for negative values
  const sign = amount < 0 ? '-' : ''
  
  // Add currency symbol with proper spacing
  if (symbol === '$' || symbol === '€') {
    return `${sign}${symbol}${formatted}`
  } else {
    return `${sign}${formatted} ${symbol}`
  }
}

/**
 * Format crypto amount with proper decimal places
 */
export function formatCryptoAmount(amount: number, symbol: string): string {
  // Use more decimal places for crypto amounts
  const decimals = amount < 0.01 ? 8 : amount < 1 ? 6 : 4
  return formatNumberWithSpaces(amount, decimals)
}

/**
 * Format investment text with proper currency formatting
 */
export function formatInvestmentText(amount: number, currency: Currency): string {
  if (!amount || amount === 0) {
    return `0 ${currency}`
  }
  
  // Format number with commas for thousands
  const formatted_amount = amount >= 1 
    ? formatNumberWithSpaces(amount, 0) 
    : formatNumberWithSpaces(amount, 8).replace(/\.?0+$/, '')
  
  const symbol = getCurrencySymbol(currency)
  return symbol === '$' || symbol === '€' 
    ? `${symbol}${formatted_amount}` 
    : `${formatted_amount} ${symbol}`
}
