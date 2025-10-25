'use client'

import { useState, useEffect, useRef } from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { CryptoSymbol } from '@/types'
import { apiClient } from '@/lib/api'

interface CryptoSearchSelectProps {
  value: string
  onValueChange: (value: string) => void
  onSymbolSelect: (symbol: CryptoSymbol) => void
  placeholder?: string
  disabled?: boolean
}

export function CryptoSearchSelect({ 
  value, 
  onValueChange, 
  onSymbolSelect, 
  placeholder = "Type to search cryptocurrencies...",
  disabled = false
}: CryptoSearchSelectProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [symbols, setSymbols] = useState<CryptoSymbol[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedSymbol, setSelectedSymbol] = useState<CryptoSymbol | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Debounced search
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (searchQuery.length >= 2) {
        searchSymbols(searchQuery)
      } else if (searchQuery.length === 0) {
        loadPopularSymbols()
      }
    }, 300)

    return () => clearTimeout(timeoutId)
  }, [searchQuery])

  // Load popular symbols on mount
  useEffect(() => {
    loadPopularSymbols()
  }, [])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const loadPopularSymbols = async () => {
    setLoading(true)
    try {
      const data = await apiClient.getCryptoSymbols(50) // Load top 50 by market cap
      setSymbols(data)
    } catch (error) {
      console.error('Failed to load crypto symbols:', error)
    } finally {
      setLoading(false)
    }
  }

  const searchSymbols = async (query: string) => {
    setLoading(true)
    try {
      const data = await apiClient.searchCryptoSymbols(query, 20)
      setSymbols(data)
    } catch (error) {
      console.error('Failed to search crypto symbols:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const query = e.target.value
    setSearchQuery(query)
    onValueChange(query)
    
    if (query.length >= 2) {
      setIsOpen(true)
    } else if (query.length === 0) {
      setIsOpen(true)
    }
  }

  const handleSymbolSelect = (symbol: CryptoSymbol) => {
    setSelectedSymbol(symbol)
    setSearchQuery(symbol.symbol)
    onValueChange(symbol.symbol)
    onSymbolSelect(symbol)
    setIsOpen(false)
  }

  const handleInputFocus = () => {
    setIsOpen(true)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setIsOpen(false)
    }
  }

  return (
    <div className="space-y-2">
      <Label htmlFor="crypto-search">Cryptocurrency</Label>
      <div className="relative" ref={dropdownRef}>
        <Input
          ref={inputRef}
          id="crypto-search"
          type="text"
          value={searchQuery}
          onChange={handleInputChange}
          onFocus={handleInputFocus}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          className="w-full"
        />
        
        {isOpen && (
          <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-md shadow-lg max-h-60 overflow-auto">
            {loading ? (
              <div className="px-3 py-2 text-sm text-gray-500">
                Loading...
              </div>
            ) : symbols.length > 0 ? (
              symbols.map((symbol) => (
                <div
                  key={symbol.symbol}
                  className="px-3 py-2 text-sm cursor-pointer hover:bg-gray-100 flex items-center justify-between"
                  onClick={() => handleSymbolSelect(symbol)}
                >
                  <div className="flex flex-col">
                    <span className="font-medium">{symbol.symbol}</span>
                    <span className="text-xs text-gray-500">{symbol.name}</span>
                  </div>
                  {symbol.market_cap_rank && (
                    <span className="text-xs text-gray-400">
                      #{symbol.market_cap_rank}
                    </span>
                  )}
                </div>
              ))
            ) : searchQuery.length >= 2 ? (
              <div className="px-3 py-2 text-sm text-gray-500">
                No cryptocurrencies found for "{searchQuery}"
              </div>
            ) : (
              <div className="px-3 py-2 text-sm text-gray-500">
                Type at least 2 characters to search
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
