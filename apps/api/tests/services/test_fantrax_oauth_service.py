"""
Unit tests for Fantrax OAuth Service

Tests OAuth flow, token management, and error handling.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from app.services.fantrax_oauth_service import FantraxOAuthService
from app.core.security import encrypt_value, decrypt_value
from fastapi import HTTPException


class TestFantraxOAuthService:
    """Test suite for Fantrax OAuth Service"""

    def test_generate_oauth_url(self):
        """
        Test OAuth URL generation

        Verifies that the authorization URL is correctly formatted
        and includes all required parameters.
        """
        user_id = 123

        with patch('app.services.fantrax_oauth_service.settings') as mock_settings:
            mock_settings.FANTRAX_CLIENT_ID = 'test_client_id'
            mock_settings.FANTRAX_REDIRECT_URI = 'https://example.com/callback'

            url, state = FantraxOAuthService.generate_oauth_url(user_id)

            # Verify URL components
            assert 'https://www.fantrax.com/oauth/authorize' in url
            assert 'client_id=test_client_id' in url
            assert 'redirect_uri=https%3A%2F%2Fexample.com%2Fcallback' in url
            assert 'response_type=code' in url
            assert f'state={user_id}' in url

            # Verify state token
            assert state is not None
            assert len(state) > 20  # State should be sufficiently long

    def test_generate_oauth_url_missing_config(self):
        """
        Test OAuth URL generation with missing configuration

        Verifies that appropriate error is raised when OAuth settings
        are not configured.
        """
        user_id = 123

        with patch('app.services.fantrax_oauth_service.settings') as mock_settings:
            mock_settings.FANTRAX_CLIENT_ID = None

            with pytest.raises(ValueError, match="Fantrax OAuth not configured"):
                FantraxOAuthService.generate_oauth_url(user_id)

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_success(self):
        """
        Test successful token exchange

        Verifies that authorization code is correctly exchanged
        for access and refresh tokens.
        """
        auth_code = 'test_auth_code'
        mock_response = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_in': 3600,
        }

        with patch('app.services.fantrax_oauth_service.settings') as mock_settings:
            mock_settings.FANTRAX_CLIENT_ID = 'test_client_id'
            mock_settings.FANTRAX_CLIENT_SECRET = 'test_client_secret'
            mock_settings.FANTRAX_REDIRECT_URI = 'https://example.com/callback'

            with patch('httpx.AsyncClient') as mock_client:
                mock_post = AsyncMock()
                mock_post.return_value.raise_for_status = Mock()
                mock_post.return_value.json = Mock(return_value=mock_response)
                mock_client.return_value.__aenter__.return_value.post = mock_post

                result = await FantraxOAuthService.exchange_code_for_tokens(auth_code)

                assert result == mock_response
                assert result['access_token'] == 'test_access_token'
                assert result['refresh_token'] == 'test_refresh_token'

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_failure(self):
        """
        Test token exchange failure

        Verifies proper error handling when token exchange fails.
        """
        auth_code = 'invalid_code'

        with patch('app.services.fantrax_oauth_service.settings') as mock_settings:
            mock_settings.FANTRAX_CLIENT_ID = 'test_client_id'
            mock_settings.FANTRAX_CLIENT_SECRET = 'test_client_secret'
            mock_settings.FANTRAX_REDIRECT_URI = 'https://example.com/callback'

            with patch('httpx.AsyncClient') as mock_client:
                mock_post = AsyncMock()
                mock_post.return_value.raise_for_status.side_effect = Exception('HTTP Error')
                mock_client.return_value.__aenter__.return_value.post = mock_post

                result = await FantraxOAuthService.exchange_code_for_tokens(auth_code)

                assert result is None

    @pytest.mark.asyncio
    async def test_validate_state_token_valid(self):
        """
        Test state token validation with valid token

        Verifies that valid state tokens are correctly validated.
        """
        user_id = 123
        state = f"{user_id}:random_token_string"

        result = await FantraxOAuthService.validate_state_token(state, user_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_state_token_invalid(self):
        """
        Test state token validation with invalid token

        Verifies that invalid state tokens are rejected.
        """
        user_id = 123
        state = "456:random_token_string"  # Different user ID

        result = await FantraxOAuthService.validate_state_token(state, user_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_state_token_malformed(self):
        """
        Test state token validation with malformed token

        Verifies that malformed state tokens are rejected.
        """
        user_id = 123
        state = "malformed_token"  # No colon separator

        result = await FantraxOAuthService.validate_state_token(state, user_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_store_tokens_success(self):
        """
        Test successful token storage

        Verifies that tokens are encrypted and stored in database.
        """
        user_id = 123
        fantrax_user_id = 'fantrax_123'
        refresh_token = 'test_refresh_token'

        mock_db = AsyncMock()
        mock_result = Mock()
        mock_result.rowcount = 1
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await FantraxOAuthService.store_tokens(
            mock_db,
            user_id,
            fantrax_user_id,
            refresh_token
        )

        assert result is True
        assert mock_db.execute.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_store_tokens_user_not_found(self):
        """
        Test token storage with non-existent user

        Verifies that appropriate error is raised when user doesn't exist.
        """
        user_id = 999
        fantrax_user_id = 'fantrax_123'
        refresh_token = 'test_refresh_token'

        mock_db = AsyncMock()
        mock_result = Mock()
        mock_result.rowcount = 0
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await FantraxOAuthService.store_tokens(
                mock_db,
                user_id,
                fantrax_user_id,
                refresh_token
            )

        assert exc_info.value.status_code == 404
        assert "User not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_refresh_access_token_success(self):
        """
        Test successful access token refresh

        Verifies that refresh token is used to obtain new access token.
        """
        encrypted_refresh_token = encrypt_value('test_refresh_token')
        mock_response = {
            'access_token': 'new_access_token',
            'expires_in': 3600,
        }

        with patch('app.services.fantrax_oauth_service.settings') as mock_settings:
            mock_settings.FANTRAX_CLIENT_ID = 'test_client_id'
            mock_settings.FANTRAX_CLIENT_SECRET = 'test_client_secret'

            with patch('httpx.AsyncClient') as mock_client:
                mock_post = AsyncMock()
                mock_post.return_value.raise_for_status = Mock()
                mock_post.return_value.json = Mock(return_value=mock_response)
                mock_client.return_value.__aenter__.return_value.post = mock_post

                result = await FantraxOAuthService.refresh_access_token(encrypted_refresh_token)

                assert result == mock_response
                assert result['access_token'] == 'new_access_token'
