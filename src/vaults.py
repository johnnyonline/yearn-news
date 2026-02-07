import json
import os
from typing import Any, cast
from urllib.request import Request, urlopen

from utils import (
    APR_ORACLE_ADDRESS,
    CHAINS,
    REGISTRY_ADDRESSES,
    fetch_btc_price,
    fetch_eth_price,
    fetch_json,
    fetch_sky_price,
    fetch_yyb_price,
    get_web3,
    load_abi,
    multicall,
)

KATANA_APR_API = "https://katana-apr-service.vercel.app/api/vaults"
MULTICALL_BATCH_SIZE = 75
KONG_GRAPHQL_URL = os.getenv("KONG_GRAPHQL_URL", "https://kong.yearn.fi/api/gql")
KONG_TIMEOUT_SECONDS = 30
KONG_VAULTS_QUERY = """
query Vaults($chainId: Int!) {
  vaults(chainId: $chainId, v3: true, yearn: true, vaultType: 1) {
    chainId
    address
    name
    tvl {
      close
    }
    performance {
      oracle {
        apr
      }
    }
    asset {
      address
    }
  }
}
"""

# Vault types
MULTI_STRATEGY_TYPE = 1

# Crypto tokens by type (everything else is USD, worth $1)
WETH_ADDRESSES = {
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",  # mainnet
    "0x4200000000000000000000000000000000000006",  # base
    "0x82af49447d8a07e3bd95bd0d56f35241523fbab1",  # arbitrum
    "0xee7d8bcfb72bc1880d0cf19822eb0a2e6577ab62",  # katana
}

WBTC_ADDRESSES = {
    "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",  # mainnet
    "0x2f2a2543b76a4166549f7aab2e75bef0aefc5b0f",  # arbitrum
    "0x0555e30da8f98308edb960aa94c0db47230d2b9c",  # base
    "0x0913da6da4b42f538b445599b46bb4622342cf52",  # katana
    "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf",  # cbBTC mainnet/base
}

SKY = "0x56072c95faa701256059aa122697b133aded9279"
YYB = "0x22222222aea0076fca927a3f44dc0b4fdf9479d6"

CRYPTO_TOKENS = WETH_ADDRESSES | WBTC_ADDRESSES | {SKY, YYB}

# Vaults to exclude
EXCLUDED_VAULTS = {
    "0x252b965400862d94BDa35FeCF7Ee0f204a53Cc36",
}
EXCLUDED_VAULTS_LOWER = {v.lower() for v in EXCLUDED_VAULTS}


def fetch_katana_aprs() -> dict[str, float]:
    """Fetch APRs from Katana API. Returns dict of address -> APR percentage."""
    try:
        data = fetch_json(KATANA_APR_API)
        aprs = {}
        for addr, vault_data in data.items():
            extra = vault_data.get("apr", {}).get("extra", {})
            katana_app_rewards = extra.get("katanaAppRewardsAPR", 0) or 0
            fixed_rate_rewards = extra.get("FixedRateKatanaRewards", 0) or 0
            native_yield = extra.get("katanaNativeYield", 0) or 0
            total_apr = katana_app_rewards + fixed_rate_rewards + native_yield
            aprs[addr.lower()] = total_apr * 100  # Convert to percentage
        return aprs
    except Exception:
        return {}


def _query_kong(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    if not KONG_GRAPHQL_URL:
        raise RuntimeError("KONG_GRAPHQL_URL is empty")

    request = Request(
        KONG_GRAPHQL_URL,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Content-Type": "application/json"},
    )

    with urlopen(request, timeout=KONG_TIMEOUT_SECONDS) as response:
        payload: Any = json.loads(response.read().decode())

    if not isinstance(payload, dict):
        raise RuntimeError("Invalid Kong GraphQL payload")

    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        messages = [str(err.get("message", "Unknown GraphQL error")) for err in errors if isinstance(err, dict)]
        raise RuntimeError("; ".join(messages) or "Kong GraphQL query failed")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Kong GraphQL response missing data")

    return data


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _get_data_from_kong() -> dict[str, Any]:
    usd_vaults: list[dict[str, Any]] = []
    crypto_vaults: list[dict[str, Any]] = []
    katana_aprs = fetch_katana_aprs()
    successful_chains = 0

    for chain_name, chain_info in CHAINS.items():
        chain_id = cast(int, chain_info["chain_id"])

        try:
            data = _query_kong(KONG_VAULTS_QUERY, {"chainId": chain_id})
        except Exception:
            continue

        successful_chains += 1
        raw_vaults = data.get("vaults", [])
        if not isinstance(raw_vaults, list):
            continue

        for raw in raw_vaults:
            if not isinstance(raw, dict):
                continue

            address_value = raw.get("address")
            if not isinstance(address_value, str) or not address_value:
                continue
            address = address_value
            address_lower = address.lower()

            if address_lower in EXCLUDED_VAULTS_LOWER:
                continue

            name_value = raw.get("name")
            if not isinstance(name_value, str) or not name_value:
                continue
            name = name_value

            if "Liquid Locker Compounder" in name:
                continue
            if not any(x in name for x in ("yVault", "BOLD", "USDaf")):
                continue

            asset_address = ""
            asset_data = raw.get("asset")
            if isinstance(asset_data, dict):
                asset_address_value = asset_data.get("address")
                if isinstance(asset_address_value, str):
                    asset_address = asset_address_value.lower()

            apr_pct = 0.0
            performance = raw.get("performance")
            if isinstance(performance, dict):
                oracle = performance.get("oracle")
                if isinstance(oracle, dict):
                    apr_pct = _to_float(oracle.get("apr")) * 100

            if chain_name == "katana":
                apr_pct = katana_aprs.get(address_lower, apr_pct)

            tvl_usd = 0.0
            tvl = raw.get("tvl")
            if isinstance(tvl, dict):
                tvl_usd = _to_float(tvl.get("close"))

            vault = {
                "name": name,
                "chain": chain_name,
                "chain_id": chain_id,
                "address": address,
                "apr": apr_pct,
                "tvl_usd": tvl_usd,
            }

            if asset_address in CRYPTO_TOKENS:
                crypto_vaults.append(vault)
            else:
                usd_vaults.append(vault)

    if successful_chains == 0:
        raise RuntimeError("Kong GraphQL query failed for all configured chains")

    usd_vaults.sort(key=lambda x: x["apr"], reverse=True)
    crypto_vaults.sort(key=lambda x: x["apr"], reverse=True)
    return {"top_usd": usd_vaults[:5], "top_crypto": crypto_vaults[:5]}


def _get_data_from_rpc() -> dict[str, Any]:
    """Fetch top V3 Multi Strategy vaults from on-chain registries."""
    usd_vaults: list[dict[str, Any]] = []
    crypto_vaults: list[dict[str, Any]] = []

    eth_price = fetch_eth_price()
    btc_price = fetch_btc_price()
    sky_price = fetch_sky_price()
    yyb_price = fetch_yyb_price()
    katana_aprs = fetch_katana_aprs()

    registry_abi = load_abi("registry")
    vault_abi = load_abi("vault")
    apr_oracle_abi = load_abi("apr_oracle")

    for chain_name, chain_info in CHAINS.items():
        try:
            w3 = get_web3(chain_name)
        except ValueError:
            continue

        # Query all registries and collect vault addresses
        vault_addresses: list[str] = []
        registry_for_vault: dict[str, str] = {}  # Track which registry each vault came from
        registry_contracts = {
            registry_addr: w3.eth.contract(
                address=w3.to_checksum_address(registry_addr),
                abi=registry_abi,
            )
            for registry_addr in REGISTRY_ADDRESSES
        }

        for registry_addr in REGISTRY_ADDRESSES:
            registry = registry_contracts[registry_addr]

            try:
                all_vaults = registry.functions.getAllEndorsedVaults().call()
                for sublist in all_vaults:
                    for addr in sublist:
                        if addr not in registry_for_vault:
                            vault_addresses.append(addr)
                            registry_for_vault[addr] = registry_addr
            except Exception:
                continue

        if not vault_addresses:
            continue

        vault_contract = w3.eth.contract(abi=vault_abi)
        apr_oracle = w3.eth.contract(
            address=w3.to_checksum_address(APR_ORACLE_ADDRESS),
            abi=apr_oracle_abi,
        )

        # First multicall: get vaultInfo to filter for Multi Strategy vaults
        info_calls = []
        for addr in vault_addresses:
            checksum_addr = w3.to_checksum_address(addr)
            reg_addr = registry_for_vault[addr]
            registry = registry_contracts[reg_addr]
            info_calls.append((reg_addr, registry.encode_abi("vaultInfo", args=[checksum_addr])))

        info_results = multicall(w3, info_calls, batch_size=MULTICALL_BATCH_SIZE)

        # Filter for Multi Strategy vaults only
        multi_strategy_vaults = []
        for i, addr in enumerate(vault_addresses):
            if addr in EXCLUDED_VAULTS:
                continue

            success, data = info_results[i]
            if not success:
                continue

            decoded = w3.codec.decode(["address", "uint96", "uint64", "uint128", "uint64", "string"], data)
            vault_type = decoded[2]

            if vault_type == MULTI_STRATEGY_TYPE:
                multi_strategy_vaults.append(addr)

        if not multi_strategy_vaults:
            continue

        # Second multicall: get name, asset, totalAssets, decimals, and APR (except Katana)
        is_katana = chain_name == "katana"
        calls = []
        for addr in multi_strategy_vaults:
            checksum_addr = w3.to_checksum_address(addr)
            calls.append((addr, vault_contract.encode_abi("name")))
            calls.append((addr, vault_contract.encode_abi("asset")))
            calls.append((addr, vault_contract.encode_abi("totalAssets")))
            calls.append((addr, vault_contract.encode_abi("decimals")))
            if not is_katana:
                calls.append((APR_ORACLE_ADDRESS, apr_oracle.encode_abi("getStrategyApr", args=[checksum_addr, 0])))

        results = multicall(w3, calls, batch_size=MULTICALL_BATCH_SIZE)
        calls_per_vault = 4 if is_katana else 5

        for i, addr in enumerate(multi_strategy_vaults):
            base_idx = i * calls_per_vault
            name_success, name_data = results[base_idx]
            asset_success, asset_data = results[base_idx + 1]
            total_assets_success, total_assets_data = results[base_idx + 2]
            decimals_success, decimals_data = results[base_idx + 3]

            if not all([name_success, asset_success, total_assets_success, decimals_success]):
                continue

            name = w3.codec.decode(["string"], name_data)[0]

            # Skip Liquid Locker Compounder vaults
            if "Liquid Locker Compounder" in name:
                continue

            # Only include vaults with yVault, BOLD, or USDaf in name
            if not any(x in name for x in ("yVault", "BOLD", "USDaf")):
                continue

            asset = w3.codec.decode(["address"], asset_data)[0].lower()
            total_assets = w3.codec.decode(["uint256"], total_assets_data)[0]
            decimals = w3.codec.decode(["uint8"], decimals_data)[0]

            # Get APR from Katana API or APR oracle
            if is_katana:
                apr_pct = katana_aprs.get(addr.lower(), 0.0)
            else:
                apr_success, apr_data = results[base_idx + 4]
                apr_pct = 0.0
                if apr_success:
                    apr_raw = w3.codec.decode(["uint256"], apr_data)[0]
                    apr_pct = (apr_raw / 1e18) * 100

            # Calculate TVL
            amount = total_assets / (10**decimals)
            if asset in WETH_ADDRESSES:
                tvl_usd = amount * eth_price
            elif asset in WBTC_ADDRESSES:
                tvl_usd = amount * btc_price
            elif asset == SKY:
                tvl_usd = amount * sky_price
            elif asset == YYB:
                tvl_usd = amount * yyb_price
            else:
                # Stablecoins assume $1
                tvl_usd = amount

            chain_id = chain_info["chain_id"]
            vault = {
                "name": name,
                "chain": chain_name,
                "chain_id": chain_id,
                "address": addr,
                "apr": apr_pct,
                "tvl_usd": tvl_usd,
            }

            if asset in CRYPTO_TOKENS:
                crypto_vaults.append(vault)
            else:
                usd_vaults.append(vault)

    usd_vaults.sort(key=lambda x: x["apr"], reverse=True)
    crypto_vaults.sort(key=lambda x: x["apr"], reverse=True)

    return {"top_usd": usd_vaults[:5], "top_crypto": crypto_vaults[:5]}


def get_data() -> dict[str, Any]:
    """Fetch top V3 Multi Strategy vaults, preferring Kong GraphQL over direct RPC."""
    try:
        kong_data = _get_data_from_kong()
        if kong_data["top_usd"] or kong_data["top_crypto"]:
            return kong_data
        print("Kong returned no vault data; falling back to direct RPC calls.")
    except Exception as error:
        print(f"Kong query failed ({error}); falling back to direct RPC calls.")

    return _get_data_from_rpc()
