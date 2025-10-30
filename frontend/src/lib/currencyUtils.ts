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
 */
export function formatCurrency(amount: number, currency: Currency = 'USD'): string {
  const locale = currencyToLocale[currency]
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(amount)
}

/**
 * Format a number as currency with no decimal places (for whole numbers)
 */
export function formatCurrencyWhole(amount: number, currency: Currency = 'USD'): string {
  const locale = currencyToLocale[currency]
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  }).format(amount)
}

/**
 * Format a number as currency with spaces for thousands separators
 * This provides better readability for large numbers
 */
export function formatCurrencyWithSpaces(amount: number, currency: Currency = 'USD'): string {
  const locale = currencyToLocale[currency]
  const formatted = new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(amount)
  
  // Add spaces for better readability (replace commas with spaces for CZK, keep commas for others)
  if (currency === 'CZK') {
    return formatted.replace(/,/g, ' ')
  }
  return formatted
}

/**
 * Format a percentage with proper sign and decimal places
 */
export function formatPercent(percent: number | null | undefined, decimals: number = 2): string {
  if (percent === null || percent === undefined || isNaN(percent)) {
    return 'N/A'
  }
  return `${percent >= 0 ? '+' : ''}${percent.toFixed(decimals)}%`
}

/**
 * Format a number with spaces for thousands separators (for non-currency values)
 */
export function formatNumberWithSpaces(amount: number, decimals: number = 2): string {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  }).format(amount).replace(/,/g, ' ')
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
 */
export function formatAmountWithSymbol(amount: number, currency: Currency = 'USD'): string {
  const symbol = getCurrencySymbol(currency)
  const formatted = formatNumberWithSpaces(amount, 2)
  
  // Add currency symbol with proper spacing
  if (symbol === '$' || symbol === '€') {
    return `${symbol}${formatted}`
  } else {
    return `${formatted} ${symbol}`
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
