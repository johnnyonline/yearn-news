import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

SUPPORTED_CHAIN_IDS = [1, 8453, 42161, 137]


def _query_graphql(query: str) -> dict[str, Any]:
    envio_graphql_url = os.getenv("ENVIO_GRAPHQL_URL", "http://localhost:8080/v1/graphql")
    request = Request(
        envio_graphql_url,
        data=json.dumps({"query": query}).encode(),
        headers={"Content-Type": "application/json"},
    )

    with urlopen(request, timeout=30) as response:
        payload: Any = json.loads(response.read().decode())

    if not isinstance(payload, dict):
        raise RuntimeError("Invalid GraphQL response payload")

    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        messages = [str(err.get("message", "Unknown GraphQL error")) for err in errors if isinstance(err, dict)]
        raise RuntimeError("; ".join(messages) or "GraphQL query failed")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("GraphQL response did not include a data object")

    return data


def _to_int(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _build_recent_strategy_changes_query(days: int, limit: int) -> str:
    min_timestamp = int((datetime.now(tz=timezone.utc) - timedelta(days=days)).timestamp())
    chain_ids = ", ".join(str(chain_id) for chain_id in SUPPORTED_CHAIN_IDS)

    return f"""
    query GetRecentStrategyChanges {{
      strategyChanges: StrategyChanged(
        where: {{
          chainId: {{ _in: [{chain_ids}] }},
          blockTimestamp: {{ _gte: {min_timestamp} }}
        }}
        order_by: {{ blockTimestamp: desc, blockNumber: desc, logIndex: desc }}
        limit: {limit}
      ) {{
        id
        strategy
        change_type
        vaultAddress
        chainId
        blockNumber
        blockTimestamp
        transactionHash
      }}
    }}
    """


def get_data(days: int = 7, limit: int = 25) -> dict[str, Any]:
    """Fetch recent StrategyChanged events from the Envio GraphQL endpoint."""
    try:
        query = _build_recent_strategy_changes_query(days=days, limit=limit)
        data = _query_graphql(query)
        raw_events = data.get("strategyChanges", [])

        if not isinstance(raw_events, list):
            raise RuntimeError("Unexpected strategyChanges response shape")

        events: list[dict[str, Any]] = []
        for event in raw_events:
            if not isinstance(event, dict):
                continue

            strategy = event.get("strategy")
            if not isinstance(strategy, str) or not strategy:
                continue

            events.append(
                {
                    "id": str(event.get("id", "")),
                    "strategy": strategy,
                    "change_type": str(event.get("change_type", "")),
                    "vaultAddress": str(event.get("vaultAddress", "")),
                    "chainId": _to_int(event.get("chainId")),
                    "blockNumber": _to_int(event.get("blockNumber")),
                    "blockTimestamp": _to_int(event.get("blockTimestamp")),
                    "transactionHash": str(event.get("transactionHash", "")),
                }
            )

        return {"days": days, "events": events, "error": None}
    except Exception as error:
        return {"days": days, "events": [], "error": str(error)}
