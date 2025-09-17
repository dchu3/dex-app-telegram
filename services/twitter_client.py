#!/usr/bin/env python3
import tweepy
from config import AppConfig

class TwitterClient:
    """Client for interacting with the Twitter API using Tweepy."""

    def __init__(self, config: AppConfig):
        """Initializes the Tweepy client with credentials from the application config."""
        if not all([config.twitter_api_key, config.twitter_api_secret, config.twitter_access_token, config.twitter_access_token_secret]):
            raise ValueError("Twitter API credentials are not fully configured.")

        self.client = tweepy.Client(
            consumer_key=config.twitter_api_key,
            consumer_secret=config.twitter_api_secret,
            access_token=config.twitter_access_token,
            access_token_secret=config.twitter_access_token_secret
        )

    def post_tweet(self, text: str):
        """
        Posts a tweet to the configured Twitter account.

        Args:
            text: The content of the tweet to be posted.

        Raises:
            tweepy.errors.TweepyException: If the API call fails.
        """
        self.client.create_tweet(text=text)
