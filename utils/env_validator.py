"""
Centralized Environment Variable Validation System for Crypto AI Agent
Provides comprehensive validation for all environment variables with proper error handling
"""

import os
import re
from typing import Dict, List, Tuple, Optional, Any
from dotenv import load_dotenv
from pathlib import Path

class EnvironmentValidator:
    """
    Centralized environment variable validation system.
    Validates all required and optional environment variables with proper error handling.
    """
    
    def __init__(self, env_file_path: str = ".env"):
        """
        Initialize the environment validator.
        
        Args:
            env_file_path: Path to the .env file
        """
        self.env_file_path = env_file_path
        self.validation_errors = []
        self.validation_warnings = []
        self.validated_vars = {}
        
        # Load environment variables
        self._load_env_file()
        
        # Define validation rules
        self._define_validation_rules()
    
    def _load_env_file(self):
        """Load environment variables from .env file"""
        try:
            if os.path.exists(self.env_file_path):
                load_dotenv(self.env_file_path)
            else:
                self.validation_errors.append(f"Environment file not found: {self.env_file_path}")
        except Exception as e:
            self.validation_errors.append(f"Failed to load environment file: {str(e)}")
    
    def _define_validation_rules(self):
        """Define validation rules for all environment variables"""
        self.required_vars = {
            "BINANCE_API_KEY": {
                "type": str,
                "min_length": 20,
                "pattern": r"^[A-Za-z0-9]+$",
                "description": "Binance API Key for cryptocurrency data access"
            },
            "BINANCE_API_SECRET": {
                "type": str,
                "min_length": 20,
                "pattern": r"^[A-Za-z0-9]+$",
                "description": "Binance API Secret for cryptocurrency data access"
            },
            "TELEGRAM_TOKEN": {
                "type": str,
                "min_length": 30,
                "pattern": r"^\d+:[A-Za-z0-9_-]+$",
                "description": "Telegram Bot Token for notifications"
            },
            "TELEGRAM_CHAT_ID": {
                "type": str,
                "pattern": r"^-?\d+$",
                "description": "Telegram Chat ID for notifications"
            }
        }
        
        self.optional_vars = {
            "MAX_ERRORS_PER_HOUR": {
                "type": int,
                "min_value": 1,
                "max_value": 100,
                "default": 10,
                "description": "Maximum error notifications per hour"
            },
            "MAX_CONNECTION_RETRIES": {
                "type": int,
                "min_value": 1,
                "max_value": 20,
                "default": 5,
                "description": "Maximum connection retry attempts"
            },
            "HTTP_TIMEOUT": {
                "type": int,
                "min_value": 5,
                "max_value": 60,
                "default": 10,
                "description": "HTTP request timeout in seconds"
            },
            "SYMBOLS": {
                "type": str,
                "default": "",
                "pattern": r"^[A-Z0-9,]*$",
                "description": "Comma-separated list of cryptocurrency symbols to track (empty for user-selected only)"
            },
            "MAX_PRICE_HISTORY": {
                "type": int,
                "min_value": 50,
                "max_value": 1000,
                "default": 200,
                "description": "Maximum price history to keep"
            },
            "DB_PATH": {
                "type": str,
                "default": "data/crypto_portfolio.db",
                "description": "Path to SQLite database file"
            },
            "UI_PORT": {
                "type": int,
                "min_value": 1000,
                "max_value": 65535,
                "default": 8501,
                "description": "Port for UI dashboard"
            },
            "UI_HOST": {
                "type": str,
                "default": "0.0.0.0",
                "description": "Host for UI dashboard"
            },
            "LOG_LEVEL": {
                "type": str,
                "valid_values": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                "default": "INFO",
                "description": "Logging level"
            },
            "LOG_FILE": {
                "type": str,
                "default": "logs/crypto_agent.log",
                "description": "Path to log file"
            },
            "LOG_FORMAT": {
                "type": str,
                "default": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "description": "Log format string"
            },
            "BINANCE_API_URL": {
                "type": str,
                "default": "https://api.binance.com/api/v3/ticker/price",
                "description": "Binance API URL for price data"
            },
            "CURRENCY_API_URL": {
                "type": str,
                "default": "https://api.exchangerate-api.com/v4/latest/USD",
                "description": "Currency exchange rate API URL"
            },
            "CURRENCY_CACHE_DURATION": {
                "type": int,
                "min_value": 300,
                "max_value": 3600,
                "default": 1800,
                "description": "Currency rate cache duration in seconds"
            },
            "CURRENCY_FALLBACK_EUR": {
                "type": float,
                "min_value": 0,
                "max_value": 0,
                "default": 0,
                "description": "Fallback EUR to USD exchange rate"
            },
            "CURRENCY_FALLBACK_CZK": {
                "type": float,
                "min_value": 0.0,
                "max_value": 0.0,
                "default": 0,
                "description": "Fallback CZK to USD exchange rate"
            },
            "SSL_VERIFY": {
                "type": bool,
                "default": False,
                "description": "Enable SSL certificate verification for API connections"
            },
            "SSL_DEBUG": {
                "type": bool,
                "default": False,
                "description": "Enable SSL debugging for troubleshooting connection issues"
            }
        }
    
    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """
        Validate all environment variables.
        
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.validation_errors = []
        self.validation_warnings = []
        self.validated_vars = {}
        
        # Validate required variables
        self._validate_required_vars()
        
        # Validate optional variables
        self._validate_optional_vars()
        
        # Validate paths and directories
        self._validate_paths()
        
        # Validate API keys format
        self._validate_api_keys()
        
        return len(self.validation_errors) == 0, self.validation_errors, self.validation_warnings
    
    def _validate_required_vars(self):
        """Validate required environment variables"""
        for var_name, rules in self.required_vars.items():
            value = os.getenv(var_name)
            
            if not value:
                self.validation_errors.append(f"Required environment variable '{var_name}' is missing. {rules['description']}")
                continue
            
            # Validate type
            if not self._validate_type(var_name, value, rules["type"]):
                continue
            
            # Validate length
            if "min_length" in rules and len(value) < rules["min_length"]:
                self.validation_errors.append(f"Environment variable '{var_name}' is too short (minimum {rules['min_length']} characters)")
                continue
            
            # Validate pattern
            if "pattern" in rules and not re.match(rules["pattern"], value):
                self.validation_errors.append(f"Environment variable '{var_name}' has invalid format")
                continue
            
            self.validated_vars[var_name] = value
    
    def _validate_optional_vars(self):
        """Validate optional environment variables"""
        for var_name, rules in self.optional_vars.items():
            value = os.getenv(var_name)
            
            # Use default if not provided
            if not value and "default" in rules:
                value = str(rules["default"])
                self.validation_warnings.append(f"Using default value for '{var_name}': {value}")
            
            if not value:
                continue
            
            # Validate type
            if not self._validate_type(var_name, value, rules["type"]):
                continue
            
            # Validate numeric ranges
            if rules["type"] in [int, float]:
                if not self._validate_numeric_range(var_name, value, rules):
                    continue
            
            # Validate string patterns
            if rules["type"] == str and "pattern" in rules:
                if not re.match(rules["pattern"], value):
                    self.validation_errors.append(f"Environment variable '{var_name}' has invalid format")
                    continue
            
            # Validate valid values
            if "valid_values" in rules and value not in rules["valid_values"]:
                self.validation_errors.append(f"Environment variable '{var_name}' must be one of: {', '.join(rules['valid_values'])}")
                continue
            
            # Special handling for boolean values
            if rules["type"] == bool:
                if value.lower() in ['true', '1', 'yes', 'on']:
                    self.validated_vars[var_name] = True
                elif value.lower() in ['false', '0', 'no', 'off']:
                    self.validated_vars[var_name] = False
                else:
                    self.validation_errors.append(f"Environment variable '{var_name}' must be a boolean value (true/false)")
                    continue
            else:
                self.validated_vars[var_name] = value
    
    def _validate_type(self, var_name: str, value: str, expected_type: type) -> bool:
        """Validate variable type"""
        try:
            if expected_type == int:
                int(value)
            elif expected_type == float:
                float(value)
            elif expected_type == str:
                pass  # Already a string
            return True
        except ValueError:
            self.validation_errors.append(f"Environment variable '{var_name}' must be of type {expected_type.__name__}")
            return False
    
    def _validate_numeric_range(self, var_name: str, value: str, rules: Dict[str, Any]) -> bool:
        """Validate numeric variable ranges"""
        try:
            if rules["type"] == int:
                num_value = int(value)
            else:
                num_value = float(value)
            
            if "min_value" in rules and num_value < rules["min_value"]:
                self.validation_errors.append(f"Environment variable '{var_name}' must be >= {rules['min_value']}")
                return False
            
            if "max_value" in rules and num_value > rules["max_value"]:
                self.validation_errors.append(f"Environment variable '{var_name}' must be <= {rules['max_value']}")
                return False
            
            return True
        except ValueError:
            return False
    
    def _validate_paths(self):
        """Validate file and directory paths"""
        # Validate database path
        db_path = self.validated_vars.get("DB_PATH", "data/crypto_portfolio.db")
        db_dir = os.path.dirname(db_path)
        
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                self.validation_warnings.append(f"Created database directory: {db_dir}")
            except Exception as e:
                self.validation_errors.append(f"Cannot create database directory '{db_dir}': {str(e)}")
        
        # Validate log file path
        log_file = self.validated_vars.get("LOG_FILE", "logs/crypto_agent.log")
        log_dir = os.path.dirname(log_file)
        
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
                self.validation_warnings.append(f"Created log directory: {log_dir}")
            except Exception as e:
                self.validation_errors.append(f"Cannot create log directory '{log_dir}': {str(e)}")
    
    def _validate_api_keys(self):
        """Validate API key formats"""
        # Validate Binance API key format
        binance_key = self.validated_vars.get("BINANCE_API_KEY")
        if binance_key and len(binance_key) < 20:
            self.validation_warnings.append("Binance API key seems too short, please verify it's correct")
        
        # Validate Telegram token format
        telegram_token = self.validated_vars.get("TELEGRAM_TOKEN")
        if telegram_token and not re.match(r"^\d+:[A-Za-z0-9_-]+$", telegram_token):
            self.validation_warnings.append("Telegram token format seems incorrect, please verify it's correct")
    
    def get_validated_value(self, var_name: str, default: Any = None) -> Any:
        """Get validated environment variable value with type conversion"""
        if var_name not in self.validated_vars:
            return default
        
        value = self.validated_vars[var_name]
        
        # Convert to appropriate type
        if var_name in self.required_vars:
            rules = self.required_vars[var_name]
        elif var_name in self.optional_vars:
            rules = self.optional_vars[var_name]
        else:
            return value
        
        try:
            if rules["type"] == int:
                return int(value)
            elif rules["type"] == float:
                return float(value)
            elif rules["type"] == bool:
                return value  # Already converted in validation
            else:
                return value
        except ValueError:
            return default
    
    def get_validation_report(self) -> str:
        """Get a detailed validation report"""
        report = []
        report.append("=" * 60)
        report.append("ENVIRONMENT VARIABLES VALIDATION REPORT")
        report.append("=" * 60)
        
        if self.validation_errors:
            report.append("\n❌ ERRORS:")
            for error in self.validation_errors:
                report.append(f"  • {error}")
        
        if self.validation_warnings:
            report.append("\n⚠️  WARNINGS:")
            for warning in self.validation_warnings:
                report.append(f"  • {warning}")
        
        if not self.validation_errors and not self.validation_warnings:
            report.append("\n✅ All environment variables validated successfully!")
        
        report.append(f"\n📊 VALIDATED VARIABLES ({len(self.validated_vars)}):")
        for var_name, value in sorted(self.validated_vars.items()):
            # Mask sensitive values
            if "KEY" in var_name or "SECRET" in var_name or "TOKEN" in var_name:
                masked_value = value[:8] + "*" * (len(value) - 8) if len(value) > 8 else "*" * len(value)
                report.append(f"  • {var_name}: {masked_value}")
            else:
                report.append(f"  • {var_name}: {value}")
        
        return "\n".join(report)
    
    def get_missing_required_vars(self) -> List[str]:
        """Get list of missing required environment variables"""
        missing = []
        for var_name in self.required_vars:
            if var_name not in self.validated_vars:
                missing.append(var_name)
        return missing

# Convenience function for easy access
def validate_environment(env_file_path: str = ".env") -> Tuple[bool, List[str], List[str]]:
    """
    Validate environment variables.
    
    Args:
        env_file_path: Path to the .env file
        
    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    validator = EnvironmentValidator(env_file_path)
    return validator.validate_all()

def get_env_validator(env_file_path: str = ".env") -> EnvironmentValidator:
    """
    Get an environment validator instance.
    
    Args:
        env_file_path: Path to the .env file
        
    Returns:
        EnvironmentValidator instance
    """
    return EnvironmentValidator(env_file_path)
