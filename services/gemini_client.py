# services/gemini_client.py
import aiohttp
import time
import asyncio
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class GeminiAnalysis:
    telegram_detail: str
    twitter_summary: str

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

    async def generate_token_analysis(self, opportunity_data: Dict) -> GeminiAnalysis:
        """Generates detailed AI analysis for Telegram and a compact Twitter summary."""
        if not self.api_key:
            return self._generate_fallback_analysis(opportunity_data, reason="Gemini API key not configured.")

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
        
        if response_json is None:  # Handle cases where api_post returned None due to error
            return self._generate_fallback_analysis(opportunity_data, reason="API response was empty")

        try:
            candidate = response_json['candidates'][0]['content']['parts'][0]['text'].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as e:
            print(f"Error parsing Gemini response: {e}")
            return self._generate_fallback_analysis(opportunity_data, reason="parsing error")

        parsed = self._parse_candidate(candidate, opportunity_data)
        if parsed:
            return parsed

        return self._generate_fallback_analysis(opportunity_data, reason="invalid model output")

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
        breakdown = data.get('momentum_breakdown') or {}
        history: List[Dict[str, Any]] = data.get('momentum_history') or []
        explanation_hint = data.get('momentum_explanation') or ""

        def _fmt(value: Optional[float], suffix: str = "") -> str:
            if value is None:
                return "n/a"
            return f"{value:.2f}{suffix}"

        flow_side = breakdown.get('dominant_flow_side')
        flow_ratio = breakdown.get('dominant_volume_ratio')
        flow_summary = "n/a"
        if flow_side and flow_ratio:
            flow_summary = f"{flow_side}-side {flow_ratio:.2f}x"

        history_lines = []
        for item in history[:3]:
            history_lines.append(
                f"- {item.get('timestamp_utc', 'n/a')}: score {item.get('momentum_score', 'n/a')} | spread {item.get('spread_pct', 'n/a')}% | net ${item.get('net_profit_usd', 'n/a')}"
            )
        if not history_lines:
            history_lines.append("- no prior records in window")

        prompt = f"""
You are a DeFi analyst creating concise, direction-neutral insights. Explain why the momentum score sits where it does, referencing the score inputs and recent history.

Context:
- token: {symbol} on {chain}
- spread: {spread:.2f}%
- momentum_score: {score:.1f}/10
- hint_from_model: {explanation_hint or 'n/a'}
- route: {buy_exchange} -> {sell_exchange}
- est_net: {('%.2f' % net_profit) if net_profit is not None else 'n/a'} on clip {('%.0f' % effective_volume) if effective_volume is not None else 'n/a'}
- volume_divergence: {_fmt(breakdown.get('volume_divergence'))}
- persistence_count: {breakdown.get('persistence_count', 'n/a')}
- rsi_value: {breakdown.get('rsi_value', 'n/a')}
- flow_bias: {flow_summary}
- short_term_volume_ratio: {_fmt(breakdown.get('short_term_volume_ratio'), 'x')}
- short_term_txns_total: {breakdown.get('short_term_txns_total', 'n/a')}
- is_early_momentum: {breakdown.get('is_early_momentum', False)}
- recent history:\n{chr(10).join(history_lines)}

Requirements:
1. Return ONLY strict JSON (no markdown) with keys "telegram_detail" and "twitter_summary".
2. "telegram_detail": 2-3 sentences (<=600 chars) explaining the score drivers and momentum trend; neutral tone, no financial advice, no hashtags, no links.
3. "twitter_summary": <=280 chars, plain text, neutral; highlight score drivers, spread, and flow bias; no hashtags, no links, no markdown.
4. Do not label the setup bullish/bearish; focus on measurable factors.
"""
        return prompt

    def _parse_candidate(self, raw_text: str, opportunity_data: Dict) -> Optional[GeminiAnalysis]:
        text = raw_text.strip()
        text = self._strip_code_fences(text)

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return None

        telegram_detail = payload.get('telegram_detail')
        twitter_summary = payload.get('twitter_summary')
        if not isinstance(telegram_detail, str) or not isinstance(twitter_summary, str):
            return None

        telegram_detail = telegram_detail.strip()
        twitter_sanitized = self._sanitize_tweet(twitter_summary)
        if twitter_sanitized is None:
            twitter_sanitized = self._sanitize_tweet(self._build_twitter_summary_from_data(opportunity_data))
        if telegram_detail == "":
            telegram_detail = self._build_telegram_detail_from_data(opportunity_data)
        return GeminiAnalysis(
            telegram_detail=telegram_detail,
            twitter_summary=twitter_sanitized or self._truncate_text(self._build_twitter_summary_from_data(opportunity_data), 280),
        )

    def _generate_fallback_analysis(self, data: Dict, reason: str | None = None) -> GeminiAnalysis:
        telegram_detail = self._build_telegram_detail_from_data(data)
        twitter_text = self._build_twitter_summary_from_data(data)
        sanitized_twitter = self._sanitize_tweet(twitter_text)
        twitter_summary = sanitized_twitter or self._truncate_text(twitter_text, 280)
        if reason:
            print(f"Gemini fallback used: {reason}")
        return GeminiAnalysis(telegram_detail=telegram_detail, twitter_summary=twitter_summary)

    def _build_telegram_detail_from_data(self, data: Dict) -> str:
        score = data.get('momentum_score')
        score_text = self._format_optional(score, 1)
        symbol = (data.get('symbol') or '').upper() or 'TOKEN'
        chain = data.get('chain') or 'Base'
        breakdown = data.get('momentum_breakdown') or {}
        explanation = data.get('momentum_explanation')
        spread = data.get('profit_percentage')
        flow_side = breakdown.get('dominant_flow_side')
        flow_ratio = breakdown.get('dominant_volume_ratio')
        net_profit = data.get('net_profit_usd')
        effective_volume = data.get('effective_volume')
        history: List[Dict[str, Any]] = data.get('momentum_history') or []

        parts: List[str] = []
        if explanation:
            parts.append(explanation)
        else:
            persistence_text = breakdown.get('persistence_count', 'n/a')
            volume_text = self._format_optional(breakdown.get('volume_divergence'))
            rsi_text = breakdown.get('rsi_value', 'n/a')
            parts.append(
                f"Momentum score {score_text}/10 reflects {persistence_text} detections with volume divergence {volume_text}x and RSI {rsi_text}."
            )

        if flow_side and flow_ratio:
            spread_txt = self._format_optional(spread)
            parts.append(f"Flow is leaning {flow_side}-side at {self._format_optional(flow_ratio)}x while spread sits at {spread_txt}%.")
        elif spread is not None:
            buy_exchange = data.get('buy_dex', 'buy venue')
            sell_exchange = data.get('sell_dex', 'sell venue')
            parts.append(f"Spread currently measures {self._format_optional(spread)}% on {buy_exchange}->{sell_exchange}.")

        if net_profit is not None and effective_volume is not None:
            parts.append(f"Estimated clip ${effective_volume:,.0f} implies about ${net_profit:.2f} net once costs are considered.")

        if history:
            history_summaries = []
            for item in history[:3]:
                timestamp = item.get('timestamp_utc', 'n/a')
                hist_score = item.get('momentum_score', 'n/a')
                history_summaries.append(f"{hist_score} on {timestamp}")
            parts.append("Recent momentum prints: " + ", ".join(history_summaries) + ".")

        if not parts:
            parts.append(f"Momentum score for {symbol} on {chain} is {score_text}/10. Data unavailable for deeper explanation.")

        return " ".join(part.strip() for part in parts if part).strip()

    def _build_twitter_summary_from_data(self, data: Dict) -> str:
        symbol = (data.get('symbol') or '').upper() or 'TOKEN'
        chain = data.get('chain') or 'Base'
        score = data.get('momentum_score')
        score_text = self._format_optional(score, 1)
        spread = data.get('profit_percentage')
        breakdown = data.get('momentum_breakdown') or {}
        flow_side = breakdown.get('dominant_flow_side')
        flow_ratio = breakdown.get('dominant_volume_ratio')
        net_profit = data.get('net_profit_usd')
        effective_volume = data.get('effective_volume')

        pieces = [f"{symbol} {chain}: score {score_text}/10" if isinstance(score, (int, float)) else f"{symbol} {chain}: momentum update"]
        if spread is not None:
            pieces.append(f"spread {self._format_optional(spread)}%")
        if flow_side and flow_ratio:
            pieces.append(f"flow {flow_side} {self._format_optional(flow_ratio)}x")
        persistence = breakdown.get('persistence_count')
        if persistence is not None:
            pieces.append(f"detections {persistence}")
        if breakdown.get('rsi_value') is not None:
            pieces.append(f"RSI {breakdown['rsi_value']}")
        if net_profit is not None and effective_volume is not None:
            pieces.append(f"~${net_profit:.2f} on ${effective_volume:,.0f}")

        return "; ".join(pieces)

    @staticmethod
    def _truncate_text(text: str, limit: int) -> str:
        text = text.strip()
        return text if len(text) <= limit else text[:limit]

    @staticmethod
    def _format_optional(value: Optional[float], decimals: int = 2) -> str:
        if value is None:
            return "n/a"
        return f"{value:.{decimals}f}"

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
                inner = "\n".join(lines[1:-1]).strip()
                if inner.startswith("json"):
                    inner = inner[4:].strip()
                return inner
        return text

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
