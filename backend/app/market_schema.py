"""Canonical market DTO + adapters for scanner and strategies."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


YES_LABELS = {"yes", "y", "long", "true", "1"}
NO_LABELS = {"no", "n", "short", "false", "0"}


class CanonicalMarket(BaseModel):
    """Single market schema shared by scanner, strategies, and executor."""

    market_id: str
    condition_id: str
    question: str
    yes_token_id: str
    no_token_id: str
    yes_price: float
    no_price: float
    volume: float = 0.0
    spread: float = 0.0
    category: str = ""
    end_date: str = ""
    tokens: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("market_id", "condition_id", "question", "yes_token_id", "no_token_id")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("required field is empty")
        return value

    @field_validator("yes_price", "no_price")
    @classmethod
    def _price_in_bounds(cls, value: float) -> float:
        value = float(value)
        if not 0.0 <= value <= 1.0:
            raise ValueError("price must be between 0 and 1")
        return round(value, 6)

    @model_validator(mode="after")
    def _derive_fields(self) -> "CanonicalMarket":
        self.spread = round(abs(1.0 - self.yes_price - self.no_price), 6)
        if not self.tokens:
            self.tokens = [
                {"token_id": self.yes_token_id, "outcome": "YES", "price": self.yes_price},
                {"token_id": self.no_token_id, "outcome": "NO", "price": self.no_price},
            ]
        return self

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.market_id,
            "market_id": self.market_id,
            "condition_id": self.condition_id,
            "question": self.question,
            "yes_token_id": self.yes_token_id,
            "no_token_id": self.no_token_id,
            "yes_price": self.yes_price,
            "no_price": self.no_price,
            "outcomePrices": [self.yes_price, self.no_price],
            "volume": self.volume,
            "spread": self.spread,
            "arb_opportunity": (self.yes_price + self.no_price) < 0.97,
            "category": self.category,
            "end_date": self.end_date,
            "tokens": self.tokens,
        }


def _normalize_outcome(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in YES_LABELS:
        return "YES"
    if raw in NO_LABELS:
        return "NO"
    return raw.upper()


def _extract_token_id(token: dict[str, Any]) -> str | None:
    for key in ("token_id", "tokenId", "clobTokenId", "clob_token_id", "id"):
        value = token.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _extract_prices(raw_market: dict[str, Any]) -> tuple[float, float]:
    outcome_prices = raw_market.get("outcomePrices") or raw_market.get("outcome_prices") or []
    yes_price = raw_market.get("yes_price")
    no_price = raw_market.get("no_price")

    if yes_price is None and outcome_prices:
        yes_price = outcome_prices[0]
    if no_price is None and len(outcome_prices) > 1:
        no_price = outcome_prices[1]

    yes_value = float(yes_price if yes_price is not None else 0.5)
    no_value = float(no_price if no_price is not None else max(0.0, 1.0 - yes_value))
    return yes_value, no_value


def adapt_market(raw_market: dict[str, Any]) -> CanonicalMarket:
    """Adapt Gamma/scanner payloads into the canonical market DTO."""

    condition_id = str(raw_market.get("condition_id") or raw_market.get("conditionId") or "").strip()
    market_id = str(raw_market.get("market_id") or raw_market.get("id") or condition_id).strip()
    question = str(raw_market.get("question") or raw_market.get("title") or "").strip()

    yes_price, no_price = _extract_prices(raw_market)

    yes_token_id = str(raw_market.get("yes_token_id") or "").strip()
    no_token_id = str(raw_market.get("no_token_id") or "").strip()

    tokens = raw_market.get("tokens") or []
    normalized_tokens: list[dict[str, Any]] = []
    for token in tokens:
        if not isinstance(token, dict):
            continue
        token_id = _extract_token_id(token)
        if not token_id:
            continue
        outcome = _normalize_outcome(token.get("outcome"))
        price = float(token.get("price", yes_price if outcome == "YES" else no_price))
        normalized_tokens.append({"token_id": token_id, "outcome": outcome, "price": price})
        if outcome == "YES" and not yes_token_id:
            yes_token_id = token_id
        if outcome == "NO" and not no_token_id:
            no_token_id = token_id

    if not yes_token_id and condition_id:
        yes_token_id = f"{condition_id}-YES"
    if not no_token_id and condition_id:
        no_token_id = f"{condition_id}-NO"

    return CanonicalMarket(
        market_id=market_id,
        condition_id=condition_id,
        question=question,
        yes_token_id=yes_token_id,
        no_token_id=no_token_id,
        yes_price=yes_price,
        no_price=no_price,
        volume=float(raw_market.get("volume", 0.0) or 0.0),
        category=str(raw_market.get("category", "") or ""),
        end_date=str(raw_market.get("end_date") or raw_market.get("endDate") or ""),
        tokens=normalized_tokens,
    )
