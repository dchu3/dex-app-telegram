#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from services.gemini_client import GeminiClient

class TestGeminiClient(unittest.TestCase):
    """Unit tests for the GeminiClient."""

    def setUp(self):
        """Set up a mock session and client for testing."""
        self.mock_session = MagicMock()
        self.api_key = "test_gemini_api_key"
        self.gemini_client = GeminiClient(self.mock_session, self.api_key)

    @patch('services.gemini_client.api_post', new_callable=AsyncMock)
    def test_generate_tweet_from_analysis(self, mock_api_post):
        """Test that a tweet is correctly generated from a mock API response."""
        # Arrange
        full_analysis = "This is a detailed analysis of a crypto signal."
        token = "AERO"
        chain = "Base"
        momentum_score = 85.25
        expected_tweet = "$AERO on Base shows a momentum score of 85.25. 📈"

        mock_api_response = {
            'candidates': [
                {
                    'content': {
                        'parts': [{'text': expected_tweet}]
                    }
                }
            ]
        }
        mock_api_post.return_value = mock_api_response

        # Act
        result = asyncio.run(self.gemini_client.generate_tweet_from_analysis(
            full_analysis, token, chain, momentum_score
        ))

        # Assert
        self.assertEqual(result, expected_tweet)
        # Verify the prompt structure as well if possible
        call_args = mock_api_post.call_args
        request_body = call_args[1]['json_data']
        prompt_text = request_body['contents'][0]['parts'][0]['text']
        
        self.assertIn(f"summarizing the provided analysis for {token} on {chain}", prompt_text)
        self.assertIn(full_analysis, prompt_text)
        self.assertIn(f"the token name (${token})", prompt_text)
        self.assertIn(f"the momentum score ({momentum_score:.2f})", prompt_text)
        self.assertIn("Do not use any hashtags", prompt_text)
        self.assertIn("Do not include any disclaimers", prompt_text)

if __name__ == '__main__':
    unittest.main()
