#!/usr/bin/env python3
from typing import Optional

import tweepy

from config import AppConfig


class TwitterClient:
    """Client for interacting with the Twitter API using Tweepy."""

    _TOKEN_URL = "https://api.twitter.com/2/oauth2/token"

    def __init__(self, config: AppConfig):
        """Initializes the Tweepy client with credentials from the application config."""
        self._config = config
        self._mode: Optional[str] = None
        self._oauth2_access_token: Optional[str] = config.twitter_oauth2_access_token
        self._oauth2_refresh_token: Optional[str] = config.twitter_oauth2_refresh_token

        oauth1_ready = all([
            config.twitter_api_key,
            config.twitter_api_secret,
            config.twitter_access_token,
            config.twitter_access_token_secret,
        ])
        oauth2_ready = all([
            config.twitter_client_id,
            config.twitter_client_secret,
            config.twitter_oauth2_access_token,
        ])

        if oauth1_ready:
            self._mode = "oauth1"
            self.client = tweepy.Client(
                consumer_key=config.twitter_api_key,
                consumer_secret=config.twitter_api_secret,
                access_token=config.twitter_access_token,
                access_token_secret=config.twitter_access_token_secret,
            )
        elif oauth2_ready:
            self._mode = "oauth2"
            self.client = self._build_oauth2_client()
        else:
            raise ValueError(
                "Twitter API credentials are not fully configured. Provide either the OAuth1 keys "
                "(API key/secret + access token/secret) or the OAuth2 set (client ID/secret + user token)."
            )

    def post_tweet(self, text: str):
        """
        Posts a tweet to the configured Twitter account.

        Args:
            text: The content of the tweet to be posted.

        Raises:
            tweepy.errors.TweepyException: If the API call fails.
        """
        try:
            self.client.create_tweet(text=text)
        except tweepy.errors.Unauthorized:
            if self._mode == "oauth2" and self._oauth2_refresh_token:
                self._refresh_oauth2_tokens()
                self.client.create_tweet(text=text)
            else:
                raise

    def _build_oauth2_client(self) -> tweepy.Client:
        return tweepy.Client(
            client_id=self._config.twitter_client_id,
            client_secret=self._config.twitter_client_secret,
            access_token=self._oauth2_access_token,
            refresh_token=self._oauth2_refresh_token,
        )

    def _refresh_oauth2_tokens(self) -> None:
        if not self._oauth2_refresh_token:
            raise tweepy.errors.Unauthorized("OAuth2 refresh token not available for Twitter client")

        response = self.client.refresh_token(
            self._TOKEN_URL,
            refresh_token=self._oauth2_refresh_token,
        )

        new_access = response.get("access_token")
        new_refresh = response.get("refresh_token", self._oauth2_refresh_token)

        if new_access:
            self._oauth2_access_token = new_access
        self._oauth2_refresh_token = new_refresh

        # Rebuild the client with the new tokens.
        self.client = self._build_oauth2_client()

        # Surface updated tokens to the operator so they can persist them.
        print("Twitter OAuth2 tokens refreshed. Update TWITTER_OAUTH2_ACCESS_TOKEN / TWITTER_OAUTH2_REFRESH_TOKEN with the new values.")
