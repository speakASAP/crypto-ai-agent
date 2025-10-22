"""
Real-time search component for Streamlit
Provides better search experience with immediate feedback
"""

import streamlit as st
from typing import List, Dict, Callable
import time

class RealTimeSearch:
    """Real-time search component for cryptocurrencies"""
    
    @staticmethod
    def display_search_with_autocomplete(search_callback: Callable, add_callback: Callable, 
                                       placeholder: str = "Search cryptocurrencies (e.g., BTC, Bitcoin, Cardano)"):
        """Display search with autocomplete functionality"""
        
        st.subheader("🔍 Search Cryptocurrencies")
        
        # Initialize session state
        if 'search_query' not in st.session_state:
            st.session_state.search_query = ""
        if 'search_results' not in st.session_state:
            st.session_state.search_results = []
        if 'last_search_time' not in st.session_state:
            st.session_state.last_search_time = 0
        
        # Search input
        search_query = st.text_input(
            "Search by symbol or name:",
            value=st.session_state.search_query,
            placeholder=placeholder,
            key="search_input",
            help="Type to search for cryptocurrencies by symbol (BTC) or full name (Bitcoin)"
        )
        
        # Update session state
        st.session_state.search_query = search_query
        
        # Perform search with debouncing
        current_time = time.time()
        if (search_query and len(search_query.strip()) >= 1 and 
            current_time - st.session_state.last_search_time > 0.5):  # 500ms debounce
            
            try:
                search_results = search_callback(search_query.strip())
                st.session_state.search_results = search_results
                st.session_state.last_search_time = current_time
            except Exception as e:
                st.error(f"Error searching: {str(e)}")
                st.session_state.search_results = []
        
        # Display results
        if search_query and len(search_query.strip()) >= 1:
            search_results = st.session_state.search_results
            
            if search_results:
                st.write(f"**Found {len(search_results)} results:**")
                
                # Display results in a scrollable container
                with st.container():
                    for i, result in enumerate(search_results[:20]):  # Limit to 20 results
                        col1, col2, col3 = st.columns([2, 4, 2])
                        
                        with col1:
                            st.write(f"**{result['symbol']}**")
                        
                        with col2:
                            st.write(f"**{result['name']}**")
                            if result.get('description'):
                                st.caption(result['description'])
                        
                        with col3:
                            if st.button("Add", key=f"add_{result['symbol']}_{i}"):
                                add_callback(result['symbol'])
                                st.success(f"Added {result['symbol']} to tracking")
                                # Clear search
                                st.session_state.search_query = ""
                                st.session_state.search_results = []
                                st.rerun()
            else:
                st.info("No cryptocurrencies found matching your search.")
        
        # Show instructions
        if not search_query:
            st.info("💡 **Tip**: Start typing to search for cryptocurrencies. You can search by symbol (BTC) or full name (Bitcoin).")
    
    @staticmethod
    def display_portfolio_search(search_callback: Callable, add_callback: Callable):
        """Display search for portfolio selection"""
        
        st.write("**Select Cryptocurrency:**")
        
        # Initialize session state
        if 'portfolio_search_query' not in st.session_state:
            st.session_state.portfolio_search_query = ""
        if 'portfolio_search_results' not in st.session_state:
            st.session_state.portfolio_search_results = []
        if 'portfolio_last_search_time' not in st.session_state:
            st.session_state.portfolio_last_search_time = 0
        
        # Search input
        search_query = st.text_input(
            "Search cryptocurrency:", 
            value=st.session_state.portfolio_search_query,
            placeholder="Type BTC, Bitcoin, Cardano, etc.",
            key="portfolio_search_input",
            help="Search by symbol or full name"
        )
        
        # Update session state
        st.session_state.portfolio_search_query = search_query
        
        # Perform search with debouncing
        current_time = time.time()
        if (search_query and len(search_query.strip()) >= 1 and 
            current_time - st.session_state.portfolio_last_search_time > 0.5):  # 500ms debounce
            
            try:
                search_results = search_callback(search_query.strip())
                st.session_state.portfolio_search_results = search_results
                st.session_state.portfolio_last_search_time = current_time
            except Exception as e:
                st.error(f"Error searching: {str(e)}")
                st.session_state.portfolio_search_results = []
        
        # Display results
        if search_query and len(search_query.strip()) >= 1:
            search_results = st.session_state.portfolio_search_results
            
            if search_results:
                st.write("**Search Results:**")
                
                for i, result in enumerate(search_results[:10]):  # Limit to 10 results
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        if st.button(f"**{result['symbol']}** - {result['name']}", key=f"select_{result['symbol']}_{i}"):
                            st.session_state.selected_portfolio_symbol = result['symbol']
                            st.session_state.portfolio_search_query = ""
                            st.session_state.portfolio_search_results = []
                            st.rerun()
                    with col2:
                        if result.get('description'):
                            st.caption(result['description'])
            else:
                st.info("No cryptocurrencies found matching your search.")
        
        # Show selected symbol
        if 'selected_portfolio_symbol' in st.session_state:
            selected_symbol = st.session_state.selected_portfolio_symbol
            st.success(f"Selected: {selected_symbol}")
            if st.button("Clear Selection", key="clear_portfolio_selection"):
                del st.session_state.selected_portfolio_symbol
                st.rerun()
