"""
Service for managing user Binance API credentials
"""
from typing import Optional, Dict, Any
from ..dependencies.auth import get_db_connection
from ..core.config import settings
from ..utils.encryption import credential_encryption
from .binance_import_service import BinanceImportService
from ..utils.logger import get_logger

logger = get_logger("backend.app.services.binance_credential_service")

class BinanceCredentialService:
    """Service for managing user Binance API credentials"""
    
    def __init__(self):
        self.encryption = credential_encryption
    
    def save_user_credentials(self, user_id: int, api_key: str, api_secret: str) -> bool:
        """
        Save encrypted Binance credentials for a user
        
        Args:
            user_id: User ID
            api_key: Binance API key
            api_secret: Binance API secret
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Encrypt credentials
            encrypted_credentials = self.encryption.encrypt_binance_credentials(api_key, api_secret)
            
            # Insert or update credentials using PostgreSQL ON CONFLICT
            cursor.execute(
                """
                INSERT INTO user_api_credentials (user_id, exchange, encrypted_credentials, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                ON CONFLICT (user_id, exchange)
                DO UPDATE SET encrypted_credentials = EXCLUDED.encrypted_credentials, updated_at = NOW()
                """,
                (user_id, 'binance', encrypted_credentials)
            )
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Saved Binance credentials for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving Binance credentials for user {user_id}: {e}")
            if 'conn' in locals():
                conn.close()
            return False
    
    def get_user_credentials(self, user_id: int) -> Optional[Dict[str, str]]:
        """
        Get decrypted Binance credentials for a user
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with 'api_key' and 'api_secret' or None if not found
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT encrypted_credentials FROM user_api_credentials WHERE user_id = %s AND exchange = 'binance'",
                (user_id,)
            )
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                encrypted_credentials = result[0]
                credentials = self.encryption.decrypt_binance_credentials(encrypted_credentials)
                logger.info(f"✅ Retrieved Binance credentials for user {user_id}")
                return credentials
            else:
                logger.info(f"ℹ️ No Binance credentials found for user {user_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting Binance credentials for user {user_id}: {e}")
            if 'conn' in locals():
                conn.close()
            return None
    
    def delete_user_credentials(self, user_id: int) -> bool:
        """
        Delete Binance credentials for a user
        
        Args:
            user_id: User ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "DELETE FROM user_api_credentials WHERE user_id = %s AND exchange = 'binance'",
                (user_id,)
            )
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Deleted Binance credentials for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error deleting Binance credentials for user {user_id}: {e}")
            if 'conn' in locals():
                conn.close()
            return False
    
    def has_user_credentials(self, user_id: int) -> bool:
        """
        Check if user has Binance credentials stored
        
        Args:
            user_id: User ID
            
        Returns:
            True if credentials exist, False otherwise
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT COUNT(*) FROM user_api_credentials WHERE user_id = %s AND exchange = 'binance'",
                (user_id,)
            )
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count > 0
            
        except Exception as e:
            logger.error(f"❌ Error checking Binance credentials for user {user_id}: {e}")
            if 'conn' in locals():
                conn.close()
            return False
    
    async def test_user_credentials(self, user_id: int) -> Dict[str, Any]:
        """
        Test user's Binance credentials
        
        Args:
            user_id: User ID
            
        Returns:
            Test result dictionary
        """
        try:
            credentials = self.get_user_credentials(user_id)
            if not credentials:
                return {
                    'success': False,
                    'message': 'No Binance credentials found. Please add your API keys first.',
                    'error_code': 'NO_CREDENTIALS'
                }
            
            # Create BinanceImportService with user credentials
            binance_service = BinanceImportService(
                api_key=credentials['api_key'],
                api_secret=credentials['api_secret']
            )
            
            # Test the connection
            result = await binance_service.test_api_connection()
            
            if result['success']:
                logger.info(f"✅ Binance credentials test successful for user {user_id}")
            else:
                logger.warning(f"⚠️ Binance credentials test failed for user {user_id}: {result['message']}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error testing Binance credentials for user {user_id}: {e}")
            return {
                'success': False,
                'message': f'Credential test failed: {str(e)}',
                'error': str(e)
            }
    
    async def import_user_portfolio(self, user_id: int) -> Dict[str, Any]:
        """
        Import portfolio using user's Binance credentials
        
        Args:
            user_id: User ID
            
        Returns:
            Import result dictionary
        """
        try:
            credentials = self.get_user_credentials(user_id)
            if not credentials:
                return {
                    'success': False,
                    'message': 'No Binance credentials found. Please add your API keys first.',
                    'error_code': 'NO_CREDENTIALS'
                }
            
            # Create BinanceImportService with user credentials
            binance_service = BinanceImportService(
                api_key=credentials['api_key'],
                api_secret=credentials['api_secret']
            )
            
            # Import portfolio
            result = await binance_service.import_portfolio(user_id)
            
            if result['success']:
                logger.info(f"✅ Portfolio import successful for user {user_id}: {result['items_imported']} items")
            else:
                logger.warning(f"⚠️ Portfolio import failed for user {user_id}: {result['message']}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error importing portfolio for user {user_id}: {e}")
            return {
                'success': False,
                'message': f'Portfolio import failed: {str(e)}',
                'error': str(e)
            }

# Global instance
binance_credential_service = BinanceCredentialService()
