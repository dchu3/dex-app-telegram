import pytest

from services.onchain_price_validator import OnChainPriceValidator


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        return None

    async def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)

    def post(self, url, json, timeout):
        if not self._responses:
            raise AssertionError("No more fake responses configured")
        return FakeResponse(self._responses.pop(0))


def _format_uint(value: int) -> str:
    return format(value, '064x')


def _make_reserve_payload(reserve0: int, reserve1: int, timestamp_last: int) -> str:
    return '0x' + _format_uint(reserve0) + _format_uint(reserve1) + _format_uint(timestamp_last)


@pytest.mark.asyncio
async def test_validate_pair_price_passes_within_tolerance():
    pair_address = '0xaaaa000000000000000000000000000000000001'
    target_token = '0xbbbb000000000000000000000000000000000002'
    counter_token = '0xcccc000000000000000000000000000000000003'

    reserve0 = 10 * 10 ** 18
    reserve1 = 15000 * 10 ** 6
    timestamp_last = 1_700_000_000

    responses = [
        {'jsonrpc': '2.0', 'id': 1, 'result': '0x10'},
        {'jsonrpc': '2.0', 'id': 2, 'result': '0x000000000000000000000000' + target_token[2:]},
        {'jsonrpc': '2.0', 'id': 3, 'result': '0x000000000000000000000000' + counter_token[2:]},
        {'jsonrpc': '2.0', 'id': 4, 'result': _make_reserve_payload(reserve0, reserve1, timestamp_last)},
        {'jsonrpc': '2.0', 'id': 5, 'result': '0x0000000000000000000000000000000000000000000000000000000000000012'},
        {'jsonrpc': '2.0', 'id': 6, 'result': '0x0000000000000000000000000000000000000000000000000000000000000006'},
    ]

    session = FakeSession(responses)
    validator = OnChainPriceValidator(
        session,
        rpc_url='http://mock-rpc',
        max_pct_diff=5.0,
        timeout=5.0,
        common_token_addresses={'base': {'usdc': counter_token}},
    )

    result = await validator.validate_pair_price(
        chain_name='base',
        pair_address=pair_address,
        target_token_address=target_token,
        counter_token_address=counter_token,
        dex_price_usd=1500.0,
        native_price_usd=2500.0,
    )

    assert result.validated is True
    assert result.passed is True
    assert result.price_usd == pytest.approx(1500.0, rel=1e-6)
    assert result.diff_pct == pytest.approx(0.0, abs=1e-6)
    assert result.block_number == 16


@pytest.mark.asyncio
async def test_validate_pair_price_fails_when_diff_exceeds_tolerance():
    pair_address = '0xaaaa000000000000000000000000000000000001'
    target_token = '0xbbbb000000000000000000000000000000000002'
    counter_token = '0xcccc000000000000000000000000000000000003'

    reserve0 = 10 * 10 ** 18
    reserve1 = 15000 * 10 ** 6
    timestamp_last = 1_700_000_000

    responses = [
        {'jsonrpc': '2.0', 'id': 1, 'result': '0x10'},
        {'jsonrpc': '2.0', 'id': 2, 'result': '0x000000000000000000000000' + target_token[2:]},
        {'jsonrpc': '2.0', 'id': 3, 'result': '0x000000000000000000000000' + counter_token[2:]},
        {'jsonrpc': '2.0', 'id': 4, 'result': _make_reserve_payload(reserve0, reserve1, timestamp_last)},
        {'jsonrpc': '2.0', 'id': 5, 'result': '0x0000000000000000000000000000000000000000000000000000000000000012'},
        {'jsonrpc': '2.0', 'id': 6, 'result': '0x0000000000000000000000000000000000000000000000000000000000000006'},
    ]

    session = FakeSession(responses)
    validator = OnChainPriceValidator(
        session,
        rpc_url='http://mock-rpc',
        max_pct_diff=1.0,
        timeout=5.0,
        common_token_addresses={'base': {'usdc': counter_token}},
    )

    result = await validator.validate_pair_price(
        chain_name='base',
        pair_address=pair_address,
        target_token_address=target_token,
        counter_token_address=counter_token,
        dex_price_usd=1000.0,
        native_price_usd=2500.0,
    )

    assert result.validated is True
    assert result.passed is False
    assert result.error == 'price_mismatch'
    assert result.diff_pct and result.diff_pct > 1.0


@pytest.mark.asyncio
async def test_validate_pair_price_skips_for_unknown_quote():
    pair_address = '0xaaaa000000000000000000000000000000000001'
    target_token = '0xbbbb000000000000000000000000000000000002'
    counter_token = '0xdddd000000000000000000000000000000000004'

    reserve0 = 10 * 10 ** 18
    reserve1 = 15000 * 10 ** 6
    timestamp_last = 1_700_000_000

    responses = [
        {'jsonrpc': '2.0', 'id': 1, 'result': '0x10'},
        {'jsonrpc': '2.0', 'id': 2, 'result': '0x000000000000000000000000' + target_token[2:]},
        {'jsonrpc': '2.0', 'id': 3, 'result': '0x000000000000000000000000' + counter_token[2:]},
        {'jsonrpc': '2.0', 'id': 4, 'result': _make_reserve_payload(reserve0, reserve1, timestamp_last)},
        {'jsonrpc': '2.0', 'id': 5, 'result': '0x0000000000000000000000000000000000000000000000000000000000000012'},
        {'jsonrpc': '2.0', 'id': 6, 'result': '0x0000000000000000000000000000000000000000000000000000000000000006'},
    ]

    session = FakeSession(responses)
    validator = OnChainPriceValidator(
        session,
        rpc_url='http://mock-rpc',
        max_pct_diff=5.0,
        timeout=5.0,
        common_token_addresses={'base': {}},
    )

    result = await validator.validate_pair_price(
        chain_name='base',
        pair_address=pair_address,
        target_token_address=target_token,
        counter_token_address=counter_token,
        dex_price_usd=1500.0,
        native_price_usd=None,
    )

    assert result.validated is False
    assert result.error == 'unsupported_quote_token'
    assert result.price_usd is None
