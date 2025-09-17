# services/gemini_client.py
import aiohttp
import time
import asyncio
from typing import Optional, Dict

async def api_post(url: str, session: aiohttp.ClientSession, json_data: Dict, headers: Optional[Dict] = None) -> Optional[Dict]:
    """Makes a generic async POST request."""
    try:
        async with session.post(url, json=json_data, headers=headers) as response:
            response.raise_for_status()
            return await response.json()
    except aiohttp.ClientError as e:
        print(f"API POST request failed: {e}")
        return None

class GeminiClient:
    def __init__(self, session: aiohttp.ClientSession, api_key: str):
        self.session = session
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        self.headers = {'Content-Type': 'application/json', 'x-goog-api-key': self.api_key}
        self._last_request_time = 0.0
        self._rate_limit_delay = 10  # 10 seconds delay between requests to avoid 429 errors

    async def _wait_for_rate_limit(self):
        """Ensures requests respect the rate limit by pausing if necessary."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    async def generate_token_analysis(self, opportunity_data: Dict) -> str:
        """
        Generates a brief AI-driven analysis of a token opportunity via HTTP.
        """
        if not self.api_key:
            return "Gemini API key not configured."

        await self._wait_for_rate_limit() # Wait before making the request

        prompt = self._build_prompt(opportunity_data)
        
        request_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        }
        
        response_json = await api_post(self.base_url, self.session, json_data=request_body, headers=self.headers)
        
        if response_json is None: # Handle cases where api_post returned None due to error
            return "AI analysis could not be generated (API error)."

        try:
            return response_json['candidates'][0]['content']['parts'][0]['text'].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as e:
            print(f"Error parsing Gemini response: {e}")
            return "AI analysis could not be generated (parsing error)."

    def _build_prompt(self, data: Dict) -> str:
        """Constructs the prompt for the Gemini API based on signal direction."""
        
        direction_text = "bullish" if data['direction'] == 'BULLISH' else "bearish"
        buy_exchange = data['buy_dex']
        sell_exchange = data['sell_dex']
        
        prompt = f"""
        As a DeFi market analyst AI, analyze this {direction_text} momentum signal for {data['symbol']}.

        **Signal Data:**
        - **Direction:** {data['direction']}
        - **Price Discrepancy:** {data['profit_percentage']:.2f}%
        - **Momentum Score:** {data['momentum_score']:.1f}/10
        - **Price (Buy Exchange: {buy_exchange}):** ${data['buy_price']:.6f}
        - **Price (Sell Exchange: {sell_exchange}):** ${data['sell_price']:.6f}
        - **Current Market Price:** ${data['current_price']:.6f}

        **Task:**
        Provide a structured, professional, and concise analysis of this signal. **Do not give trading advice, financial advice, or a hypothetical trading plan.** Your analysis must be objective and data-driven, formatted exactly as follows:

        **AI Thesis:**
        **Market Sentiment:** (Your analysis of the current market sentiment for this token)
        **Key Drivers:** (Your analysis of the factors driving this price discrepancy and momentum)
        **Potential Risks:** (Your analysis of the potential risks associated with this signal)
        """
        return prompt

    async def generate_tweet_from_analysis(self, full_analysis: str, token: str, chain: str, momentum_score: float) -> str:
        """Generates a 280-character tweet from the full analysis."""
        if not self.api_key:
            return "Gemini API key not configured."

        await self._wait_for_rate_limit()

        prompt = self._build_tweet_prompt(full_analysis, token, chain, momentum_score)

        request_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        }

        response_json = await api_post(self.base_url, self.session, json_data=request_body, headers=self.headers)

        if response_json is None:
            return "Tweet could not be generated (API error)."

        try:
            return response_json['candidates'][0]['content']['parts'][0]['text'].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as e:
            print(f"Error parsing Gemini response for tweet: {e}")
            return "Tweet could not be generated (parsing error)."

    def _build_tweet_prompt(self, full_analysis: str, token: str, chain: str, momentum_score: float) -> str:
        """
        Constructs the prompt for generating a tweet.
        """
        return f"""
        You are a financial markets analyst who specializes in crafting concise, engaging social media updates about cryptocurrency momentum.

        Generate a tweet (max 280 characters) summarizing the provided analysis for {token} on {chain}.

        **Full Analysis:**
        ---
        {full_analysis}
        ---

        **Instructions for the tweet:**
        - Must be 280 characters or less.
        - Must state the token name (${token}), the blockchain ({chain}), and the momentum score ({momentum_score:.2f}).
        - Include one or two relevant emojis (e.g., 📈, 🚀, 💰).
        - Do not use any hashtags.
        - Do not include any disclaimers, "not financial advice" statements, or similar warnings.
        - Focus on the opportunity or key finding.

        **Example Format:**
        $AERO on Base shows a momentum score of 85.25. A significant price discrepancy between two major DEXs suggests a potential short-term arbitrage opportunity. 📈
        """
