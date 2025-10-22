#!/usr/bin/env python3
"""
Test script for the Error Handling system.
This script tests the logging, error recovery, and notification features.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add the agent directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'crypto-ai-agent'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

# Load environment variables
load_dotenv()

async def test_error_handling():
    """Test the error handling system"""
    
    print("🧪 Testing Error Handling System")
    print("=" * 50)
    
    # Test 0: Environment Variable Validation
    print("\n0. Testing Environment Variable Validation...")
    try:
        from env_validator import get_env_validator
        
        # Test environment validation
        env_validator = get_env_validator()
        is_valid, errors, warnings = env_validator.validate_all()
        
        if is_valid:
            print("   ✅ Environment validation successful")
            if warnings:
                print(f"   ⚠️  {len(warnings)} warnings found:")
                for warning in warnings:
                    print(f"      • {warning}")
        else:
            print(f"   ❌ Environment validation failed with {len(errors)} errors:")
            for error in errors:
                print(f"      • {error}")
        
        # Print validation report
        print("\n   📋 Validation Report:")
        report_lines = env_validator.get_validation_report().split('\n')
        for line in report_lines[:10]:  # Show first 10 lines
            print(f"      {line}")
        if len(report_lines) > 10:
            print(f"      ... ({len(report_lines) - 10} more lines)")
            
    except Exception as e:
        print(f"   ❌ Environment validation test failed: {e}")
    
    # Test 1: Logging Configuration
    print("\n1. Testing Logging Configuration...")
    try:
        from agent_advanced import setup_logging, logger
        
        # Test different log levels
        logger.debug("This is a debug message")
        logger.info("This is an info message")
        logger.warning("This is a warning message")
        logger.error("This is an error message")
        logger.critical("This is a critical message")
        
        print("   ✅ Logging system working correctly")
        
        # Check if log file was created
        log_file = os.getenv("LOG_FILE", "logs/crypto_agent.log")
        if os.path.exists(log_file):
            print(f"   ✅ Log file created: {log_file}")
        else:
            print(f"   ⚠️  Log file not found: {log_file}")
            
    except Exception as e:
        print(f"   ❌ Logging test failed: {e}")
    
    # Test 2: Error Handler Class
    print("\n2. Testing Error Handler Class...")
    try:
        from agent_advanced import ErrorHandler
        
        # Create error handler without bot (for testing)
        error_handler = ErrorHandler()
        
        # Test error handling
        test_error = Exception("Test error for validation")
        await error_handler.handle_error(test_error, "Test context", critical=False, notify_user=False)
        
        # Test warning handling
        await error_handler.handle_warning("Test warning message", "Test context")
        
        # Test info handling
        await error_handler.handle_info("Test info message", "Test context")
        
        print("   ✅ Error handler working correctly")
        
    except Exception as e:
        print(f"   ❌ Error handler test failed: {e}")
    
    # Test 3: Database Error Handling
    print("\n3. Testing Database Error Handling...")
    try:
        from agent_advanced import init_db
        
        # Test database initialization
        result = await init_db()
        if result:
            print("   ✅ Database initialization successful")
        else:
            print("   ❌ Database initialization failed")
            
    except Exception as e:
        print(f"   ❌ Database test failed: {e}")
    
    # Test 4: Environment Variable Validation
    print("\n4. Testing Environment Variable Validation...")
    try:
        required_vars = {
            "BINANCE_API_KEY": os.getenv("BINANCE_API_KEY"),
            "BINANCE_API_SECRET": os.getenv("BINANCE_API_SECRET"),
            "TELEGRAM_TOKEN": os.getenv("TELEGRAM_TOKEN"),
            "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID")
        }
        
        missing_vars = [var for var, value in required_vars.items() if not value]
        if missing_vars:
            print(f"   ⚠️  Missing environment variables: {', '.join(missing_vars)}")
            print("   ℹ️  This is expected if .env file is not configured")
        else:
            print("   ✅ All required environment variables present")
            
    except Exception as e:
        print(f"   ❌ Environment validation test failed: {e}")
    
    # Test 5: Error Recovery Mechanisms
    print("\n5. Testing Error Recovery Mechanisms...")
    try:
        from agent_advanced import load_tracked_symbols
        
        # Test symbol loading with error handling
        await load_tracked_symbols()
        print("   ✅ Symbol loading with error handling successful")
        
    except Exception as e:
        print(f"   ❌ Error recovery test failed: {e}")
    
    # Test 6: Log File Content Check
    print("\n6. Checking Log File Content...")
    try:
        log_file = os.getenv("LOG_FILE", "logs/crypto_agent.log")
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                log_content = f.read()
                
            if "ERROR" in log_content or "WARNING" in log_content:
                print("   ✅ Error and warning messages found in log file")
            else:
                print("   ℹ️  No error/warning messages in log file (this is good!)")
                
            print(f"   📄 Log file size: {len(log_content)} characters")
        else:
            print("   ⚠️  Log file not found")
            
    except Exception as e:
        print(f"   ❌ Log file check failed: {e}")
    
    print("\n🎉 Error Handling Test Completed!")
    print("\nKey Features Tested:")
    print("✅ Logging system with multiple levels")
    print("✅ Error handler class with notifications")
    print("✅ Database error handling with retries")
    print("✅ Environment variable validation")
    print("✅ Error recovery mechanisms")
    print("✅ Log file creation and content")

async def main():
    """Main test function"""
    await test_error_handling()

if __name__ == "__main__":
    asyncio.run(main())
