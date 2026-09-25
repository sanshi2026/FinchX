"""One Provider for Tonghuashun hot stock, sector, fund and content rankings."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from finchx.contracts import Source
from finchx.datasets.hotlist import (HotContentRequest, HotConvertibleBondsRequest,
    HotEtfsRequest, HotSectorsRequest, HotStocksRequest)
from finchx.entities import Exchange
from finchx.providers.errors import ProviderError
from finchx.providers.http import DEFAULT_TIMEOUT_SECONDS, build_headers, http_status_failure_reason

STOCK_URL = "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock"
NEW_STOCK_URL = "https://eq.10jqka.com.cn/open/api/hot_list/rank/v1/new_stock.txt"
PLATE_URL = "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/plate"
BOND_URL = "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/bond"
TOPIC_URL = "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/topic"
COMMENT_URL = "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/comment"
INDEX_SECTOR_URL = "https://dq.10jqka.com.cn/fuyao/fund_fe_tools/fund/v1/index_sector"
ETF_RECOMMEND_URL = "https://fund.10jqka.com.cn/quotation/fund/recommend/v1/batch/single"
ETF_SPECIFIC_URL = "https://fund.10jqka.com.cn/datahub/dataapi/fetch/outer/v1/specific_data"
IWENCAI_URL = "https://ai.iwencai.com/index/urp/getdata/basic"
FUND_POOL_URL = "https://fund.10jqka.com.cn/quotation/fund_pool/v2/query"
FUND_SPECIFIC_URL = "https://fund.10jqka.com.cn/quotation/temp/data_api/fetch/v1/specific_data"
TAG_DATA_URL = "https://dataq.10jqka.com.cn/dataapi/tagservice/fetch/v1/tag_data"
_POOL_KEYS = {"popular":"347c9f28-8a67-48a7-8c05-380ff8e595c7", "t0":"fa2c6ba4-c243-4057-af9a-3dfe2d98d73b", "price_limit_20":"8dfbaf18-9408-331a-93cd-1b2174e64619", "cross_border":"8c2b110c-8913-4fc0-bd31-0d298e9d2ff2", "commodity":"847cee32-8433-4d62-b379-833410f600c1"}
# THS fund-pool market codes: 20/17 identify SSE ETFs and 36/18 identify SZSE ETFs.
_ETF_EXCHANGES = {"17": Exchange.SSE, "20": Exchange.SSE, "18": Exchange.SZSE, "36": Exchange.SZSE}
_LIST_TYPES = {"popular":"normal", "rising":"skyrocket", "technical":"tech", "value":"value", "trend":"trend"}
_TAG_KEYS = ("ifund_etf_t0", "ifund_biz_FS34806_tech_side", "ifund_biz_FS34806_fund_side")
_JSONP = re.compile(r"^\s*[A-Za-z_$][\w.$]*\s*\((.*)\)\s*;?\s*$", re.DOTALL)
_SHANGHAI = ZoneInfo("Asia/Shanghai")

class THSHotListProvider:
    """Provider for the five public hotlist datasets."""
    provider_id = "tonghuashun.hotlist"
    def __init__(self, opener: Callable[..., Any] | None = None, *, clock=None) -> None:
        self._open = opener or urlopen
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._source = Source(providerId=self.provider_id, sourceUrl=STOCK_URL)
    @property
    def source(self) -> Source: return self._source
    def fetch_raw_hotlist(self, request: Any) -> list[dict[str, object]]:
        if isinstance(request, HotStocksRequest): return self._stocks(request)
        if isinstance(request, HotSectorsRequest): return self._sectors(request)
        if isinstance(request, HotConvertibleBondsRequest): return self._bonds(request)
        if isinstance(request, HotEtfsRequest): return self._etfs(request)
        if isinstance(request, HotContentRequest): return self._content(request)
        self._fail(f"unsupported request type {type(request).__name__}")

    def _stocks(self, req: HotStocksRequest) -> list[dict[str, object]]:
        period = req.period or ("1h" if req.category in {"popular", "rising"} else "24h")
        if req.category not in {"popular", "rising"} and period != "24h": self._fail("this stock category only supports 24h")
        payload = self._get(NEW_STOCK_URL) if req.category == "new" else self._get(STOCK_URL, {"stock_type":"a", "list_type":_LIST_TYPES[req.category], "type":"hour" if period == "1h" else "day"})
        source_rows = self._array(payload, "data", "stock_list", "list", "rows")
        ranked = []
        for pos, raw in enumerate(source_rows, 1):
            if not isinstance(raw, Mapping): continue
            code = self._text(raw.get("code"))
            if not code: continue
            rank = self._int(raw.get("display_order")) or self._int(raw.get("order")) or self._int(raw.get("rank")) or pos
            tag = raw.get("tag") if isinstance(raw.get("tag"), Mapping) else {}
            ranked.append((rank, pos, {"rank":rank, "symbol":code.zfill(6), "name":self._text(raw.get("name")) or "",
                "category":req.category, "period":period, "changePct":self._decimal(raw.get("rise_and_fall")),
                "heat":self._decimal(raw.get("rate")), "rankChange":self._int(raw.get("hot_rank_chg")),
                "conceptTags":self._strings(tag.get("concept_tag")), "popularityTag":self._text(tag.get("popularity_tag")),
                "analysisTitle":self._text(raw.get("analyse_title")), "analysis":self._text(raw.get("analyse")),
                "searchCount":self._int(raw.get("search_cnt")), "updatedAt":self._datetime(raw.get("update_time")),
                "pe":self._decimal(raw.get("pe")) if req.category == "new" else None}))
        ranked.sort(key=lambda x:(x[0],x[1]))
        return self._rows([item for _,_,item in ranked[:req.limit]], "stocks", source_url=NEW_STOCK_URL if req.category=="new" else STOCK_URL)

    def _sectors(self, req: HotSectorsRequest) -> list[dict[str, object]]:
        rows = []
        if req.sector_type == "index":
            payload = self._post(INDEX_SECTOR_URL, {"page_info":{"page_begin":0,"page_size":max(20,req.limit)}})
            indexes = self._indexes(payload)
            source_rows = self._array(payload,"data","rows","list")
            for pos, raw in enumerate(source_rows,1):
                if not isinstance(raw,Mapping): continue
                values = self._values(raw,indexes)
                name = self._text(values.get("security_name") or raw.get("security_name") or raw.get("name"))
                if not name: continue
                source_code = self._text(raw.get("code") or raw.get("security_code")) or name
                embedded_market, code = self._split_code(source_code)
                market = self._text(raw.get("market_id") or raw.get("marketId")) or embedded_market
                rows.append({"rank":pos,"sectorCode":code,"name":name,"sectorType":"index",
                    "changePct":self._decimal(values.get("price_change_ratio_pct") or raw.get("price_change_ratio_pct")),
                    "heat":self._decimal(values.get("ths-hot-data-minute-attention-rate") or raw.get("ths-hot-data-minute-attention-rate")),
                    "rankChange":None,"tag":None,"hotTag":None,"relatedEtfSymbol":None,"relatedEtfName":None,"relatedEtfChangePct":None,
                    "__source_index_key":f"{market}:{code}" if market else source_code})
            source_references = [{"providerId":self.provider_id,"sourceRecordId":"index-sector-metrics","sourceUrl":INDEX_SECTOR_URL}]
            optional_partial = False
            input_codes = []
            for raw in source_rows:
                if isinstance(raw,Mapping) and raw.get("code") is not None:
                    market = self._text(raw.get("market_id") or raw.get("marketId"))
                    code = self._text(raw.get("code"))
                    if code:
                        embedded_market, bare_code = self._split_code(code)
                        market = market or embedded_market
                        input_codes.append(f"{market}:{bare_code}" if market else bare_code)
            if input_codes:
                try:
                    recommendation = self._post(ETF_RECOMMEND_URL, {
                        "code_selectors":{"include":[{"type":"stock_code","values":input_codes}]},
                    })
                    recommended = self._recommendations(recommendation, input_codes)
                    etf_codes = [item["code"] for item in recommended if item.get("code")]
                    metrics_by_code: dict[str, Decimal] = {}
                    if etf_codes:
                        detail = self._post(ETF_SPECIFIC_URL, {
                            "code_selectors":{"include":[{"type":"stock_code","values":etf_codes}]},
                            "indexes":[{"index_id":"price_change_ratio_pct"}],
                            "page_info":{"page_begin":0,"page_size":len(etf_codes)},
                        })
                        detail_indexes = self._indexes(detail)
                        for entry in self._array(detail,"data","rows","list"):
                            if not isinstance(entry,Mapping): continue
                            metric_values = self._values(entry,detail_indexes)
                            metric = self._decimal(metric_values.get("price_change_ratio_pct"))
                            code = self._text(entry.get("code"))
                            if code and metric is not None: metrics_by_code[code] = metric
                    recommendations_by_index = {}
                    ambiguous_keys = set()
                    for item in recommended:
                        key = str(item.get("indexCode") or "")
                        if not key: continue
                        if key in recommendations_by_index:
                            ambiguous_keys.add(key)
                        else:
                            recommendations_by_index[key] = item
                    for key in ambiguous_keys:
                        recommendations_by_index.pop(key, None)
                    for row in rows:
                        index_key = str(row.get("__source_index_key") or "")
                        rec = recommendations_by_index.get(index_key)
                        if rec is None and ":" in index_key:
                            rec = recommendations_by_index.get(index_key.rsplit(":", 1)[-1])
                        if rec is None: continue
                        code = str(rec.get("code") or "")
                        _, symbol = self._split_code(code)
                        row["relatedEtfSymbol"] = symbol or self._text(rec.get("etfCode"))
                        row["relatedEtfName"] = self._text(rec.get("name"))
                        row["relatedEtfChangePct"] = metrics_by_code.get(code)
                    source_references.append({"providerId":self.provider_id,"sourceRecordId":"index-sector-etf-recommendations","sourceUrl":ETF_RECOMMEND_URL})
                    if etf_codes:
                        source_references.append({"providerId":self.provider_id,"sourceRecordId":"index-sector-etf-quotes","sourceUrl":ETF_SPECIFIC_URL})
                    if any(not row.get("relatedEtfSymbol") or row.get("relatedEtfChangePct") is None for row in rows):
                        optional_partial = True
                except Exception:
                    optional_partial = True
            else:
                source_references = [{"providerId":self.provider_id,"sourceRecordId":"index-sector-metrics","sourceUrl":INDEX_SECTOR_URL}]
            if optional_partial:
                for row in rows: row["__partial"] = True
                for row in rows: row["__partial_detail"] = "Related ETF enrichment data was unavailable or could not be associated with an index."
            for row in rows:
                row["__source_url"] = INDEX_SECTOR_URL
                row["__source_references"] = source_references
        else:
            payload = self._get(PLATE_URL,{"type":req.sector_type})
            for pos, raw in enumerate(self._array(payload,"data","plate_list","list","rows"),1):
                if not isinstance(raw,Mapping): continue
                code,name=self._text(raw.get("code")),self._text(raw.get("name"))
                if not code or not name: continue
                rows.append({"rank":self._int(raw.get("order")) or pos,"sectorCode":code,"name":name,"sectorType":req.sector_type,
                    "changePct":self._decimal(raw.get("rise_and_fall")),"heat":self._decimal(raw.get("rate")),
                    "rankChange":self._int(raw.get("hot_rank_chg")),"tag":self._text(raw.get("tag")),"hotTag":self._text(raw.get("hot_tag")),
                    "relatedEtfSymbol":self._text(raw.get("etf_product_id")),"relatedEtfName":self._text(raw.get("etf_name")),
                    "relatedEtfChangePct":self._decimal(raw.get("etf_rise_and_fall"))})
            for row in rows:
                row["__source_url"] = PLATE_URL
        rows.sort(key=lambda x:int(x["rank"]))
        return self._rows(rows[:req.limit],f"sectors:{req.sector_type}",source_url=INDEX_SECTOR_URL if req.sector_type=="index" else PLATE_URL)

    def _bonds(self, req: HotConvertibleBondsRequest) -> list[dict[str, object]]:
        rows=[]
        for pos,raw in enumerate(self._array(self._get(BOND_URL),"data","list","rows"),1):
            if not isinstance(raw,Mapping): continue
            code=self._text(raw.get("code"))
            if code: rows.append({"rank":self._int(raw.get("order")) or pos,"symbol":code.zfill(6),"name":self._text(raw.get("name")) or "","changePct":self._decimal(raw.get("rise_and_fall")),"heat":self._decimal(raw.get("hot"))})
        rows.sort(key=lambda x:int(x["rank"]))
        return self._rows(rows[:req.limit],"convertible_bonds",source_url=BOND_URL)

    def _etfs(self, req: HotEtfsRequest) -> list[dict[str, object]]:
        pool=self._post(FUND_POOL_URL,{"businessPoolKey":_POOL_KEYS[req.category],"custom":{"fieldList":["etfName","subMarket","tradeCode"],"offset":0,"limit":10000}})
        pool_rows=self._pool_rows(pool)
        codes=list(dict.fromkeys(code for row in pool_rows if (code:=self._pool_code(row))))
        metrics=[]
        for offset in range(0,len(codes),100):
            batch=codes[offset:offset+100]
            payload=self._post(FUND_SPECIFIC_URL,{"code_selectors":{"include":[{"type":"stock_code","values":batch}]},
                "indexes":[{"index_id":"price_change_ratio_pct"},{"index_id":"ths-hot-data-day-attention-rate"}],"sort":[{"idx":1,"order":"desc"}],"page_info":{"page_begin":0,"page_size":len(batch)}},{"Source-Id":"ths-hot-list"})
            indexes=self._indexes(payload)
            for raw in self._array(payload,"data","rows","list"):
                if not isinstance(raw,Mapping): continue
                code=self._text(raw.get("code") or raw.get("stock_code")); vals=self._values(raw,indexes)
                heat=self._decimal(vals.get("ths-hot-data-day-attention-rate")); change=self._decimal(vals.get("price_change_ratio_pct"))
                if code and heat is not None: metrics.append({"code":code,"heat":heat,"changePct":change})
        if codes and not metrics: self._fail("ETF heat metric request returned no ranked rows")
        metrics.sort(key=lambda x:Decimal(str(x["heat"])),reverse=True)
        pool_by_code={self._pool_code(row):row for row in pool_rows if self._pool_code(row)}
        selected=metrics[:req.limit]; tags={}; partial=False
        try:
            tag_payload=self._post(TAG_DATA_URL,{"code_selectors":{"include":[{"type":"stock_code","values":[x["code"] for x in selected]}]},"tags":list(_TAG_KEYS)},{"Source-Id":"ths-hot-list"})
            for raw in self._array(tag_payload,"data","rows","list"):
                if not isinstance(raw,Mapping): continue
                values=raw.get("values",[]); found=[]
                if isinstance(values,list):
                    for item in values:
                        if isinstance(item,Mapping): found.extend(self._strings(item.get("show_tag")))
                tags[str(raw.get("code"))]=list(dict.fromkeys(found))
        except Exception: partial=True
        rows=[]
        for rank,metric in enumerate(selected,1):
            metric_code=str(metric["code"])
            market,symbol=self._split_code(metric_code)
            pool_row=pool_by_code.get(metric_code) or pool_by_code.get(symbol) or {}
            source_market=market or self._text(pool_row.get("subMarket") or pool_row.get("market"))
            exchange=_ETF_EXCHANGES.get(source_market or "")
            unknown_market=bool(source_market and exchange is None)
            partial_details=[]
            if partial: partial_details.append("ETF tag enrichment request failed; returning ranked ETF metrics without tags.")
            if unknown_market: partial_details.append(f"ETF source market id {source_market!r} is unrecognized; exchange was omitted.")
            rows.append({"rank":rank,"symbol":symbol.zfill(6),"name":self._text(pool_row.get("etfName") or pool_row.get("name")) or symbol,
                "changePct":metric["changePct"],"heat":metric["heat"],"tags":tags.get(str(metric["code"]),tags.get(symbol,[])),"__partial":bool(partial_details),
                "__partial_detail":" ".join(partial_details) or None,
                "__instrument_exchange":exchange.value if exchange is not None else None,
                "__infer_instrument_exchange":not unknown_market})
        for row in rows:
            row["__source_url"] = FUND_SPECIFIC_URL
            row["__source_references"] = [
                {"providerId":self.provider_id,"sourceRecordId":"fund-pool-members","sourceUrl":FUND_POOL_URL},
                {"providerId":self.provider_id,"sourceRecordId":"fund-attention-metrics","sourceUrl":FUND_SPECIFIC_URL},
            ]
            if not partial:
                row["__source_references"].append({"providerId":self.provider_id,"sourceRecordId":"fund-tags","sourceUrl":TAG_DATA_URL})
        return self._rows(rows,f"etfs:{req.category}",source_url=FUND_SPECIFIC_URL)

    def _content(self, req: HotContentRequest) -> list[dict[str, object]]:
        if req.content_type=="topic":
            rows=[]; page=1; page_size=max(30,req.limit)
            while len(rows)<req.limit:
                payload=self._get(TOPIC_URL,{"page":page,"page_size":page_size}); raw_rows=self._array(payload,"data","topic_list","list","rows")
                if not raw_rows: break
                for raw in raw_rows:
                    if not isinstance(raw,Mapping): continue
                    info=raw.get("attach_info") if isinstance(raw.get("attach_info"),Mapping) else {}
                    related=[]
                    for stock in info.get("att_stock",[]) if isinstance(info.get("att_stock",[]),list) else []:
                        if isinstance(stock,Mapping) and self._text(stock.get("code")):
                            related.append({"symbol":self._text(stock.get("code")).zfill(6),"name":self._text(stock.get("name")) or "","changePct":self._decimal(stock.get("rise_and_fall"))})
                    title=self._text(raw.get("title"))
                    if title: rows.append({"contentType":"topic","rank":len(rows)+1,"title":title,"summary":self._text(raw.get("description")),"heat":self._decimal(raw.get("hot_value")),"url":self._url(raw.get("jump_url")),"relatedStocks":related,"__source_id":self._text(raw.get("code")) or f"topic:{len(rows)+1}"})
                    if len(rows)>=req.limit: break
                if len(raw_rows)<page_size: break
                page+=1
            return self._rows(rows,"content:topic",source_url=TOPIC_URL)
        if req.content_type=="comment":
            raw_rows=self._array(self._get(COMMENT_URL),"data","list","rows"); codes=[self._text(x.get("code")) for x in raw_rows if isinstance(x,Mapping) and self._text(x.get("code"))]
            details={}; partial=False
            try:
                if codes:
                    result=self._get(IWENCAI_URL,{"tag":"同花顺热榜_热评评论点赞","appName":"thsHotList","codes":",".join(codes)})
                    for item in self._nested_result(result):
                        if isinstance(item,Mapping): details[str(item.get("code"))]=item
            except Exception: partial=True
            rows=[]
            for pos,raw in enumerate(raw_rows,1):
                if not isinstance(raw,Mapping): continue
                code=self._text(raw.get("code"));
                if not code: continue
                detail=details.get(code,{})
                rows.append({"contentType":"comment","rank":self._int(raw.get("order")) or pos,"symbol":code.zfill(6),"name":self._text(raw.get("name")) or "","changePct":self._decimal(raw.get("rise_and_fall")),"heat":self._decimal(raw.get("hot")),"text":self._text(detail.get("content")),"likes":self._int(detail.get("agreenum")),"contentId":self._text(detail.get("pid")),"__source_id":f"comment:{code}","__partial":partial})
            rows.sort(key=lambda x:int(x["rank"]))
            for row in rows: row["__source_url"] = COMMENT_URL
            if not partial:
                for row in rows: row["__source_references"] = [{"providerId":self.provider_id,"sourceRecordId":"comment-details","sourceUrl":IWENCAI_URL}]
            return self._rows(rows[:req.limit],"content:comment",source_url=COMMENT_URL)
        raw_rows=self._nested_result(self._get(IWENCAI_URL,{"tag":"同花顺热榜_新热文","appName":"thsHotList"}))
        ranked=[]
        for pos,raw in enumerate(raw_rows,1):
            if not isinstance(raw,Mapping): continue
            source_rank=self._int(raw.get("rank")) or pos; related=[]
            for stock in raw.get("stockInfo",[]) if isinstance(raw.get("stockInfo",[]),list) else []:
                if isinstance(stock,Mapping) and (symbol:=self._text(stock.get("stockCode"))):
                    related.append({"symbol":symbol,"sourceMarket":self._text(stock.get("stockMarket")),"name":self._text(stock.get("stockName")) or "","changePct":self._decimal(stock.get("stockZdf"))})
            urls=raw.get("contentUrl"); url=self._text(urls[0]) if isinstance(urls,list) and urls else self._text(urls)
            title=self._text(raw.get("title"))
            if title: ranked.append((source_rank,pos,raw,related,url,title))
        ranked.sort(key=lambda x:(x[0],x[1])); rows=[]
        for rank,(source_rank,_,raw,related,url,title) in enumerate(ranked[:req.limit],1):
            # The source labels these values as ratios but its unit convention
            # could not be verified. Do not put ambiguous values in Percentage.
            rows.append({"contentType":"article","rank":rank,"title":title,"heat":self._decimal(raw.get("score")),"likeRatio":None,"commentRatio":None,"contentId":self._text(raw.get("newsId")),"url":url,"relatedStocks":related,"__source_id":self._text(raw.get("newsId")) or f"article:{source_rank}","__partial":True,"__partial_detail":"Source like/comment ratio units are unverified; values were omitted."})
        return self._rows(rows,"content:article",source_url=IWENCAI_URL)

    def _pool_rows(self,payload:object)->list[Mapping[str,object]]:
        data=payload.get("data",payload) if isinstance(payload,Mapping) else None
        if not isinstance(data,Mapping): return []
        indexes=data.get("indexes",[]); rows=data.get("itemList",[])
        mapping={str(x.get("type")):i for i,x in enumerate(indexes) if isinstance(x,Mapping) and x.get("type")} if isinstance(indexes,list) else {}
        return [{k:r[i] for k,i in mapping.items() if i<len(r)} for r in rows if isinstance(r,list)] if isinstance(rows,list) else []
    def _recommendations(self,payload:object,input_codes:Sequence[str])->list[dict[str,object]]:
        found=[]
        known=set(input_codes)
        known_codes={code.rsplit(":",1)[-1] for code in input_codes}
        def visit(value:object,parent_key:str|None=None)->None:
            if isinstance(value,Mapping):
                code=self._text(value.get("etfCode")); market=self._text(value.get("etfMarket"))
                if code:
                    source_code=self._text(value.get("sourceCode") or value.get("indexCode") or value.get("securityCode") or value.get("security_code"))
                    source_market=self._text(value.get("sourceMarket") or value.get("market_id") or value.get("marketId"))
                    returned_code=self._text(value.get("code"))
                    if source_code is None and returned_code and returned_code != code:
                        source_code=returned_code
                    index_key=f"{source_market}:{source_code}" if source_market and source_code else source_code
                    if index_key not in known and source_code in known_codes:
                        index_key=source_code
                    if index_key not in known and parent_key in known:
                        index_key=parent_key
                    found.append({"code":f"{market}:{code}" if market else code,"etfCode":code,"indexCode":index_key,
                                  "name":self._text(value.get("thsName") or value.get("etfName"))})
                else:
                    for key,child in value.items(): visit(child,str(key))
            elif isinstance(value,list):
                for child in value: visit(child)
        visit(payload)
        return found
    def _pool_code(self,row:Mapping[str,object])->str|None:
        code=self._text(row.get("tradeCode") or row.get("code")); market=self._text(row.get("subMarket") or row.get("market"))
        if not code:return None
        return code if ":" in code or not market else f"{market}:{code}"
    def _indexes(self,payload:object)->dict[int,str]:
        data=payload.get("data",payload) if isinstance(payload,Mapping) else None
        raw=data.get("indexes",[]) if isinstance(data,Mapping) else []
        if not isinstance(raw,list):return {}
        return {(self._int(x.get("idx")) if self._int(x.get("idx")) is not None else pos):str(x.get("index_id") or x.get("indexId") or x.get("type") or x.get("name")) for pos,x in enumerate(raw) if isinstance(x,Mapping) and (x.get("index_id") or x.get("indexId") or x.get("type") or x.get("name"))}
    def _values(self,row:Mapping[str,object],indexes:Mapping[int,str])->dict[str,object]:
        raw=row.get("values",[]); result={}
        if isinstance(raw,list):
            for pos,item in enumerate(raw):
                if isinstance(item,Mapping):
                    idx=self._int(item.get("idx")); key=indexes.get(idx if idx is not None else pos)
                    if key: result[key]=item.get("value")
                    elif item.get("index_id"): result[str(item["index_id"])]=item.get("value")
        return result
    def _nested_result(self,payload:object)->list[object]:
        answer=payload.get("answer",payload) if isinstance(payload,Mapping) else None
        components=answer.get("components",[]) if isinstance(answer,Mapping) else []
        if isinstance(components,list):
            direct_rows=[]
            for comp in components:
                data=comp.get("data",{}) if isinstance(comp,Mapping) else {}; datas=data.get("datas",[]) if isinstance(data,Mapping) else []
                for item in datas if isinstance(datas,list) else []:
                    if isinstance(item,Mapping):
                        result=item.get("result")
                        if isinstance(result,list):return result
                        if isinstance(result,Mapping):return list(result.values())
                        direct_rows.append(item)
            if direct_rows:return direct_rows
        return payload.get("data",[]) if isinstance(payload,Mapping) and isinstance(payload.get("data"),list) else []
    def _array(self,payload:object,*keys:str)->list[object]:
        current=payload
        for _ in range(4):
            if isinstance(current,list):return current
            if not isinstance(current,Mapping):return []
            for key in keys:
                if isinstance(current.get(key),list):return current[key]
            nxt=current.get("data")
            if nxt is current:break
            current=nxt
        return []
    def _rows(self,rows:Sequence[dict[str,object]],source_id:str,*,source_url:str)->list[dict[str,object]]:
        captured=self._clock()
        if captured.tzinfo is None or captured.utcoffset() is None:self._fail("capture clock returned a naive datetime")
        out=[]
        for pos,row in enumerate(rows,1):
            data={k:v for k,v in row.items() if not k.startswith("__")}; record=str(row.get("__source_id") or f"{source_id}:{pos}")
            metadata={"sourceRecordId":record,"recordId":f"{source_id}:{record}","capturedAt":captured,"partial":bool(row.get("__partial")),"partialDetail":row.get("__partial_detail"),"sourceUrl":row.get("__source_url") or source_url,"sourceReferences":row.get("__source_references",[])}
            if row.get("__instrument_exchange") is not None:
                metadata["instrumentExchange"]=row["__instrument_exchange"]
            if "__infer_instrument_exchange" in row:
                metadata["inferInstrumentExchange"]=row["__infer_instrument_exchange"]
            out.append({"data":data,"__finchx":metadata})
        return out
    def _get(self,url:str,query:Mapping[str,object]|None=None)->object:
        return self._request(url+("?"+urlencode(query) if query else ""),"GET")
    def _post(self,url:str,body:Mapping[str,object],extra:Mapping[str,str]|None=None)->object:
        return self._request(url,"POST",body,extra)
    def _request(self,url:str,method:str,body:Mapping[str,object]|None=None,extra:Mapping[str,str]|None=None)->object:
        headers=build_headers(referer="https://www.10jqka.com.cn/",extra={"Content-Type":"application/json",**(extra or {})})
        request=Request(url,data=json.dumps(dict(body),ensure_ascii=False).encode() if body is not None else None,headers=headers,method=method)
        try:
            response=self._open(request,timeout=DEFAULT_TIMEOUT_SECONDS)
            with response if hasattr(response,"__enter__") else _ResponseContext(response) as stream:
                status=getattr(stream,"status",None) or stream.getcode(); text=stream.read().decode("utf-8","replace")
        except HTTPError as exc:self._fail(f"THS returned {http_status_failure_reason(exc.code)}")
        except (URLError,TimeoutError,OSError) as exc:self._fail(f"THS transport failure: {type(exc).__name__}")
        if http_status_failure_reason(int(status)):self._fail(f"THS returned {http_status_failure_reason(int(status))}")
        if not text.strip():self._fail("THS returned an empty response body")
        match=_JSONP.fullmatch(text)
        if match:text=match.group(1)
        try:payload=json.loads(text,parse_float=Decimal)
        except (json.JSONDecodeError,ValueError) as exc:self._fail(f"THS malformed JSON ({type(exc).__name__})")
        if isinstance(payload,Mapping):
            source_code = payload.get("status_code", payload.get("code"))
            if source_code not in (None,0,"0",200,"200","success"):
                self._fail(f"THS source status_code={source_code!r}")
        return payload
    @staticmethod
    def _split_code(code:str)->tuple[str,str]:
        return tuple(code.rsplit(":",1)) if ":" in code else ("",code)
    @staticmethod
    def _decimal(value:object)->Decimal|None:
        if value is None or value in ("","-","--"):return None
        try:out=Decimal(str(value))
        except (InvalidOperation,ValueError):return None
        return out if out.is_finite() else None
    @staticmethod
    def _int(value:object)->int|None:
        if value is None or isinstance(value,bool) or value=="":return None
        try:return int(Decimal(str(value)))
        except (InvalidOperation,ValueError,TypeError):return None
    @staticmethod
    def _text(value:object)->str|None:
        if isinstance(value,str):return value.strip() or None
        if isinstance(value,(int,Decimal)):return str(value)
        return None
    @classmethod
    def _url(cls,value:object)->str|None:
        text=cls._text(value)
        return f"https:{text}" if text and text.startswith("//") else text
    @classmethod
    def _strings(cls,value:object)->list[str]:
        if isinstance(value,str):return [x.strip() for x in re.split(r"[,，|/、]",value) if x.strip()]
        if isinstance(value,list):return [x for v in value if (x:=cls._text(v))]
        return []
    @staticmethod
    def _datetime(value:object)->datetime|None:
        if isinstance(value,datetime):return value
        if not isinstance(value,str) or not value.strip():return None
        raw=value.strip().replace("Z","+00:00")
        for fmt in ("%Y-%m-%d %H:%M:%S","%Y/%m/%d %H:%M:%S"):
            try:return datetime.strptime(raw,fmt).replace(tzinfo=_SHANGHAI)
            except ValueError:pass
        try:
            parsed=datetime.fromisoformat(raw); return parsed if parsed.tzinfo else parsed.replace(tzinfo=_SHANGHAI)
        except ValueError:return None
    def _fail(self,message:str)->None:raise ProviderError(self.source,message)

class _ResponseContext:
    def __init__(self,response:Any)->None:self.response=response
    def __enter__(self)->Any:return self.response
    def __exit__(self,*_args:object)->None:
        close=getattr(self.response,"close",None)
        if callable(close):close()

__all__=["THSHotListProvider"]
