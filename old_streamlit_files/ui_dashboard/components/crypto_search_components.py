"""
Cryptocurrency Search Components for Crypto AI Agent Dashboard
Reusable components for cryptocurrency symbol search and selection
"""

import streamlit as st
import pandas as pd
import asyncio
from typing import List, Dict, Optional, Callable
import sys
import os

# Add utils directory to path for centralized logging
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'utils'))
from utils.logger import (
    get_logger, log_function_entry, log_function_exit, log_user_action,
    log_error_with_context, log_info_with_context
)

class CryptoSearchComponents:
    """Reusable cryptocurrency search and selection components"""
    
    def __init__(self):
        self.logger = get_logger("crypto_search_components")
    
    @staticmethod
    def display_crypto_search_form(search_callback: Callable, add_callback: Callable, 
                                 placeholder: str = "Search cryptocurrencies (e.g., BTC, Bitcoin, Cardano)"):
        """Display cryptocurrency search form with real-time autocomplete functionality"""
        log_function_entry("display_crypto_search_form", "crypto_search_components")
        
        # Import and use the real-time search component
        from .real_time_search import RealTimeSearch
        RealTimeSearch.display_search_with_autocomplete(search_callback, add_callback, placeholder)
        
        log_function_exit("display_crypto_search_form", "crypto_search_components")
    
    @staticmethod
    def display_crypto_selector(available_symbols: List[Dict], add_callback: Callable, 
                              title: str = "Select Cryptocurrency"):
        """Display a dropdown selector for cryptocurrencies"""
        log_function_entry("display_crypto_selector", "crypto_search_components", symbols_count=len(available_symbols))
        
        if not available_symbols:
            st.info("No cryptocurrencies available. Please refresh the symbol database.")
            log_function_exit("display_crypto_selector", "crypto_search_components", result="no_symbols")
            return
        
        st.subheader(f"📋 {title}")
        
        # Create options for selectbox
        options = []
        symbol_to_data = {}
        
        for symbol_data in available_symbols:
            display_text = f"{symbol_data['symbol']} - {symbol_data['name']}"
            options.append(display_text)
            symbol_to_data[display_text] = symbol_data
        
        # Display selector
        selected_option = st.selectbox(
            "Choose a cryptocurrency:",
            options=options,
            key="crypto_selector",
            help="Select from available cryptocurrencies"
        )
        
        # Add button
        if st.button("Add Selected Cryptocurrency", key="add_selected_crypto"):
            if selected_option:
                selected_data = symbol_to_data[selected_option]
                add_callback(selected_data['symbol'])
                st.success(f"Added {selected_data['symbol']} to tracking")
                st.rerun()
        
        log_function_exit("display_crypto_selector", "crypto_search_components", result="selector_displayed")
    
    @staticmethod
    def display_popular_cryptocurrencies(add_callback: Callable):
        """Display popular cryptocurrencies for quick selection"""
        log_function_entry("display_popular_cryptocurrencies", "crypto_search_components")
        
        st.subheader("⭐ Popular Cryptocurrencies")
        
        # Popular cryptocurrencies with descriptions
        popular_crypto = [
            {"symbol": "BTC", "name": "Bitcoin", "description": "The first and largest cryptocurrency"},
            {"symbol": "ETH", "name": "Ethereum", "description": "Smart contract platform and cryptocurrency"},
            {"symbol": "BNB", "name": "Binance Coin", "description": "Binance exchange native token"},
            {"symbol": "ADA", "name": "Cardano", "description": "Proof-of-stake blockchain platform"},
            {"symbol": "SOL", "name": "Solana", "description": "High-performance blockchain platform"},
            {"symbol": "DOT", "name": "Polkadot", "description": "Multi-chain blockchain protocol"},
            {"symbol": "MATIC", "name": "Polygon", "description": "Ethereum scaling solution"},
            {"symbol": "AVAX", "name": "Avalanche", "description": "Fast and low-cost blockchain platform"},
            {"symbol": "LINK", "name": "Chainlink", "description": "Decentralized oracle network"},
            {"symbol": "UNI", "name": "Uniswap", "description": "Decentralized exchange protocol"}
        ]
        
        # Display in a grid
        cols = st.columns(2)
        
        for i, crypto in enumerate(popular_crypto):
            with cols[i % 2]:
                with st.container():
                    st.write(f"**{crypto['symbol']}** - {crypto['name']}")
                    st.caption(crypto['description'])
                    
                    if st.button(f"Add {crypto['symbol']}", key=f"add_popular_{crypto['symbol']}"):
                        add_callback(crypto['symbol'])
                        st.success(f"Added {crypto['symbol']} to tracking")
                        st.rerun()
        
        log_function_exit("display_popular_cryptocurrencies", "crypto_search_components")
    
    @staticmethod
    def display_crypto_search_sidebar(search_callback: Callable, add_callback: Callable):
        """Display cryptocurrency search in sidebar"""
        log_function_entry("display_crypto_search_sidebar", "crypto_search_components")
        
        st.sidebar.subheader("🔍 Search Cryptocurrencies")
        
        # Search input
        search_query = st.sidebar.text_input(
            "Search:",
            placeholder="BTC, Bitcoin, etc.",
            key="sidebar_crypto_search",
            help="Search by symbol or name"
        )
        
        # Search results
        if search_query and len(search_query.strip()) >= 1:
            try:
                search_results = search_callback(search_query.strip())
                
                if search_results:
                    st.sidebar.write(f"**Found {len(search_results)} results:**")
                    
                    for i, result in enumerate(search_results[:10]):  # Limit to 10 in sidebar
                        col1, col2 = st.sidebar.columns([3, 1])
                        
                        with col1:
                            st.sidebar.write(f"{result['symbol']} - {result['name']}")
                        
                        with col2:
                            if st.sidebar.button("+", key=f"sidebar_add_{result['symbol']}_{i}"):
                                add_callback(result['symbol'])
                                st.sidebar.success(f"Added {result['symbol']}")
                                st.rerun()
                else:
                    st.sidebar.info("No results found")
                    
            except Exception as e:
                log_error_with_context(e, "display_crypto_search_sidebar", "crypto_search_components", query=search_query)
                st.sidebar.error("Search error")
        
        log_function_exit("display_crypto_search_sidebar", "crypto_search_components")
    
    @staticmethod
    def display_crypto_database_status(symbol_count: int, last_updated: Optional[str] = None):
        """Display cryptocurrency database status"""
        log_function_entry("display_crypto_database_status", "crypto_search_components", symbol_count=symbol_count)
        
        st.subheader("📊 Cryptocurrency Database Status")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Available Cryptocurrencies", symbol_count)
        
        with col2:
            if last_updated:
                st.metric("Last Updated", last_updated)
            else:
                st.metric("Last Updated", "Unknown")
        
        # Refresh button
        if st.button("🔄 Refresh Cryptocurrency Database", key="refresh_crypto_db"):
            st.info("Refreshing database... This may take a moment.")
            # The refresh logic should be handled by the calling function
            st.rerun()
        
        log_function_exit("display_crypto_database_status", "crypto_search_components")
