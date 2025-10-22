"""
Portfolio Management Components for Crypto AI Agent Dashboard
Reusable components for portfolio-related functionality with multi-currency support
"""

import streamlit as st
import pandas as pd
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

class PortfolioComponents:
    """Reusable portfolio management components"""
    
    @staticmethod
    def display_portfolio_summary(metrics: Dict[str, Any]):
        """Display portfolio summary metrics in cards"""
        if not metrics or metrics.get('total_value', 0) == 0:
            st.info("No portfolio data available. Add some coins to get started!")
            return
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Value", f"${metrics['total_value']:,.2f}")
        
        with col2:
            st.metric("Total Cost", f"${metrics['total_cost']:,.2f}")
        
        with col3:
            pnl_color = "normal" if metrics['total_pnl'] >= 0 else "inverse"
            st.metric("P&L", f"${metrics['total_pnl']:,.2f}", delta=f"{metrics['total_pnl_percent']:.2f}%")
        
        with col4:
            portfolio_count = len(metrics.get('portfolio_data', []))
            st.metric("Portfolio Items", portfolio_count)
    
    @staticmethod
    def display_portfolio_table(portfolio_data: pd.DataFrame):
        """Display formatted portfolio table with correct currency symbols"""
        if portfolio_data.empty:
            st.info("No portfolio holdings to display")
            return
        
        # Display enhanced portfolio table
        display_df = portfolio_data[['symbol', 'amount', 'price_buy', 'current_price', 'current_value', 'pnl', 'pnl_percent', 'base_currency']].copy()
        display_df.columns = ['Symbol', 'Amount', 'Buy Price', 'Current Price', 'Current Value', 'P&L', 'P&L %', 'Currency']
        
        # Format the dataframe with correct currency symbols
        def format_currency(value, currency):
            if currency == 'USD':
                return f"${value:,.2f}"
            elif currency == 'EUR':
                return f"€{value:,.2f}"
            elif currency == 'CZK':
                return f"{value:,.2f} Kč"
            else:
                return f"{value:,.2f} {currency}"
        
        # Convert numeric columns to object type to allow string formatting
        display_df['Buy Price'] = display_df['Buy Price'].astype('object')
        display_df['Current Price'] = display_df['Current Price'].astype('object')
        display_df['Current Value'] = display_df['Current Value'].astype('object')
        display_df['P&L'] = display_df['P&L'].astype('object')
        display_df['P&L %'] = display_df['P&L %'].astype('object')
        
        # Format each row with its original currency
        for idx, row in display_df.iterrows():
            currency = row['Currency']
            display_df.at[idx, 'Buy Price'] = format_currency(row['Buy Price'], currency)
            display_df.at[idx, 'Current Price'] = format_currency(row['Current Price'], currency)
            display_df.at[idx, 'Current Value'] = format_currency(row['Current Value'], currency)
            display_df.at[idx, 'P&L'] = format_currency(row['P&L'], currency)
            display_df.at[idx, 'P&L %'] = f"{row['P&L %']:.2f}%"
        
        # Remove the Currency column from display
        display_df = display_df.drop('Currency', axis=1)
        
        st.dataframe(display_df, width='stretch')
    
    @staticmethod
    def display_portfolio_table_with_actions(portfolio_data: pd.DataFrame, update_callback, delete_callback):
        """Display portfolio table with Edit and Remove buttons for each row"""
        if portfolio_data.empty:
            st.info("No portfolio holdings to display")
            return
        
        st.write("**Portfolio Holdings**")
        
        # Display each portfolio item with action buttons
        for idx, row in portfolio_data.iterrows():
            with st.container():
                col1, col2, col3, col4, col5, col6, col7, col8, col9 = st.columns([2, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1, 1])
                
                # Format currency values
                currency = row.get('base_currency', 'USD')
                def format_currency(value, currency):
                    if currency == 'USD':
                        return f"${value:,.2f}"
                    elif currency == 'EUR':
                        return f"€{value:,.2f}"
                    elif currency == 'CZK':
                        return f"{value:,.2f} Kč"
                    else:
                        return f"{value:,.2f} {currency}"
                
                with col1:
                    st.write(f"**{row['symbol']}**")
                with col2:
                    st.write(f"{row['amount']:,.6f}")
                with col3:
                    st.write(format_currency(row['price_buy'], currency))
                with col4:
                    st.write(format_currency(row['current_price'], currency))
                with col5:
                    st.write(format_currency(row['current_value'], currency))
                with col6:
                    pnl_color = "normal" if row['pnl'] >= 0 else "inverse"
                    st.write(format_currency(row['pnl'], currency))
                with col7:
                    pnl_percent_color = "normal" if row['pnl_percent'] >= 0 else "inverse"
                    st.write(f"{row['pnl_percent']:.2f}%")
                with col8:
                    if st.button("✏️", key=f"edit_{row['symbol']}_{idx}", help="Edit this coin"):
                        st.session_state[f"edit_{row['symbol']}_{idx}"] = True
                with col9:
                    if st.button("🗑️", key=f"delete_{row['symbol']}_{idx}", help="Remove this coin"):
                        delete_callback(row['symbol'])
                        st.success(f"Removed {row['symbol']} from portfolio")
                        st.rerun()
                
                # Edit form (appears when Edit button is clicked)
                if st.session_state.get(f"edit_{row['symbol']}_{idx}", False):
                    with st.expander(f"Edit {row['symbol']}", expanded=True):
                        PortfolioComponents._display_edit_form_enhanced(row, update_callback, idx)
                
                st.divider()
    
    @staticmethod
    def _display_edit_form_enhanced(row: pd.Series, update_callback, idx):
        """Display enhanced edit form for portfolio item"""
        with st.form(f"edit_form_{row['symbol']}_{idx}"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                new_amount = st.number_input("Amount", value=float(row['amount']), min_value=0.0, step=0.001, key=f"amount_{row['symbol']}_{idx}")
            with col2:
                new_price = st.number_input("Buy Price", value=float(row['price_buy']), min_value=0.0, step=0.01, key=f"price_{row['symbol']}_{idx}")
            with col3:
                new_currency = st.selectbox("Currency", ["USD", "EUR", "CZK"], index=["USD", "EUR", "CZK"].index(row.get('base_currency', 'USD')), key=f"currency_{row['symbol']}_{idx}")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.form_submit_button("✅ Update", use_container_width=True):
                    update_callback(row['symbol'], new_amount, new_price, new_currency)
                    st.session_state[f"edit_{row['symbol']}_{idx}"] = False
                    st.success(f"Updated {row['symbol']}")
                    st.rerun()
            with col2:
                if st.form_submit_button("❌ Cancel", use_container_width=True):
                    st.session_state[f"edit_{row['symbol']}_{idx}"] = False
                    st.rerun()
            with col3:
                if st.form_submit_button("🗑️ Delete", use_container_width=True):
                    # This will be handled by the delete callback
                    st.session_state[f"edit_{row['symbol']}_{idx}"] = False
                    st.rerun()
    
    @staticmethod
    def display_portfolio_management(portfolio_data: pd.DataFrame, update_callback, delete_callback):
        """Display portfolio management interface with edit/delete functionality"""
        if portfolio_data.empty:
            return
        
        st.subheader("Manage Holdings")
        for _, row in portfolio_data.iterrows():
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{row['symbol']}** - {row['amount']} coins")
            with col2:
                if st.button("Edit", key=f"edit_{row['symbol']}"):
                    st.session_state[f"edit_{row['symbol']}"] = True
            with col3:
                if st.button("Delete", key=f"delete_{row['symbol']}"):
                    delete_callback(row['symbol'])
                    st.success(f"Deleted {row['symbol']} from portfolio")
                    st.rerun()
            
            # Edit form (appears when Edit button is clicked)
            if st.session_state.get(f"edit_{row['symbol']}", False):
                PortfolioComponents._display_edit_form(row, update_callback)
    
    @staticmethod
    def _display_edit_form(row: pd.Series, update_callback):
        """Display edit form for portfolio item"""
        with st.form(f"edit_form_{row['symbol']}"):
            st.write(f"Edit {row['symbol']}")
            new_amount = st.number_input("Amount", value=float(row['amount']), min_value=0.0, step=0.001, key=f"amount_{row['symbol']}")
            new_price = st.number_input("Buy Price", value=float(row['price_buy']), min_value=0.0, step=0.01, key=f"price_{row['symbol']}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Update"):
                    update_callback(row['symbol'], new_amount, new_price)
                    st.session_state[f"edit_{row['symbol']}"] = False
                    st.success(f"Updated {row['symbol']}")
                    st.rerun()
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state[f"edit_{row['symbol']}"] = False
                    st.rerun()
    
    @staticmethod
    def display_add_coin_form(add_callback):
        """Display form to add new coin to portfolio"""
        st.subheader("Add New Coin to Portfolio")
        
        with st.form("add_coin_form"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                symbol = st.text_input("Symbol", placeholder="BTC", help="Enter the trading pair symbol (e.g., BTC)")
            
            with col2:
                amount = st.number_input("Amount", min_value=0.0, step=0.001, help="Number of coins you own")
            
            with col3:
                price_buy = st.number_input("Buy Price (USD)", min_value=0.0, step=0.01, help="Price per coin when you bought")
            
            if st.form_submit_button("Add to Portfolio", type="primary"):
                if symbol and amount > 0 and price_buy > 0:
                    add_callback(symbol, amount, price_buy)
                    st.success(f"Added {symbol.upper()} to portfolio!")
                    st.rerun()
                else:
                    st.error("Please fill in all fields with valid values")
    
    @staticmethod
    def display_performance_metrics(portfolio_data: pd.DataFrame):
        """Display portfolio performance metrics and charts"""
        if portfolio_data.empty:
            st.info("Add coins to your portfolio to see performance metrics")
            return
        
        st.subheader("Portfolio Performance")
        
        # Performance metrics
        col1, col2 = st.columns(2)
        
        with col1:
            best_performer = portfolio_data.loc[portfolio_data['pnl_percent'].idxmax()]
            st.metric("Best Performer", 
                     best_performer['symbol'],
                     f"{best_performer['pnl_percent']:.2f}%")
        
        with col2:
            worst_performer = portfolio_data.loc[portfolio_data['pnl_percent'].idxmin()]
            st.metric("Worst Performer", 
                     worst_performer['symbol'],
                     f"{worst_performer['pnl_percent']:.2f}%")
        
        # Simple performance chart
        if len(portfolio_data) > 1:
            st.subheader("P&L by Coin")
            chart_data = portfolio_data[['symbol', 'pnl_percent']].set_index('symbol')
            st.bar_chart(chart_data)
    
    @staticmethod
    def display_currency_selector():
        """Display currency selection controls"""
        col1, col2 = st.columns(2)
        
        with col1:
            selected_currency = st.selectbox(
                "Display Currency",
                ["CZK", "EUR", "USD"],
                help="Select the currency to display portfolio values in"
            )
        
        with col2:
            show_currency_rates = st.checkbox(
                "Show Currency Rates",
                help="Display current exchange rates"
            )
        
        return selected_currency, show_currency_rates
    
    @staticmethod
    def display_multi_currency_portfolio(portfolio_data: pd.DataFrame, currency_rates: Dict[str, float], target_currency: str = 'USD'):
        """Display portfolio in multiple currencies"""
        if portfolio_data.empty:
            st.info("No portfolio data available")
            return
        
        st.subheader(f"Portfolio Overview - {target_currency}")
        
        # Display currency rates if available
        if currency_rates:
            st.info(f"Current Exchange Rates: 1 USD = {currency_rates.get('EUR', 0):.4f} EUR, {currency_rates.get('CZK', 0):.2f} CZK")
        
        # Multi-currency summary cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_value = portfolio_data['current_value'].sum()
            st.metric("Total Value", f"{target_currency} {total_value:,.2f}")
        
        with col2:
            total_cost = portfolio_data['cost_basis'].sum()
            st.metric("Total Cost", f"{target_currency} {total_cost:,.2f}")
        
        with col3:
            total_pnl = portfolio_data['pnl'].sum()
            pnl_color = "normal" if total_pnl >= 0 else "inverse"
            st.metric("Total P&L", f"{target_currency} {total_pnl:,.2f}")
        
        with col4:
            total_pnl_percent = (total_pnl / total_cost * 100) if total_cost > 0 else 0
            st.metric("P&L %", f"{total_pnl_percent:.2f}%")
    
    @staticmethod
    def display_purchase_date_tracking(portfolio_data: pd.DataFrame):
        """Display purchase date tracking information"""
        if portfolio_data.empty:
            return
        
        st.subheader("Purchase History")
        
        # Check if purchase_date column exists
        if 'purchase_date' in portfolio_data.columns:
            # Display purchase timeline
            purchase_data = portfolio_data[['symbol', 'amount', 'price_buy', 'purchase_date', 'base_currency']].copy()
            purchase_data = purchase_data.sort_values('purchase_date', ascending=False)
            
            st.dataframe(purchase_data, width='stretch')
        else:
            st.info("Purchase date tracking not available. Update your portfolio entries to include purchase dates.")
    
    @staticmethod
    def display_multi_currency_metrics(portfolio_data: pd.DataFrame, target_currency: str = 'USD'):
        """Display multi-currency performance metrics"""
        if portfolio_data.empty:
            st.info("No portfolio data available")
            return
        
        st.subheader(f"Performance Metrics - {target_currency}")
        
        # Performance by currency
        if 'base_currency' in portfolio_data.columns:
            currency_performance = portfolio_data.groupby('base_currency').agg({
                'pnl': 'sum',
                'pnl_percent': 'mean',
                'current_value': 'sum'
            }).round(2)
            
            st.write("Performance by Original Currency:")
            st.dataframe(currency_performance, width='stretch')
        
        # Best and worst performers
        col1, col2 = st.columns(2)
        
        with col1:
            if not portfolio_data.empty:
                best_performer = portfolio_data.loc[portfolio_data['pnl_percent'].idxmax()]
                st.metric(
                    "Best Performer", 
                    best_performer['symbol'],
                    f"{target_currency} {best_performer['pnl']:,.2f} ({best_performer['pnl_percent']:.2f}%)"
                )
        
        with col2:
            if not portfolio_data.empty:
                worst_performer = portfolio_data.loc[portfolio_data['pnl_percent'].idxmin()]
                st.metric(
                    "Worst Performer", 
                    worst_performer['symbol'],
                    f"{target_currency} {worst_performer['pnl']:,.2f} ({worst_performer['pnl_percent']:.2f}%)"
                )
    
    @staticmethod
    def display_add_coin_form_multi_currency(add_callback, default_currency="USD"):
        """Display enhanced form to add new coin with multi-currency support
        
        Args:
            add_callback: Function to call when coin is added
            default_currency: Default currency for purchase (should match display currency)
        """
        st.subheader("Add New Coin to Portfolio")
        
        with st.form("add_coin_form_multi_currency"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                symbol = st.text_input("Symbol", placeholder="BTC", help="Enter the trading pair symbol (e.g., BTC)")
            
            with col2:
                amount_str = st.text_input("Amount", placeholder="0.00000000", help="Number of coins you own (e.g., 1.50000000)")
                try:
                    amount = float(amount_str) if amount_str else 0.0
                except ValueError:
                    amount = 0.0
                    if amount_str:
                        st.error("Invalid amount format. Use decimal point (.) not comma (,).")
            
            with col3:
                # Set default currency based on display currency selection
                currency_options = ["CZK", "EUR", "USD"]
                default_index = currency_options.index(default_currency) if default_currency in currency_options else 0
                base_currency = st.selectbox("Purchase Currency", currency_options, index=default_index, help="Currency you used to purchase")
            
            col4, col5, col6 = st.columns(3)
            
            with col4:
                price_str = st.text_input("Buy Price", placeholder="0.00000000", help=f"Price per coin in {base_currency} (e.g., 50000.00000000)")
                try:
                    price_buy = float(price_str) if price_str else 0.0
                except ValueError:
                    price_buy = 0.0
                    if price_str:
                        st.error("Invalid price format. Use decimal point (.) not comma (,).")
            
            with col5:
                purchase_date = st.date_input("Purchase Date", value=datetime.now().date(), help="Date when you purchased")
            
            with col6:
                st.write("")  # Empty column for spacing
            
            if st.form_submit_button("Add to Portfolio", type="primary"):
                
                # Validate all fields
                errors = []
                
                if not symbol or not symbol.strip():
                    errors.append("Symbol is required")
                
                if amount is None or amount <= 0:
                    errors.append("Amount must be greater than 0")
                
                if price_buy is None or price_buy <= 0:
                    errors.append("Buy price must be greater than 0")
                
                if not purchase_date:
                    errors.append("Purchase date is required")
                elif purchase_date > datetime.now().date():
                    errors.append("Purchase date cannot be in the future")
                
                if not base_currency:
                    errors.append("Purchase currency is required")
                
                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    # Round to 8 decimal places for precision
                    amount_rounded = round(float(amount), 8)
                    price_rounded = round(float(price_buy), 8)
                    
                    # Handle async callback properly
                    import asyncio
                    asyncio.run(add_callback(symbol, amount_rounded, price_rounded, purchase_date, base_currency))
                    st.success(f"Added {symbol.upper()} to portfolio!")
                    st.rerun()
    
    @staticmethod
    def display_add_coin_form_with_search(add_callback, search_callback, default_currency="USD"):
        """Display enhanced form to add new coin with cryptocurrency search functionality
        
        Args:
            add_callback: Function to call when coin is added
            search_callback: Function to search for cryptocurrencies
            default_currency: Default currency for purchase
        """
        st.subheader("Add New Coin to Portfolio")
        
        # Symbol selection with search using real-time search component
        from .real_time_search import RealTimeSearch
        RealTimeSearch.display_portfolio_search(search_callback, add_callback)
        
        # Initialize selected_symbol
        selected_symbol = None
        if 'selected_portfolio_symbol' in st.session_state:
            selected_symbol = st.session_state.selected_portfolio_symbol
        
        with st.form("add_coin_form_with_search"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                symbol = st.text_input(
                    "Symbol", 
                    value=selected_symbol if selected_symbol else "",
                    placeholder="BTC",
                    help="Enter the trading pair symbol (e.g., BTC) or use search above"
                )
            
            with col2:
                amount_str = st.text_input("Amount", placeholder="0.00000000", help="Number of coins you own (e.g., 1.50000000)")
                try:
                    amount = float(amount_str) if amount_str else 0.0
                except ValueError:
                    amount = 0.0
                    if amount_str:
                        st.error("Invalid amount format. Use decimal point (.) not comma (,).")
            
            with col3:
                # Set default currency based on display currency selection
                currency_options = ["CZK", "EUR", "USD"]
                default_index = currency_options.index(default_currency) if default_currency in currency_options else 0
                base_currency = st.selectbox("Purchase Currency", currency_options, index=default_index, help="Currency you used to purchase")
            
            col4, col5, col6 = st.columns(3)
            
            with col4:
                price_str = st.text_input("Buy Price", placeholder="0.00000000", help=f"Price per coin in {base_currency} (e.g., 50000.00000000)")
                try:
                    price_buy = float(price_str) if price_str else 0.0
                except ValueError:
                    price_buy = 0.0
                    if price_str:
                        st.error("Invalid price format. Use decimal point (.) not comma (,).")
            
            with col5:
                purchase_date = st.date_input("Purchase Date", value=datetime.now().date(), help="Date when you purchased")
            
            with col6:
                st.write("")  # Empty column for spacing
            
            if st.form_submit_button("Add to Portfolio", type="primary"):
                # Validate all fields
                errors = []
                if not symbol or not symbol.strip():
                    errors.append("Symbol is required")
                if not amount or amount <= 0:
                    errors.append("Amount must be greater than 0")
                if not price_buy or price_buy <= 0:
                    errors.append("Buy price must be greater than 0")
                if not purchase_date:
                    errors.append("Purchase date is required")
                
                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    # Round to 8 decimal places for precision
                    amount_rounded = round(float(amount), 8)
                    price_rounded = round(float(price_buy), 8)
                    
                    # Handle async callback properly
                    import asyncio
                    asyncio.run(add_callback(symbol, amount_rounded, price_rounded, purchase_date, base_currency))
                    st.success(f"Added {symbol.upper()} to portfolio!")
                    # Clear selected symbol
                    if 'selected_portfolio_symbol' in st.session_state:
                        del st.session_state.selected_portfolio_symbol
                    st.rerun()