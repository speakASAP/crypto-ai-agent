# TELEGRAM INTEGRATION ENHANCEMENT PLAN

> 📚 **Documentation Navigation**: [Main README](README.md) | [Current Plan](CURRENT_PLAN.md) | [Price Alerts Plan](PRICE_ALERTS_PLAN.md) | [Multi-Currency Plan](MULTI_CURRENCY_PORTFOLIO_PLAN.md)

## PROJECT STATUS

**Current Issue**: Telegram notifications currently use global environment variables only
**Priority**: HIGH - Users need personal Telegram bot integration for privacy and control
**Impact**: Users cannot configure their own Telegram bots for personal notifications

## CURRENT IMPLEMENTATION

### Existing Telegram Integration

- ✅ Global Telegram bot token and chat ID from .env file
- ✅ Price alert notifications via Telegram
- ✅ Alert history and management system
- ✅ WebSocket-based real-time notifications

### Missing Features

- ❌ User-specific Telegram bot configuration
- ❌ Personal Telegram credentials in user profile
- ❌ Fallback mechanism from user settings to global settings
- ❌ UI for managing personal Telegram settings

## TECHNICAL SPECIFICATION

### OVERVIEW

Implement user-specific Telegram integration that allows users to:

1. Configure their own Telegram bot token and chat ID in profile settings
2. Use personal Telegram credentials for price alert notifications
3. Fall back to global .env settings when user settings are not available
4. Test their Telegram connection before saving settings
5. Maintain privacy and control over their notifications

### IMPLEMENTATION PHASES

#### PHASE 1: DATABASE SCHEMA UPDATES

**File**: `backend/app/main.py`

- Add `telegram_bot_token` and `telegram_chat_id` columns to users table
- Update database initialization to create new columns
- Update UserResponse model to include Telegram fields
- Update UserProfileUpdate model to include Telegram fields

#### PHASE 2: BACKEND API ENHANCEMENTS

**File**: `backend/app/main.py`

- Update profile update endpoint to handle Telegram credentials
- Add validation for Telegram bot token format
- Add test Telegram connection endpoint
- Update user response models

#### PHASE 3: TELEGRAM INTEGRATION ENHANCEMENT WITH FALLBACK LOGIC

**File**: `backend/app/main.py`

- **CRITICAL**: Modify `send_telegram_notification` function to use user-specific credentials with .env fallback
- Update `check_and_trigger_alerts` function to pass user_id to notification function
- Create new `send_user_telegram_notification` function with fallback logic
- Update alert triggering to use individual user Telegram settings with fallback
- Add comprehensive error handling for both user and global settings

#### PHASE 4: FRONTEND UI COMPONENTS

**File**: `frontend/src/app/profile/page.tsx`

- Add new "Telegram Settings" tab to profile page
- Create form fields for Telegram bot token and chat ID
- Add instructions for obtaining Telegram credentials
- Add test connection button
- Update profile data state management

#### PHASE 5: TYPES AND STORES UPDATES

**Files**:

- `frontend/src/types/auth.ts`
- `frontend/src/stores/authStore.ts`

- Update TypeScript interfaces to include Telegram fields
- Update auth store to handle Telegram settings
- Update API client methods

#### PHASE 6: TESTING AND VALIDATION

- Test user-specific Telegram settings
- Test fallback to global .env settings
- Test mixed scenarios (some users with settings, some without)
- Test error handling for invalid credentials
- Validate complete user flow

### DATABASE SCHEMA CHANGES

#### Update Users Table

```sql
ALTER TABLE users ADD COLUMN telegram_bot_token TEXT;
ALTER TABLE users ADD COLUMN telegram_chat_id TEXT;
```

#### Updated UserResponse Model

```python
class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    preferred_currency: str
    is_active: bool
    created_at: str
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
```

#### Updated UserProfileUpdate Model

```python
class UserProfileUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    preferred_currency: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    @validator('telegram_bot_token')
    def validate_telegram_bot_token(cls, v):
        if v is not None and v.strip():
            # Basic validation for Telegram bot token format
            if not v.startswith(('1', '2', '3', '4', '5', '6', '7', '8', '9')) or ':' not in v:
                raise ValueError('Invalid Telegram bot token format')
        return v
```

### FALLBACK LOGIC IMPLEMENTATION

#### Core Fallback Function

```python
async def send_user_telegram_notification(user_id: int, message: str):
    """Send Telegram notification using user-specific credentials with .env fallback"""
    try:
        # Try to get user's personal Telegram credentials
        user_credentials = get_user_telegram_credentials(user_id)
        
        if user_credentials and user_credentials['bot_token'] and user_credentials['chat_id']:
            # Use user's personal settings
            logger.info(f"Using user-specific Telegram credentials for user {user_id}")
            return await send_telegram_notification_with_credentials(
                message, 
                user_credentials['bot_token'], 
                user_credentials['chat_id']
            )
        else:
            # Fall back to global .env settings
            logger.info(f"Using global Telegram credentials for user {user_id} (no user settings)")
            return await send_telegram_notification(message)  # Uses .env
            
    except Exception as e:
        logger.error(f"Error sending Telegram notification for user {user_id}: {e}")
        return False

def get_user_telegram_credentials(user_id: int) -> Optional[dict]:
    """Get user's personal Telegram credentials from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT telegram_bot_token, telegram_chat_id FROM users WHERE id = ?", 
            (user_id,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] and result[1]:
            return {
                'bot_token': result[0],
                'chat_id': result[1]
            }
        return None
    except Exception as e:
        logger.error(f"Error getting user Telegram credentials: {e}")
        return None
```

### IMPLEMENTATION CHECKLIST

#### Database Layer

1. Add telegram_bot_token column to users table
2. Add telegram_chat_id column to users table  
3. Update database initialization in init_database()
4. Update UserResponse model with Telegram fields
5. Update UserProfileUpdate model with Telegram fields
6. Add validation for Telegram bot token format

#### Backend API

7. Update profile update endpoint to handle Telegram credentials
8. Add test Telegram connection endpoint
9. Update user response serialization
10. Add comprehensive logging for Telegram operations

#### **CRITICAL: Telegram Integration with Fallback Logic**

11. **Modify `send_telegram_notification` function to accept user_id parameter**
12. **Create `get_user_telegram_credentials(user_id)` function that:**
    - Queries database for user's Telegram settings
    - Returns user settings if available, otherwise returns None
13. **Create `send_user_telegram_notification(user_id, message)` function that:**
    - Gets user's personal Telegram credentials
    - Falls back to global .env settings if user settings are empty
    - Logs which credential source is being used (user vs global)
    - Calls the existing notification logic
14. **Update `check_and_trigger_alerts` to pass user_id to notification function**
15. **Update all alert triggering calls to use user-specific function**
16. **Add comprehensive error handling for both user and global settings**

#### Frontend UI

17. Add "Telegram Settings" tab to profile page
18. Create Telegram bot token input field
19. Create Telegram chat ID input field
20. Add step-by-step instructions for obtaining credentials
21. Add test connection button
22. Add clear indication that these are optional (global settings will be used as fallback)
23. Update profile data state management

#### Types and Stores

24. Update TypeScript interfaces to include Telegram fields
25. Update auth store to handle Telegram settings
26. Update API client methods

#### Testing and Validation

27. Test user-specific Telegram settings
28. Test fallback to global .env settings
29. Test mixed scenarios (some users with settings, some without)
30. Test error handling for invalid credentials
31. Validate complete user flow

### USER INSTRUCTIONS FOR TELEGRAM SETUP

#### How to Get Telegram Bot Token

1. Open Telegram and search for @BotFather
2. Start a chat with @BotFather
3. Send `/newbot` command
4. Follow the instructions to create your bot
5. Copy the bot token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
6. Paste the token in the "Telegram Bot Token" field

#### How to Get Telegram Chat ID

1. Start a chat with your bot (search for the bot name you created)
2. Send any message to the bot
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find your chat ID in the response (look for "chat":{"id":123456789})
5. Copy the chat ID number
6. Paste the chat ID in the "Telegram Chat ID" field

#### Testing Your Setup

1. Click "Test Connection" button
2. You should receive a test message in your Telegram chat
3. If successful, save your settings
4. If failed, check your credentials and try again

### TECHNICAL REQUIREMENTS

#### Dependencies

- FastAPI (already available)
- SQLite (already available)
- aiohttp (already available)
- Pydantic (already available)

#### Database

- SQLite with new columns (telegram_bot_token, telegram_chat_id)
- No breaking changes to existing schema
- Backward compatibility maintained

#### Performance Targets

- Handle user-specific Telegram settings efficiently
- Fallback logic with <100ms overhead
- Support real-time notifications
- Cache user credentials for performance

#### Error Handling

- Graceful handling of missing user Telegram settings
- Fallback to global settings when user settings are empty
- User-friendly error messages for invalid credentials
- Automatic recovery from Telegram API errors

### FILE STRUCTURE

#### Files Modified

- `backend/app/main.py` - Backend API and Telegram integration
- `frontend/src/app/profile/page.tsx` - Profile UI with Telegram settings
- `frontend/src/types/auth.ts` - TypeScript interfaces
- `frontend/src/stores/authStore.ts` - State management

#### New Functions Added

- `get_user_telegram_credentials(user_id)` - Get user Telegram settings
- `send_user_telegram_notification(user_id, message)` - Send with fallback
- `test_telegram_connection(user_id)` - Test user's Telegram setup

### SUCCESS CRITERIA

- Users can configure their own Telegram bot in profile settings
- System falls back to global .env settings when user settings are empty
- Price alerts work with both user-specific and global Telegram settings
- UI provides clear instructions for obtaining Telegram credentials
- Test connection functionality works reliably
- Error handling works for edge cases
- All operations are properly logged
- Integration with existing UI is seamless

### IMPLEMENTATION TIMELINE

- **Phase 1-2**: Database and API (1-2 hours)
- **Phase 3**: Telegram Integration with Fallback (2-3 hours)
- **Phase 4-5**: Frontend UI and Types (2-3 hours)
- **Phase 6**: Testing & Validation (1-2 hours)

**Total Estimated Time**: 6-10 hours

---

## 📋 Related Documentation

- **[Main README](README.md)** - Complete project overview and setup instructions
- **[CURRENT_PLAN.md](CURRENT_PLAN.md)** - Current implementation status and completed features
- **[PRICE_ALERTS_PLAN.md](PRICE_ALERTS_PLAN.md)** - Price alerts implementation details
- **[LOGGING_CONFIG.md](LOGGING_CONFIG.md)** - Detailed logging system configuration

---

*Plan created: 2025-01-24*
*Status: READY FOR EXECUTION*
*Priority: HIGH - User-specific Telegram integration with fallback to global settings*
