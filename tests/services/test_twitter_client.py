#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import unittest
from unittest.mock import MagicMock, patch

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
            trading_private_key=None
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

if __name__ == '__main__':
    unittest.main()
