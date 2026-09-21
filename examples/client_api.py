"""Small examples for the frozen FinchX Client API."""

from datetime import date

from finchx import FinchX
from finchx.collectors import MissingOptionalDependency
from finchx.datasets import FinancialSummaryRequest, MarketStockKeywordRequest
from finchx.entities import Exchange, InstrumentId, InstrumentKind, Market


def basic_usage(client: FinchX):
    """Canonical Client entry and one real public endpoint."""
    result = client.market.quote()
    print(result.data)
    return result


def explicit_provider_usage(client: FinchX):
    """Pin one Provider explicitly; this disables Provider fallback."""
    return client.market.quote(provider="tencent.finance.qq.market")


def optional_calendar_usage(client: FinchX):
    """Use the calendar extra when selecting its optional Provider explicitly."""
    try:
        return client.reference.trading_calendar(
            date(2026, 9, 1),
            date(2026, 9, 30),
            provider="pandas_market_calendars",
        )
    except MissingOptionalDependency as exc:
        print(f"Install the calendar extra for {exc.dependency!r}.")
        return None


def main() -> None:
    client = FinchX()

    # Simple calls use the existing default request construction.
    basic_usage(client)
    explicit_provider_usage(client)
    optional_calendar_usage(client)

    instrument = InstrumentId(
        code="600519",
        market=Market.CN_A,
        kind=InstrumentKind.EQUITY,
        exchange=Exchange.SSE,
    )
    client.fundamental.financial_summary(
        FinancialSummaryRequest(instrumentId=instrument)
    )
    client.news.search(instrument, provider="eastmoney.news")
    client.market.stock_keyword(MarketStockKeywordRequest(instrumentId=instrument))
    client.market.deviation(instrument, windows=(10, 30))
    client.disclosure.search(instrument, use_cache=True)


if __name__ == "__main__":
    main()
