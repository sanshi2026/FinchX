"""Complete, concrete calls for representative FinchX Client capabilities.

The bilingual API reference contains one complete call for every public
endpoint. This file demonstrates common workflows and keeps each call's
available arguments visible for copy-and-adapt use.
"""

from finchx import FinchX


def basic_usage(client: FinchX):
    """Fetch a full-market A-share quote snapshot using the default universe."""
    result = client.market.quote()
    print(result.data)
    print(result.to_dicts()[:1])
    print(result.warnings)
    return result


def calendar_usage(client: FinchX):
    """Fetch trading-day flags for an inclusive A-share date range."""
    result = client.reference.trading_calendar(
        start_date="2026-09-01",  # Inclusive first calendar date.
        end_date="2026-09-23",  # Inclusive last calendar date.
    )
    print(result.data, result.to_dicts()[:1], result.warnings)
    return result


def article_from_hotlist(client: FinchX):
    """Fetch one article body from the content hotlist when available."""
    listing = client.hotlist.content(
        content_type="article",  # Return article entries.
        limit=20,  # Maximum number of entries.
    )
    print(listing.data, listing.to_dicts()[:1], listing.warnings)
    if not listing.data:
        return None
    url = listing.data[0].data.get("url")
    if not url:
        return None
    result = client.articles.get(
        url=url,  # Article URL from the hotlist entry.
    )
    print(result.data, result.to_dicts()[:1], result.warnings)
    return result


def articles_from_topic(client: FinchX):
    """Filter a topic feed to article entries and fetch its items."""
    listing = client.hotlist.content(
        content_type="topic",  # Return topic entries.
        limit=20,  # Maximum number of entries.
    )
    print(listing.data, listing.to_dicts()[:1], listing.warnings)
    if not listing.data:
        return None
    topic_url = listing.data[0].data.get("url")
    if not topic_url:
        return None
    result = client.articles.from_topic(
        topic_url=topic_url,  # T-code topic URL from the content list.
        sort="recommend",  # Sort by the supported recommendation order.
        limit=20,  # Maximum number of article entries.
    )
    print(result.data, result.to_dicts()[:1], result.warnings)
    return result


def news_and_disclosure(client: FinchX):
    """Search dated news and notices, then fetch one article body."""
    news = client.news.search(
        instrument="600519",  # Six-digit A-share code.
        page=1,  # Start at the first page for a date-bounded scan.
        page_size=20,  # Number of source rows requested per page.
        max_results=40,  # Bound the number of matching references.
        since="2026-09-01",  # Inclusive publication-date lower bound.
        until="2026-09-23",  # Inclusive publication-date upper bound.
        sort="published_desc",  # Sort newest publication first.
    )
    notices = client.disclosure.search(
        instrument="600519",  # Six-digit A-share code.
        page=1,  # Start at the first page for a date-bounded scan.
        page_size=20,  # Number of source rows requested per page.
        max_results=40,  # Bound the number of matching references.
        since="2026-09-01",  # Inclusive publication-date lower bound.
        until="2026-09-23",  # Inclusive publication-date upper bound.
        categories=None,  # Do not filter notice categories.
        sort="published_desc",  # Sort newest publication first.
    )
    print(news.data, news.to_dicts()[:1], news.warnings)
    print(notices.data, notices.to_dicts()[:1], notices.warnings)
    if news.data:
        ref = news.data[0]
        print(ref.document_url)  # Body URL; source_url is the listing page.
        detail = client.news.get_document(ref=ref)  # Reference from news.search.
        print(detail.data, detail.to_dicts(), detail.warnings)
    return news, notices


def representative_data_calls(client: FinchX):
    """Show complete calls for fundamentals and computed deviation data."""
    financials = client.fundamental.financial_summary(
        instrument="600519",  # Six-digit A-share code.
    )
    keywords = client.market.stock_keyword(
        instrument="600519",  # Six-digit A-share code.
    )
    concepts = client.market.concept_list()
    deviation = client.market.deviation(
        instrument="600519",  # Six-digit A-share code.
        windows=(10, 30),  # Calculate the 10- and 30-session windows.
        as_of="2026-09-23",  # Last completed trading date to include.
        window_convention="max_deviation_scan",  # Select the documented scan rule.
    )
    for result in (financials, keywords, concepts, deviation):
        print(result.data, result.to_dicts()[:1], result.warnings)
    return financials, keywords, concepts, deviation


def main() -> None:
    client = FinchX()
    basic_usage(client)
    calendar_usage(client)
    article_from_hotlist(client)
    articles_from_topic(client)
    news_and_disclosure(client)
    representative_data_calls(client)


if __name__ == "__main__":
    main()
