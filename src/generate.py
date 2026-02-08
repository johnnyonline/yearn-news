from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import content
import strategy_changes
import tvl
import vaults
import ycrv
import yyb
from utils import fmt_usd, get_week_and_year

OUTPUT_FILE = Path(__file__).parent.parent / "output.md"
MAX_STRATEGY_CHANGE_LINES = 10

CHAIN_NAMES = {
    1: "Ethereum",
    137: "Polygon",
    8453: "Base",
    42161: "Arbitrum",
    747474: "Katana",
}

CHAIN_EXPLORERS = {
    1: "https://etherscan.io",
    137: "https://polygonscan.com",
    8453: "https://basescan.org",
    42161: "https://arbiscan.io",
    747474: "https://katanascan.com",
}


def render_overview(week: int, year: int) -> str:
    return "## Overview" + content.OVERVIEW.format(week=week, year=year)


def fmt_eth(val: float) -> str:
    if val >= 1_000_000:
        return f"{val / 1_000_000:.2f}M ETH"
    if val >= 1_000:
        return f"{val / 1_000:.0f}K ETH"
    return f"{val:,.0f} ETH"


def render_glance(tvl_data: dict[str, Any]) -> str:
    lines = ["## Yearn at a glance"]

    # Yearn TVL
    if tvl_data["wow_usd_pct"] is not None:
        direction = "increased" if tvl_data["wow_usd_pct"] > 0 else "declined"
        lines.append(
            f"Yearn TVL {direction} week-over-week by **~{abs(tvl_data['wow_usd_pct']):.0f}%**, "
            f"from **{fmt_usd(tvl_data['prev_tvl_usd'])}** (**{tvl_data['prev_tvl_eth']:,.0f} ETH**) "
            f"to **{fmt_usd(tvl_data['tvl_usd'])}** (**{tvl_data['tvl_eth']:,.0f} ETH**)."
        )
    else:
        lines.append(f"Yearn TVL: **{fmt_usd(tvl_data['tvl_usd'])}** (**{tvl_data['tvl_eth']:,.0f} ETH**)")

    # DeFi TVL
    lines.append("")
    defi_wow = tvl_data.get("defi_wow_pct")
    if defi_wow is not None and tvl_data.get("prev_defi_tvl_usd"):
        direction = "increased" if defi_wow > 0 else "declined"
        lines.append(
            f"Total DeFi TVL {direction} week-over-week by **~{abs(defi_wow):.0f}%**, "
            f"from **{fmt_usd(tvl_data['prev_defi_tvl_usd'])}** (**{fmt_eth(tvl_data['prev_defi_tvl_eth'])}**) "
            f"to **{fmt_usd(tvl_data['defi_tvl_usd'])}** (**{fmt_eth(tvl_data['defi_tvl_eth'])}**),"
        )
    else:
        lines.append(
            f"Total DeFi TVL: **{fmt_usd(tvl_data['defi_tvl_usd'])}** (**{fmt_eth(tvl_data['defi_tvl_eth'])}**),"
        )
    lines.append(f"with Yearn's share at **{tvl_data['yearn_share_defi']:.2f}%**.")

    return "\n".join(lines)


def render_vault_list(vaults: list[dict[str, Any]]) -> list[str]:
    lines = []
    for v in vaults:
        url = f"https://yearn.fi/v3/{v['chain_id']}/{v['address']}"
        lines.append(
            f"- [**{v['name']}**]({url}) ({v['chain']}): **{v['apr']:.2f}%** APR | {fmt_usd(v['tvl_usd'])} TVL"
        )
    return lines


def render_vaults(data: dict[str, Any]) -> str:
    lines = ["## Vaults"]

    if content.VAULTS.strip():
        lines.append(content.VAULTS.strip())

    top_usd = data.get("top_usd", [])
    top_crypto = data.get("top_crypto", [])

    if not top_usd and not top_crypto:
        lines.append("Coming soon!")
        return "\n".join(lines)

    if top_usd:
        lines.append("**Top Stablecoin Vaults:**")
        lines.extend(render_vault_list(top_usd))

    if top_crypto:
        lines.append("")
        lines.append("**Top Crypto Vaults:**")
        lines.extend(render_vault_list(top_crypto))

    return "\n".join(lines)


def render_ycrv(data: dict[str, Any]) -> str:
    wow = f"+{data['wow_pct']:.1f}" if data["wow_pct"] > 0 else f"{data['wow_pct']:.1f}"
    text = content.YCRV.format(
        rewards=f"{data['rewards_crvusd']:,.2f}",
        prev_rewards=f"{data['prev_rewards_crvusd']:,.2f}",
        wow=wow,
    )
    return "## yCRV" + text


def _strategy_change_label(change_type: str) -> str:
    return {"0": "Added", "1": "Revoked"}.get(change_type, "Changed")


def _fmt_timestamp(ts: int | None) -> str:
    if ts is None:
        return "unknown time"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def render_strategy_changes(data: dict[str, Any]) -> str:
    lines = ["## Strategy Changes"]
    days = int(data.get("days", 7))
    error = data.get("error")

    if isinstance(error, str) and error:
        lines.append(f"Could not fetch `StrategyChanged` events from Envio for the last {days} days.")
        return "\n".join(lines)

    events = data.get("events", [])
    if not isinstance(events, list) or not events:
        lines.append(f"No `StrategyChanged` events were indexed in the last {days} days.")
        return "\n".join(lines)

    lines.append(f"Recent `StrategyChanged` events (last {days} days):")
    for event in events[:MAX_STRATEGY_CHANGE_LINES]:
        if not isinstance(event, dict):
            continue

        strategy = str(event.get("strategy", ""))
        change_type = _strategy_change_label(str(event.get("change_type", "")))
        chain_id = event.get("chainId")
        chain_name = CHAIN_NAMES.get(chain_id, f"Chain {chain_id}") if isinstance(chain_id, int) else "Unknown chain"
        timestamp = _fmt_timestamp(event.get("blockTimestamp") if isinstance(event.get("blockTimestamp"), int) else None)
        tx_hash = str(event.get("transactionHash", ""))
        explorer = CHAIN_EXPLORERS.get(chain_id, "https://etherscan.io") if isinstance(chain_id, int) else None
        tx_link = f" | [tx]({explorer}/tx/{tx_hash})" if tx_hash and explorer else ""

        lines.append(f"- **{change_type}** strategy `{strategy}` on **{chain_name}** ({timestamp}){tx_link}")

    if len(events) > MAX_STRATEGY_CHANGE_LINES:
        remaining = len(events) - MAX_STRATEGY_CHANGE_LINES
        lines.append(f"- ...and {remaining} more event(s).")

    return "\n".join(lines)


def has_strategy_changes_content(data: dict[str, Any]) -> bool:
    events = data.get("events", [])
    return isinstance(events, list) and len(events) > 0


def render_yyb(data: dict[str, Any]) -> str:
    if data["wow_pct"] is None or data["prev_rewards_crvusd"] is None:
        return f"## yYB\nThis week yYB stakers received **{data['rewards_crvusd']:,.2f} crvUSD** rewards."
    wow = f"+{data['wow_pct']:.1f}" if data["wow_pct"] > 0 else f"{data['wow_pct']:.1f}"
    text = content.YYB.format(
        rewards=f"{data['rewards_crvusd']:,.2f}",
        prev_rewards=f"{data['prev_rewards_crvusd']:,.2f}",
        wow=wow,
    )
    return "## yYB" + text


def render_alpha() -> str:
    return "## Alpha Corner" + content.ALPHA


def render_disclaimer() -> str:
    return "## Disclaimer" + content.DISCLAIMER


def render_sign_off() -> str:
    return content.SIGN_OFF.strip()


def generate() -> None:
    week, year = get_week_and_year()

    tvl_data = tvl.get_data()
    vaults_data = vaults.get_data()
    strategy_changes_data = strategy_changes.get_data()
    ycrv_data = ycrv.get_data()
    yyb_data = yyb.get_data()

    sections = [
        render_overview(week, year),
        render_glance(tvl_data),
        render_vaults(vaults_data),
        render_ycrv(ycrv_data),
        render_yyb(yyb_data),
        render_alpha(),
        render_disclaimer(),
        render_sign_off(),
    ]

    if has_strategy_changes_content(strategy_changes_data):
        sections.insert(3, render_strategy_changes(strategy_changes_data))

    output = "\n\n".join(sections)
    OUTPUT_FILE.write_text(output)
    print(f"Newsletter generated: {OUTPUT_FILE}")


if __name__ == "__main__":
    generate()
