"""
Data Display Components for Crypto AI Agent Dashboard
Reusable components for displaying data tables and metrics
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional
from .app_setup_components import AppSetupComponents

class DataDisplayComponents:
    """Reusable data display components"""
    
    
    # @staticmethod
    # def display_dashboard_statistics(portfolio_df: pd.DataFrame, symbols_df: pd.DataFrame, 
    #                                metrics: Dict[str, Any]):
    #     """Display dashboard statistics in metric cards"""
    #     # TEMPORARILY DISABLED FOR REFACTORING - Dashboard Statistics section removed
    #     AppSetupComponents.display_section_header("Dashboard Statistics", "📊")
    #     col1, col2, col3 = st.columns(3)

    #     with col1:
    #         active_count = len(symbols_df[symbols_df['is_active'] == 1]) if not symbols_df.empty else 0
    #         st.metric("Active Symbols", active_count)

    #     with col2:
    #         portfolio_count = len(portfolio_df) if not portfolio_df.empty else 0
    #         st.metric("Portfolio Items", portfolio_count)

    #     with col3:
    #         if not portfolio_df.empty and metrics and metrics.get('total_value', 0) > 0:
    #             st.metric("Portfolio Value", f"${metrics['total_value']:,.0f}")
    #         else:
    #             st.metric("Portfolio Value", "$0")
    
    @staticmethod
    def display_portfolio_tabs(portfolio_df: pd.DataFrame, metrics: Dict[str, Any], 
                             add_callback, update_callback, delete_callback):
        """Display portfolio management tabs"""
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Portfolio Overview", "➕ Add/Edit Coins", "📈 Performance", "🔔 Price Alerts"])

        with tab1:
            # Portfolio Table with P&L
            if not portfolio_df.empty and metrics and metrics.get('portfolio_data') is not None:
                st.subheader("Portfolio Holdings")
                
                # Import here to avoid circular imports
                from .portfolio_components import PortfolioComponents
                
                # Display portfolio table
                PortfolioComponents.display_portfolio_table(metrics['portfolio_data'])
                
                # Display portfolio management
                PortfolioComponents.display_portfolio_management(
                    metrics['portfolio_data'], update_callback, delete_callback
                )
            else:
                st.info("No portfolio data available. Add some coins to get started!")

        with tab2:
            # Import here to avoid circular imports
            from .portfolio_components import PortfolioComponents
            PortfolioComponents.display_add_coin_form(add_callback)

        with tab3:
            # Import here to avoid circular imports
            from .portfolio_components import PortfolioComponents
            if not portfolio_df.empty and metrics and metrics.get('portfolio_data') is not None:
                PortfolioComponents.display_performance_metrics(metrics['portfolio_data'])
            else:
                AppSetupComponents.display_info_message("Add coins to your portfolio to see performance metrics")
        
        with tab4:
            # Price Alerts for Portfolio Symbols
            if not portfolio_df.empty:
                st.subheader("Portfolio Price Alerts")
                
                # Import here to avoid circular imports
                from .alert_components import AlertComponents
                
                portfolio_symbols = portfolio_df['symbol'].tolist()
                
                # Get alert data
                import asyncio
                from ..app import get_price_alerts, get_alert_history, create_price_alert, update_price_alert, delete_price_alert
                
                alerts = asyncio.run(get_price_alerts())
                alert_history = asyncio.run(get_alert_history(50))
                
                # Filter alerts for portfolio symbols
                portfolio_alerts = alerts[alerts['symbol'].isin(portfolio_symbols)] if not alerts.empty else alerts
                
                # Alert management callbacks
                async def create_alert_callback(symbol, alert_type, threshold_price, message, is_active):
                    await create_price_alert(symbol, alert_type, threshold_price, message, is_active)
                
                async def update_alert_callback(alert_id, symbol, alert_type, threshold_price, message, is_active):
                    await update_price_alert(alert_id, symbol, alert_type, threshold_price, message, is_active)
                
                async def delete_alert_callback(alert_id):
                    await delete_price_alert(alert_id)
                
                # Display alert management interface
                AlertComponents.display_alert_management(
                    portfolio_alerts, 
                    alert_history, 
                    portfolio_symbols, 
                    create_alert_callback, 
                    update_alert_callback, 
                    delete_alert_callback
                )
            else:
                st.info("Add coins to your portfolio to manage price alerts.")
    
    @staticmethod
    def display_empty_state(message: str, icon: str = "ℹ️"):
        """Display empty state message"""
        AppSetupComponents.display_info_message(message)
    
    @staticmethod
    def display_error_message(message: str):
        """Display error message"""
        AppSetupComponents.display_error_message(message)
    
    @staticmethod
    def display_success_message(message: str):
        """Display success message"""
        AppSetupComponents.display_success_message(message)
    
    @staticmethod
    def display_warning_message(message: str):
        """Display warning message"""
        AppSetupComponents.display_warning_message(message)
    
    @staticmethod
    def display_loading_spinner(message: str = "Loading..."):
        """Display loading spinner"""
        return AppSetupComponents.display_loading_message(message)
