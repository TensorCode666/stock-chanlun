"""
股票数据服务 - 使用腾讯财经 API 直接获取数据
"""
import warnings
warnings.filterwarnings("ignore", message="Unverified HTTPS request")
import logging
import threading
import pandas as pd
import json
import re
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx

from utils import with_retry

log = logging.getLogger(__name__)

# 创建 HTTP 客户端（带重试机制的同步客户端）
_http_client: httpx.Client | None = None
_http_client_lock = threading.RLock()


def _get_client() -> httpx.Client:
    """获取或创建 HTTP 客户端（禁用代理，直连，共享连接池）"""
    global _http_client
    with _http_client_lock:
        if _http_client is None:
            limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
            _http_client = httpx.Client(
                timeout=30.0,
                follow_redirects=True,
                trust_env=False,
                limits=limits,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': 'https://finance.qq.com/',
                    'Accept': '*/*',
                }
            )
        return _http_client


def get_stock_news(limit: int = 10) -> list:
    """
    获取财经新闻列表，按优先级尝试：东方财富快讯 → 同花顺 → 东方财富资讯。
    返回 [{ title, time, url, source, digest }]。
    """
    cache_key = f"stock_news:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # ① 东方财富实时快讯（最及时）
    news = _fetch_em_breaking_news(limit)
    if news:
        _cache_set(cache_key, news, ttl=300)
        log.info("东方财富快讯获取成功 count=%s", len(news))
        return news

    # ② 同花顺行业/市场新闻
    news = _fetch_ths_news(limit)
    if news:
        _cache_set(cache_key, news, ttl=300)
        log.info("同花顺新闻获取成功 count=%s", len(news))
        return news

    # ③ 东方财富资讯列表兜底
    news = _fetch_em_article_news(limit)
    if news:
        _cache_set(cache_key, news, ttl=300)
        log.info("东方财富资讯获取成功 count=%s", len(news))
        return news

    log.warning("新闻所有来源均获取失败")
    return []


def _fetch_em_breaking_news(limit: int) -> list:
    """东方财富实时快讯 API"""
    try:
        client = _get_client()
        url = (
            "https://np-anotice-stock.eastmoney.com/api/security/ann"
            f"?sr=-1&page_size={limit}&page_index=1"
            "&ann_type=A&client_source=web"
            "&fields=title,notice_date,art_code,source"
        )
        resp = client.get(url, timeout=10, headers={"Referer": "https://data.eastmoney.com/"})
        js = resp.json()
        items = (js.get("data") or {}).get("list") or []
        news = []
        for item in items:
            title = str(item.get("title", "") or "").strip()
            if not title:
                continue
            news.append({
                "title": title,
                "time": str(item.get("notice_date", "") or "")[:16],
                "source": "东方财富",
                "url": f"https://data.eastmoney.com/notices/{item.get('art_code', '')}.html",
                "digest": "",
            })
        return news
    except Exception:
        log.exception("东方财富快讯获取失败")
        return []


def _fetch_ths_news(limit: int) -> list:
    """同花顺财经快讯"""
    try:
        client = _get_client()
        url = (
            "https://news.10jqka.com.cn/tapp/news/push/stock/"
            f"?page=1&tag=&track=website&pagesize={limit}"
        )
        resp = client.get(url, timeout=10, headers={"Referer": "https://www.10jqka.com.cn/"})
        js = resp.json()
        items = (js.get("data") or {}).get("list") or []
        news = []
        for item in items:
            title = str(item.get("title", "") or "").strip()
            if not title:
                continue
            news.append({
                "title": title,
                "time": str(item.get("time", "") or "")[:16],
                "source": str(item.get("from", "") or "同花顺").strip() or "同花顺",
                "url": str(item.get("url", "") or ""),
                "digest": str(item.get("summary", "") or "").strip()[:120],
            })
        return news
    except Exception:
        log.exception("同花顺新闻获取失败")
        return []


def _fetch_em_article_news(limit: int) -> list:
    """东方财富资讯列表（兜底）"""
    try:
        client = _get_client()
        url = (
            "https://np-listapi.eastmoney.com/comm/web/getNormalListByConditions"
            "?client=web&biz=web_home_article"
            "&category=gc-推-7"
            f"&page=1&pageSize={limit}"
            "&order=0&orderBy=1"
            "&fields=Title,ShowTime,DocAbstract,Url,Source"
            "&debutType=1"
        )
        resp = client.get(url, timeout=15, headers={"Referer": "https://www.eastmoney.com/"})
        js = resp.json()
        items = (js.get("data") or {}).get("list") or []
        news = []
        for item in items:
            title = str(item.get("Title", "") or "").strip()
            if not title:
                continue
            news.append({
                "title": title,
                "time": str(item.get("ShowTime", "") or ""),
                "source": str(item.get("Source", "") or "").strip() or "东方财富",
                "url": str(item.get("Url", "") or ""),
                "digest": str(item.get("DocAbstract", "") or "").strip()[:120],
            })
        return news
    except Exception:
        log.exception("东方财富资讯兜底获取失败")
        return []


# 简单的内存缓存（LRU，避免热 key 被 FIFO 误驱逐）
from collections import OrderedDict

_cache: OrderedDict[str, tuple] = OrderedDict()
_CACHE_MAX_ENTRIES = 512
_cache_lock = threading.RLock()


def _cache_get(key: str):
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        data, timestamp, ttl = entry
        if datetime.now().timestamp() - timestamp < ttl:
            _cache.move_to_end(key)
            return data
        _cache.pop(key, None)
        return None


def _cache_set(key: str, data, ttl: int = 60):
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
        elif len(_cache) >= _CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)
        _cache[key] = (data, datetime.now().timestamp(), ttl)


def normalize_stock_code(code: str) -> tuple[str, str]:
    """规范化股票代码，返回 (market_code, exchange)
       sz=深圳, sh=上海
    """
    code = code.strip().zfill(6)
    if code.startswith(('00', '30', '002', '003')):
        return code, "sz"
    elif code.startswith(('60', '68', '500', '501')):
        return code, "sh"
    elif code.startswith('8') or code.startswith('4'):
        return code, "bj"
    return code, "sz"


def _get_qq_market_code(code: str) -> str:
    """获取腾讯API的市场前缀"""
    code = code.strip().zfill(6)
    if code.startswith(('00', '30', '002', '003')):
        return "sz"  # 深圳
    elif code.startswith(('60', '68', '500', '501')):
        return "sh"  # 上海
    elif code.startswith('8') or code.startswith('4'):
        return "bj"  # 北交所
    return "sz"


def get_realtime_quote(codes: list[str]) -> pd.DataFrame:
    """获取实时行情，分批并发拉取（腾讯 API 单 URL 约 150 只为上限）。"""
    if not codes:
        return pd.DataFrame()

    cache_key = f"realtime:{','.join(sorted(codes))}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # 腾讯 API 单次请求上限约 150 只，分批并发
    BATCH = 150

    def _fetch_batch(batch: list[str]) -> list[dict]:
        qq_codes = []
        for code in batch:
            sym, _ = normalize_stock_code(code)
            mkt = _get_qq_market_code(code)
            qq_codes.append(f"{mkt}{sym}")
        url = f"https://qt.gtimg.cn/q={','.join(qq_codes)}"
        try:
            client = _get_client()
            resp = client.get(url, timeout=10)
            records = []
            lines = resp.text.strip().split('\n')
            for i, line in enumerate(lines):
                if not line or '=' not in line:
                    continue
                match = re.search(r'v_\w+="(.+)"', line)
                if not match:
                    continue
                data = match.group(1).split('~')
                if len(data) < 38:
                    continue
                try:
                    stock_code = batch[i] if i < len(batch) else data[2]
                    records.append({
                        "代码": data[2] if len(data) > 2 else stock_code,
                        "名称": data[1] if len(data) > 1 else "",
                        "最新价": float(data[3]) if data[3] else 0,
                        "涨跌幅": float(data[32]) if len(data) > 32 and data[32] else 0,
                        "成交量": float(data[6]) if data[6] else 0,
                        "成交额": float(data[37]) if len(data) > 37 and data[37] else 0,
                        "今开": float(data[4]) if data[4] else 0,
                        "最高": float(data[33]) if len(data) > 33 and data[33] else 0,
                        "最低": float(data[34]) if len(data) > 34 and data[34] else 0,
                        "昨收": float(data[5]) if data[5] else 0,
                    })
                except (ValueError, IndexError):
                    continue
            return records
        except Exception as e:
            log.warning(f"[行情] 批次拉取失败: {e}")
            return []

    # 并发分批
    batches = [codes[i:i + BATCH] for i in range(0, len(codes), BATCH)]
    workers = min(len(batches), 10)
    all_records: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for records in pool.map(_fetch_batch, batches):
            all_records.extend(records)

    df = pd.DataFrame(all_records)
    if not df.empty:
        _cache_set(cache_key, df, ttl=60)
    return df


def get_kline_hist(
    code: str,
    period: str = "daily",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    adjust: str = "qfq",
    limit: int = 500,
) -> pd.DataFrame:
    """
    获取历史K线数据
    period: daily/weekly/monthly/5/15/30/60 分钟
    adjust: qfq=前复权 hfq=后复权 None=不复权
    limit: 最多返回根数（与缠论/图表窗口对齐，纳入缓存键）
    """
    limit = max(20, min(int(limit), 2000))
    cache_key = f"kline:{code}:{period}:{adjust}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    sym, _ = normalize_stock_code(code)
    mkt = _get_qq_market_code(code)

    # 分钟数据使用新浪API
    minute_periods = ["5", "15", "30", "60"]
    if period in minute_periods:
        df = _get_minute_data_sina(sym, mkt, period, adjust)
        if not df.empty:
            _cache_set(cache_key, df, ttl=60)  # 分钟数据缓存60秒
        return df

    # 日/周/月数据使用腾讯API
    period_map = {
        "daily": "day",
        "weekly": "week",
        "monthly": "month",
    }
    period_qq = period_map.get(period, "day")

    # 复权处理
    if adjust == "qfq":
        adjust_suffix = "qfq"
    elif adjust == "hfq":
        adjust_suffix = "hfq"
    else:
        adjust_suffix = ""

    # 默认获取 limit 条数据（腾讯 API 单次上限约 2000）
    fetch_limit = limit

    try:
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline_{period_qq}{adjust_suffix}&param={mkt}{sym},{period_qq},,,{fetch_limit},{adjust_suffix}"
        client = _get_client()
        resp = client.get(url)
        text = resp.text

        # 解析返回数据: kline_dayqfq={...}
        json_match = re.search(r'=({.+})', text)
        if not json_match:
            return pd.DataFrame()

        data = json.loads(json_match.group(1))
        key = f"{mkt}{sym}"

        if key not in data.get("data", {}):
            return pd.DataFrame()

        # 获取数据 - 注意腾讯API返回的key格式可能是 "qfqweek" 而不是 "weekqfq"
        data_key = f"{period_qq}{adjust_suffix}" if adjust_suffix else period_qq
        klines = data["data"][key].get(data_key, [])

        if not klines:
            # 尝试其他可能的key格式
            for k in [f"qfq{period_qq}", f"{period_qq}qfq", period_qq, "day", "qfqday", "hfqday", "dayhfq"]:
                if k in data["data"][key]:
                    klines = data["data"][key][k]
                    break

        if not klines:
            return pd.DataFrame()

        records = []
        for kl in klines:
            if len(kl) >= 6:
                try:
                    records.append({
                        "date": kl[0],
                        "open": float(kl[1]),
                        "close": float(kl[2]),
                        "high": float(kl[3]),
                        "low": float(kl[4]),
                        "volume": float(kl[5]),
                    })
                except (ValueError, IndexError):
                    continue

        df = pd.DataFrame(records)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            if len(df) > limit:
                df = df.tail(limit).reset_index(drop=True)
            # 分钟数据缓存 30 秒（盘中波动大）；日线缓存 5 分钟
            _cache_set(cache_key, df, ttl=30 if period in minute_periods else 300)
        return df
    except Exception as e:
        log.warning(f"K线获取失败 {code} {period}: {e}")
        return pd.DataFrame()


def get_index_quote(index_code: str = "000001") -> dict:
    """获取指数实时行情"""
    cache_key = f"index:{index_code}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        index_map = {
            "000001": "sh000001",
            "399001": "sz399001",
            "399006": "sz399006",
            "000688": "sh000688",
            "399300": "sz399300",  # 沪深300
            "000016": "sh000016",   # 上证50
            "000905": "sh000905",   # 中证500
            "000852": "sh000852",   # 中证1000
            "399303": "sz399303",   # 国证2000（部分行情源）
        }
        qq_code = index_map.get(index_code, f"sh{index_code}" if index_code.startswith("0") else f"sz{index_code}")

        url = f"https://qt.gtimg.cn/q={qq_code}"
        client = _get_client()
        resp = client.get(url)
        text = resp.text

        match = re.search(r'v_\w+="(.+)"', text)
        if match:
            data = match.group(1).split('~')
            if len(data) > 30:
                result = {
                    "代码": data[2] if len(data) > 2 else index_code,
                    "名称": data[1] if len(data) > 1 else "",
                    "最新价": float(data[3]) if data[3] else 0,
                    "涨跌幅": float(data[32]) if data[32] else 0,
                }
                _cache_set(cache_key, result, ttl=15)
                return result
        return {}
    except Exception as e:
        log.warning(f"指数行情获取失败: {e}")
        return {}


def _normalize_index_row(index_code: str, display_name: str) -> dict:
    """将 get_index_quote 结果转为前端统一字段"""
    q = get_index_quote(index_code)
    if not q:
        return {
            "code": index_code,
            "name": display_name,
            "price": 0.0,
            "change_pct": 0.0,
        }
    return {
        "code": str(q.get("代码", index_code)),
        "name": str(q.get("名称") or display_name),
        "price": float(q.get("最新价", 0) or 0),
        "change_pct": float(q.get("涨跌幅", 0) or 0),
    }


def get_a_share_market_breadth() -> dict:
    """
    A 股涨跌家数：
      ① 东方财富 clist 分页统计（与涨幅榜同源，稳定）
      ② 兜底：新浪 Market_Center 分页
    """
    cache_key = "market_breadth:hs_a:v2"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    result = _fetch_em_breadth_via_clist()
    if result and (result["advancers"] + result["decliners"] + result["unchanged"]) >= 500:
        _cache_set(cache_key, result, ttl=300)
        return result

    result = _fetch_sina_breadth_paginated()
    if result and (result["advancers"] + result["decliners"] + result["unchanged"]) > 0:
        _cache_set(cache_key, result, ttl=300)
        return result

    log.warning("[涨跌家数] 所有来源均失败")
    return {"advancers": 0, "decliners": 0, "unchanged": 0}


# 与热门股涨幅榜一致的 A 股范围（沪主板/科创 + 深主板/创业板）
_EM_A_SHARE_FS = "m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23"

# 东方财富多个 push 入口：82 节点在部分网络下比主域名更稳定（避免 SSL 握手超时）
_EM_PUSH_BASES = (
    "https://push2delay.eastmoney.com",
    "https://82.push2.eastmoney.com",
    "https://push2.eastmoney.com",
)


def _em_clist_request(params: dict, *, timeout: float = 25.0) -> dict | None:
    """依次尝试各 push 域名请求 api/qt/clist/get，成功返回 JSON dict。
    用 requests 直接调用（可被 http_adapter_patch 拦截：禁用代理；TLS 校验见 FINANCE_TLS_RELAXED）。"""
    from config import FINANCE_TLS_RELAXED

    import requests as _req
    _no_proxy = {"http": None, "https": None}
    verify_tls = not FINANCE_TLS_RELAXED
    for base in _EM_PUSH_BASES:
        try:
            resp = _req.get(
                f"{base}/api/qt/clist/get",
                params=params,
                timeout=timeout,
                verify=verify_tls,
                proxies=_no_proxy,
                headers={"Referer": "https://quote.eastmoney.com/"},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.warning(f"[EM clist] {base} 失败: {e}")
    return None


def _fetch_em_breadth_via_clist() -> dict | None:
    """东方财富 clist 分页拉全 A，按 f3 涨跌幅统计涨跌平家数。"""
    try:
        adv, dec, flat = 0, 0, 0
        page = 1
        page_size = 500
        total_expected = None

        while page <= 30:
            js = _em_clist_request(
                {
                    "pn": page,
                    "pz": page_size,
                    "po": 1,
                    "np": 1,
                    "fltt": 2,
                    "invt": 2,
                    "fid": "f3",
                    "fs": _EM_A_SHARE_FS,
                    "fields": "f3",
                    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                },
                timeout=22.0,
            )
            if not js:
                break
            data = js.get("data") or {}
            if total_expected is None:
                try:
                    total_expected = int(data.get("total", 0) or 0)
                except (TypeError, ValueError):
                    total_expected = 0
            diff = data.get("diff") or []
            if not diff:
                break
            for row in diff:
                try:
                    chg = float(row.get("f3", 0) or 0)
                except (TypeError, ValueError):
                    chg = 0.0
                if chg > 0.001:
                    adv += 1
                elif chg < -0.001:
                    dec += 1
                else:
                    flat += 1
            if len(diff) < page_size:
                break
            page += 1

        total = adv + dec + flat
        log.debug(f"[涨跌家数] EM clist: 涨 {adv} 跌 {dec} 平 {flat} 合计 {total} (预期约 {total_expected})")
        if total <= 0:
            return None
        return {"advancers": adv, "decliners": dec, "unchanged": flat}
    except Exception as e:
        log.warning(f"[涨跌家数] EM clist 失败: {e}")
        return None


def _fetch_sina_breadth_paginated() -> dict | None:
    """新浪 A 股列表分页统计涨跌家数（兜底）。"""
    adv, dec, flat = 0, 0, 0
    page = 1
    page_size = 800
    try:
        client = _get_client()
        while page <= 25:
            url = (
                "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php"
                "/Market_Center.getHQNodeDataSimple"
                f"?node=hs_a&num={page_size}&sort=symbol&asc=1&page={page}"
            )
            resp = client.get(url, timeout=15)
            text = resp.content.decode("gbk", errors="replace")
            data = json.loads(text)
            if not isinstance(data, list) or len(data) == 0:
                break
            for item in data:
                try:
                    chg = float(item.get("changepercent", 0) or 0)
                except (TypeError, ValueError):
                    chg = 0.0
                if chg > 0.0001:
                    adv += 1
                elif chg < -0.0001:
                    dec += 1
                else:
                    flat += 1
            if len(data) < page_size:
                break
            page += 1
        total = adv + dec + flat
        log.debug(f"[涨跌家数] 新浪分页: 涨 {adv} 跌 {dec} 平 {flat} 合计 {total}")
        if total <= 0:
            return None
        return {"advancers": adv, "decliners": dec, "unchanged": flat}
    except Exception as e:
        log.warning(f"[涨跌家数] 新浪分页失败: {e}")
        return None


def get_all_industry_boards() -> list[dict]:
    """
    全部行业板块：① 东方财富行业板块（m:90+t:2）
                  ② 兜底：东方财富概念板块（m:90+t:3）
    返回 { name, change_pct } 列表，按涨跌幅降序排列。
    """
    cache_key = "industry_boards:all:v2"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # ① 行业板块
    boards = _fetch_em_industry_boards()
    if boards:
        _cache_set(cache_key, boards, ttl=120)
        log.info(f"[行业板块] 东方财富获取成功，共 {len(boards)} 个")
        return boards

    # ② 概念板块兜底
    boards = _fetch_em_concept_boards()
    if boards:
        _cache_set(cache_key, boards, ttl=120)
        log.info(f"[行业板块] 概念板块兜底成功，共 {len(boards)} 个")
        return boards

    log.warning("[行业板块] 所有来源均失败")
    return []


def _fetch_em_industry_boards() -> list[dict]:
    """东方财富行业板块（m:90+t:2）"""
    try:
        js = _em_clist_request(
            {
                "pn": 1,
                "pz": 500,
                "po": 1,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fid": "f3",
                "fs": "m:90+t:2",
                "fields": "f14,f3",
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            },
            timeout=20.0,
        )
        if not js:
            return []
        diff = (js.get("data") or {}).get("diff") or []
        rows: list[tuple[str, float]] = []
        for row in diff:
            name = str(row.get("f14", "") or "").strip()
            if not name:
                continue
            try:
                pct = float(row.get("f3", 0) or 0)
            except (TypeError, ValueError):
                pct = 0.0
            rows.append((name, pct))
        if not rows:
            return []
        rows.sort(key=lambda x: x[1], reverse=True)
        return [{"name": n, "change_pct": round(p, 2)} for n, p in rows]
    except Exception as e:
        log.warning(f"[行业板块] 东方财富行业失败: {e}")
        return []


def _fetch_em_concept_boards() -> list[dict]:
    """东方财富概念板块（m:90+t:3）兜底"""
    try:
        js = _em_clist_request(
            {
                "pn": 1,
                "pz": 500,
                "po": 1,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fid": "f3",
                "fs": "m:90+t:3",
                "fields": "f14,f3",
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            },
            timeout=20.0,
        )
        if not js:
            return []
        diff = (js.get("data") or {}).get("diff") or []
        rows: list[tuple[str, float]] = []
        for row in diff:
            name = str(row.get("f14", "") or "").strip()
            if not name:
                continue
            try:
                pct = float(row.get("f3", 0) or 0)
            except (TypeError, ValueError):
                pct = 0.0
            rows.append((name, pct))
        if not rows:
            return []
        rows.sort(key=lambda x: x[1], reverse=True)
        return [{"name": n, "change_pct": round(p, 2)} for n, p in rows]
    except Exception as e:
        log.warning(f"[行业板块] 概念板块兜底失败: {e}")
        return []


def get_industry_board_movers(limit_each: int = 5) -> dict:
    """
    行业板块涨跌幅（兼容旧接口）：东方财富 push2 接口。
    返回 top（涨幅前 N）与 bottom（跌幅前 N）。
    """
    all_boards = get_all_industry_boards()
    if not all_boards:
        return {"top": [], "bottom": []}

    top = all_boards[:limit_each]
    bottom = list(reversed(all_boards[-limit_each:]))
    return {"top": top, "bottom": bottom}


def _em_request(url: str, params: dict, *, timeout: float = 25.0) -> dict | None:
    """东方财富 API 请求：多域名兜底，禁用代理，直连。
    East Money 接口返回 GBK 编码，手动解码避免乱码。"""
    hosts = [
        "https://push2delay.eastmoney.com",
        "https://82.push2.eastmoney.com",
        "https://push2.eastmoney.com",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://quote.eastmoney.com/",
    }
    for base in hosts:
        try:
            client = _get_client()
            resp = client.get(f"{base}{url}", params=params, timeout=timeout, headers=headers)
            resp.raise_for_status()
            raw = resp.content
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("gbk", errors="replace")
            import json
            return json.loads(text)
        except Exception as e:
            log.warning(f"[EM] {base}{url} 失败: {e}")
    return None


_EM_INDUSTRY_NAME_MAP: dict[str, str] = {}
_INDUSTRY_MAP_LOADED = False


def _load_industry_name_map() -> None:
    """加载行业板块名称→代码映射（m:90+t:2），分页拉取直到取完全部。"""
    global _EM_INDUSTRY_NAME_MAP, _INDUSTRY_MAP_LOADED
    if _INDUSTRY_MAP_LOADED:
        return
    page, page_size, total = 1, 100, None
    while True:
        js = _em_request(
            "/api/qt/clist/get",
            {
                "pn": page,
                "pz": page_size,
                "po": 1,
                "np": 1,
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": 2,
                "invt": 2,
                "fid": "f3",
                "fs": "m:90+t:2",
                "fields": "f14,f12",
            },
            timeout=30.0,
        )
        if not js:
            break
        data = js.get("data") or {}
        if total is None:
            total = int(data.get("total", 0) or 0)
        diff = data.get("diff") or []
        for row in diff:
            name = str(row.get("f14") or "").strip()
            code = str(row.get("f12") or "").strip()
            if name and code:
                _EM_INDUSTRY_NAME_MAP[name] = code
        if len(diff) < page_size or len(_EM_INDUSTRY_NAME_MAP) >= total:
            break
        page += 1
    _INDUSTRY_MAP_LOADED = True
    log.info(f"[板块] 行业名称映射加载完毕，共 {len(_EM_INDUSTRY_NAME_MAP)} 条（total={total}）")


_EM_CONCEPT_NAME_MAP: dict[str, str] = {}
_CONCEPT_MAP_LOADED = False


def _load_concept_name_map() -> None:
    """加载概念板块名称→代码映射（m:90+t:3），全量分页拉取。"""
    global _EM_CONCEPT_NAME_MAP, _CONCEPT_MAP_LOADED
    if _CONCEPT_MAP_LOADED:
        return
    page, page_size, total = 1, 100, None
    while True:
        js = _em_request(
            "/api/qt/clist/get",
            {
                "pn": page,
                "pz": page_size,
                "po": 1,
                "np": 1,
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": 2,
                "invt": 2,
                "fid": "f3",
                "fs": "m:90+t:3",
                "fields": "f14,f12",
            },
            timeout=30.0,
        )
        if not js:
            break
        data = js.get("data") or {}
        if total is None:
            total = int(data.get("total", 0) or 0)
        diff = data.get("diff") or []
        for row in diff:
            name = str(row.get("f14") or "").strip()
            code = str(row.get("f12") or "").strip()
            if name and code:
                _EM_CONCEPT_NAME_MAP[name] = code
        if len(diff) < page_size:
            break  # 最后一页
        if len(_EM_CONCEPT_NAME_MAP) >= total:
            break  # 全部拉完
        page += 1
    _CONCEPT_MAP_LOADED = True
    log.info(f"[板块] 概念名称映射加载完毕，共 {len(_EM_CONCEPT_NAME_MAP)} 条（total={total}）")


def _finite_num(v, default: float = 0.0) -> float:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _parse_em_board_cons_df(df: pd.DataFrame | None) -> list[dict]:
    """东方财富行业/概念成分股 DataFrame → 统一结构。"""
    if df is None or df.empty:
        return []
    rows: list[dict] = []
    for _, r in df.iterrows():
        raw = str(r.get("代码", "") or "").strip()
        digits = re.sub(r"\D", "", raw)
        if not digits:
            continue
        code = digits.zfill(6)[-6:]
        name = str(r.get("名称", "") or "").strip()
        if not name:
            continue
        rows.append({
            "code": code,
            "name": name,
            "price": round(_finite_num(r.get("最新价")), 4),
            "change_pct": round(_finite_num(r.get("涨跌幅")), 4),
            "volume": round(_finite_num(r.get("成交量")), 2),
            "amount": round(_finite_num(r.get("成交额")), 2),
            "turnover_pct": round(_finite_num(r.get("换手率")), 4),
            "pe_ttm": round(_finite_num(r.get("市盈率-动态")), 4),
            "pb": round(_finite_num(r.get("市净率")), 4),
        })
    return rows


def _parse_em_board_diff(diff: list[dict]) -> list[dict]:
    """
    解析东方财富板块成分 diff（字段 ID dict 格式）→ 统一结构。
    关键字段：f12=代码, f14=名称, f2=最新价, f3=涨跌幅,
              f4=涨跌额, f5=成交量, f6=成交额, f8=振幅,
              f15=今开, f16=最高, f17=最低, f18=昨收,
              f23=换手率, f24=市盈率-动态, f25=市净率
    """
    rows: list[dict] = []
    for r in diff:
        raw = str(r.get("f12") or "").strip()
        digits = re.sub(r"\D", "", raw)
        if not digits:
            continue
        code = digits.zfill(6)[-6:]
        name = str(r.get("f14") or "").strip()
        if not name:
            continue
        rows.append({
            "code": code,
            "name": name,
            "price": round(_finite_num(r.get("f2")), 4),
            "change_pct": round(_finite_num(r.get("f3")), 4),
            "volume": round(_finite_num(r.get("f5")), 2),
            "amount": round(_finite_num(r.get("f6")), 2),
            "turnover_pct": round(_finite_num(r.get("f23")), 4),
            "pe_ttm": round(_finite_num(r.get("f24")), 4),
            "pb": round(_finite_num(r.get("f25")), 4),
        })
    return rows


def get_board_constituents_em(board_name: str) -> dict:
    """
    板块成分股（东方财富）：直接请求 East Money API，无需 akshare。
    ① 先用行业板块映射查；② 兜底概念板块映射查。
    成分股按涨跌幅降序排列，缓存 90 秒。
    """
    name = (board_name or "").strip()
    if not name:
        return {"sector_name": "", "board_type": None, "stocks": [], "total": 0}

    cache_key = f"board_cons:{name}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    stocks: list[dict] = []
    board_type: str | None = None

    # ── ① 行业板块 ──────────────────────────────────────────────
    _load_industry_name_map()
    board_code = _EM_INDUSTRY_NAME_MAP.get(name)
    # 模糊匹配：找包含 name 的键
    if not board_code:
        for k, v in _EM_INDUSTRY_NAME_MAP.items():
            if name in k or k in name:
                board_code = v
                log.warning(f"[板块] 精确匹配失败，模糊匹配: {name!r} → {k!r} ({v})")
                break
    log.debug(f"[板块] 查找行业: name={name!r}, found={board_code}, total_keys={len(_EM_INDUSTRY_NAME_MAP)}, sample_keys={list(_EM_INDUSTRY_NAME_MAP.keys())[:5]}")
    if board_code:
        js = _em_request(
            "/api/qt/clist/get",
            {
                "pn": 1,
                "pz": 500,
                "po": 1,
                "np": 1,
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": 2,
                "invt": 2,
                "fid": "f3",
                "fs": f"b:{board_code}+f:!50",
                "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f45",
            },
            timeout=30.0,
        )
        if js:
            diff = (js.get("data") or {}).get("diff") or []
            if diff:
                board_type = "industry"
                stocks = _parse_em_board_diff(diff)

    # ── ② 概念板块兜底 ─────────────────────────────────────────
    if not stocks:
        _load_concept_name_map()
        board_code = _EM_CONCEPT_NAME_MAP.get(name)
        if not board_code:
            for k, v in _EM_CONCEPT_NAME_MAP.items():
                if name in k or k in name:
                    board_code = v
                    log.debug(f"[板块] 概念模糊匹配: {name!r} → {k!r} ({v})")
                    break
        if board_code:
            js = _em_request(
                "/api/qt/clist/get",
                {
                    "pn": 1,
                    "pz": 200,
                    "po": 1,
                    "np": 1,
                    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                    "fltt": 2,
                    "invt": 2,
                    "fid": "f3",
                    "fs": f"b:{board_code}+f:!50",
                    "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f45",
                },
                timeout=30.0,
            )
            if js:
                diff = (js.get("data") or {}).get("diff") or []
                if diff:
                    board_type = "concept"
                    stocks = _parse_em_board_diff(diff)

    stocks.sort(key=lambda x: x["change_pct"], reverse=True)
    for i, s in enumerate(stocks, start=1):
        s["rank"] = i

    out = {
        "sector_name": name,
        "board_type": board_type,
        "stocks": stocks,
        "total": len(stocks),
    }
    _cache_set(cache_key, out, ttl=90)
    return out


def akshare_cache_stats() -> dict:
    """内存行情缓存统计（供 /health）。"""
    with _cache_lock:
        return {"entries": len(_cache), "max_entries": _CACHE_MAX_ENTRIES}


def get_market_overview_bundle() -> dict:
    """聚合：主要指数 + 涨跌家数 + 全部行业板块（供 /api/market/overview）"""
    cache_key = "market_overview:bundle:v1"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    index_specs = [
        ("sh", "000001", "上证指数"),
        ("sz", "399001", "深证成指"),
        ("cyb", "399006", "创业板指"),
        ("kc50", "000688", "科创50"),
        ("hs300", "399300", "沪深300"),
        ("zz500", "000905", "中证500"),
    ]
    indices: dict = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(_normalize_index_row, sym, label): key
            for key, sym, label in index_specs
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                indices[key] = future.result()
            except Exception:
                log.debug("指数行情获取失败 key=%s", key, exc_info=True)
                indices[key] = {}
    breadth = get_a_share_market_breadth()
    all_boards = get_all_industry_boards()
    top5 = all_boards[:5]
    bottom5 = list(reversed(all_boards[-5:]))
    out = {
        "indices": indices,
        "market_breadth": breadth,
        "sectors": all_boards,
        "sectors_top": top5,
        "sectors_bottom": bottom5,
        "stale": False,
    }
    _cache_set(cache_key, out, ttl=60)
    return out


def _parse_sina_suggest(text: str) -> list[dict]:
    """
    解析新浪搜索响应
    两种格式：
      名称搜索: "徐工机械,11,000425,sz000425,徐工机械,..."
      代码搜索: "sz000425,11,000425,sz000425,徐工机械,..."
    """
    if not text.startswith('var suggestvalue='):
        return []
    content = text[len('var suggestvalue='):].strip().strip('"').rstrip(';')
    if not content or content == 'N':
        return []

    records = []
    for entry in content.split(';'):
        items = entry.split(',')
        if len(items) < 5:
            continue

        first_field = items[0]
        # 判断格式：市场代码搜索（以sz/sh开头）还是名称搜索
        if first_field.startswith(('sz', 'sh')):
            # 代码搜索格式: 市场代码,类型,代码,市场代码,名称,...
            market_code = items[0]
            code = items[2]
            name = items[4]
        else:
            # 名称搜索格式: 名称,类型,代码,市场代码,名称,...
            name = items[0]
            code = items[2]
            market_code = items[3]

        # 只保留A股
        if (market_code.startswith('sh') or market_code.startswith('sz')) and not name.isdigit():
            records.append({"code": code, "name": name})

    return records


def search_stocks(keyword: str) -> pd.DataFrame:
    """搜索股票 - 使用新浪搜索API"""
    cache_key = f"search:{keyword}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        # 始终使用 UTF-8 URL encode（两种搜索都有效）
        keyword_encoded = urllib.parse.quote(keyword)
        url = f"https://suggest3.sinajs.cn/suggest/type=11,12,13,14,15&key={keyword_encoded}"
        client = _get_client()
        resp = client.get(url)
        text = resp.content.decode('gbk', errors='replace').strip()

        records = _parse_sina_suggest(text)

        # 去重并限制数量
        seen: set[str] = set()
        unique = []
        for r in records:
            if r['code'] not in seen:
                seen.add(r['code'])
                unique.append(r)

        df = pd.DataFrame(unique[:20])
        _cache_set(cache_key, df, ttl=3600)
        return df
    except Exception as e:
        log.warning(f"股票搜索失败: {e}")
        return pd.DataFrame()


def get_daily_hot_stocks(limit: int = 20) -> list:
    """当日个股人气榜（东方财富），返回含代码、名称、排名等；缓存为空时直接获取实时数据。"""
    limit = max(1, int(limit))
    cache_key = f"hot:daily:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    return _fetch_and_cache_hot(limit)


def _fetch_and_cache_hot(limit: int = 20) -> list:
    """按优先级尝试多个来源获取热门股票：东方财富涨幅榜 → 同花顺 → 新浪人气榜。"""
    limit = max(1, int(limit))
    cache_key = f"hot:daily:{limit}"

    # ① 东方财富涨幅榜（按涨跌幅）
    stocks = _fetch_em_hot_stocks(limit)
    if stocks:
        _cache_set(cache_key, stocks, ttl=120)
        log.info(f"[热门] 东方财富涨幅榜获取成功，共 {len(stocks)} 条")
        return stocks

    # ② 同花顺热门
    stocks = _fetch_ths_hot_stocks(limit)
    if stocks:
        _cache_set(cache_key, stocks, ttl=120)
        log.info(f"[热门] 同花顺热门获取成功，共 {len(stocks)} 条")
        return stocks

    # ③ 新浪人气榜兜底
    stocks = _fetch_sina_hot_stocks(limit)
    _cache_set(cache_key, stocks, ttl=60)
    if stocks:
        log.info(f"[热门] 新浪人气榜获取成功，共 {len(stocks)} 条")
    else:
        log.warning("[热门] 所有来源均获取失败")
    return stocks


def _fetch_em_hot_stocks(limit: int) -> list:
    """东方财富涨幅榜（今日涨跌幅从高到低），并发分页，最多支持 1000 条。"""
    PAGE_SIZE = 100
    total_pages = (limit + PAGE_SIZE - 1) // PAGE_SIZE

    def fetch_page(pn: int) -> list[dict]:
        try:
            js = _em_clist_request(
                {
                    "pn": pn,
                    "pz": PAGE_SIZE,
                    "po": 1,
                    "np": 1,
                    "fltt": 2,
                    "invt": 2,
                    "fid": "f3",
                    "fs": "m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23",
                    "fields": "f2,f3,f4,f5,f6,f12,f14",
                    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                },
                timeout=20.0,
            )
            if not js:
                return []
            diff = (js.get("data") or {}).get("diff") or []
            stocks = []
            for row in diff:
                try:
                    price = float(row.get("f2", 0) or 0)
                    chg = float(row.get("f3", 0) or 0)
                    volume = float(row.get("f5", 0) or 0)
                    amount = float(row.get("f6", 0) or 0)
                except (TypeError, ValueError):
                    price, chg, volume, amount = 0.0, 0.0, 0.0, 0.0
                code = str(row.get("f12", "") or "").strip()
                name = str(row.get("f14", "") or "").strip()
                if not code:
                    continue
                stocks.append({
                    "code": code.zfill(6),
                    "name": name,
                    "change_pct": round(chg, 2),
                    "price": round(price, 2),
                    "volume": volume,
                    "amount": amount,
                })
            return stocks
        except Exception as e:
            log.warning(f"[热门-分页] 第 {pn} 页失败: {e}")
            return []

    all_stocks: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(total_pages, 10)) as pool:
        futures = {pool.submit(fetch_page, pn): pn for pn in range(1, total_pages + 1)}
        for future in as_completed(futures):
            try:
                page_stocks = future.result(timeout=25.0)
                all_stocks.extend(page_stocks)
            except Exception as e:
                pn = futures[future]
                log.warning(f"[热门-分页] 第 {pn} 页超时/异常: {e}")

    # 按涨幅降序重新编号
    all_stocks.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
    for idx, s in enumerate(all_stocks, start=1):
        s["rank"] = idx

    return all_stocks[:limit]


def _fetch_ths_hot_stocks(limit: int) -> list:
    """同花顺热门股票"""
    try:
        client = _get_client()
        url = (
            "https://d.10jqka.com.cn/v6/line/hs_a/01/order=desc/page=1/ajax=1/fund=2"
        )
        resp = client.get(url, timeout=10, headers={"Referer": "https://www.10jqka.com.cn/"})
        text = resp.text
        data = json.loads(text)
        items = data.get("data", []) if isinstance(data, dict) else []
        stocks = []
        for idx, item in enumerate(items[:limit], start=1):
            try:
                chg = float(item.get("zxdf", 0))
            except (TypeError, ValueError):
                chg = 0.0
            code = str(item.get("code", "") or "").strip()
            name = str(item.get("name", "") or "").strip()
            if not code:
                continue
            stocks.append({
                "rank": idx,
                "code": code.zfill(6),
                "name": name,
                "change_pct": round(chg, 2),
                "volume": 0,
            })
        return stocks
    except Exception as e:
        log.warning(f"[热门] 同花顺热门失败: {e}")
        return []


def _fetch_sina_hot_stocks(limit: int) -> list:
    """新浪人气榜（兜底）"""
    try:
        client = _get_client()
        url = (
            "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php"
            "/Market_Center.getHQNodeDataSimple"
            f"?node=hs_a&num={limit}&sort=focus&asc=0&page=1"
        )
        resp = client.get(url, timeout=15)
        text = resp.content.decode("gbk", errors="replace")
        data = json.loads(text)
        if not isinstance(data, list):
            log.warning(f"[热门] 新浪人气榜返回格式异常: {text[:200]}")
            return []

        stocks = []
        for idx, item in enumerate(data, start=1):
            symbol = str(item.get("symbol", "")).strip()
            for p in ("sh", "sz", "bj", "SH", "SZ", "BJ"):
                if symbol.startswith(p):
                    code = symbol[len(p):].zfill(6)
                    break
            else:
                code = symbol.zfill(6) if symbol.isdigit() else symbol

            try:
                chg = float(item.get("changepercent", 0))
            except (TypeError, ValueError):
                chg = 0.0
            try:
                vol = int(float(item.get("volume", 0) or 0))
            except (TypeError, ValueError):
                vol = 0

            stocks.append({
                "rank": idx,
                "code": code,
                "name": str(item.get("name", "") or "").strip(),
                "change_pct": round(chg, 2),
                "volume": vol,
            })
        return stocks
    except Exception as e:
        log.warning(f"[热门] 新浪人气榜失败: {e}")
        return []


def warm_hot_cache():
    """后台线程预热热门股票缓存（5 分钟刷新一次）。"""
    import threading, time
    def _loop():
        while True:
            _fetch_and_cache_hot(20)
            time.sleep(300)
    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    log.info("热门股票后台预热线程已启动")


def get_stock_info(code: str) -> dict:
    """获取股票基本信息"""
    cache_key = f"info:{code}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    sym, _ = normalize_stock_code(code)
    mkt = _get_qq_market_code(code)

    try:
        url = f"https://qt.gtimg.cn/q={mkt}{sym}"
        client = _get_client()
        resp = client.get(url)
        text = resp.text

        match = re.search(r'v_\w+="(.+)"', text)
        if match:
            data = match.group(1).split('~')
            # 与 get_realtime_quote 一致：≥38 即可解析核心字段；勿用 >45 过严导致部分行情返回被丢弃
            if len(data) >= 38:
                info = {
                    "代码": data[2] if len(data) > 2 else sym,
                    "名称": data[1] if len(data) > 1 else "",
                    "现价": float(data[3]) if data[3] else 0,
                    "涨跌幅": float(data[32]) if len(data) > 32 and data[32] else 0,
                    "涨跌额": float(data[31]) if len(data) > 31 and data[31] else 0,
                    "成交量": float(data[6]) if data[6] else 0,
                    "成交额": float(data[37]) if len(data) > 37 and data[37] else 0,
                    "振幅": float(data[43]) if len(data) > 43 and data[43] else 0,
                    "最高": float(data[33]) if len(data) > 33 and data[33] else 0,
                    "最低": float(data[34]) if len(data) > 34 and data[34] else 0,
                    "今开": float(data[4]) if data[4] else 0,
                    "昨收": float(data[5]) if data[5] else 0,
                    "市净率": float(data[46]) if len(data) > 46 and data[46] else 0,
                    "市盈率": float(data[39]) if len(data) > 39 and data[39] else 0,
                }
                _cache_set(cache_key, info, ttl=300)
                return info
        return {}
    except Exception as e:
        log.warning(f"股票信息获取失败: {e}")
        return {}


def get_stock_depth_em(code: str) -> dict:
    """
    东方财富五档盘口（买卖各五档）。
    返回 {"asks": [{"price": float, "volume": int}, ...], "bids": [...]}，
    asks 顺序为卖五→卖一（由上到下）。
    """
    cache_key = f"depth_em:{code}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    sym, _ = normalize_stock_code(code)
    secid = f"1.{sym}" if sym.startswith("6") else f"0.{sym}"
    params = {
        "fltt": "2",
        "invt": "2",
        "secid": secid,
        "fields": "f31,f32,f33,f34,f35,f36,f37,f38,f39,f40,f41,f42,f19,f20,f21,f22,f23,f24",
    }

    # 多域名兜底，顺序尝试
    hosts = [
        "https://push2.eastmoney.com/api/qt/stock/get",
        "https://push2delay.eastmoney.com/api/qt/stock/get",
        "https://push2his.eastmoney.com/api/qt/stock/get",
    ]

    d = None
    for host in hosts:
        try:
            client = _get_client()
            resp = client.get(host, params=params, timeout=8)
            js = resp.json()
            d = js.get("data")
            if d:
                break
        except Exception as e:
            log.warning(f"[盘口] {host} 失败: {e}")
            continue

    if not d:
        out = {"asks": [], "bids": []}
        _cache_set(cache_key, out, ttl=30)
        return out

    # 直接解析字段，不依赖 pandas
    asks: list[dict] = []
    for i in range(5, 0, -1):
        pair = {5: (31, 32), 4: (33, 34), 3: (35, 36), 2: (37, 38), 1: (39, 40)}[i]
        p_idx, v_idx = pair
        price = d.get(f"f{p_idx}")
        vol = d.get(f"f{v_idx}")
        asks.append({
            "price": round(float(price), 3) if price else 0.0,
            "volume": int(float(vol or 0) * 100),
        })

    bids: list[dict] = []
    for i in range(1, 6):
        pair = {1: (19, 20), 2: (21, 22), 3: (23, 24), 4: (25, 26), 5: (27, 28)}[i]
        p_idx, v_idx = pair
        price = d.get(f"f{p_idx}")
        vol = d.get(f"f{v_idx}")
        bids.append({
            "price": round(float(price), 3) if price else 0.0,
            "volume": int(float(vol or 0) * 100),
        })

    out = {"asks": asks, "bids": bids}
    _cache_set(cache_key, out, ttl=15)
    return out


def get_stock_boards_em(code: str) -> dict:
    """
    个股资料中的行业等信息，直接请求东方财富接口（替代 akshare）。
    """
    cache_key = f"boards_em:{code}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    sym, _ = normalize_stock_code(code)
    secid = f"1.{sym}" if sym.startswith("6") else f"0.{sym}"
    params = {
        "fltt": "2",
        "invt": "2",
        "secid": secid,
        "fields": "f127,f84,f85,f116,f117,f189,f43",
    }

    hosts = [
        "https://push2.eastmoney.com/api/qt/stock/get",
        "https://push2delay.eastmoney.com/api/qt/stock/get",
        "https://push2his.eastmoney.com/api/qt/stock/get",
    ]

    d = None
    for host in hosts:
        try:
            client = _get_client()
            resp = client.get(host, params=params, timeout=8)
            js = resp.json()
            d = js.get("data")
            if d:
                break
        except Exception as e:
            log.warning(f"[板块] {host} 失败: {e}")
            continue

    if d is None:
        out = {"industry": "", "highlights": []}
        _cache_set(cache_key, out, ttl=60)
        return out

    industry = str(d.get("f127") or "").strip()
    highlights: list[dict] = []
    interest = ("行业", "总市值", "流通市值", "总股本", "流通股", "上市时间")
    seen: set[str] = set()

    def _add(label: str, val):
        if val is None:
            return
        val_s = str(val).strip()
        if not val_s:
            return
        if label in interest or any(x in label for x in interest):
            if label not in seen:
                seen.add(label)
                highlights.append({"label": label, "value": val_s})

    _add("行业", d.get("f127"))
    _add("总市值", d.get("f116"))
    _add("流通市值", d.get("f117"))
    _add("总股本", d.get("f84"))
    _add("流通股", d.get("f85"))

    # 上市时间处理
    listed_date = d.get("f189")
    if listed_date:
        try:
            listed_str = str(int(float(listed_date)))
            if len(listed_str) == 8:
                formatted = f"{listed_str[:4]}-{listed_str[4:6]}-{listed_str[6:]}"
                _add("上市时间", formatted)
        except (ValueError, TypeError):
            pass

    highlights.sort(key=lambda x: (0 if "行业" in x["label"] else 1, x["label"]))
    out = {"industry": industry, "highlights": highlights[:8]}
    _cache_set(cache_key, out, ttl=600)
    return out


def _fetch_em_symbol_news(code: str, limit: int) -> list:
    """东方财富个股新闻（直连 HTTP，避免 akshare 额外开销）。"""
    sym, _ = normalize_stock_code(code)
    market_prefix = "SH" if sym.startswith(("5", "6", "9")) else "SZ"
    secu_code = f"{market_prefix}{sym}"
    try:
        client = _get_client()
        url = (
            "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns"
            f"?client=web&biz=web_news_col&column=350&page_index=1&page_size={limit}"
            f"&req_trace=1&fields=title,showtime,mediaName,url,uniqueUrl"
            f"&secuCode={secu_code}"
        )
        resp = client.get(
            url,
            timeout=8,
            headers={"Referer": "https://quote.eastmoney.com/"},
        )
        js = resp.json()
        raw = (js.get("data") or {}).get("list") or []
        items = []
        for item in raw[:limit]:
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            link = str(item.get("uniqueUrl") or item.get("url") or "").strip()
            items.append({
                "title": title[:300],
                "time": str(item.get("showtime") or "")[:32],
                "source": str(item.get("mediaName") or "")[:48],
                "url": link if link.startswith("http") else "",
            })
        return items
    except Exception as e:
        log.debug("[个股新闻] HTTP 失败 %s: %s", code, e)
        return []


def get_stock_symbol_news_em(code: str, limit: int = 8) -> list:
    """东方财富个股相关新闻。"""
    limit = max(1, min(20, int(limit)))
    cache_key = f"sym_news_em:{code}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    items = _fetch_em_symbol_news(code, limit)
    _cache_set(cache_key, items, ttl=600)
    return items


# ─── 分时数据 ────────────────────────────────────────────────────────────────
def get_minute_data(code: str, period: str = "5") -> pd.DataFrame:
    """获取分钟K线数据"""
    cache_key = f"minute:{code}:{period}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    df = get_kline_hist(code, period=period, adjust="qfq")
    if not df.empty:
        _cache_set(cache_key, df, ttl=60)
    return df


# ─── 新浪分钟数据 ─────────────────────────────────────────────────────────────
def _get_minute_data_sina(code: str, market: str, period: str, adjust: str = "qfq") -> pd.DataFrame:
    """
    使用新浪API获取分钟K线数据
    period: 5, 15, 30, 60 (分钟)
    """
    # 新浪代码格式: sz000001, sh600000
    sina_code = f"{market}{code}"

    # 新浪API参数
    scale_map = {"5": 5, "15": 15, "30": 30, "60": 60}
    scale = scale_map.get(period, 30)

    # 新浪API URL
    url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={sina_code}&scale={scale}&ma=no&datalen=500"

    try:
        client = _get_client()
        resp = client.get(url)
        data = resp.json()

        if not data or not isinstance(data, list):
            return pd.DataFrame()

        records = []
        for kl in data:
            try:
                records.append({
                    "date": pd.to_datetime(kl.get("day", "")),
                    "open": float(kl.get("open", 0)),
                    "close": float(kl.get("close", 0)),
                    "high": float(kl.get("high", 0)),
                    "low": float(kl.get("low", 0)),
                    "volume": float(kl.get("volume", 0)),
                })
            except (ValueError, TypeError):
                continue

        df = pd.DataFrame(records)
        return df
    except Exception as e:
        log.warning(f"新浪分钟数据获取失败 {code} {period}: {e}")
        return pd.DataFrame()
