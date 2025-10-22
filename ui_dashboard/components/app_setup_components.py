"""
Application Setup Components for Crypto AI Agent Dashboard
Reusable components for application initialization and error handling
"""

import streamlit as st
from typing import List, Tuple, Optional

class AppSetupComponents:
    """Reusable application setup and error handling components"""
    
    @staticmethod
    def setup_page_config(title: str = "Crypto Portfolio Dashboard", layout: str = "wide"):
        """Setup page configuration"""
        st.set_page_config(page_title=title, layout=layout)
    
    @staticmethod
    def display_page_title(title: str = "Crypto AI Portfolio Dashboard"):
        """Display page title"""
        st.title(title)
    
    @staticmethod
    def handle_environment_validation(is_valid: bool, errors: List[str], warnings: List[str], 
                                    validation_report: str, logger):
        """Handle environment validation results"""
        if errors:
            for error in errors:
                logger.critical(f"Environment validation error: {error}")
        
        if warnings:
            for warning in warnings:
                logger.warning(f"Environment validation warning: {warning}")
        
        if not is_valid:
            logger.critical("Environment validation failed. Please fix the errors above.")
            logger.critical(validation_report)
            AppSetupComponents.display_error_message("Environment validation failed. Please check the logs for details.")
            st.stop()
        
        logger.info("Environment variables validated successfully")
        logger.info(validation_report)
    
    @staticmethod
    def display_error_message(message: str):
        """Display error message"""
        st.error(f"❌ {message}")
    
    @staticmethod
    def display_success_message(message: str):
        """Display success message"""
        st.success(f"✅ {message}")
    
    @staticmethod
    def display_warning_message(message: str):
        """Display warning message"""
        st.warning(f"⚠️ {message}")
    
    @staticmethod
    def display_info_message(message: str):
        """Display info message"""
        st.info(f"ℹ️ {message}")
    
    @staticmethod
    def display_loading_message(message: str = "Loading..."):
        """Display loading message"""
        return st.spinner(message)
    
    @staticmethod
    def display_section_header(header: str, icon: str = ""):
        """Display section header with optional icon"""
        if icon:
            st.header(f"{icon} {header}")
        else:
            st.header(header)
    
    @staticmethod
    def display_subsection_header(header: str, icon: str = ""):
        """Display subsection header with optional icon"""
        if icon:
            st.subheader(f"{icon} {header}")
        else:
            st.subheader(header)
    
    @staticmethod
    def handle_api_error(error: Exception, context: str = "API call"):
        """Handle API errors with consistent formatting"""
        error_message = f"Error in {context}: {str(error)}"
        AppSetupComponents.display_error_message(error_message)
        return error_message
