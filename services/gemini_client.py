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
            fallback_parts = [
                "Momentum snapshot: {symbol} on {chain}".format(
                    symbol=(opportunity_data.get('symbol') or '').upper() or 'TOKEN',
                    chain=opportunity_data.get('chain') or 'Base'
                ),
                "spread {profit_pct:.2f}%".format(profit_pct=opportunity_data.get('profit_percentage') or 0.0),
                "score {score:.1f}/10".format(score=opportunity_data.get('momentum_score') or 0.0),
                "{buy} -> {sell}".format(
                    buy=opportunity_data.get('buy_dex') or 'buy venue',
                    sell=opportunity_data.get('sell_dex') or 'sell venue'
                ),
            ]

            net_profit = opportunity_data.get('net_profit_usd')
            eff_volume = opportunity_data.get('effective_volume')
            if net_profit is not None and eff_volume is not None:
                fallback_parts.append(
                    "est net ${net:.2f} on ${vol:,.0f}".format(net=net_profit, vol=eff_volume)
                )

            flow_ratio = opportunity_data.get('dominant_volume_ratio')
            flow_side = opportunity_data.get('dominant_flow_side')
            if flow_ratio and flow_ratio > 0 and flow_side in {"buy", "sell"}:
                fallback_parts.append(
                    "{side}-side flow {ratio:.2f}x".format(side=flow_side, ratio=flow_ratio)
                )

            if opportunity_data.get('is_early_momentum'):
                fallback_parts.append("early momentum cue")

            fallback_text = " | ".join(fallback_parts)
            sanitized_fallback = self._sanitize_tweet(fallback_text)
            return sanitized_fallback or fallback_text[:280]
        return validated

    def _build_prompt(self, data: Dict) -> str:
        """Constructs a direction-neutral prompt for Gemini outputs."""

        symbol = (data.get('symbol') or '').upper() or 'TOKEN'
        chain = data.get('chain') or 'Base'
        spread = data.get('profit_percentage') or 0.0
        score = data.get('momentum_score') or 0.0
        buy_exchange = data.get('buy_dex') or 'buy venue'
        sell_exchange = data.get('sell_dex') or 'sell venue'
        net_profit = data.get('net_profit_usd')
        effective_volume = data.get('effective_volume')
        flow_ratio = data.get('dominant_volume_ratio')
        flow_side = data.get('dominant_flow_side')
        is_early = bool(data.get('is_early_momentum'))

        data_points = [
            f"token {symbol}",
            f"chain {chain}",
            f"spread {spread:.2f}%",
            f"score {score:.1f}/10",
            f"route {buy_exchange} -> {sell_exchange}",
        ]

        if net_profit is not None and effective_volume is not None:
            data_points.append(f"est net ${net_profit:.2f} on ${effective_volume:,.0f}")
        if flow_ratio and flow_ratio > 0 and flow_side in {"buy", "sell"}:
            data_points.append(f"flow leans {flow_side}-side {flow_ratio:.2f}x")
        if is_early:
            data_points.append("early momentum cue")

        prompt = """You are a DeFi analyst drafting concise, direction-neutral social updates. Compose a single alert that fits in 280 characters, plain text, no links, no hashtags, suitable for Twitter and Telegram.

Summary must weave in these data points: {data_points}. Do not label the setup bullish or bearish and avoid telling readers to trade. Keep the tone factual with at most two emojis. Return one sentence or two short clauses separated by a period.""".format(
            data_points=", ".join(data_points)
        )
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
