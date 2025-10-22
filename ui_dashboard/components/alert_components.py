"""
Price Alert Components for Crypto AI Agent Dashboard
Reusable components for price alert functionality
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime

class AlertComponents:
    """Reusable price alert management components"""
    
    @staticmethod
    def display_alert_creation_form(available_symbols: List[str], create_callback):
        """Display form to create new price alert"""
        st.subheader("Create New Price Alert")
        
        with st.form("create_alert_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                symbol = st.selectbox(
                    "Symbol",
                    available_symbols,
                    help="Select the cryptocurrency symbol to monitor"
                )
                
                alert_type = st.selectbox(
                    "Alert Type",
                    ["ABOVE", "BELOW"],
                    help="Choose whether to alert when price goes above or below the threshold"
                )
            
            with col2:
                threshold_price = st.number_input(
                    "Threshold Price (USD)",
                    min_value=0.0,
                    step=0.01,
                    help="Set the price threshold for the alert"
                )
                
                is_active = st.checkbox(
                    "Active",
                    value=True,
                    help="Enable or disable this alert"
                )
            
            message = st.text_area(
                "Alert Message",
                placeholder="e.g., 'Consider selling 50% of holdings' or 'Good time to buy more'",
                help="Custom message that will be sent when the alert triggers"
            )
            
            if st.form_submit_button("Create Alert", type="primary"):
                if symbol and threshold_price > 0 and message.strip():
                    create_callback(symbol, alert_type, threshold_price, message, is_active)
                    st.success(f"Alert created for {symbol}!")
                    st.rerun()
                else:
                    st.error("Please fill in all required fields")
    
    @staticmethod
    def display_active_alerts(alerts_df: pd.DataFrame, update_callback, delete_callback):
        """Display active alerts with management options"""
        if alerts_df.empty:
            st.info("No active alerts configured")
            return
        
        st.subheader("Active Alerts")
        
        for _, alert in alerts_df.iterrows():
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    alert_type_icon = "📈" if alert['alert_type'] == 'ABOVE' else "📉"
                    st.write(f"**{alert_type_icon} {alert['symbol']}** - {alert['alert_type']} ${alert['threshold_price']:.2f}")
                    st.write(f"*{alert['message']}*")
                
                with col2:
                    if st.button("Edit", key=f"edit_alert_{alert['id']}"):
                        st.session_state[f"edit_alert_{alert['id']}"] = True
                
                with col3:
                    if st.button("Toggle", key=f"toggle_alert_{alert['id']}"):
                        update_callback(alert['id'], alert['symbol'], alert['alert_type'], 
                                     alert['threshold_price'], alert['message'], not alert['is_active'])
                        st.success(f"Alert {'activated' if not alert['is_active'] else 'deactivated'}")
                        st.rerun()
                
                with col4:
                    if st.button("Delete", key=f"delete_alert_{alert['id']}"):
                        delete_callback(alert['id'])
                        st.success("Alert deleted")
                        st.rerun()
                
                # Edit form (appears when Edit button is clicked)
                if st.session_state.get(f"edit_alert_{alert['id']}", False):
                    AlertComponents._display_edit_alert_form(alert, update_callback)
                
                st.divider()
    
    @staticmethod
    def _display_edit_alert_form(alert: pd.Series, update_callback):
        """Display edit form for alert"""
        with st.form(f"edit_alert_form_{alert['id']}"):
            st.write(f"Edit Alert for {alert['symbol']}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                new_alert_type = st.selectbox(
                    "Alert Type",
                    ["ABOVE", "BELOW"],
                    index=0 if alert['alert_type'] == 'ABOVE' else 1,
                    key=f"edit_type_{alert['id']}"
                )
                
                new_threshold = st.number_input(
                    "Threshold Price",
                    value=float(alert['threshold_price']),
                    min_value=0.0,
                    step=0.01,
                    key=f"edit_threshold_{alert['id']}"
                )
            
            with col2:
                new_message = st.text_area(
                    "Alert Message",
                    value=alert['message'],
                    key=f"edit_message_{alert['id']}"
                )
                
                new_active = st.checkbox(
                    "Active",
                    value=bool(alert['is_active']),
                    key=f"edit_active_{alert['id']}"
                )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Update Alert"):
                    update_callback(alert['id'], alert['symbol'], new_alert_type, 
                                 new_threshold, new_message, new_active)
                    st.session_state[f"edit_alert_{alert['id']}"] = False
                    st.success("Alert updated")
                    st.rerun()
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state[f"edit_alert_{alert['id']}"] = False
                    st.rerun()
    
    @staticmethod
    def display_alert_history(history_df: pd.DataFrame):
        """Display alert history table"""
        if history_df.empty:
            st.info("No alert history available")
            return
        
        st.subheader("Alert History")
        
        # Format the dataframe for display
        display_df = history_df.copy()
        display_df['triggered_at'] = pd.to_datetime(display_df['triggered_at'])
        display_df = display_df.sort_values('triggered_at', ascending=False)
        
        # Format columns
        display_df['triggered_price'] = display_df['triggered_price'].apply(lambda x: f"${x:.2f}")
        display_df['threshold_price'] = display_df['threshold_price'].apply(lambda x: f"${x:.2f}")
        display_df['triggered_at'] = display_df['triggered_at'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Rename columns
        display_df.columns = ['ID', 'Alert ID', 'Symbol', 'Triggered Price', 'Threshold Price', 
                            'Alert Type', 'Message', 'Triggered At']
        
        st.dataframe(display_df, width='stretch')
    
    @staticmethod
    def display_alert_statistics(alerts_df: pd.DataFrame, history_df: pd.DataFrame):
        """Display alert statistics and metrics"""
        if alerts_df.empty and history_df.empty:
            st.info("No alert data available")
            return
        
        st.subheader("Alert Statistics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            active_count = len(alerts_df[alerts_df['is_active'] == 1]) if not alerts_df.empty else 0
            st.metric("Active Alerts", active_count)
        
        with col2:
            total_alerts = len(alerts_df) if not alerts_df.empty else 0
            st.metric("Total Alerts", total_alerts)
        
        with col3:
            triggered_count = len(history_df) if not history_df.empty else 0
            st.metric("Alerts Triggered", triggered_count)
        
        with col4:
            if not history_df.empty:
                recent_triggers = len(history_df[history_df['triggered_at'] >= 
                    (datetime.now() - pd.Timedelta(days=7)).strftime('%Y-%m-%d')])
                st.metric("This Week", recent_triggers)
            else:
                st.metric("This Week", 0)
        
        # Alert type distribution
        if not alerts_df.empty:
            st.subheader("Alert Type Distribution")
            alert_types = alerts_df['alert_type'].value_counts()
            st.bar_chart(alert_types)
        
        # Most triggered symbols
        if not history_df.empty:
            st.subheader("Most Triggered Symbols")
            symbol_counts = history_df['symbol'].value_counts().head(5)
            if not symbol_counts.empty:
                st.bar_chart(symbol_counts)
    
    @staticmethod
    def display_alert_management(alerts_df: pd.DataFrame, history_df: pd.DataFrame, 
                               available_symbols: List[str], create_callback, 
                               update_callback, delete_callback):
        """Display complete alert management interface"""
        # Statistics
        AlertComponents.display_alert_statistics(alerts_df, history_df)
        
        # Create new alert
        AlertComponents.display_alert_creation_form(available_symbols, create_callback)
        
        # Active alerts
        AlertComponents.display_active_alerts(alerts_df, update_callback, delete_callback)
        
        # Alert history
        AlertComponents.display_alert_history(history_df)
    
    @staticmethod
    def display_alert_quick_actions(symbol: str, current_price: float):
        """Display quick alert creation for specific symbol"""
        st.sidebar.subheader(f"Quick Alerts for {symbol}")
        st.sidebar.write(f"Current Price: ${current_price:.2f}")
        
        # Quick above alert
        if st.sidebar.button(f"Alert Above ${current_price * 1.05:.2f}", key=f"quick_above_{symbol}"):
            st.session_state[f"quick_alert_{symbol}"] = {
                'type': 'ABOVE',
                'price': current_price * 1.05,
                'message': f'Price reached above ${current_price * 1.05:.2f}'
            }
        
        # Quick below alert
        if st.sidebar.button(f"Alert Below ${current_price * 0.95:.2f}", key=f"quick_below_{symbol}"):
            st.session_state[f"quick_alert_{symbol}"] = {
                'type': 'BELOW',
                'price': current_price * 0.95,
                'message': f'Price dropped below ${current_price * 0.95:.2f}'
            }
