"""
Symbol Management Components for Crypto AI Agent Dashboard
Reusable components for symbol tracking functionality
"""

import streamlit as st
import pandas as pd
from typing import Callable, Optional

class SymbolComponents:
    """Reusable symbol management components"""
    
    @staticmethod
    def display_add_symbol_form(add_callback: Callable):
        """Display form to add new symbol for tracking"""
        st.sidebar.subheader("Add New Symbol")
        new_symbol = st.sidebar.text_input("Enter symbol (e.g., BTC):", placeholder="BTC")
        if st.sidebar.button("Add Symbol") and new_symbol:
            add_callback(new_symbol.upper())
            st.sidebar.success(f"Added {new_symbol.upper()} to tracking")
            st.rerun()
    
    @staticmethod
    def display_active_symbols(symbols_df: pd.DataFrame, remove_callback: Callable):
        """Display active symbols with remove functionality"""
        if symbols_df.empty:
            return
        
        active_symbols = symbols_df[symbols_df['is_active'] == 1]
        if active_symbols.empty:
            return
        
        st.sidebar.write("**Active Symbols:**")
        for _, row in active_symbols.iterrows():
            col1, col2 = st.sidebar.columns([3, 1])
            with col1:
                st.write(row['symbol'])
            with col2:
                if st.button("Remove", key=f"remove_{row['symbol']}"):
                    remove_callback(row['symbol'])
                    st.sidebar.success(f"Removed {row['symbol']} from tracking")
                    st.rerun()
    
    @staticmethod
    def display_inactive_symbols(symbols_df: pd.DataFrame, restore_callback: Callable):
        """Display inactive symbols with restore functionality"""
        if symbols_df.empty:
            return
        
        inactive_symbols = symbols_df[symbols_df['is_active'] == 0]
        if inactive_symbols.empty:
            return
        
        st.sidebar.write("**Inactive Symbols:**")
        for _, row in inactive_symbols.iterrows():
            col1, col2 = st.sidebar.columns([3, 1])
            with col1:
                st.write(row['symbol'])
            with col2:
                if st.button("Restore", key=f"restore_{row['symbol']}"):
                    restore_callback(row['symbol'])
                    st.sidebar.success(f"Restored {row['symbol']} to tracking")
                    st.rerun()
    
    # @staticmethod
    # def display_symbols_overview(symbols_df: pd.DataFrame):
    #     """Display tracked symbols overview table - shows only active symbols"""
    #     # TEMPORARILY DISABLED FOR REFACTORING - Tracked Symbols Overview section removed
    #     st.subheader("Tracked Symbols Overview")
    #     if symbols_df.empty:
    #         st.info("No tracked symbols configured")
    #         return
    #     
    #     # Filter to show only active symbols
    #     active_symbols = symbols_df[symbols_df['is_active'] == 1]
    #     if active_symbols.empty:
    #         st.info("No active symbols configured")
    #         return
    #     
    #     # Convert is_active to readable format (all will be 'Active' now)
    #     active_symbols = active_symbols.copy()
    #     active_symbols['status'] = 'Active'
    #     display_df = active_symbols[['symbol', 'status', 'created_at']].copy()
    #     st.dataframe(display_df, width='stretch')
    
    @staticmethod
    def display_symbol_management_sidebar(symbols_df: pd.DataFrame, add_callback: Callable, 
                                        remove_callback: Callable, restore_callback: Callable = None):
        """Display complete symbol management sidebar"""
        st.sidebar.title("Symbol Management")
        
        # Add new symbol form
        SymbolComponents.display_add_symbol_form(add_callback)
        
        # Manage existing symbols
        if not symbols_df.empty:
            st.sidebar.subheader("Manage Tracked Symbols")
            SymbolComponents.display_active_symbols(symbols_df, remove_callback)
