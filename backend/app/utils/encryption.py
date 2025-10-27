"""
Encryption utilities for secure storage of user API credentials
"""
import base64
import os
import time
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class CredentialEncryption:
    """Handles encryption and decryption of user API credentials"""
    
    def __init__(self, master_key: str = None):
        """
        Initialize encryption with master key
        
        Args:
            master_key: Master key for encryption. If None, uses JWT_SECRET from settings
        """
        from ..core.config import settings
        
        if master_key is None:
            master_key = settings.jwt_secret
        
        # Generate a key from the master key using PBKDF2
        self.key = self._derive_key(master_key)
        self.cipher_suite = Fernet(self.key)
    
    def _derive_key(self, password: str) -> bytes:
        """Derive encryption key from password using PBKDF2"""
        # Use a fixed salt for consistency (in production, consider storing salt separately)
        salt = b'crypto_ai_agent_salt_2024'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt_credentials(self, credentials: Dict[str, Any]) -> str:
        """
        Encrypt user credentials dictionary
        
        Args:
            credentials: Dictionary containing API credentials
            
        Returns:
            Base64 encoded encrypted string
        """
        try:
            import json
            # Convert credentials to JSON string
            credentials_json = json.dumps(credentials)
            
            # Encrypt the JSON string
            encrypted_data = self.cipher_suite.encrypt(credentials_json.encode())
            
            # Return base64 encoded encrypted data
            return base64.urlsafe_b64encode(encrypted_data).decode()
            
        except Exception as e:
            logger.error(f"Error encrypting credentials: {e}")
            raise ValueError(f"Failed to encrypt credentials: {str(e)}")
    
    def decrypt_credentials(self, encrypted_credentials: str) -> Dict[str, Any]:
        """
        Decrypt user credentials
        
        Args:
            encrypted_credentials: Base64 encoded encrypted credentials
            
        Returns:
            Dictionary containing decrypted credentials
        """
        try:
            import json
            
            # Decode base64
            encrypted_data = base64.urlsafe_b64decode(encrypted_credentials.encode())
            
            # Decrypt the data
            decrypted_data = self.cipher_suite.decrypt(encrypted_data)
            
            # Parse JSON and return dictionary
            return json.loads(decrypted_data.decode())
            
        except Exception as e:
            logger.error(f"Error decrypting credentials: {e}")
            raise ValueError(f"Failed to decrypt credentials: {str(e)}")
    
    def encrypt_binance_credentials(self, api_key: str, api_secret: str) -> str:
        """
        Encrypt Binance API credentials specifically
        
        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            
        Returns:
            Encrypted credentials string
        """
        credentials = {
            'api_key': api_key,
            'api_secret': api_secret,
            'exchange': 'binance',
            'timestamp': str(int(time.time()))
        }
        return self.encrypt_credentials(credentials)
    
    def decrypt_binance_credentials(self, encrypted_credentials: str) -> Dict[str, str]:
        """
        Decrypt Binance API credentials
        
        Args:
            encrypted_credentials: Encrypted credentials string
            
        Returns:
            Dictionary with 'api_key' and 'api_secret'
        """
        credentials = self.decrypt_credentials(encrypted_credentials)
        
        if credentials.get('exchange') != 'binance':
            raise ValueError("Invalid credentials: not Binance credentials")
        
        return {
            'api_key': credentials['api_key'],
            'api_secret': credentials['api_secret']
        }

    def encrypt_bitfinex_credentials(self, api_key: str, api_secret: str) -> str:
        """
        Encrypt Bitfinex API credentials specifically
        
        Args:
            api_key: Bitfinex API key
            api_secret: Bitfinex API secret
            
        Returns:
            Encrypted credentials string
        """
        credentials = {
            'api_key': api_key,
            'api_secret': api_secret,
            'exchange': 'bitfinex',
            'timestamp': str(int(time.time()))
        }
        return self.encrypt_credentials(credentials)

    def decrypt_bitfinex_credentials(self, encrypted_credentials: str) -> Dict[str, str]:
        """
        Decrypt Bitfinex API credentials
        
        Args:
            encrypted_credentials: Encrypted credentials string
            
        Returns:
            Dictionary with 'api_key' and 'api_secret'
        """
        credentials = self.decrypt_credentials(encrypted_credentials)
        
        if credentials.get('exchange') != 'bitfinex':
            raise ValueError("Invalid credentials: not Bitfinex credentials")
        
        return {
            'api_key': credentials['api_key'],
            'api_secret': credentials['api_secret']
        }

# Global instance for use throughout the application
credential_encryption = CredentialEncryption()
