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
            candidate = response_json['candidates'][0]['content']['parts'][0]['text'].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as e:
            print(f"Error parsing Gemini response: {e}")
            return "AI analysis could not be generated (parsing error)."

        validated = self._sanitize_tweet(candidate)
        if validated is None:
            return "Momentum snapshot: {direction} signal on {symbol} | Δ {profit_pct:.2f}% | Score {score:.1f}/10 | Buy {buy} @ ${buy_price:.4f} → Sell {sell} @ ${sell_price:.4f}".format(
                direction=opportunity_data['direction'].capitalize(),
                symbol=opportunity_data['symbol'].upper(),
                profit_pct=opportunity_data['profit_percentage'],
                score=opportunity_data['momentum_score'],
                buy=opportunity_data['buy_dex'],
                sell=opportunity_data['sell_dex'],
                buy_price=opportunity_data['buy_price'],
                sell_price=opportunity_data['sell_price'],
            )
        return validated

    def _build_prompt(self, data: Dict) -> str:
        """Constructs the prompt for the Gemini API based on signal direction."""
        
        direction_text = "bullish" if data['direction'] == 'BULLISH' else "bearish"
        buy_exchange = data['buy_dex']
        sell_exchange = data['sell_dex']
        
        prompt = f"""
You are a DeFi analyst who writes concise social updates. Craft a single-paragraph, tweet-ready alert (<=280 characters) with NO links or hashtags.

Mention token ({data['symbol']}), chain ({data.get('chain', 'Base')}), signal direction ({data['direction']}), price spread ({data['profit_percentage']:.2f}%), and momentum score ({data['momentum_score']:.1f}/10). Reference buy venue ({buy_exchange}) and sell venue ({sell_exchange}).

Rules: no financial advice, no calls to action like "buy/sell". Avoid tickers with $ prefix unless provided. Keep it upbeat but factual. Include at most two emojis. Output must be plain text, one sentence or two short clauses, no bullet points, no markdown.
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
        return f"Summarize this analysis in <=280 chars without links or hashtags, highlighting token {token}, chain {chain}, score {momentum_score:.1f}, and main takeaway: {full_analysis}"

    @staticmethod
    def _sanitize_tweet(content: str) -> Optional[str]:
        """Validate tweet constraints: <=280 chars, no URLs."""
        sanitized = " ".join(content.strip().split())
        if len(sanitized) > 280:
            return None
        lowered = sanitized.lower()
        if any(tag in lowered for tag in ("http://", "https://")):
            return None
        return sanitized
