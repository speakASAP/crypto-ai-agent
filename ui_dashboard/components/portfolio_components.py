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
    def get_common_exchanges():
        """Get list of common cryptocurrency exchanges"""
        return [
            "Binance",
            "Coinbase",
            "Revolut", 
            "Kraken",
            "KuCoin",
            "Huobi",
            "OKX",
            "Bybit",
            "Gate.io",
            "Bitfinex",
            "Bitstamp",
            "Gemini",
            "Crypto.com",
            "eToro",
            "Robinhood",
            "Webull",
            "Other",
            "Unknown"
        ]
    
    @staticmethod
    def get_user_sources_from_portfolio(portfolio_data):
        """Get unique sources from user's portfolio for suggestions"""
        if portfolio_data.empty or 'source' not in portfolio_data.columns:
            return []
        
        # Get unique sources, excluding 'Unknown' and 'Other'
        sources = portfolio_data['source'].dropna().unique()
        sources = [s for s in sources if s not in ['Unknown', 'Other']]
        return sorted(sources)
    
    @staticmethod
    def display_portfolio_summary(metrics: Dict[str, Any]):
        """Display portfolio summary metrics in cards"""
        if not metrics or metrics.get('total_value', 0) == 0:
            st.info("No portfolio data available. Add some coins to get started!")
            return
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Value", f"${metrics['total_value']:,.8f}")
        
        with col2:
            st.metric("Total Cost", f"${metrics['total_cost']:,.8f}")
        
        with col3:
            pnl_color = "normal" if metrics['total_pnl'] >= 0 else "inverse"
            st.metric("P&L", f"${metrics['total_pnl']:,.8f}", delta=f"{metrics['total_pnl_percent']:.8f}%")
        
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
                return f"${value:,.0f}"
            elif currency == 'EUR':
                return f"€{value:,.0f}"
            elif currency == 'CZK':
                return f"{value:,.0f} Kč"
            else:
                return f"{value:,.0f} {currency}"
        
        def format_price(value, currency):
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
        
        # Format each row with its original currency (for display only)
        for idx, row in display_df.iterrows():
            currency = row['Currency']
            # Store the original numeric values for calculations
            original_buy_price = row['Buy Price']
            original_current_price = row['Current Price']
            original_current_value = row['Current Value']
            original_pnl = row['P&L']
            original_pnl_percent = row['P&L %']
            
            # Format for display only
            display_df.at[idx, 'Buy Price'] = format_price(original_buy_price, currency)
            display_df.at[idx, 'Current Price'] = format_price(original_current_price, currency)
            display_df.at[idx, 'Current Value'] = format_currency(original_current_value, currency)
            display_df.at[idx, 'P&L'] = format_currency(original_pnl, currency)
            display_df.at[idx, 'P&L %'] = f"{original_pnl_percent:.2f}%"
        
        # Remove the Currency column from display
        display_df = display_df.drop('Currency', axis=1)
        
        st.dataframe(display_df, width='stretch')
    
    @staticmethod
    def display_portfolio_table_with_actions(portfolio_data: pd.DataFrame, update_callback, delete_callback):
        """Display portfolio table with Edit and Remove buttons for each row"""
        if portfolio_data.empty:
            st.info("No portfolio holdings to display")
            return
        
        # Display each portfolio item with action buttons
        for idx, row in portfolio_data.iterrows():
            with st.container():
                col1, col2, col3, col4, col5, col6, col7, col8, col9, col10, col11 = st.columns([2, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.2, 1, 1])
                
                # Format currency values for display only
                currency = row.get('base_currency', 'USD')
                def format_currency(value, currency):
                    if currency == 'USD':
                        return f"${value:,.0f}"
                    elif currency == 'EUR':
                        return f"€{value:,.0f}"
                    elif currency == 'CZK':
                        return f"{value:,.0f} Kč"
                    else:
                        return f"{value:,.0f} {currency}"
                
                def format_price(value, currency):
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
                    st.write(f"{row['amount']:,.8f}")
                with col3:
                    st.write(format_price(row['price_buy'], currency))
                with col4:
                    st.write(format_price(row['current_price'], currency))
                with col5:
                    st.write(format_currency(row['cost_basis'], currency))
                with col6:
                    st.write(format_currency(row['current_value'], currency))
                with col7:
                    pnl_color = "normal" if row['pnl'] >= 0 else "inverse"
                    st.write(format_currency(row['pnl'], currency))
                with col8:
                    pnl_percent_color = "normal" if row['pnl_percent'] >= 0 else "inverse"
                    st.write(f"{row['pnl_percent']:.2f}%")
                with col9:
                    source = row.get('source', 'Unknown')
                    st.write(f"**{source}**")
                
                # Use forms for better session state management
                with col10:
                    with st.form(f"edit_form_{row['symbol']}_{idx}", clear_on_submit=False):
                        if st.form_submit_button("✏️", help="Edit this coin", use_container_width=True):
                            st.session_state[f"editing_{row['symbol']}_{idx}"] = True
                            st.rerun()
                
                with col11:
                    with st.form(f"delete_form_{row['symbol']}_{idx}", clear_on_submit=False):
                        if st.form_submit_button("🗑️", help="Remove this coin", use_container_width=True):
                            # Call the synchronous delete callback
                            delete_callback(row['symbol'])
                            st.success(f"Removed {row['symbol']} from portfolio")
                
                # Edit form (appears when Edit button is clicked)
                editing_key = f"editing_{row['symbol']}_{idx}"
                is_editing = st.session_state.get(editing_key, False)
                if is_editing:
                    with st.expander(f"✏️ Edit {row['symbol']}", expanded=True):
                        PortfolioComponents._display_edit_form_enhanced(row, update_callback, idx)
                
                st.divider()
    
    @staticmethod
    def _display_edit_form_enhanced(row: pd.Series, update_callback, idx):
        """Display enhanced edit form for portfolio item"""
        with st.form(f"edit_form_{row['symbol']}_{idx}_main", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                new_amount = st.number_input("Amount", value=float(row['amount']), min_value=0.0, step=0.00000001, format="%.8f", key=f"amount_{row['symbol']}_{idx}")
            with col2:
                new_price = st.number_input("Buy Price", value=float(row['price_buy']), min_value=0.0, step=0.00000001, format="%.8f", key=f"price_{row['symbol']}_{idx}")
            with col3:
                new_currency = st.selectbox("Currency", ["USD", "EUR", "CZK"], index=["USD", "EUR", "CZK"].index(row.get('base_currency', 'USD')), key=f"currency_{row['symbol']}_{idx}")
            
            col4, col5, col6 = st.columns(3)
            with col4:
                # Optional: Total Invested helper field
                current_total_invested = float(row['amount']) * float(row['price_buy'])
                new_total_invested = st.number_input("Total Invested (Optional)", value=current_total_invested, min_value=0.0, step=0.00000001, format="%.8f", key=f"total_invested_{row['symbol']}_{idx}", help="If provided, will calculate buy price when buy price is 0")
                
                # Calculate buy price from total invested only if buy price is 0
                if new_price == 0 and new_total_invested > 0 and new_amount > 0:
                    calculated_price = new_total_invested / new_amount
                    st.info(f"💰 Calculated buy price: {calculated_price:.8f} {new_currency} per coin")
                    new_price = calculated_price
            
            with col5:
                # Get source options (user's previous sources + common exchanges)
                common_exchanges = PortfolioComponents.get_common_exchanges()
                source_options = common_exchanges.copy()
                
                # Add user's previous sources at the top
                if 'portfolio_data' in st.session_state:
                    user_sources = PortfolioComponents.get_user_sources_from_portfolio(st.session_state.portfolio_data)
                    for source in user_sources:
                        if source not in source_options:
                            source_options.insert(0, source)
                
                current_source = row.get('source', 'Unknown')
                source_index = source_options.index(current_source) if current_source in source_options else 0
                new_source = st.selectbox("Source", source_options, index=source_index, key=f"source_{row['symbol']}_{idx}")
            
            with col6:
                new_commission = st.number_input("Commission/Fees", value=float(row.get('commission', 0)), min_value=0.0, step=0.00000001, format="%.8f", key=f"commission_{row['symbol']}_{idx}")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.form_submit_button("✅ Update", use_container_width=True):
                    try:
                        # Update the coin
                        update_callback(row['symbol'], new_amount, new_price, new_currency, new_source, new_commission)
                        
                        # Clear the editing session state to close the form
                        editing_key = f"editing_{row['symbol']}_{idx}"
                        if editing_key in st.session_state:
                            del st.session_state[editing_key]
                        
                        # Show success message and force refresh
                        st.success(f"✅ Successfully updated {row['symbol']}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error updating {row['symbol']}: {str(e)}")
                        # Keep form open on error so user can fix and retry
            with col2:
                if st.form_submit_button("❌ Cancel", use_container_width=True):
                    # Clear form editing state
                    editing_key = f"editing_{row['symbol']}_{idx}"
                    if editing_key in st.session_state:
                        del st.session_state[editing_key]
                    st.rerun()
            with col3:
                if st.form_submit_button("🗑️ Delete", use_container_width=True):
                    # Clear form editing state
                    editing_key = f"editing_{row['symbol']}_{idx}"
                    if editing_key in st.session_state:
                        del st.session_state[editing_key]
                    st.info(f"Deleting {row['symbol']}...")
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
                    # Call the synchronous delete callback
                    delete_callback(row['symbol'])
                    st.success(f"Deleted {row['symbol']} from portfolio")
            
            # Edit form (appears when Edit button is clicked)
            if st.session_state.get(f"edit_{row['symbol']}", False):
                PortfolioComponents._display_edit_form(row, update_callback)
    
    @staticmethod
    def _display_edit_form(row: pd.Series, update_callback):
        """Display edit form for portfolio item"""
        with st.form(f"edit_form_{row['symbol']}"):
            st.write(f"Edit {row['symbol']}")
            new_amount = st.number_input("Amount", value=float(row['amount']), min_value=0.0, step=0.00000001, format="%.8f", key=f"amount_{row['symbol']}")
            new_price = st.number_input("Buy Price", value=float(row['price_buy']), min_value=0.0, step=0.00000001, format="%.8f", key=f"price_{row['symbol']}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Update"):
                    try:
                        update_callback(row['symbol'], new_amount, new_price)
                        st.session_state[f"edit_{row['symbol']}"] = False
                        st.success(f"✅ Successfully updated {row['symbol']}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error updating {row['symbol']}: {str(e)}")
                        # Keep form open on error so user can fix and retry
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
                amount = st.number_input("Amount", min_value=0.0, step=0.00000001, format="%.8f", help="Number of coins you own")
            
            with col3:
                price_buy = st.number_input("Buy Price (USD)", min_value=0.0, step=0.00000001, format="%.8f", help="Price per coin when you bought")
            
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
            st.metric("Total Value", f"{target_currency} {total_value:,.0f}")
        
        with col2:
            total_cost = portfolio_data['cost_basis'].sum()
            st.metric("Total Cost", f"{target_currency} {total_cost:,.0f}")
        
        with col3:
            total_pnl = portfolio_data['pnl'].sum()
            pnl_color = "normal" if total_pnl >= 0 else "inverse"
            st.metric("Total P&L", f"{target_currency} {total_pnl:,.0f}")
        
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
                    f"{target_currency} {best_performer['pnl']:,.8f} ({best_performer['pnl_percent']:.8f}%)"
                )
        
        with col2:
            if not portfolio_data.empty:
                worst_performer = portfolio_data.loc[portfolio_data['pnl_percent'].idxmin()]
                st.metric(
                    "Worst Performer", 
                    worst_performer['symbol'],
                    f"{target_currency} {worst_performer['pnl']:,.8f} ({worst_performer['pnl_percent']:.8f}%)"
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
                total_invested_str = st.text_input("Total Invested", placeholder="0.00000000", help=f"Total amount spent in {base_currency} (e.g., 1500.00000000)")
                try:
                    total_invested = float(total_invested_str) if total_invested_str else 0.0
                except ValueError:
                    total_invested = 0.0
                    if total_invested_str:
                        st.error("Invalid total invested format. Use decimal point (.) not comma (,).")
            
            with col5:
                price_str = st.text_input("Buy Price (Optional)", placeholder="0.00000000", help=f"Price per coin in {base_currency} - will be calculated from Total Invested if left empty")
                try:
                    price_buy = float(price_str) if price_str else 0.0
                except ValueError:
                    price_buy = 0.0
                    if price_str:
                        st.error("Invalid price format. Use decimal point (.) not comma (,).")
            
            with col6:
                commission_str = st.text_input("Commission/Fees", placeholder="0.00000000", help=f"Trading fees/commission in {base_currency} (e.g., 45.00000000)")
                try:
                    commission = float(commission_str) if commission_str else 0.0
                except ValueError:
                    commission = 0.0
                    if commission_str:
                        st.error("Invalid commission format. Use decimal point (.) not comma (,).")
            
            col7, col8, col9 = st.columns(3)
            
            with col7:
                purchase_date = st.date_input("Purchase Date", value=datetime.now().date(), help="Date when you purchased")
            
            with col8:
                # Get source options (user's previous sources + common exchanges)
                common_exchanges = PortfolioComponents.get_common_exchanges()
                source_options = common_exchanges.copy()
                
                # Add user's previous sources at the top
                if 'portfolio_data' in st.session_state:
                    user_sources = PortfolioComponents.get_user_sources_from_portfolio(st.session_state.portfolio_data)
                    for source in user_sources:
                        if source not in source_options:
                            source_options.insert(0, source)
                
                source = st.selectbox("Source", source_options, help="Where you bought this cryptocurrency")
            
            with col9:
                st.write("")  # Empty column for spacing
            
            if st.form_submit_button("Add to Portfolio", type="primary"):
                
                # Validate all fields
                errors = []
                
                if not symbol or not symbol.strip():
                    errors.append("Symbol is required")
                
                if amount is None or amount <= 0:
                    errors.append("Amount must be greater than 0")
                
                # Calculate buy price from total invested if provided, otherwise use direct price input
                if total_invested > 0 and amount > 0:
                    # Calculate price from total invested
                    calculated_price = total_invested / amount
                    price_buy = calculated_price
                    st.info(f"💰 Calculated buy price: {calculated_price:.8f} {base_currency} per coin (Total Invested ÷ Amount)")
                elif price_buy <= 0:
                    errors.append("Either Total Invested or Buy Price must be provided and greater than 0")
                
                if not purchase_date:
                    errors.append("Purchase date is required")
                elif purchase_date > datetime.now().date():
                    errors.append("Purchase date cannot be in the future")
                
                if not base_currency:
                    errors.append("Purchase currency is required")
                
                if not source:
                    errors.append("Source is required")
                
                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    # Round to 8 decimal places for precision
                    amount_rounded = round(float(amount), 8)
                    price_rounded = round(float(price_buy), 8)
                    commission_rounded = round(float(commission), 8)
                    
                    # Handle async callback properly
                    import asyncio
                    asyncio.run(add_callback(symbol, amount_rounded, price_rounded, purchase_date, base_currency, source, commission_rounded))
                    st.success(f"Added {symbol.upper()} to portfolio!")
                    # Set active tab to Overview after adding coin
                    st.session_state['active_portfolio_tab'] = 0
                    st.rerun()
    
    @staticmethod
    def display_add_coin_form_with_search(add_callback, search_callback, default_currency="USD"):
        """Display enhanced form to add new coin with cryptocurrency validation
        
        Args:
            add_callback: Function to call when coin is added
            search_callback: Function to search for cryptocurrencies (used for validation)
            default_currency: Default currency for purchase
        """
        st.subheader("Add New Coin to Portfolio")
        
        # Form section
        with st.form("add_coin_form_with_search"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Symbol input field - user types directly here
                symbol = st.text_input(
                    "Symbol", 
                    placeholder="BTC, ADA, ETH...",
                    help="Enter the cryptocurrency symbol (e.g., BTC, ADA, ETH)",
                    key="symbol_input_direct"
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
                total_invested_str = st.text_input("Total Invested", placeholder="0.00000000", help=f"Total amount spent in {base_currency} (e.g., 1500.00000000)")
                try:
                    total_invested = float(total_invested_str) if total_invested_str else 0.0
                except ValueError:
                    total_invested = 0.0
                    if total_invested_str:
                        st.error("Invalid total invested format. Use decimal point (.) not comma (,).")
            
            with col5:
                price_str = st.text_input("Buy Price (Optional)", placeholder="0.00000000", help=f"Price per coin in {base_currency} - will be calculated from Total Invested if left empty")
                try:
                    price_buy = float(price_str) if price_str else 0.0
                except ValueError:
                    price_buy = 0.0
                    if price_str:
                        st.error("Invalid price format. Use decimal point (.) not comma (,).")
            
            with col6:
                commission_str = st.text_input("Commission/Fees", placeholder="0.00000000", help=f"Trading fees/commission in {base_currency} (e.g., 45.00000000)")
                try:
                    commission = float(commission_str) if commission_str else 0.0
                except ValueError:
                    commission = 0.0
                    if commission_str:
                        st.error("Invalid commission format. Use decimal point (.) not comma (,).")
            
            col7, col8, col9 = st.columns(3)
            
            with col7:
                purchase_date = st.date_input("Purchase Date", value=datetime.now().date(), help="Date when you purchased")
            
            with col8:
                # Get source options (user's previous sources + common exchanges)
                common_exchanges = PortfolioComponents.get_common_exchanges()
                source_options = common_exchanges.copy()
                
                # Add user's previous sources at the top
                if 'portfolio_data' in st.session_state:
                    user_sources = PortfolioComponents.get_user_sources_from_portfolio(st.session_state.portfolio_data)
                    for source in user_sources:
                        if source not in source_options:
                            source_options.insert(0, source)
                
                source = st.selectbox("Source", source_options, help="Where you bought this cryptocurrency")
            
            with col8:
                st.write("")  # Empty column for spacing
            with col9:
                st.write("")  # Empty column for spacing
            
            if st.form_submit_button("Add to Portfolio", type="primary"):
                # Validate all fields
                errors = []
                if not symbol or not symbol.strip():
                    errors.append("Symbol is required")
                else:
                    # Validate symbol exists in database
                    try:
                        # Use search callback to validate symbol
                        search_results = search_callback(symbol.strip().upper())
                        if not search_results:
                            errors.append(f"Symbol '{symbol.upper()}' not found in cryptocurrency database")
                        else:
                            # Use the first result (most relevant match)
                            symbol = search_results[0]['symbol']
                    except Exception as e:
                        errors.append(f"Error validating symbol: {str(e)}")
                
                if not amount or amount <= 0:
                    errors.append("Amount must be greater than 0")
                
                # Calculate buy price from total invested if provided, otherwise use direct price input
                if total_invested > 0 and amount > 0:
                    # Calculate price from total invested
                    calculated_price = total_invested / amount
                    price_buy = calculated_price
                    st.info(f"💰 Calculated buy price: {calculated_price:.8f} {base_currency} per coin (Total Invested ÷ Amount)")
                elif price_buy <= 0:
                    errors.append("Either Total Invested or Buy Price must be provided and greater than 0")
                if not purchase_date:
                    errors.append("Purchase date is required")
                if not source:
                    errors.append("Source is required")
                
                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    # Round to 8 decimal places for precision
                    amount_rounded = round(float(amount), 8)
                    price_rounded = round(float(price_buy), 8)
                    commission_rounded = round(float(commission), 8)
                    
                    # Handle async callback properly
                    import asyncio
                    asyncio.run(add_callback(symbol, amount_rounded, price_rounded, purchase_date, base_currency, source, commission_rounded))
                    st.success(f"Added {symbol.upper()} to portfolio!")
                    # Set active tab to Overview after adding coin
                    st.session_state['active_portfolio_tab'] = 0
                    st.rerun()