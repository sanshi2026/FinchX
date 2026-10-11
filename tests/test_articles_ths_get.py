"""同花顺单篇多路由、来源身份与缺失契约；公开源样本及针对性损坏测试。"""

import json
from pathlib import Path

import pytest

from finchx._common.errors import SourceError
from finchx.sources.tonghuashun import articles as source
from finchx.sources.tonghuashun._article_url import decode_encoded_seq, encode_news_seq

FIXTURES = Path(__file__).parent / "fixtures" / "articles_ths"
NEWS = "https://stock.10jqka.com.cn/20261008/c680459704.shtml"
LONG = "https://t.10jqka.com.cn/pid_700648219.shtml"
ENCODED = "https://news.10jqka.com.cn/mobile/news/article/v1/encoded/a0e38678246048836a5"
SHORT = "https://t.10jqka.com.cn/lgt/short_view/index.html?pid=701123319"
FIELDS = {"content_type", "title", "published_at", "source_time", "source_name", "author", "original_url", "content", "image_urls", "video_urls", "cover_url", "disclaimer", "related_entities"}


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def news():
    return json.loads(fixture("detail_news.json"))


def long():
    return json.loads(fixture("detail_long.json"))


def short():
    return json.loads(fixture("detail_short.json"))


def wire(monkeypatch, *values):
    iterator = iter(values)
    calls = []
    def read(url, *, timeout):
        calls.append((url, timeout))
        value = next(iterator)
        if isinstance(value, BaseException):
            raise value
        return json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value
    monkeypatch.setattr(source, "_read", read)
    return calls


@pytest.mark.parametrize("url", [NEWS, ENCODED, "http://news.10jqka.com.cn/20261008/c680459704.shtml?track=1#anchor", "https://fund.10jqka.com.cn/20261008/c680459704.shtml", "https://fe.10jqka.com.cn/20261008/c680459704.shtml", "https://goodsfu.10jqka.com.cn/20261008/c680459704.shtml", "https://invest.10jqka.com.cn/20261008/c680459704.shtml", "https://field.10jqka.com.cn/20261008/c680459704.shtml"])
def test_news_routes_same_id_business_fields_and_full_related_objects(monkeypatch, url):
    calls = wire(monkeypatch, news())
    result = source.ths_get(url, timeout=2.5)
    assert set(result) == FIELDS
    assert result["content_type"] == "news"
    assert result["published_at"] == "2026-10-08T10:20:40+08:00"
    assert result["source_time"] is None
    assert result["source_name"] == "财闻"
    assert result["author"] is None
    assert result["original_url"] == "https://www.caiwennews.com/article/1639346.shtml"
    assert "力王股份(920627.BJ)" in result["content"]
    assert result["image_urls"] == [] and result["video_urls"] == []
    assert len(result["related_entities"]) == 11
    assert {r["market"] for r in result["related_entities"]} == {"33", "151", "48", "49"}
    assert all(set(r) == {"code", "name", "market"} for r in result["related_entities"])
    assert calls == [(source._NEWS_API + "a0e38678246048836a5", 2.5)]


@pytest.mark.parametrize("url", [LONG, LONG.replace("/pid_", "/m/zhibo/pid_"), "https://t.10jqka.com.cn/m/post/articleShare/articleshare.html?pid=700648219", "https://t.10jqka.com.cn/lgt/share_page/articleShare.html?pid=700648219&type=circle", "https://t.10jqka.com.cn/lgt/share_page/articleShare.html?pid=700648219&amp;type=circle"])
def test_community_routes_preserve_yearless_time_and_missing_related(monkeypatch, url):
    calls = wire(monkeypatch, long())
    result = source.ths_get(url, timeout=4)
    assert set(result) == FIELDS
    assert result["content_type"] == "article"
    assert result["published_at"] is None
    assert result["source_time"] == "10-08 10:35"
    assert result["author"] == "每经ETF风向标"
    assert result["related_entities"] is None
    assert "截至10月8日10时17分" in result["content"]
    assert len(calls) == 1 and calls[0] == (source._SHARE_API + "700648219", 4)


def test_video_without_text_has_actual_media_and_source_cover(monkeypatch):
    calls = wire(monkeypatch, fixture("detail_video.json"))
    result = source.ths_get("https://t.10jqka.com.cn/m/zhibo/pid_699674777.shtml", timeout=3)
    assert result["content_type"] == "video" and result["content"] is None
    assert result["video_urls"][0].endswith(".mp4")
    assert result["cover_url"] == "http://u.thsi.cn/imgsrc/media/29ae2bfa774d9fdb1b096593d84ae528.png"
    assert result["published_at"] is None and result["source_time"] == "09-30 06:30"
    assert len(calls) == 1


@pytest.mark.parametrize("raw_time,expected,literal", [(None,None,None), ("今天 07:06",None,"今天 07:06"), ("54分钟前",None,"54分钟前"), ("2026-10-08 10:35","2026-10-08T10:35+08:00",None), ("2026-10-08 10:35:00","2026-10-08T10:35:00+08:00",None), ("2026-10-08T02:35:00Z","2026-10-08T10:35:00+08:00",None)])
def test_source_time_only_converts_explicit_complete_source_time(monkeypatch, raw_time, expected, literal):
    payload = long(); payload["result"]["data"]["post"]["time"] = raw_time
    wire(monkeypatch, payload)
    result = source.ths_get(LONG, timeout=3)
    assert (result["published_at"],result["source_time"]) == (expected,literal)


@pytest.mark.parametrize("raw_time", [True, 0, [], "2026-02-30 12:00", "2026-10-08 25:00", "2026-10-08 10:35:00.5", "10-32 12:00", "今天 25:00", "昨天 09:60"])
def test_invalid_known_source_time_fails(monkeypatch, raw_time):
    payload = long(); payload["result"]["data"]["post"]["time"] = raw_time
    wire(monkeypatch, payload)
    with pytest.raises(SourceError): source.ths_get(LONG, timeout=3)


@pytest.mark.parametrize("related", [None, []])
def test_related_null_and_empty_array_distinct(monkeypatch, related):
    payload = news(); payload["data"]["relatedModules"]["associatedStocks"] = related
    wire(monkeypatch, payload)
    assert source.ths_get(NEWS, timeout=3)["related_entities"] == related


def test_zero_timestamp_and_generic_market_zero_are_not_missing(monkeypatch):
    payload = news(); payload["data"]["article"]["ctime"] = 0
    payload["data"]["relatedModules"]["associatedStocks"] = [{"stockCode":"CL", "stockName":"原油", "marketId":0}]
    wire(monkeypatch, payload)
    result = source.ths_get(NEWS, timeout=3)
    assert result["published_at"] == "1970-01-01T08:00:00+08:00"
    assert result["related_entities"] == [{"code":"CL", "name":"原油", "market":"0"}]


def test_oversized_source_timestamp_is_source_error_without_fallback(monkeypatch):
    for value in (10**1000, -(10**1000)):
        payload=news();payload["data"]["article"]["ctime"]=value
        calls=wire(monkeypatch,payload)
        with pytest.raises(SourceError,match="时间戳无效"):
            source.ths_get(NEWS,timeout=3)
        assert len(calls)==1


@pytest.mark.parametrize("field,value", [("seq","680459705"),("encodedSeq","wrong"),("ctime",True),("ctime",float("nan")),("ctime",float("inf")),("ctime","1791426040"),("title",False),("content",[]),("author",23),("media",[]),("sourceUrl","javascript:alert(1)")])
def test_damaged_news_business_fields_fail_without_fallback(monkeypatch, field, value):
    payload = news(); payload["data"]["article"][field] = value
    calls=wire(monkeypatch,payload)
    with pytest.raises(SourceError): source.ths_get(NEWS,timeout=3)
    assert len(calls)==1


@pytest.mark.parametrize("where,value", [("status_code",False),("status_code",1),("data",[]),("modules",[]),("settings",False),("related",{}),("related",[{"stockCode":"CL","marketId":False}]),("related",[{"stockCode":"CL","marketId":"65","stockName":[]}])])
def test_damaged_news_status_and_structure_fail(monkeypatch, where, value):
    payload=news()
    if where in {"status_code","data"}: payload[where]=value
    elif where=="modules":payload["data"]["relatedModules"]=value
    elif where=="settings":payload["data"]["pageSettings"]=value
    else:payload["data"]["relatedModules"]["associatedStocks"]=value
    calls=wire(monkeypatch,payload)
    with pytest.raises(SourceError):source.ths_get(NEWS,timeout=3)
    assert len(calls)==1


@pytest.mark.parametrize("field,value", [("hotKey","group_post_700648219"),("hotKey","sns_post_700648220"),("content",False),("hasVideo",True),("hasVideo",2),("video",[]),("videoCover","data:image/png;base64,AAAA")])
def test_damaged_community_response_fails(monkeypatch, field, value):
    payload=long();payload["result"]["data"]["post"][field]=value
    calls=wire(monkeypatch,payload)
    with pytest.raises(SourceError):source.ths_get(LONG,timeout=3)
    assert len(calls)==1


def test_image_only_body_is_valid_and_never_downloads_images(monkeypatch):
    payload=news();payload["data"]["article"]["content"]='<p><img src="http://u.thsi.cn/imgsrc/news/long-image.jpg"></p>'
    payload["data"]["article"]["title"]=None
    calls=wire(monkeypatch,payload)
    result=source.ths_get(NEWS,timeout=3)
    assert result["title"] is None and result["content"] is None
    assert result["image_urls"]==["http://u.thsi.cn/imgsrc/news/long-image.jpg"] and len(calls)==1


def test_body_paragraph_table_and_source_risk_text_preserved_not_widgets(monkeypatch):
    payload=news();payload["data"]["article"]["content"]='<p>第一段 &amp; 第二段</p><table><tr><td>科目</td><td>0</td></tr></table><script>secret()</script><div class="recommend">推荐广告</div><p>风险提示：来源正文中的风险说明。</p>'
    wire(monkeypatch,payload);result=source.ths_get(NEWS,timeout=3)
    assert "第一段 & 第二段" in result["content"] and "科目 | 0" in result["content"]
    assert "来源正文中的风险说明" in result["content"]
    assert "secret" not in result["content"] and "推荐广告" not in result["content"]


@pytest.mark.parametrize("url,name,title", [("https://mams.10jqka.com.cn/new/server/html/112940.html?injectAdaptive=true","detail_mams.html","国庆假期，两大重磅数据来袭！"),("https://news.10jqka.com.cn/deep-topic/topic/dt_01M3QZJ7BMT2BRZXP301DK9A1H","detail_deep.html","特朗普大开绿灯：AI监管不立法只执法，美政府成第一大客户")])
def test_real_public_topic_templates_do_not_invent_publication_date(monkeypatch,url,name,title):
    calls=wire(monkeypatch,fixture(name));result=source.ths_get(url,timeout=3)
    assert set(result)==FIELDS and result["content_type"]=="topic" and result["title"]==title
    assert result["published_at"] is None and result["source_time"] is None
    assert len(result["content"])>1000 and len(calls)==1
    assert "window." not in result["content"] and "activityId" not in result["content"]


def test_mams_identity_and_component_damage_fail(monkeypatch):
    raw=fixture("detail_mams.html").replace("activityId = 112940", "activityId = 112941")
    wire(monkeypatch,raw)
    with pytest.raises(SourceError,match="身份"):source.ths_get("https://mams.10jqka.com.cn/new/server/html/112940.html",timeout=3)


def test_valid_same_id_html_fallback_does_not_mix_api_fields(monkeypatch):
    markup='<html><head><link rel="canonical" href="'+NEWS+'"><meta name="author" content="正文作者"></head><body><h1>网页来源标题</h1><div class="publish-time">2026-10-08 10:21</div><div class="news-content article-content"><p>网页正文</p><img src="https://u.thsi.cn/imgsrc/news/pic.png"></div><div class="recommend">不能混入</div></body></html>'
    calls=wire(monkeypatch,source._ReadError("HTTP404",fallback=True),markup)
    result=source.ths_get(NEWS,timeout=3)
    assert result["title"]=="网页来源标题" and result["author"]=="正文作者"
    assert result["related_entities"] is None and result["source_name"] is None
    assert result["published_at"]=="2026-10-08T10:21+08:00"
    assert "不能混入" not in result["content"] and len(calls)==2


def test_html_embedded_news_state_preserves_same_source_fields(monkeypatch):
    raw=news()["data"]
    markup='<script>window.__PAGE_DATA__ = '+json.dumps({"__NEWS_DETAIL_DATA__":{"detailData":raw}},ensure_ascii=False)+';</script>'
    wire(monkeypatch,source._ReadError("HTTP404",fallback=True),markup)
    assert source.ths_get(NEWS,timeout=3)["published_at"]=="2026-10-08T10:20:40+08:00"


@pytest.mark.parametrize("denied",["401","403","429"])
def test_denied_public_api_never_tries_other_full_text(monkeypatch,denied):
    calls=wire(monkeypatch,source._ReadError(denied))
    with pytest.raises(SourceError):source.ths_get(NEWS,timeout=3)
    assert len(calls)==1


def test_missing_body_is_failure_not_empty_success_or_other_article(monkeypatch):
    payload=news();payload["data"]["article"]["content"]=""
    calls=wire(monkeypatch,payload)
    with pytest.raises(SourceError,match="正文"):source.ths_get(NEWS,timeout=3)
    assert len(calls)==1


def test_cross_identity_page_and_transport_rejected():
    for target in [NEWS.replace("680459704","680459705"),"https://evil.example/20261008/c680459704.shtml",NEWS.replace("stock.","news."),NEWS.replace("20261008","20261009")]:
        with pytest.raises(SourceError):source._transport_target(NEWS,target)
    with pytest.raises(SourceError):source._transport_target(source._SHARE_API+"700648219",source._SHARE_API+"700648220")
    with pytest.raises(SourceError):source._html_article('<link rel="canonical" href="'+NEWS.replace("680459704","680459705")+'"><div class="article-content">正文</div>',"680459704",NEWS)


@pytest.mark.parametrize("url", [None, "", " "+NEWS, NEWS+"\x7f",NEWS+"\n",NEWS+"\t",NEWS.replace("680459704","６８０４５９７０４"),"https://user:password@stock.10jqka.com.cn/20261008/c680459704.shtml","https://stock.10jqka.com.cn.evil.example/20261008/c680459704.shtml","https://mp.10jqka.com.cn/lgt/article_detail/index.html?contentId=esbiai5ny2buf5f6f1639","https://t.10jqka.com.cn/m/post/discussDetail/?pid=2173365374","https://t.10jqka.com.cn/lgt/share_page/articleShare.html?pid=700648219&pid=700648220","https://t.10jqka.com.cn/lgt/share_page/articleShare.html?pid=700648219&type=discussion","https://news.10jqka.com.cn/20260230/c680459704.shtml",ENCODED[:-1]+"1"])
def test_bad_public_url_rejected_before_network(monkeypatch,url):
    calls=wire(monkeypatch)
    with pytest.raises(ValueError):source.ths_get(url,timeout=3)
    assert calls==[]


def test_encoder_roundtrip_and_checksum():
    for seq in ["680459704","680499486","12345678901"]:
        assert decode_encoded_seq(encode_news_seq(seq))==seq
    with pytest.raises(ValueError):decode_encoded_seq("a0e38678246048836a1")


def test_repeated_calls_fetch_again(monkeypatch):
    calls=wire(monkeypatch,news(),news())
    first=source.ths_get(NEWS,timeout=3);second=source.ths_get(NEWS,timeout=3)
    assert first==second and first is not second and len(calls)==2


def test_json_declaration_lookalikes_in_prose_strings_and_comments_are_not_executed(monkeypatch):
    payload=news()["data"]
    payload["article"]["content"]='<p>原文说明：var activity = 和 __PAGE_DATA__ = 仅是文字。</p>'
    raw='<script>/* __PAGE_DATA__ = broken; var activity = broken; */\n// var activityId = 999;\nconst example = "__PAGE_DATA__ = bad"; window.__PAGE_DATA__ = '+json.dumps({"__NEWS_DETAIL_DATA__":{"detailData":payload}},ensure_ascii=False)+';</script>'
    wire(monkeypatch,source._ReadError("404",fallback=True),raw)
    result=source.ths_get(NEWS,timeout=3)
    assert "var activity =" in result["content"]


def test_mams_decoded_prose_can_contain_activity_and_activityid_declarations(monkeypatch):
    value={"page":{"components":[{"detail":{"name":"ai-html-component","text":"<p>正文 var activity = {文字}; var activityId = 999; __PAGE_DATA__ = 仅说明。</p>"}}]}}
    raw='<title>来源标题</title><script>/* var activity = bad; */ const example = "var activityId = 999;"; var activity = '+json.dumps(value,ensure_ascii=False)+'; var activityId = 112940;</script>'
    wire(monkeypatch,raw)
    result=source.ths_get("https://mams.10jqka.com.cn/new/server/html/112940.html",timeout=3)
    assert "var activityId = 999" in result["content"]


@pytest.mark.parametrize("extra", ['var activity = {"page":{"components":[]}};', 'var activityId = 112940;'])
def test_true_duplicate_mams_declarations_fail(monkeypatch,extra):
    value={"page":{"components":[{"detail":{"name":"ai-html-component","text":"<p>正文</p>"}}]}}
    raw='<script>var activity = '+json.dumps(value)+'; var activityId = 112940; '+extra+'</script>'
    wire(monkeypatch,raw)
    with pytest.raises(SourceError):source.ths_get("https://mams.10jqka.com.cn/new/server/html/112940.html",timeout=3)


def test_true_duplicate_embedded_state_declarations_fail(monkeypatch):
    statement='window.__PAGE_DATA__ = '+json.dumps({"__NEWS_DETAIL_DATA__":{"detailData":news()["data"]}})+';'
    wire(monkeypatch,source._ReadError("404",fallback=True),'<script>'+statement+statement+'</script>')
    with pytest.raises(SourceError,match="重复"):source.ths_get(NEWS,timeout=3)


def test_disjoint_html_bodies_fail_instead_of_arbitrary_first(monkeypatch):
    wire(monkeypatch,source._ReadError("404",fallback=True),'<h1>标题</h1><div class="article-content">第一主体</div><div class="news-content">第二主体</div>')
    with pytest.raises(SourceError,match="多个正文"):source.ths_get(NEWS,timeout=3)


def test_video_missing_content_has_empty_image_array(monkeypatch):
    payload=json.loads(fixture("detail_video.json"));payload["result"]["data"]["post"]["content"]=None
    wire(monkeypatch,payload)
    result=source.ths_get("https://t.10jqka.com.cn/pid_699674777.shtml",timeout=3)
    assert result["content"] is None and result["image_urls"]==[] and len(result["video_urls"])==1


def test_html_video_template_remains_valid_with_no_text_body(monkeypatch):
    raw='<html><body data-pid="699674777"><h1>来源视频标题</h1><div class="pc-video-con"><div class="pc-video-wrap"><div class="pc-video" data-videohref="https://media.example/actual.mp4"></div></div></div></body></html>'
    wire(monkeypatch,source._ReadError("404",fallback=True),raw)
    result=source.ths_get("https://t.10jqka.com.cn/pid_699674777.shtml",timeout=3)
    assert result["content_type"]=="video" and result["content"] is None
    assert result["video_urls"]==["https://media.example/actual.mp4"] and result["image_urls"]==[]


@pytest.mark.parametrize("field", ["shareCover", "videoCover", "video"])
def test_source_protocol_relative_business_media_objectively_use_https(monkeypatch,field):
    payload=long();post=payload["result"]["data"]["post"]
    post[field]="//e.thsi.cn/img/a5eae483bfbf09e5"
    if field=="video":post["hasVideo"]=1
    wire(monkeypatch,payload)
    result=source.ths_get(LONG,timeout=3)
    assert (result["video_urls"][0] if field=="video" else result["cover_url"])=="https://e.thsi.cn/img/a5eae483bfbf09e5"


def test_transport_checks_actual_final_url_and_does_not_send_cookies(monkeypatch):
    from email.message import Message
    calls=[]
    class Response:
        status=200
        headers=Message()
        def __enter__(self):return self
        def __exit__(self,*args):return None
        def geturl(self):return source._NEWS_API+"a0e38678246048836a5"
        def read(self,size):
            assert size==source._MAX_BYTES+1
            return b'{"status_code":0}'
    class Opener:
        def open(self,request,*,timeout):
            calls.append((request.full_url,request.headers,timeout))
            return Response()
    monkeypatch.setattr(source,"build_opener",lambda handler:Opener())
    assert source._read(source._NEWS_API+"a0e38678246048836a5",timeout=2)== '{"status_code":0}'
    assert len(calls)==1 and calls[0][2]==2
    assert not any(k.lower() in {"cookie","authorization"} for k in calls[0][1])
    monkeypatch.setattr(Response,"geturl",lambda self:source._NEWS_API+"different")
    with pytest.raises(SourceError,match="跳转"):source._read(source._NEWS_API+"a0e38678246048836a5",timeout=2)


@pytest.mark.parametrize("status,fallback", [(401,False),(403,False),(429,False),(404,True),(503,True)])
def test_transport_http_denial_vs_legal_fallback_classification(monkeypatch,status,fallback):
    from urllib.error import HTTPError
    class Opener:
        def open(self,request,*,timeout):raise HTTPError(request.full_url,status,"reason",{},None)
    monkeypatch.setattr(source,"build_opener",lambda handler:Opener())
    with pytest.raises(source._ReadError) as caught:source._read(source._NEWS_API+"a0e38678246048836a5",timeout=2)
    assert caught.value.fallback is fallback


def test_real_shortview_native_route_keeps_no_title_and_same_response_business(monkeypatch):
    calls=wire(monkeypatch,short())
    result=source.ths_get(SHORT,timeout=3)
    assert set(result)==FIELDS and result["content_type"]=="article"
    assert result["title"] is None  # share title/postTitle are derived display snippets.
    assert result["published_at"]=="2026-10-08T21:39:01+08:00" and result["source_time"] is None
    assert result["author"]=="大同证券徐强"
    assert result["source_name"] is None and result["original_url"] is None
    assert "国庆假期" in result["content"] and len(result["content"])>800
    assert result["image_urls"]==[] and result["video_urls"]==[] and result["cover_url"] is None
    assert result["disclaimer"].startswith("该内容由大同证券投资顾问提供")
    assert result["related_entities"]==[{"code":"603200","name":None,"market":"17"},{"code":"886032","name":None,"market":"48"},{"code":"300073","name":None,"market":"33"}]
    assert calls==[(source._SHORT_API+"701123319",3)]


def test_real_shortview_company_query_link_preserves_body_without_inventing_security(monkeypatch):
    payload=json.loads(fixture("detail_short_kuaicha.json"))
    calls=wire(monkeypatch,payload)
    result=source.ths_get(SHORT.replace("701123319","701111283"),timeout=3)
    assert set(result)==FIELDS and result["content_type"]=="article"
    assert result["title"] is None
    assert result["published_at"]=="2026-10-08T20:18:42+08:00"
    assert result["source_time"] is None
    assert "华为将联合江淮重新测评" in result["content"]
    assert "华为与江淮汽车联合打造" in result["content"]
    assert result["related_entities"]==[{"code":"600418","name":None,"market":"17"}]
    assert result["image_urls"]==[] and result["video_urls"]==[]
    assert calls==[(source._SHORT_API+"701111283",3)]


@pytest.mark.parametrize("identity", [
    'data-code=""', 'data-code="600418"', 'data-marketid=""', 'data-marketid="17"',
    'data-hx-tag="stock"', 'data-hx-tag="stock" data-code="600418"',
])
def test_company_marker_cannot_hide_incomplete_security_identity(monkeypatch,identity):
    payload=short()
    payload["result"]["contentData"]["content"]='<a class="_dollar_" data-type="kuaicha" '+identity+' href="https://kuaicha.10jqka.com.cn/yuqingwebapp/yuqingapp/#/companyDetail?id=T000155271">华为</a>'
    calls=wire(monkeypatch,payload)
    with pytest.raises(SourceError,match="缺少必要来源身份"):
        source.ths_get(SHORT,timeout=3)
    assert len(calls)==1


@pytest.mark.parametrize("attributes", [
    'data-code="600418"', 'data-marketid="17"', 'data-hx-tag="stock"',
])
def test_partial_structured_security_still_fails(monkeypatch,attributes):
    payload=short()
    payload["result"]["contentData"]["content"]='<a '+attributes+'>来源标签</a>'
    wire(monkeypatch,payload)
    with pytest.raises(SourceError,match="缺少必要来源身份"):
        source.ths_get(SHORT,timeout=3)


@pytest.mark.parametrize("attributes", [
    'class="_dollar_"', 'class="_dollar_" data-type="unknown"',
    'class="_dollar_" data-type="topic" href="/unknown-topic?id=opaque"',
    'class="_dollar_" data-type="kuaicha" href="javascript:unused"',
    'href="https://other.example/display#opaque"',
])
def test_display_link_preserves_text_without_inventing_security_or_reading_target(monkeypatch,attributes):
    payload=short()
    payload["result"]["contentData"]["content"]='<a '+attributes+'>来源标签</a>'
    calls=wire(monkeypatch,payload)
    result=source.ths_get(SHORT,timeout=3)
    assert result["content"]=="来源标签" and result["related_entities"] is None
    assert calls==[(source._SHORT_API+"701123319",3)]


@pytest.mark.parametrize("href", [
    'https://other.example/yuqingwebapp/yuqingapp/#/companyDetail?id=T000155271',
    'https://kuaicha.10jqka.com.cn/unknown/#/companyDetail?id=T000155271',
    'https://kuaicha.10jqka.com.cn/yuqingwebapp/yuqingapp/#/unknown?id=T000155271',
    'https://kuaicha.10jqka.com.cn/yuqingwebapp/yuqingapp/#/companyDetail',
    'https://kuaicha.10jqka.com.cn/yuqingwebapp/yuqingapp/#/companyDetail?id=T1&id=T2',
    'https://kuaicha.10jqka.com.cn/yuqingwebapp/yuqingapp/#/companyDetail?id=600418',
])
def test_company_query_target_is_not_needed_to_read_body(monkeypatch,href):
    payload=short()
    payload["result"]["contentData"]["content"]='<a class="_dollar_" data-type="kuaicha" href="'+href+'">企业</a>'
    calls=wire(monkeypatch,payload)
    result=source.ths_get(SHORT,timeout=3)
    assert result["content"]=="企业" and result["related_entities"] is None
    assert calls==[(source._SHORT_API+"701123319",3)]


def test_real_company_query_with_opaque_q_identity_keeps_all_structured_entities(monkeypatch):
    payload=json.loads(fixture("detail_short_kuaicha_q.json"))
    calls=wire(monkeypatch,payload)
    result=source.ths_get(SHORT.replace("701123319","701116596"),timeout=3)
    assert set(result)==FIELDS and result["title"] is None
    assert "三星SDI" in result["content"]
    assert result["related_entities"]==[
        {"code":code,"name":None,"market":market} for code,market in [
            ("886032","48"),("886069","48"),("850101","64"),("603200","17"),
            ("688778","17"),("300073","33"),("002882","33"),("603663","17"),
            ("301662","33"),("920522","151"),("920284","151"),("688155","17"),
            ("300033","33"),("601519","17"),
        ]
    ]
    assert calls==[(source._SHORT_API+"701116596",3)]


def test_company_marker_with_complete_security_identity_keeps_actual_business(monkeypatch):
    payload=short()
    payload["result"]["contentData"]["content"]='<a class="_dollar_" data-type="kuaicha" data-code="STLA" data-marketid="169">显示标签不当名称</a>'
    wire(monkeypatch,payload)
    assert source.ths_get(SHORT,timeout=3)["related_entities"]==[{"code":"STLA","name":None,"market":"169"}]


def test_display_style_does_not_change_explicit_security_identity(monkeypatch):
    payload=short()
    payload["result"]["contentData"]["content"]='<p><a data-type="unknown" data-code="600418" data-marketid="17">来源证券</a><a class="_dollar_" data-code="STLA" data-marketid="169">海外证券</a></p>'
    wire(monkeypatch,payload)
    assert source.ths_get(SHORT,timeout=3)["related_entities"]==[
        {"code":"600418","name":None,"market":"17"},{"code":"STLA","name":None,"market":"169"},
    ]


@pytest.mark.parametrize("stamp",[0,None])
def test_shortview_zero_timestamp_distinct_from_missing_and_literal_time(monkeypatch,stamp):
    payload=short();payload["result"]["contentData"]["postTimestamp"]=stamp
    wire(monkeypatch,payload);result=source.ths_get(SHORT,timeout=3)
    assert result["published_at"]==("1970-01-01T08:00:00+08:00" if stamp==0 else None)
    assert result["source_time"]==(None if stamp==0 else "10-08 21:39")


def test_shortview_optional_title_author_disclaimer_and_time_missing_stay_missing(monkeypatch):
    payload=short();r=payload["result"]
    r["dataPack"]["contentInfo"].pop("title")
    r["contentData"].pop("postTimestamp");r["contentData"].pop("time")
    r["modules"][0]["data"].pop("name")
    r["modules"]=[r["modules"][0]]
    wire(monkeypatch,payload);result=source.ths_get(SHORT,timeout=3)
    assert all(result[k] is None for k in ("title","author","disclaimer","published_at","source_time"))


@pytest.mark.parametrize("field,value", [("postTimestamp",True),("postTimestamp","1791466741"),("postTimestamp",float("nan")),("postTimestamp",10**1000),("time",False),("content",{}),("imgs",False),("imgs",[None]),("isHasVideo",True),("isHasVideo",2),("videoSrc",{}),("videoCover","javascript:alert(1)")])
def test_shortview_known_business_damage_fails_without_long_share_fallback(monkeypatch,field,value):
    payload=short();payload["result"]["contentData"][field]=value
    calls=wire(monkeypatch,payload)
    with pytest.raises(SourceError):source.ths_get(SHORT,timeout=3)
    assert len(calls)==1


@pytest.mark.parametrize("where,value", [("status",False),("status",1),("type",2),("type",True),("id",701123320),("pid",701123320),("pid",True),("hotKey","sns_post_701123320"),("creativeHotKey","sns_post_701123320"),("title",[]),("author",False),("modules",{}),("modules",[])])
def test_shortview_identity_status_and_necessary_structure_damage_fail(monkeypatch,where,value):
    payload=short();r=payload["result"]
    if where=="status":payload["errorCode"]=value
    elif where in ("type","id"):r["tagObj"][where]=value
    elif where in ("pid","title"):r["dataPack"]["contentInfo"][where]=value
    elif where=="hotKey":r["contentData"]["hotKey"]=value
    elif where=="creativeHotKey":r["modules"][0]["data"]["hotKey"]=value
    elif where=="author":r["modules"][0]["data"]["name"]=value
    else:r["modules"]=value
    calls=wire(monkeypatch,payload)
    with pytest.raises(SourceError):source.ths_get(SHORT,timeout=3)
    assert len(calls)==1


def test_shortview_deduplicates_structured_entities_only_and_ignores_recommendations(monkeypatch):
    payload=short();r=payload["result"]
    r["contentData"]["content"]='<p><a class="_dollar_" data-code="NVDA" data-marketid="185" data-name="英伟达">显示文字不当名称</a></p><p><a class="_dollar_" data-code="NVDA" data-marketid="185" data-name="新名称">再次提到</a></p><div class="recommend"><a class="_dollar_" data-code="AAPL" data-marketid="185">广告</a></div>'
    r["tagObj"]["code"]=["无关标签码"]
    r["modules"].append({"name":"recommend_read","data":[{"stockCode":"AAPL"}]})
    wire(monkeypatch,payload);result=source.ths_get(SHORT,timeout=3)
    assert result["related_entities"]==[{"code":"NVDA","name":"英伟达","market":"185"}]
    assert "广告" not in result["content"]


@pytest.mark.parametrize("value",[None,[]])
def test_shortview_explicit_associated_array_precedes_body_and_null_is_not_empty(monkeypatch,value):
    payload=short();payload["result"]["relatedModules"]={"associatedStocks":value}
    wire(monkeypatch,payload)
    assert source.ths_get(SHORT,timeout=3)["related_entities"]==value


def test_shortview_image_only_media_is_valid_without_title_or_extra_request(monkeypatch):
    payload=short();d=payload["result"]["contentData"]
    d["content"]=None;d["imgs"]=["//u.thsi.cn/imgsrc/news/source.jpg"]
    calls=wire(monkeypatch,payload);result=source.ths_get(SHORT,timeout=3)
    assert result["content"] is None and result["title"] is None
    assert result["image_urls"]==["https://u.thsi.cn/imgsrc/news/source.jpg"] and len(calls)==1


@pytest.mark.parametrize("url",[SHORT.replace("pid=701123319","contentId=esoi3e6gpewiqcf47afbb"),SHORT+"&contentId=esoi3e6gpewiqcf47afbb",SHORT+"&pid=701123320",SHORT.replace("701123319","７０１１２３３１９"),SHORT.replace("https:","http:")])
def test_shortview_opaque_or_ambiguous_identity_rejected_before_request(monkeypatch,url):
    calls=wire(monkeypatch)
    with pytest.raises(ValueError):source.ths_get(url,timeout=3)
    assert calls==[]


def test_shortview_api_cannot_redirect_to_long_share_or_other_pid():
    with pytest.raises(SourceError):source._transport_target(source._SHORT_API+"701123319",source._SHORT_API+"701123320")
    with pytest.raises(SourceError):source._transport_target(source._SHORT_API+"701123319",source._SHARE_API+"701123319")
