#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import unittest
from unittest.mock import MagicMock, patch

import tweepy

from config import AppConfig
from services.twitter_client import TwitterClient

class TestTwitterClient(unittest.TestCase):
    """Unit tests for the TwitterClient."""

    def setUp(self):
        """Set up a mock config for testing."""
        self.mock_config = AppConfig(
            chains=['base'],
            tokens=['AERO'],
            telegram_enabled=False,
            twitter_enabled=True,
            twitter_api_key='test_key',
            twitter_api_secret='test_secret',
            twitter_access_token='test_token',
            twitter_access_token_secret='test_token_secret',
            # Fill in other required AppConfig fields with dummy data
            dex_fee=0.3, slippage=0.5, min_bullish_profit=0.0, min_bearish_discrepancy=1.0,
            min_momentum_score_bullish=0.0, min_momentum_score_bearish=0.0, trade_volume=500,
            min_liquidity=1000, min_volume=1000, min_txns_h1=1, interval=60, min_profit=0.0,
            alert_cooldown=3600, etherscan_api_key='dummy_etherscan',
            telegram_bot_token=None, telegram_chat_id=None, coingecko_api_key=None,
            gemini_api_key=None, ai_analysis_enabled=True, multi_leg=False, max_cycle_length=3, max_depth=2,
            scanner_enabled=False,
            min_tweet_momentum_score=6.0,
            show_momentum=False,
            momentum_limit=10,
            momentum_token=None,
            momentum_direction=None,
            limit_base_dexes=False,
            integration_test=False,
            auto_trade=False,
            trade_rpc_url=None,
            trade_wallet_address=None,
            trade_max_slippage=1.0,
            trading_private_key=None,
            twitter_client_id=None,
            twitter_client_secret=None,
            twitter_oauth2_access_token=None,
            twitter_oauth2_refresh_token=None,
            onchain_validation_enabled=False,
            onchain_validation_rpc_url=None,
            onchain_validation_max_pct_diff=5.0,
            onchain_validation_timeout=8.0,
        )

    @patch('tweepy.Client')
    def test_post_tweet(self, mock_tweepy_client):
        """Test that the post_tweet method calls the tweepy client with the correct text."""
        # Arrange
        mock_client_instance = MagicMock()
        mock_tweepy_client.return_value = mock_client_instance
        
        twitter_client = TwitterClient(self.mock_config)
        tweet_text = "This is a test tweet."

        # Act
        twitter_client.post_tweet(tweet_text)

        # Assert
        mock_tweepy_client.assert_called_once_with(
            consumer_key='test_key',
            consumer_secret='test_secret',
            access_token='test_token',
            access_token_secret='test_token_secret'
        )
        mock_client_instance.create_tweet.assert_called_once_with(text=tweet_text)

    def test_initialization_raises_error_if_credentials_missing(self):
        """Test that ValueError is raised if Twitter credentials are not set."""
        # Arrange
        invalid_config = self.mock_config._replace(twitter_api_key=None)

        # Act & Assert
        with self.assertRaises(ValueError):
            TwitterClient(invalid_config)

    @patch('tweepy.Client')
    def test_oauth2_initialisation(self, mock_tweepy_client):
        oauth2_config = self.mock_config._replace(
            twitter_api_key=None,
            twitter_api_secret=None,
            twitter_access_token=None,
            twitter_access_token_secret=None,
            twitter_client_id='client-id',
            twitter_client_secret='client-secret',
            twitter_oauth2_access_token='access-token',
            twitter_oauth2_refresh_token='refresh-token',
        )

        mock_client_instance = MagicMock()
        mock_tweepy_client.return_value = mock_client_instance

        twitter_client = TwitterClient(oauth2_config)
        twitter_client.post_tweet("OAuth2 tweet")

        mock_tweepy_client.assert_called_once_with(
            client_id='client-id',
            client_secret='client-secret',
            access_token='access-token',
            refresh_token='refresh-token'
        )
        mock_client_instance.create_tweet.assert_called_once_with(text="OAuth2 tweet")

    @patch('tweepy.Client')
    def test_oauth2_refresh_flow(self, mock_tweepy_client):
        oauth2_config = self.mock_config._replace(
            twitter_api_key=None,
            twitter_api_secret=None,
            twitter_access_token=None,
            twitter_access_token_secret=None,
            twitter_client_id='client-id',
            twitter_client_secret='client-secret',
            twitter_oauth2_access_token='old-access',
            twitter_oauth2_refresh_token='old-refresh',
        )

        first_client = MagicMock()
        second_client = MagicMock()
        unauthorized_response = MagicMock(status_code=401, text='expired', status=401)
        first_client.create_tweet.side_effect = [tweepy.errors.Unauthorized(unauthorized_response)]
        first_client.refresh_token.return_value = {
            'access_token': 'new-access',
            'refresh_token': 'new-refresh',
        }
        second_client.create_tweet.return_value = None

        mock_tweepy_client.side_effect = [first_client, second_client]

        twitter_client = TwitterClient(oauth2_config)
        twitter_client.post_tweet("Refresh me")

        # First client created during initialisation
        initial_call_kwargs = mock_tweepy_client.call_args_list[0].kwargs
        self.assertEqual(initial_call_kwargs['access_token'], 'old-access')
        self.assertEqual(initial_call_kwargs['refresh_token'], 'old-refresh')

        # Second client created after refresh with new tokens
        refreshed_call_kwargs = mock_tweepy_client.call_args_list[1].kwargs
        self.assertEqual(refreshed_call_kwargs['access_token'], 'new-access')
        self.assertEqual(refreshed_call_kwargs['refresh_token'], 'new-refresh')

        second_client.create_tweet.assert_called_once_with(text="Refresh me")
        self.assertEqual(twitter_client._oauth2_access_token, 'new-access')
        self.assertEqual(twitter_client._oauth2_refresh_token, 'new-refresh')

if __name__ == '__main__':
    unittest.main()
