#!/usr/bin/env python3
"""
Simple test script to verify environment variable validation works correctly.
This test doesn't require external dependencies.
"""

import os
import sys
from dotenv import load_dotenv

# Add utils directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

# Load environment variables
load_dotenv()

def test_environment_validation():
    """Test the environment validation system"""
    
    print("🧪 Testing Environment Variable Validation System")
    print("=" * 60)
    
    try:
        from env_validator import get_env_validator
        
        # Test environment validation
        env_validator = get_env_validator()
        is_valid, errors, warnings = env_validator.validate_all()
        
        print(f"\n📊 Validation Results:")
        print(f"   Valid: {is_valid}")
        print(f"   Errors: {len(errors)}")
        print(f"   Warnings: {len(warnings)}")
        
        if errors:
            print(f"\n❌ ERRORS:")
            for error in errors:
                print(f"   • {error}")
        
        if warnings:
            print(f"\n⚠️  WARNINGS:")
            for warning in warnings:
                print(f"   • {warning}")
        
        # Test getting validated values
        print(f"\n🔍 Testing Validated Values:")
        test_vars = [
            "BINANCE_API_KEY",
            "BINANCE_API_SECRET", 
            "TELEGRAM_TOKEN",
            "TELEGRAM_CHAT_ID",
            "SYMBOLS",
            "WINDOW",
            "PREDICTION_CACHE_TIME",
            "DB_PATH",
            "LOG_LEVEL"
        ]
        
        for var in test_vars:
            value = env_validator.get_validated_value(var)
            if value:
                # Mask sensitive values
                if "KEY" in var or "SECRET" in var or "TOKEN" in var:
                    masked_value = str(value)[:8] + "*" * (len(str(value)) - 8) if len(str(value)) > 8 else "*" * len(str(value))
                    print(f"   • {var}: {masked_value}")
                else:
                    print(f"   • {var}: {value}")
            else:
                print(f"   • {var}: Not set")
        
        # Test missing required variables
        print(f"\n🔍 Testing Missing Required Variables:")
        missing = env_validator.get_missing_required_vars()
        if missing:
            print(f"   Missing: {', '.join(missing)}")
        else:
            print(f"   ✅ All required variables present")
        
        # Print full validation report
        print(f"\n📋 Full Validation Report:")
        print(env_validator.get_validation_report())
        
        if is_valid:
            print(f"\n✅ Environment validation test PASSED!")
            return True
        else:
            print(f"\n❌ Environment validation test FAILED!")
            return False
            
    except Exception as e:
        print(f"\n❌ Environment validation test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_environment_validation()
    if success:
        print(f"\n🎉 All tests completed successfully!")
        sys.exit(0)
    else:
        print(f"\n💥 Tests failed!")
        sys.exit(1)
