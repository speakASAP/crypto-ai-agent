#!/usr/bin/env python3
"""
Test script for the Centralized Logging System.
This script demonstrates all logging features across the project.
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add utils directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

# Load environment variables
load_dotenv()

async def test_centralized_logging():
    """Test the centralized logging system"""
    
    print("🧪 Testing Centralized Logging System")
    print("=" * 60)
    
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
                print(f"   ⚠️  {len(warnings)} warnings found")
        else:
            print(f"   ❌ Environment validation failed with {len(errors)} errors")
            
    except Exception as e:
        print(f"   ❌ Environment validation test failed: {e}")
    
    # Test 1: Import and Initialize Logging
    print("\n1. Testing Centralized Logger Import...")
    try:
        from logger import (
            get_logger, log_function_entry, log_function_exit, log_database_operation,
            log_api_call, log_performance, log_user_action, log_system_event,
            log_error_with_context, log_warning_with_context, log_info_with_context,
            log_function_calls, log_performance_timing, central_logger
        )
        
        print("   ✅ All logging functions imported successfully")
        
        # Test logger initialization
        logger = get_logger("test_module")
        print("   ✅ Logger instance created successfully")
        
    except Exception as e:
        print(f"   ❌ Import test failed: {e}")
        return
    
    # Test 2: Basic Logging Functions
    print("\n2. Testing Basic Logging Functions...")
    try:
        # Test different log levels
        logger.debug("This is a debug message")
        logger.info("This is an info message")
        logger.warning("This is a warning message")
        logger.error("This is an error message")
        logger.critical("This is a critical message")
        
        print("   ✅ Basic logging functions working")
        
    except Exception as e:
        print(f"   ❌ Basic logging test failed: {e}")
    
    # Test 3: Structured Logging Functions
    print("\n3. Testing Structured Logging Functions...")
    try:
        # Test function entry/exit logging
        log_function_entry("test_function", "test_module", param1="value1", param2=123)
        log_function_exit("test_function", "test_module", result="success")
        
        # Test database operation logging
        log_database_operation("select", "test_table", "test_module", id=1, name="test")
        
        # Test API call logging
        log_api_call("TestAPI", "/test/endpoint", "test_module", status_code=200)
        
        # Test performance logging
        log_performance("test_operation", 0.123, "test_module", items_processed=10)
        
        # Test user action logging
        log_user_action("test_action", {"user_id": 123, "action": "test"}, "test_module")
        
        # Test system event logging
        log_system_event("test_event", "test_module", status="success", count=5)
        
        print("   ✅ Structured logging functions working")
        
    except Exception as e:
        print(f"   ❌ Structured logging test failed: {e}")
    
    # Test 4: Error Context Logging
    print("\n4. Testing Error Context Logging...")
    try:
        # Test error logging with context
        test_error = Exception("Test error for logging validation")
        log_error_with_context(test_error, "test_context", "test_module", 
                              user_id=123, operation="test_operation")
        
        # Test warning logging with context
        log_warning_with_context("Test warning message", "test_context", "test_module",
                                retry_count=2, max_retries=3)
        
        # Test info logging with context
        log_info_with_context("Test info message", "test_context", "test_module",
                             processed_items=15, total_items=20)
        
        print("   ✅ Error context logging working")
        
    except Exception as e:
        print(f"   ❌ Error context logging test failed: {e}")
    
    # Test 5: Decorator Functions
    print("\n5. Testing Logging Decorators...")
    try:
        # Test function call decorator
        @log_function_calls("test_module")
        def test_decorated_function(x, y):
            return x + y
        
        result = test_decorated_function(5, 3)
        print(f"   ✅ Function decorator working, result: {result}")
        
        # Test performance timing decorator
        @log_performance_timing("test_timing", "test_module")
        def test_timed_function():
            import time
            time.sleep(0.1)  # Simulate work
            return "completed"
        
        result = test_timed_function()
        print(f"   ✅ Performance timing decorator working, result: {result}")
        
    except Exception as e:
        print(f"   ❌ Decorator test failed: {e}")
    
    # Test 6: Log File Verification
    print("\n6. Verifying Log File Creation...")
    try:
        log_file = os.getenv("LOG_FILE", "logs/crypto_agent.log")
        
        if os.path.exists(log_file):
            print(f"   ✅ Log file created: {log_file}")
            
            # Check log file content
            with open(log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()
                
            print(f"   📄 Log file size: {len(log_content)} characters")
            
            # Count different log levels
            debug_count = log_content.count("DEBUG")
            info_count = log_content.count("INFO")
            warning_count = log_content.count("WARNING")
            error_count = log_content.count("ERROR")
            critical_count = log_content.count("CRITICAL")
            
            print(f"   📊 Log level counts:")
            print(f"      DEBUG: {debug_count}")
            print(f"      INFO: {info_count}")
            print(f"      WARNING: {warning_count}")
            print(f"      ERROR: {error_count}")
            print(f"      CRITICAL: {critical_count}")
            
            # Show sample log entries
            print(f"   📝 Sample log entries:")
            lines = log_content.split('\n')
            for i, line in enumerate(lines[-5:], 1):  # Show last 5 lines
                if line.strip():
                    print(f"      {i}. {line}")
                    
        else:
            print(f"   ⚠️  Log file not found: {log_file}")
            
    except Exception as e:
        print(f"   ❌ Log file verification failed: {e}")
    
    # Test 7: Module-Specific Loggers
    print("\n7. Testing Module-Specific Loggers...")
    try:
        # Test different module loggers
        agent_logger = get_logger("agent")
        ui_logger = get_logger("ui_dashboard")
        test_logger = get_logger("test_module")
        
        agent_logger.info("Agent module logging test")
        ui_logger.info("UI dashboard module logging test")
        test_logger.info("Test module logging test")
        
        print("   ✅ Module-specific loggers working")
        
    except Exception as e:
        print(f"   ❌ Module-specific logger test failed: {e}")
    
    print("\n🎉 Centralized Logging System Test Completed!")
    print("\nKey Features Demonstrated:")
    print("✅ Centralized logger initialization")
    print("✅ Multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    print("✅ Structured logging with context")
    print("✅ Function entry/exit logging")
    print("✅ Database operation logging")
    print("✅ API call logging")
    print("✅ Performance timing logging")
    print("✅ User action logging")
    print("✅ System event logging")
    print("✅ Error context logging")
    print("✅ Logging decorators")
    print("✅ Log file creation and content")
    print("✅ Module-specific loggers")
    
    print(f"\n📊 Logging Configuration:")
    print(f"   Log Level: {os.getenv('LOG_LEVEL', 'INFO')}")
    print(f"   Log File: {os.getenv('LOG_FILE', 'logs/crypto_agent.log')}")
    print(f"   Log Format: {os.getenv('LOG_FORMAT', 'default')}")

async def main():
    """Main test function"""
    await test_centralized_logging()

if __name__ == "__main__":
    asyncio.run(main())
