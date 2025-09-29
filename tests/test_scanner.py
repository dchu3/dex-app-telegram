import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from analysis.models import ArbitrageOpportunity
from config import AppConfig
from scanner import ArbitrageScanner
from services.gemini_client import GeminiAnalysis


@pytest.fixture
def mock_config():
    return AppConfig(
        chains=['ethereum'],
        tokens=['WETH'],
        dex_fee=0.3,
        slippage=0.5,
        min_bullish_profit=0.0,
        min_bearish_discrepancy=1.0,
        min_momentum_score_bullish=5.0,
        min_momentum_score_bearish=5.0,
        trade_volume=500.0,
        min_liquidity=1000.0,
        min_volume=1000.0,
        min_txns_h1=1,
        interval=60,
        min_profit=0.0,
        telegram_enabled=True,
        twitter_enabled=False,
        min_tweet_momentum_score=6.0,
        alert_cooldown=0,
        etherscan_api_key='mock_key',
        telegram_bot_token='mock_token',
        telegram_chat_id='mock_chat_id',
        coingecko_api_key=None,
        gemini_api_key=None,
        ai_analysis_enabled=True,
        twitter_api_key=None,
        twitter_api_secret=None,
        twitter_access_token=None,
        twitter_access_token_secret=None,
        multi_leg=False,
        max_cycle_length=3,
        max_depth=2,
        scanner_enabled=True,
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


@pytest.fixture
def mock_application():
    app = MagicMock()
    app.bot = AsyncMock()
    app.bot_data = {}
    return app


@pytest.fixture
def mock_clients():
    dexscreener_client = MagicMock()
    etherscan_client = MagicMock()
    coingecko_client = MagicMock()
    coingecko_client.search_coin = AsyncMock(return_value={'id': 'weth'})
    coingecko_client.get_rsi = AsyncMock(return_value=70.0)
    blockscout_client = MagicMock()
    gemini_client = MagicMock()
    gemini_client.generate_token_analysis = AsyncMock(
        return_value=GeminiAnalysis(
            telegram_detail='Mock AI Analysis',
            twitter_summary='Mock tweet summary'
        )
    )
    twitter_client = MagicMock()
    return (
        dexscreener_client,
        etherscan_client,
        coingecko_client,
        blockscout_client,
        gemini_client,
        twitter_client,
    )


@pytest.fixture
def scanner(mock_config, mock_application, mock_clients):
    dex_client, etherscan_client, coingecko_client, blockscout_client, gemini_client, twitter_client = mock_clients
    return ArbitrageScanner(
        mock_config,
        mock_application,
        dex_client,
        etherscan_client,
        coingecko_client,
        blockscout_client,
        gemini_client,
        twitter_client,
    )


def _base_opportunity(**overrides):
    payload = dict(
        pair_name='WETH/USDC',
        chain_name='ethereum',
        buy_dex='Uniswap',
        sell_dex='Sushiswap',
        buy_price=1000.0,
        sell_price=1010.0,
        gross_diff_pct=1.0,
        effective_volume=100.0,
        gross_profit_usd=10.0,
        gas_cost_usd=0.0,
        dex_fee_cost=0.0,
        slippage_cost=0.0,
        net_profit_usd=5.0,
        gas_price_gwei=0.0,
        base_token_address='0xmock',
        buy_dex_volume_usd=10000.0,
        sell_dex_volume_usd=10000.0,
        dominant_is_buy_side=True,
        dominant_volume_ratio=2.0,
        price_impact_pct=0.5,
        buy_price_change_h1=0.0,
        sell_price_change_h1=0.0,
        short_term_volume_ratio=0.0,
        short_term_txns_total=0,
        is_early_momentum=False,
    )
    payload.update(overrides)
    return ArbitrageOpportunity(**payload)


@pytest.mark.asyncio
@patch('scanner.calculate_momentum_score')
async def test_telegram_notification_bullish_low_momentum_skipped(mock_calculate_momentum_score, scanner, mock_application):
    mock_calculate_momentum_score.return_value = (4.0, "Too weak")
    opp = _base_opportunity(direction='BULLISH')

    await scanner._send_telegram_notification(opp)

    mock_application.bot.send_message.assert_not_called()


@pytest.mark.asyncio
@patch('scanner.calculate_momentum_score')
async def test_telegram_notification_bearish_low_momentum_skipped(mock_calculate_momentum_score, scanner, mock_application):
    mock_calculate_momentum_score.return_value = (4.0, "Too weak")
    opp = _base_opportunity(
        direction='BEARISH',
        buy_price=1010.0,
        sell_price=1000.0,
        dominant_is_buy_side=False,
    )

    await scanner._send_telegram_notification(opp)

    mock_application.bot.send_message.assert_not_called()


@pytest.mark.asyncio
@patch('scanner.calculate_momentum_score')
async def test_telegram_notification_bullish_sufficient_momentum_sent(mock_calculate_momentum_score, scanner, mock_application):
    mock_calculate_momentum_score.return_value = (5.0, "Momentum OK")
    opp = _base_opportunity(direction='BULLISH')

    with patch.object(scanner, '_resolve_dex_name', new_callable=AsyncMock) as mock_resolve:
        mock_resolve.return_value = 'MockDex'
        await scanner._send_telegram_notification(opp)

    mock_application.bot.send_message.assert_called_once()


@pytest.mark.asyncio
@patch('scanner.calculate_momentum_score')
async def test_telegram_notification_bearish_sufficient_momentum_sent(mock_calculate_momentum_score, scanner, mock_application):
    mock_calculate_momentum_score.return_value = (5.0, "Momentum OK")
    opp = _base_opportunity(
        direction='BEARISH',
        buy_price=1010.0,
        sell_price=1000.0,
        dominant_is_buy_side=False,
        dominant_volume_ratio=3.0,
        buy_price_change_h1=-1.0,
        sell_price_change_h1=-1.5,
        short_term_volume_ratio=0.2,
        short_term_txns_total=5,
        is_early_momentum=True,
    )

    with patch.object(scanner, '_resolve_dex_name', new_callable=AsyncMock) as mock_resolve:
        mock_resolve.return_value = 'MockDex'
        await scanner._send_telegram_notification(opp)

    mock_application.bot.send_message.assert_called_once()


@pytest.mark.asyncio
@patch('scanner.calculate_momentum_score')
async def test_ai_analysis_disabled_skips_generation(mock_calculate_momentum_score, scanner, mock_application):
    mock_calculate_momentum_score.return_value = (5.0, "Momentum OK")
    scanner.config = scanner.config._replace(ai_analysis_enabled=False)
    scanner.gemini_client.generate_token_analysis = AsyncMock()

    opp = _base_opportunity(direction='BULLISH')

    with patch.object(scanner, '_resolve_dex_name', new_callable=AsyncMock) as mock_resolve:
        mock_resolve.return_value = 'MockDex'
        await scanner._send_telegram_notification(opp)

    scanner.gemini_client.generate_token_analysis.assert_not_awaited()
    mock_application.bot.send_message.assert_called_once()
    message_text = mock_application.bot.send_message.call_args.kwargs['text']
    assert 'AI analysis disabled.' in message_text


@pytest.mark.asyncio
@patch('scanner.calculate_momentum_score')
async def test_rsi_falls_back_to_history(mock_calculate_momentum_score, scanner, mock_application):
    mock_calculate_momentum_score.return_value = (5.0, "Momentum OK")
    scanner.coingecko_client.get_rsi = AsyncMock(return_value=None)

    recent_history = [
        {
            "timestamp_utc": "2024-01-01 12:00:00",
            "momentum_score": 6.0,
            "spread_pct": 1.2,
            "net_profit_usd": 2.5,
            "clip_usd": 500,
            "rsi_value": 62.0,
        }
    ]

    with patch.object(scanner, '_load_recent_momentum_history', AsyncMock(return_value=recent_history)), \
         patch.object(scanner, '_resolve_dex_name', AsyncMock(return_value='MockDex')):
        opp = _base_opportunity(direction='BULLISH')
        await scanner._send_telegram_notification(opp)

    # Ensure we sent a notification and RSI fallback kept processing
    mock_application.bot.send_message.assert_called_once()
    args, kwargs = mock_calculate_momentum_score.call_args
    assert kwargs['rsi_value'] == pytest.approx(59.0, rel=0.05)


@pytest.mark.asyncio
@patch('scanner.calculate_momentum_score')
async def test_tweet_skipped_when_below_threshold(mock_calculate_momentum_score, scanner, mock_application):
    mock_calculate_momentum_score.return_value = (5.5, "Solid momentum")
    scanner.config = scanner.config._replace(
        twitter_enabled=True,
        gemini_api_key='mock_key',
        min_tweet_momentum_score=6.0,
        signal_tweets_enabled=True,
    )

    with patch.object(scanner, '_load_recent_momentum_history', AsyncMock(return_value=[])), \
         patch.object(scanner, '_resolve_dex_name', AsyncMock(return_value='MockDex')):
        opp = _base_opportunity(direction='BULLISH')
        await scanner._send_telegram_notification(opp)

    scanner.twitter_client.post_tweet.assert_not_called()
    mock_application.bot.send_message.assert_called_once()


@pytest.mark.asyncio
@patch('scanner.calculate_momentum_score')
async def test_tweet_sent_when_above_threshold(mock_calculate_momentum_score, scanner, mock_application):
    mock_calculate_momentum_score.return_value = (6.5, "High momentum")
    scanner.config = scanner.config._replace(
        twitter_enabled=True,
        gemini_api_key='mock_key',
        min_tweet_momentum_score=6.0,
        signal_tweets_enabled=True,
    )

    with patch.object(scanner, '_load_recent_momentum_history', AsyncMock(return_value=[])), \
         patch.object(scanner, '_resolve_dex_name', AsyncMock(return_value='MockDex')):
        opp = _base_opportunity(direction='BULLISH')
        await scanner._send_telegram_notification(opp)

    scanner.twitter_client.post_tweet.assert_called_once()
    mock_application.bot.send_message.assert_called_once()
