import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from scanner import ArbitrageScanner
from config import AppConfig
from analysis.models import ArbitrageOpportunity

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
        telegram_enabled=True,
        twitter_enabled=False,
        alert_cooldown=0, # Disable cooldown for testing
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
    )

@pytest.fixture
def mock_application():
    app = MagicMock()
    app.bot = AsyncMock()
    app.bot_data = {}
    return app

@pytest.fixture
def mock_clients():
    return (
        MagicMock(), # DexScreenerClient
        MagicMock(), # EtherscanClient
        MagicMock(), # CoinGeckoClient
        MagicMock(), # BlockscoutClient
        MagicMock(), # GeminiClient
        MagicMock(), # TwitterClient
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
        twitter_client
    )

@pytest.mark.asyncio
@patch('scanner.calculate_momentum_score')
async def test_telegram_notification_bullish_low_momentum_skipped(
    mock_calculate_momentum_score, scanner, mock_application
):
    # Set momentum score to be lower than the threshold
    mock_calculate_momentum_score.return_value = (4.0, {})

    opp = ArbitrageOpportunity(
        pair_name='WETH/USDC',
        chain_name='ethereum',
        buy_dex='Uniswap',
        sell_dex='Sushiswap',
        buy_price=1000,
        sell_price=1010,
        gross_profit_usd=10,
        net_profit_usd=5,
        gross_diff_pct=1.0,
        effective_volume=100.0,
        gas_cost_usd=0.0,
        dex_fee_cost=0.0,
        slippage_cost=0.0,
        gas_price_gwei=0.0,
        base_token_address='0xmockaddress',
        direction='BULLISH',
        buy_dex_volume_usd=10000,
        sell_dex_volume_usd=10000,
        dominant_is_buy_side=True,
    )

    await scanner._send_telegram_notification(opp)

    # Assert that send_message was NOT called
    mock_application.bot.send_message.assert_not_called()

@pytest.mark.asyncio
@patch('scanner.calculate_momentum_score')
async def test_telegram_notification_bearish_low_momentum_skipped(
    mock_calculate_momentum_score, scanner, mock_application
):
    # Set momentum score to be lower than the threshold
    mock_calculate_momentum_score.return_value = (4.0, {})

    opp = ArbitrageOpportunity(
        pair_name='WETH/USDC',
        chain_name='ethereum',
        buy_dex='Uniswap',
        sell_dex='Sushiswap',
        buy_price=1010,
        sell_price=1000,
        gross_profit_usd=10,
        net_profit_usd=5,
        gross_diff_pct=1.0,
        effective_volume=100.0,
        gas_cost_usd=0.0,
        dex_fee_cost=0.0,
        slippage_cost=0.0,
        gas_price_gwei=0.0,
        base_token_address='0xmockaddress',
        direction='BEARISH',
        buy_dex_volume_usd=10000,
        sell_dex_volume_usd=10000,
        dominant_is_buy_side=False,
    )

    await scanner._send_telegram_notification(opp)

    # Assert that send_message was NOT called
    mock_application.bot.send_message.assert_not_called()

@pytest.mark.asyncio
@patch('scanner.calculate_momentum_score')
async def test_telegram_notification_bullish_sufficient_momentum_sent(
    mock_calculate_momentum_score, scanner, mock_application
):
    # Set momentum score to be higher than or equal to the threshold
    mock_calculate_momentum_score.return_value = (5.0, {})

    opp = ArbitrageOpportunity(
        pair_name='WETH/USDC',
        chain_name='ethereum',
        buy_dex='Uniswap',
        sell_dex='Sushiswap',
        buy_price=1000,
        sell_price=1010,
        gross_profit_usd=10,
        net_profit_usd=5,
        gross_diff_pct=1.0,
        effective_volume=100.0,
        gas_cost_usd=0.0,
        dex_fee_cost=0.0,
        slippage_cost=0.0,
        gas_price_gwei=0.0,
        base_token_address='0xmockaddress',
        direction='BULLISH',
        buy_dex_volume_usd=10000,
        sell_dex_volume_usd=10000,
        dominant_is_buy_side=True,
    )

    # Mock resolve_dex_name and generate_token_analysis to prevent errors
    with patch.object(scanner, '_resolve_dex_name', new_callable=AsyncMock) as mock_resolve_dex_name, patch.object(scanner.gemini_client, 'generate_token_analysis', new_callable=AsyncMock) as mock_generate_token_analysis:
        mock_resolve_dex_name.return_value = 'MockDex'
        mock_generate_token_analysis.return_value = 'Mock AI Analysis'
        await scanner._send_telegram_notification(opp)

    # Assert that send_message was called
    mock_application.bot.send_message.assert_called_once()

@pytest.mark.asyncio
@patch('scanner.calculate_momentum_score')
async def test_telegram_notification_bearish_sufficient_momentum_sent(
    mock_calculate_momentum_score, scanner, mock_application
):
    # Set momentum score to be higher than or equal to the threshold
    mock_calculate_momentum_score.return_value = (5.0, {})

    opp = ArbitrageOpportunity(
        pair_name='WETH/USDC',
        chain_name='ethereum',
        buy_dex='Uniswap',
        sell_dex='Sushiswap',
        buy_price=1010,
        sell_price=1000,
        gross_profit_usd=10,
        net_profit_usd=5,
        gross_diff_pct=1.0,
        effective_volume=100.0,
        gas_cost_usd=0.0,
        dex_fee_cost=0.0,
        slippage_cost=0.0,
        gas_price_gwei=0.0,
        base_token_address='0xmockaddress',
        direction='BEARISH',
        buy_dex_volume_usd=10000,
        sell_dex_volume_usd=10000,
        dominant_is_buy_side=False,
    )

    # Mock resolve_dex_name and generate_token_analysis to prevent errors
    with patch.object(scanner, '_resolve_dex_name', new_callable=AsyncMock) as mock_resolve_dex_name, patch.object(scanner.gemini_client, 'generate_token_analysis', new_callable=AsyncMock) as mock_generate_token_analysis:
        mock_resolve_dex_name.return_value = 'MockDex'
        mock_generate_token_analysis.return_value = 'Mock AI Analysis'
        await scanner._send_telegram_notification(opp)

    # Assert that send_message was called
    mock_application.bot.send_message.assert_called_once()

@pytest.mark.asyncio
@patch('scanner.calculate_momentum_score')
async def test_ai_analysis_disabled_skips_generation(
    mock_calculate_momentum_score, scanner, mock_application
):
    mock_calculate_momentum_score.return_value = (5.0, {})

    scanner.config = scanner.config._replace(ai_analysis_enabled=False)
    scanner.gemini_client.generate_token_analysis = AsyncMock()

    opp = ArbitrageOpportunity(
        pair_name='WETH/USDC',
        chain_name='ethereum',
        buy_dex='Uniswap',
        sell_dex='Sushiswap',
        buy_price=1000,
        sell_price=1010,
        gross_profit_usd=10,
        net_profit_usd=5,
        gross_diff_pct=1.0,
        effective_volume=100.0,
        gas_cost_usd=0.0,
        dex_fee_cost=0.0,
        slippage_cost=0.0,
        gas_price_gwei=0.0,
        base_token_address='0xmockaddress',
        direction='BULLISH',
        buy_dex_volume_usd=10000,
        sell_dex_volume_usd=10000,
        dominant_is_buy_side=True,
    )

    with patch.object(scanner, '_resolve_dex_name', new_callable=AsyncMock) as mock_resolve_dex_name:
        mock_resolve_dex_name.return_value = 'MockDex'
        await scanner._send_telegram_notification(opp)

    scanner.gemini_client.generate_token_analysis.assert_not_awaited()
    mock_application.bot.send_message.assert_called_once()
    message_text = mock_application.bot.send_message.call_args.kwargs['text']
    assert 'AI analysis disabled by configuration.' in message_text
    assert 'AI-Generated Analysis' not in message_text
    assert 'AI-generated' not in message_text

