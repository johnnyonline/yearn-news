import json
import os
from datetime import date
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"

# Chain configs
CHAINS = {
    "mainnet": {"rpc": os.getenv("RPC_MAINNET", ""), "chain_id": 1},
    "arbitrum": {"rpc": os.getenv("RPC_ARBITRUM", ""), "chain_id": 42161},
    "base": {"rpc": os.getenv("RPC_BASE", ""), "chain_id": 8453},
    "katana": {"rpc": os.getenv("RPC_KATANA", ""), "chain_id": 747474},
}

# Contract addresses (same across all chains)
REGISTRY_ADDRESSES = [
    "0xd40ecF29e001c76Dcc4cC0D9cd50520CE845B038",
    "0xff31A1B020c868F6eA3f61Eb953344920EeCA3af",
]
APR_ORACLE_ADDRESS = "0x1981AD9F44F2EA9aDd2dC4AD7D075c102C70aF92"
MULTICALL3_ADDRESS = "0xcA11bde05977b3631167028862bE2a173976CA11"

# Token addresses
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
WBTC_ADDRESS = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"


def get_week_and_year() -> tuple[int, int]:
    """Week number where week 1 is the first Friday of the year, plus year."""
    today = date.today()
    year_start = date(today.year, 1, 1)
    first_friday = year_start
    while first_friday.weekday() != 4:  # 4 = Friday
        first_friday = first_friday.replace(day=first_friday.day + 1)
    days_since = (today - first_friday).days
    return max(1, (days_since // 7) + 1), today.year


def is_previous_week(prev: dict[str, Any] | None, week: int, year: int) -> bool:
    if not prev:
        return False
    if prev.get("year") == year and prev.get("week") == week - 1:
        return True
    if prev.get("year") == year - 1 and week == 1:
        return True
    return False


def load_cache(name: str) -> dict[str, Any] | None:
    """Load the most recent entry from cache."""
    path = DATA_DIR / f"{name}_cache.json"
    if path.exists():
        data: Any = json.loads(path.read_text())
        if isinstance(data, list) and data:
            return dict(data[-1])
        elif isinstance(data, dict):
            return dict(data)
    return None


def load_cache_history(name: str) -> list[dict[str, Any]]:
    """Load all historical entries from cache."""
    path = DATA_DIR / f"{name}_cache.json"
    if path.exists():
        data: Any = json.loads(path.read_text())
        if isinstance(data, list):
            return [dict(d) for d in data]
        elif isinstance(data, dict):
            return [dict(data)]
    return []


def get_previous_week_data(name: str, week: int, year: int) -> dict[str, Any] | None:
    """Get data from the previous week."""
    history = load_cache_history(name)
    for entry in history:
        if entry.get("year") == year and entry.get("week") == week - 1:
            return entry
        if entry.get("year") == year - 1 and week == 1:
            return entry
    return None


def save_cache(name: str, data: dict[str, Any]) -> None:
    """Append data to cache history, avoiding duplicates for same week."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{name}_cache.json"

    history = load_cache_history(name)

    # Remove existing entry for same week/year if present
    history = [e for e in history if not (e.get("week") == data.get("week") and e.get("year") == data.get("year"))]

    history.append(data)
    path.write_text(json.dumps(history, indent=2))


def fetch_json(url: str) -> dict[str, Any]:
    with urlopen(url) as r:
        return dict(json.loads(r.read().decode()))


def fetch_eth_price() -> float:
    data = fetch_json("https://coins.llama.fi/prices/current/coingecko:ethereum")
    return float(data["coins"]["coingecko:ethereum"]["price"])


def fetch_btc_price() -> float:
    data = fetch_json("https://coins.llama.fi/prices/current/coingecko:bitcoin")
    return float(data["coins"]["coingecko:bitcoin"]["price"])


def fetch_sky_price() -> float:
    data = fetch_json("https://coins.llama.fi/prices/current/ethereum:0x56072C95FAA701256059aa122697B133aDEd9279")
    return float(data["coins"]["ethereum:0x56072C95FAA701256059aa122697B133aDEd9279"]["price"])


def fetch_yyb_price() -> float:
    data = fetch_json("https://coins.llama.fi/prices/current/ethereum:0x22222222aEA0076fCA927a3f44dc0B4FdF9479D6")
    return float(data["coins"]["ethereum:0x22222222aEA0076fCA927a3f44dc0B4FdF9479D6"]["price"])


def fmt_usd(val: float) -> str:
    if val >= 1_000_000_000:
        return f"${val / 1_000_000_000:.2f}B"
    if val >= 1_000_000:
        return f"${val / 1_000_000:.1f}M"
    if val >= 1_000:
        return f"${val / 1_000:.1f}K"
    return f"${val:.2f}"


def fmt_pct(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val:+.1f}%"


# Web3 helpers
ABIS_DIR = Path(__file__).parent / "abis"


def load_abi(name: str) -> list[dict[str, Any]]:
    return list(json.loads((ABIS_DIR / f"{name}.json").read_text()))


def get_web3(chain: str) -> Web3:
    rpc = CHAINS[chain]["rpc"]
    if not rpc:
        raise ValueError(f"RPC URL not configured for {chain}")
    return Web3(Web3.HTTPProvider(str(rpc)))


def multicall(w3: Web3, calls: list[tuple[str, bytes]], batch_size: int | None = None) -> list[tuple[bool, bytes]]:
    """Execute calls via Multicall3. Returns list of (success, returnData)."""
    multicall_abi = load_abi("multicall3")
    multicall_contract = w3.eth.contract(address=Web3.to_checksum_address(MULTICALL3_ADDRESS), abi=multicall_abi)
    call_data = [(Web3.to_checksum_address(target), True, data) for target, data in calls]

    if not batch_size or len(call_data) <= batch_size:
        results = multicall_contract.functions.aggregate3(call_data).call()
        return [(r[0], r[1]) for r in results]

    results = []
    for i in range(0, len(call_data), batch_size):
        chunk = call_data[i : i + batch_size]
        chunk_results = multicall_contract.functions.aggregate3(chunk).call()
        results.extend(chunk_results)

    return [(r[0], r[1]) for r in results]
