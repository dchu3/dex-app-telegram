#!/usr/bin/env python3
from typing import Dict, Union

# --- ANSI Color Codes ---
C_GREEN = '\033[92m'
C_RED = '\033[91m'
C_YELLOW = '\033[93m'
C_BLUE = '\033[94m'
C_RESET = '\033[0m'

# --- API Configuration ---
ETHERSCAN_API_BASE_URL = 'https://api.etherscan.io/v2/api'
TELEGRAM_API_BASE_URL = 'https://api.telegram.org/bot'
DEXSCREENER_API_BASE_URL = 'https://api.dexscreener.com/latest/dex'
COINGECKO_API_BASE_URL = 'https://api.coingecko.com/api/v3'

# --- Environment Variable Names ---
ETHERSCAN_API_KEY_ENV_VAR = 'ETHERSCAN_API_KEY'
TELEGRAM_BOT_TOKEN_ENV_VAR = 'TELEGRAM_BOT_TOKEN'
TELEGRAM_CHAT_ID_ENV_VAR = 'TELEGRAM_CHAT_ID'
COINGECKO_API_KEY_ENV_VAR = 'COINGECKO_API_KEY'
AI_ANALYSIS_ENABLED_ENV_VAR = 'AI_ANALYSIS_ENABLED'
ONCHAIN_VALIDATION_RPC_URL_ENV_VAR = 'ONCHAIN_VALIDATION_RPC_URL'

# --- Twitter API Environment Variable Names ---
TWITTER_API_KEY_ENV_VAR = 'TWITTER_API_KEY'
TWITTER_API_SECRET_ENV_VAR = 'TWITTER_API_SECRET'
TWITTER_ACCESS_TOKEN_ENV_VAR = 'TWITTER_ACCESS_TOKEN'
TWITTER_ACCESS_TOKEN_SECRET_ENV_VAR = 'TWITTER_ACCESS_TOKEN_SECRET'
TWITTER_CLIENT_ID_ENV_VAR = 'TWITTER_CLIENT_ID'
TWITTER_CLIENT_ID_SECRET_ENV_VAR = 'TWITTER_CLIENT_ID_SECRET'
TWITTER_OAUTH2_ACCESS_TOKEN_ENV_VAR = 'TWITTER_OAUTH2_ACCESS_TOKEN'
TWITTER_OAUTH2_REFRESH_TOKEN_ENV_VAR = 'TWITTER_OAUTH2_REFRESH_TOKEN'

# --- Chain Configuration ---
CHAIN_CONFIG: Dict[str, Dict[str, Union[str, int]]] = {
    'ethereum': {
        'chainId': 1,
        'dexscreenerName': 'ethereum',
        'nativeTokenPair': '0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640',  # WETH/USDC
        'nativeSymbol': 'ETH',
    },
    'polygon': {
        'chainId': 137,
        'dexscreenerName': 'polygon',
        'nativeTokenPair': '0x6e7a5fafcec6bb1e78bae2a1f0b612012bf14827',  # WMATIC/USDC
        'nativeSymbol': 'MATIC',
    },
    'base': {
        'chainId': 8453,
        'dexscreenerName': 'base',
        'nativeTokenPair': '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913', # WETH/USDC on Uniswap v3
        'nativeSymbol': 'ETH',
    },
    'bsc': {
        'chainId': 56,
        'dexscreenerName': 'bsc',
        'nativeTokenPair': '0x16b9a82891338f9ba80e2d6970fdda79d1eb0dae', # WBNB/USDC on PancakeSwap
        'nativeSymbol': 'BNB',
    },
}

# --- Gas Configuration ---
GAS_UNITS_PER_SWAP: Dict[str, int] = {
    'ethereum': 150000,
    'polygon': 100000,
    'base': 85000,
    'bsc': 120000,
}

# --- Common Token Addresses (Lowercase for case-insensitive matching) ---
COMMON_TOKEN_ADDRESSES: Dict[str, Dict[str, str]] = {
    'ethereum': {
        'wbtc': '0x2260fac5e5542a773aa44fbcfedf7c193bc2c599',
        'weth': '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2',
        'usdc': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
        'doge': '0x67ae46ef0942053b6ed083d932a65403e058ebed', # Wrapped DOGE on Ethereum
    },
    'polygon': {
        'wbtc': '0x1bfd67037b42cf73acf2047067bd4f2c47d9bfd6',
        'wmatic': '0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270',
        'usdc': '0x3c499c542cef5e3811e1192ce70d8cc03d5c3359',
        'doge': '0xbA2aE424d960c26247Dd6c32edC70B295c744C43', # PoS DOGE on Polygon
        'yfi': '0xda537104d6a5edd53c6fbba9a898708e465260b6', # YFI on Polygon
    },
    'bsc': {
        'wbtc': '0x7130d2a12b9bcbfae4f2634d864a1ee1ce3ead9c',
        'wbnb': '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c',
        'usdc': '0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d',
        'doge': '0xbA2aE424d960c26247Dd6c32edC70B295c744C43', # BEP20 DOGE on BSC
        'crv': '0xd533a949740bb3306d119cc777fa900ba034cd52', # CRV on BSC
    },
    'base': {
        'weth': '0x4200000000000000000000000000000000000006',
        'usdc': '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913',
    }
}

# --- Early Momentum Heuristics ---
EARLY_MOMENTUM_MIN_LIQUIDITY = 200000.0
EARLY_MOMENTUM_MIN_VOLUME = 300000.0
EARLY_MOMENTUM_MIN_VOLUME_M5 = 25000.0
EARLY_MOMENTUM_MIN_TXNS_M5 = 3
EARLY_MOMENTUM_VOLUME_RATIO_THRESHOLD = 0.035

# --- DEX Allowlist ---
BASE_ALLOWED_SINGLES = {'aerodrome', 'uniswap', 'uniswap-v3'}

# --- On-Chain Validation Defaults ---
ONCHAIN_VALIDATION_DEFAULT_MAX_DIFF_PCT = 5.0
ONCHAIN_VALIDATION_DEFAULT_TIMEOUT = 8.0
