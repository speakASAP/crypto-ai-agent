import { apiClient } from './api'

/**
 * Shared refresh utility that can be used by both UI components and stores
 * This is the same logic as the refresh button in the UI
 */
export const refreshCryptoPrices = async () => {
  try {
    // Refresh crypto prices (same as refresh button)
    const cryptoResult = await apiClient.refreshCryptoPrices()
    
    console.log(`✅ Refreshed ${cryptoResult.symbols_count} crypto prices`)
    return cryptoResult
  } catch (error) {
    console.error('Failed to refresh crypto prices:', error)
    throw error
  }
}

/**
 * Full refresh including both currency rates and crypto prices
 * This is the complete refresh button functionality
 */
export const refreshAllData = async () => {
  try {
    // Refresh both currency rates and crypto prices simultaneously
    const [currencyResult, cryptoResult] = await Promise.all([
      apiClient.refreshExchangeRates(),
      apiClient.refreshCryptoPrices()
    ])
    
    console.log(`✅ Refreshed ${currencyResult.rates_count} currency rates and ${cryptoResult.symbols_count} crypto prices`)
    return { currencyResult, cryptoResult }
  } catch (error) {
    console.error('Failed to refresh data:', error)
    throw error
  }
}
