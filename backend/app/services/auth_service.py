"""
Auth Service
Service to handle authentication via auth-microservice
"""

import os
import httpx
from typing import Optional, Dict, Any
from fastapi import HTTPException
from ..core.config import settings

logger = None
try:
    from utils.logger import get_logger
    logger = get_logger("backend.app.services.auth_service")
except Exception:
    try:
        from ..utils.logger import get_logger
        logger = get_logger("backend.app.services.auth_service")
    except Exception:
        import logging
        logger = logging.getLogger("backend.app.services.auth_service")


class AuthService:
    """Service for interacting with auth-microservice"""

    def __init__(self):
        self.auth_service_url = os.getenv(
            'AUTH_SERVICE_URL',
            'https://auth.statex.cz'
        )
        self.timeout = 10.0

    async def register(
        self,
        email: str,
        password: str,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Register a new user via auth-microservice

        Args:
            email: User email
            password: User password
            username: Optional username
            full_name: Optional full name

        Returns:
            Dict with user data and tokens

        Raises:
            HTTPException: If registration fails
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.auth_service_url}/auth/register",
                    json={
                        "email": email,
                        "password": password,
                        "firstName": full_name.split()[0] if full_name and ' ' in full_name else full_name,
                        "lastName": ' '.join(full_name.split()[1:]) if full_name and ' ' in full_name else None,
                    },
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 201 or response.status_code == 200:
                    data = response.json()
                    # Map auth-microservice response to expected format
                    return {
                        "access_token": data.get("accessToken"),
                        "refresh_token": data.get("refreshToken"),
                        "user": {
                            "id": data.get("user", {}).get("id"),
                            "email": data.get("user", {}).get("email"),
                            "username": username or email.split("@")[0],
                            "full_name": full_name or f"{data.get('user', {}).get('firstName', '')} {data.get('user', {}).get('lastName', '')}".strip(),
                            "preferred_currency": "USD",
                            "is_active": data.get("user", {}).get("isActive", True),
                            "created_at": data.get("user", {}).get("createdAt"),
                        }
                    }
                elif response.status_code == 409:
                    raise HTTPException(
                        status_code=400,
                        detail="Email or username already registered"
                    )
                else:
                    error_detail = response.json().get("message", "Registration failed")
                    logger.error(f"Registration failed: {error_detail}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=error_detail
                    )
        except httpx.TimeoutException:
            logger.error("Auth service timeout during registration")
            raise HTTPException(
                status_code=503,
                detail="Authentication service is temporarily unavailable"
            )
        except httpx.RequestError as e:
            logger.error(f"Auth service request error during registration: {e}")
            raise HTTPException(
                status_code=503,
                detail="Authentication service is temporarily unavailable"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during registration: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Registration failed"
            )

    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """
        Login user via auth-microservice

        Args:
            email: User email
            password: User password

        Returns:
            Dict with user data and tokens

        Raises:
            HTTPException: If login fails
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.auth_service_url}/auth/login",
                    json={
                        "email": email,
                        "password": password,
                    },
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200 or response.status_code == 201:
                    data = response.json()
                    # Map auth-microservice response to expected format
                    user_data = data.get("user", {})
                    return {
                        "access_token": data.get("accessToken"),
                        "refresh_token": data.get("refreshToken"),
                        "user": {
                            "id": user_data.get("id"),
                            "email": user_data.get("email"),
                            "username": email.split("@")[0],  # Use email prefix as username
                            "full_name": f"{user_data.get('firstName', '')} {user_data.get('lastName', '')}".strip() or None,
                            "preferred_currency": "USD",
                            "is_active": user_data.get("isActive", True),
                            "created_at": user_data.get("createdAt"),
                        }
                    }
                elif response.status_code == 401:
                    raise HTTPException(
                        status_code=401,
                        detail="Invalid email or password"
                    )
                else:
                    error_detail = response.json().get("message", "Login failed")
                    logger.error(f"Login failed: {error_detail}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=error_detail
                    )
        except httpx.TimeoutException:
            logger.error("Auth service timeout during login")
            raise HTTPException(
                status_code=503,
                detail="Authentication service is temporarily unavailable"
            )
        except httpx.RequestError as e:
            logger.error(f"Auth service request error during login: {e}")
            raise HTTPException(
                status_code=503,
                detail="Authentication service is temporarily unavailable"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during login: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Login failed"
            )

    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate JWT token via auth-microservice

        Args:
            token: JWT token to validate

        Returns:
            Dict with user data if token is valid

        Raises:
            HTTPException: If token is invalid
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.auth_service_url}/auth/validate",
                    json={"token": token},
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("valid") and data.get("user"):
                        return data["user"]
                    else:
                        raise HTTPException(
                            status_code=401,
                            detail="Invalid token"
                        )
                else:
                    raise HTTPException(
                        status_code=401,
                        detail="Invalid token"
                    )
        except httpx.TimeoutException:
            logger.error("Auth service timeout during token validation")
            raise HTTPException(
                status_code=503,
                detail="Authentication service is temporarily unavailable"
            )
        except httpx.RequestError as e:
            logger.error(f"Auth service request error during token validation: {e}")
            raise HTTPException(
                status_code=503,
                detail="Authentication service is temporarily unavailable"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during token validation: {e}", exc_info=True)
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token via auth-microservice

        Args:
            refresh_token: Refresh token

        Returns:
            Dict with new tokens and user data

        Raises:
            HTTPException: If refresh fails
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.auth_service_url}/auth/refresh",
                    json={"refreshToken": refresh_token},
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    data = response.json()
                    user_data = data.get("user", {})
                    return {
                        "access_token": data.get("accessToken"),
                        "refresh_token": data.get("refreshToken"),
                        "user": {
                            "id": user_data.get("id"),
                            "email": user_data.get("email"),
                            "username": user_data.get("email", "").split("@")[0],
                            "full_name": f"{user_data.get('firstName', '')} {user_data.get('lastName', '')}".strip() or None,
                            "preferred_currency": "USD",
                            "is_active": user_data.get("isActive", True),
                        }
                    }
                else:
                    raise HTTPException(
                        status_code=401,
                        detail="Invalid refresh token"
                    )
        except httpx.TimeoutException:
            logger.error("Auth service timeout during token refresh")
            raise HTTPException(
                status_code=503,
                detail="Authentication service is temporarily unavailable"
            )
        except httpx.RequestError as e:
            logger.error(f"Auth service request error during token refresh: {e}")
            raise HTTPException(
                status_code=503,
                detail="Authentication service is temporarily unavailable"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during token refresh: {e}", exc_info=True)
            raise HTTPException(
                status_code=401,
                detail="Invalid refresh token"
            )


    async def request_password_reset(self, email: str) -> Dict[str, Any]:
        """
        Request password reset via auth-microservice

        Args:
            email: User email

        Returns:
            Dict with message

        Raises:
            HTTPException: If request fails
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.auth_service_url}/auth/password-reset-request",
                    json={"email": email},
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    error_detail = response.json().get("message", "Password reset request failed")
                    logger.error(f"Password reset request failed: {error_detail}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=error_detail
                    )
        except httpx.TimeoutException:
            logger.error("Auth service timeout during password reset request")
            raise HTTPException(
                status_code=503,
                detail="Authentication service is temporarily unavailable"
            )
        except httpx.RequestError as e:
            logger.error(f"Auth service request error during password reset request: {e}")
            raise HTTPException(
                status_code=503,
                detail="Authentication service is temporarily unavailable"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during password reset request: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Password reset request failed"
            )

    async def confirm_password_reset(self, token: str, new_password: str) -> Dict[str, Any]:
        """
        Confirm password reset via auth-microservice

        Args:
            token: Reset token
            new_password: New password

        Returns:
            Dict with message

        Raises:
            HTTPException: If confirmation fails
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.auth_service_url}/auth/password-reset-confirm",
                    json={"token": token, "newPassword": new_password},
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    error_detail = response.json().get("message", "Password reset confirmation failed")
                    logger.error(f"Password reset confirmation failed: {error_detail}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=error_detail
                    )
        except httpx.TimeoutException:
            logger.error("Auth service timeout during password reset confirmation")
            raise HTTPException(
                status_code=503,
                detail="Authentication service is temporarily unavailable"
            )
        except httpx.RequestError as e:
            logger.error(f"Auth service request error during password reset confirmation: {e}")
            raise HTTPException(
                status_code=503,
                detail="Authentication service is temporarily unavailable"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during password reset confirmation: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Password reset confirmation failed"
            )

    async def change_password(self, current_password: str, new_password: str, access_token: str) -> Dict[str, Any]:
        """
        Change password via auth-microservice (requires authentication)

        Args:
            current_password: Current password
            new_password: New password
            access_token: JWT access token

        Returns:
            Dict with message

        Raises:
            HTTPException: If password change fails
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.auth_service_url}/auth/password-change",
                    json={"currentPassword": current_password, "newPassword": new_password},
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {access_token}",
                    },
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    raise HTTPException(
                        status_code=401,
                        detail="Invalid current password or unauthorized"
                    )
                else:
                    error_detail = response.json().get("message", "Password change failed")
                    logger.error(f"Password change failed: {error_detail}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=error_detail
                    )
        except httpx.TimeoutException:
            logger.error("Auth service timeout during password change")
            raise HTTPException(
                status_code=503,
                detail="Authentication service is temporarily unavailable"
            )
        except httpx.RequestError as e:
            logger.error(f"Auth service request error during password change: {e}")
            raise HTTPException(
                status_code=503,
                detail="Authentication service is temporarily unavailable"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during password change: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Password change failed"
            )


# Create singleton instance
auth_service = AuthService()

