# News and disclosure datasets v1

This document defines two independent Dataset contracts:

```text
news.document@1.0
disclosure.document@1.0
```

Both use EastMoney individual-stock sources. Industry news, Tencent news,
Tencent HyNews, summaries, sentiment, impact scoring, and automated research
logic are outside this contract.

## Public query entry points

The package exposes no network side effect on import. Explicit services are
available as `finchx.news` and `finchx.disclosure`, or as `NewsService` and
`DisclosureService` instances for injected offline Providers:

```python
from finchx import disclosure, news

news_refs = news.search(
    instrument="001376",
    page=1,
    page_size=20,
    since=None,
    until=None,
    sort="published_desc",
)
selected_news = [news_refs[0], news_refs[3]]
documents = news.get_documents(selected_news)

disclosure_refs = disclosure.search(
    instrument="001376",
    page=1,
    page_size=20,
    max_results=10,
    categories=["001002009"],
)
selected_disclosures = [disclosure_refs[0], disclosure_refs[3]]
announcement_documents = disclosure.get_documents(selected_disclosures)
```

The services return tuples of lightweight, JSON-compatible `NewsDocumentRef`
or `DisclosureDocumentRef` values. A ref contains the stable document IDs,
title, normalized time fields, source identity, captured time, provenance, and
the list metadata needed for later retrieval; it does not fetch full text.
`get_document(ref)` and `get_documents(refs)` accept only the corresponding
Ref type, fetch complete source content sequentially, and merge it with the
Ref metadata. There is no cross-call cache or unbounded concurrency.

`page` and `page_size` control one upstream page. `max_results` starts at
page 1 and automatically fetches more pages until the requested count, the
source end, or the source total is reached. To avoid ambiguous behavior,
`max_results` with `page != 1` is rejected. Both News and Disclosure support
`since`, `until`, and `sort=published_desc|published_asc` over their
normalized `publishedAt`. Disclosure additionally supports `categories`; both
services apply time filters and sorting after normalization and never
substitute `noticeDate`, `sourceRecordedAt`, or a source sort field for a
missing `publishedAt`.

Document IDs are provider/domain-qualified and namespace-separated:

```text
eastmoney:news:{Art_Code}
eastmoney:disclosure:{art_code}
```

They are stable, serializable, URL-independent route keys. Public APIs do not
expose EastMoney `callback`, `traceId`, `_`, `cfh`, `client_source`, or
`market_code` as source-specific API concepts.

## News contract

`news.document@1.0` contains `documentId`, `sourceDocumentId`, `title`,
`contentText`, `publishedAt`, `url`, `originalUrl`, `contentAvailable`,
`source`, and `relatedInstruments`. Search leaves `contentText` null while
advertising that a detail fetch is available. Detail fetch returns non-empty
continuous text.

Provider field mapping matched `Art_ShowTime` to the article-page displayed time,
so it is normalized as Asia/Shanghai `publishedAt`. The detail fallback is
server-rendered HTML at `finance.eastmoney.com/a/{Art_Code}.html`; extraction
is Provider-owned and preserves table rows, lists, headings, quotes, and
paragraphs as `contentText`. `Art_Code`, `Art_Url`, and `Art_OriginUrl` are
provenance-bearing source values.

## Disclosure contract

`disclosure.document@1.0` contains `documentId`, `sourceDocumentId`, `title`,
`contentText`, `noticeDate`, `publishedAt`, `sourceRecordedAt`, `categories`,
`relatedInstruments`, `contentAvailable`, `pdfAvailable`,
`originalDocumentUrl`, `attachments`, and `sourceType`.

`categories` retain EastMoney's stable `code`, `name`, and `source` without
forcing a FinchX enum. `relatedInstruments` retains every security in
`codes[]`/`security[]`. PDF URLs and attachment metadata are references only:
FinchX does not download, parse, or OCR PDF files in this stage.

The content API's `page_size` is an internal total-page count. FinchX always
retrieves every page and joins `notice_content` in ascending page order before
returning one document. Callers never handle EastMoney page indexes.

The search result is a `DisclosureDocumentRef` with the same stable public
metadata plus `sourceUrl`, `originalDocumentUrl`, `source`, `capturedAt`, and
`provenance`. For disclosure list rows, EastMoney `display_time` is normalized as the public
`publishedAt` in Asia/Shanghai with source milliseconds preserved. `eiTime`
and content `eitime` are EastMoney internal record times and normalize as the
generic `sourceRecordedAt`; `noticeDate` is the formal notice/document date;
`sort_date` is retained only in provenance as an internal ordering timestamp.
Disclosure PIT cutoffs and sorting use only normalized `publishedAt`, never
`noticeDate`, `sourceRecordedAt`, or `sort_date`. The content-only detail
endpoint has no `display_time`; this is why the public full-document API
requires a `DisclosureDocumentRef` and merges its confirmed list metadata with
the detail content. It never guesses or loses `publishedAt`, categories, or
related instruments.

The same two-stage rule applies to news: `news.search()` returns
`NewsDocumentRef`, and `news.get_document(ref)` / `news.get_documents(refs)`
return full documents while preserving the Ref's title, IDs, time, source,
capturedAt, and provenance metadata.

## Status, provenance, and limitations

Records use the existing FinchX StandardRecord envelope with `status=live`,
direct EastMoney source identity, source record ID, source URL, transformation
version, and `capturedAt`. A Provider failure is not represented as a
successful empty result. Schema drift, malformed JSON/HTML, HTTP error,
identity mismatch, duplicate conflict, and missing content pages fail fast.

The field mapping, time semantics, endpoint behavior, and known limitations
are described by this contract and covered by the offline tests.

## Validation record

The offline fixture suite covers SSE and SZSE news lists, news HTML with a
table/list/quote, SSE and SZSE disclosure lists, single-page content, and a
two-page content response. Offline tests cover normalization, routing,
pagination, max-results, date/category filters, document IDs, HTML completeness,
PDF references, failure handling, and both JSON Schemas.

On 2026-09-19, bounded live checks returned HTTP 200 for news list/detail and
disclosure list/content for SSE `600519`, SZSE `000001`, and SZSE `300434`;
identity, non-empty metadata/content, source URLs, categories, notice time
fields, independent disclosure time mapping, display-time filtering, Ref
serialization, Ref-to-full merge, and ordered batch retrieval passed for the
samples checked.
This is a run-specific validation, not a permanent availability guarantee.
