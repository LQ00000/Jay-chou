#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
酷6网 Spider
https://www.ku6.com
结构参考 effedupmovies PY
接口优先: /video/feed  JSON
HTML 兜底: 首页/频道页卡片
"""
import json
import re
import gzip
import urllib.parse
import urllib.request

try:
    import requests
except ImportError:
    requests = None

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""):
            pass


HOST = "https://www.ku6.com"
MHOST = "https://m.ku6.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# subjectId 来自历史频道映射（站点改版后以 HTML 兜底）
CHANNELS = [
    ("home", "首页", ""),
    ("76", "精彩视频", "76"),
    ("news", "资讯", "news"),
    ("movie", "影视剧", "movie"),
    ("ent", "娱乐", "ent"),
    ("sports", "体育", "sports"),
    ("game", "游戏", "game"),
    ("anime", "动漫", "anime"),
    ("auto", "汽车", "auto"),
    ("funny", "搞笑", "funny"),
]


class Spider(BaseSpider):
    def __init__(self):
        self.siteUrl = HOST
        self.userAgent = UA

    def getName(self):
        return "酷6网"

    def init(self, extend=""):
        pass

    def _headers(self, extra=None):
        h = {
            "User-Agent": self.userAgent,
            "Referer": HOST + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        if extra:
            h.update(extra)
        return h

    def _decode(self, raw):
        if not raw:
            return ""
        if isinstance(raw, str):
            return raw
        if raw[:2] == b"\x1f\x8b":
            try:
                raw = gzip.decompress(raw)
            except Exception:
                pass
        return raw.decode("utf-8", "ignore")

    def fetch_text(self, url, headers=None):
        try:
            if requests is not None:
                r = requests.get(
                    url, headers=self._headers(headers), timeout=20,
                    verify=False, allow_redirects=True,
                )
                return r.text or ""
            req = urllib.request.Request(url, headers=self._headers(headers))
            with urllib.request.urlopen(req, timeout=20) as resp:
                return self._decode(resp.read())
        except Exception as e:
            print("fetch error", url, e)
            return ""

    def fetch_json(self, url, headers=None):
        txt = self.fetch_text(url, headers)
        if not txt:
            return None
        try:
            return json.loads(txt)
        except Exception:
            m = re.search(r"\{[\s\S]*\}", txt)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    return None
            return None

    def _abs(self, u):
        if not u:
            return ""
        u = str(u).strip().replace("\\/", "/")
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return HOST + u
        return u

    def _clean(self, t):
        t = re.sub(r"<[^>]+>", "", str(t or ""))
        t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#39;", "'")
        return re.sub(r"\s+", " ", t).strip()

    def _item_from_feed(self, it):
        if not isinstance(it, dict):
            return None
        vid = str(
            it.get("id") or it.get("vid") or it.get("videoId") or it.get("rid") or ""
        )
        name = self._clean(
            it.get("title") or it.get("name") or it.get("videoName") or ""
        )
        pic = self._abs(
            it.get("cover") or it.get("pic") or it.get("img") or it.get("poster") or it.get("thumb") or ""
        )
        play = (
            it.get("playUrl") or it.get("play_url") or it.get("url")
            or it.get("mp4") or it.get("videoUrl") or ""
        )
        if isinstance(play, dict):
            play = play.get("url") or play.get("mp4") or ""
        play = str(play or "").replace("\\/", "/")
        remarks = str(it.get("count") or it.get("playCount") or it.get("hits") or "")
        if remarks and not str(remarks).endswith("次"):
            try:
                n = int(re.sub(r"\D", "", str(remarks)) or 0)
                if n >= 10000:
                    remarks = "%.1f万" % (n / 10000.0)
                else:
                    remarks = str(n) if n else ""
            except Exception:
                pass
        if not vid and play:
            vid = play
        if not name:
            return None
        if not vid:
            vid = name
        return {
            "vod_id": vid,
            "vod_name": name[:120],
            "vod_pic": pic,
            "vod_remarks": remarks,
            "vod_play": play,  # 内部暂存，列表不输出
            "style": {"type": "rect", "ratio": 1.78},
        }

    def _feed(self, page=0, size=24, subject=""):
        page = max(0, int(page or 0))
        size = int(size or 24)
        urls = []
        q = "pageNo=%d&pageSize=%d" % (page, size)
        if subject and str(subject).isdigit():
            q += "&subjectId=%s" % subject
        for base in (HOST, MHOST):
            urls.append("%s/video/feed?%s" % (base, q))
        videos = []
        for u in urls:
            d = self.fetch_json(
                u,
                {
                    "Accept": "application/json, text/plain, */*",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": HOST + "/index",
                },
            )
            if not d:
                continue
            arr = []
            if isinstance(d, dict):
                data = d.get("data")
                if isinstance(data, list):
                    arr = data
                elif isinstance(data, dict):
                    arr = data.get("list") or data.get("records") or data.get("items") or []
                else:
                    arr = d.get("list") or d.get("videos") or []
            elif isinstance(d, list):
                arr = d
            for it in arr:
                v = self._item_from_feed(it)
                if v:
                    # 去掉内部字段
                    play = v.pop("vod_play", "")
                    if play and not v.get("vod_id"):
                        v["vod_id"] = play
                    videos.append(v)
            if videos:
                break
        return videos

    def _parse_html_list(self, html):
        videos, seen = [], set()
        if not html:
            return videos
        # 常见卡片: a[href*=video] / data-id
        patterns = [
            r'href="((?:https?://(?:www\.)?ku6\.com)?/[^"]*(?:video|detail|show)[^"]*)"[^>]*(?:title="([^"]*)")?',
            r'data-(?:id|vid)="(\d+)"[^>]{0,200}?title="([^"]+)"',
            r'<a[^>]+href="(/video/[^"]+)"[^>]*>\s*(?:<[^>]+>\s*)*([^<]{2,80})',
        ]
        for pat in patterns:
            for m in re.finditer(pat, html, re.I):
                a, b = m.group(1), (m.group(2) if m.lastindex >= 2 else "")
                if a.isdigit():
                    vid, title = a, self._clean(b)
                else:
                    vid = a
                    title = self._clean(b)
                    mid = re.search(r"[?&](?:id|vid)=(\w+)", a) or re.search(r"/(\d{5,})", a)
                    if mid:
                        vid = mid.group(1)
                if not title or vid in seen:
                    continue
                if any(x in str(vid) for x in ("javascript", "login", "upload", "#")):
                    continue
                seen.add(vid)
                near = html[max(0, m.start() - 500) : m.end() + 400]
                pic = ""
                pm = re.search(
                    r'(?:src|data-src|data-original)="(https?://[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
                    near, re.I,
                )
                if pm:
                    pic = pm.group(1)
                videos.append({
                    "vod_id": vid,
                    "vod_name": title[:120],
                    "vod_pic": self._abs(pic),
                    "vod_remarks": "",
                    "style": {"type": "rect", "ratio": 1.78},
                })
            if len(videos) >= 8:
                break
        return videos

    def homeContent(self, filter=False):
        classes = [{"type_id": c[0], "type_name": c[1]} for c in CHANNELS]
        return {"class": classes, "filters": {}, "list": []}

    def homeVideoContent(self):
        videos = self._feed(0, 24, "")
        if not videos:
            html = self.fetch_text(HOST + "/index") or self.fetch_text(HOST + "/")
            videos = self._parse_html_list(html)
        return {"list": videos[:24]}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg or 1)
        tid = str(tid or "home")
        subject = ""
        for c in CHANNELS:
            if c[0] == tid:
                subject = c[2]
                break
        # feed 页码从 0 开始
        videos = self._feed(pg - 1, 24, subject if subject.isdigit() else "")
        if not videos:
            if tid == "home" or not tid:
                url = HOST + "/index" if pg <= 1 else HOST + "/index?page=%d" % pg
            elif subject.isdigit():
                url = HOST + "/video/list?subjectId=%s&pageNo=%d" % (subject, pg - 1)
            else:
                url = HOST + "/%s" % tid
            html = self.fetch_text(url)
            videos = self._parse_html_list(html)
        return {
            "list": videos,
            "page": pg,
            "pagecount": pg + 1 if len(videos) >= 12 else max(pg, 1),
            "limit": 24,
            "total": 9999 if videos else 0,
        }

    def searchContent(self, key, quick=False, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick=False, pg=1):
        pg = int(pg or 1)
        key = (key or "").strip()
        if not key:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}
        q = urllib.parse.quote(key)
        videos = []
        # API 搜索
        for u in (
            "%s/video/search?q=%s&pageNo=%d&pageSize=24" % (HOST, q, pg - 1),
            "%s/search/video?keyword=%s&page=%d" % (HOST, q, pg),
            "%s/video/feed?pageNo=%d&pageSize=24&keyword=%s" % (HOST, pg - 1, q),
        ):
            d = self.fetch_json(u, {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"})
            if not d:
                continue
            arr = []
            if isinstance(d, dict):
                data = d.get("data")
                if isinstance(data, list):
                    arr = data
                elif isinstance(data, dict):
                    arr = data.get("list") or data.get("records") or []
                else:
                    arr = d.get("list") or []
            for it in arr:
                v = self._item_from_feed(it)
                if v:
                    v.pop("vod_play", None)
                    videos.append(v)
            if videos:
                break
        if not videos:
            html = self.fetch_text("%s/search?q=%s" % (HOST, q)) or self.fetch_text(
                "%s/search.html?keyword=%s" % (HOST, q)
            )
            videos = self._parse_html_list(html)
        return {
            "list": videos,
            "page": pg,
            "pagecount": pg + 1 if len(videos) >= 10 else max(pg, 1),
            "limit": 24,
            "total": 9999 if videos else 0,
        }

    def _extract_play(self, html, data=None):
        parts, seen = [], set()

        def add(label, u):
            u = str(u or "").replace("\\/", "/").strip()
            if not u or u in seen:
                return
            if not re.search(r"https?://", u) and not u.startswith("//"):
                return
            if u.startswith("//"):
                u = "https:" + u
            seen.add(u)
            parts.append("%s$%s" % (label, u))

        if isinstance(data, dict):
            for k in ("playUrl", "play_url", "url", "mp4", "videoUrl", "src", "hdUrl", "sdUrl"):
                v = data.get(k)
                if isinstance(v, str) and v.startswith("http"):
                    add("高清" if "hd" in k.lower() else "播放", v)
                elif isinstance(v, dict):
                    for kk, vv in v.items():
                        if isinstance(vv, str) and vv.startswith("http"):
                            add(str(kk), vv)

        for m in re.finditer(
            r"https?://[^\"'\s<>]+\.(?:mp4|m3u8)[^\"'\s<>]*", html or "", re.I
        ):
            u = m.group(0).rstrip("\\'\";")
            if "fluidplayer" in u:
                continue
            label = "M3U8" if ".m3u8" in u.lower() else "MP4"
            add(label, u)

        # player config
        for m in re.finditer(
            r'(?:playUrl|video_url|src|url)\s*[:=]\s*["\'](https?://[^"\']+)["\']',
            html or "",
            re.I,
        ):
            add("播放", m.group(1))

        return parts

    def detailContent(self, ids):
        raw = str((ids or [""])[0]).strip()
        if not raw:
            return {"list": []}

        # 若 vod_id 已是直链
        if re.search(r"\.(mp4|m3u8)(\?|$)", raw, re.I) and raw.startswith("http"):
            return {"list": [{
                "vod_id": raw,
                "vod_name": "酷6视频",
                "vod_pic": "",
                "vod_content": "酷6网",
                "vod_play_from": "酷6",
                "vod_play_url": "播放$%s" % raw,
                "style": {"type": "rect", "ratio": 1.78},
            }]}

        vid = raw
        html = ""
        data = None
        # 详情 API
        for u in (
            "%s/video/detail?id=%s" % (HOST, urllib.parse.quote(vid)),
            "%s/video/info?id=%s" % (HOST, urllib.parse.quote(vid)),
            "%s/v/%s" % (HOST, vid),
        ):
            d = self.fetch_json(u, {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"})
            if isinstance(d, dict) and (d.get("data") or d.get("playUrl") or d.get("title")):
                data = d.get("data") if isinstance(d.get("data"), dict) else d
                break

        # HTML 详情
        detail_urls = []
        if raw.startswith("http"):
            detail_urls.append(raw)
        else:
            detail_urls.extend([
                "%s/video/detail?id=%s" % (HOST, vid),
                "%s/show/%s.html" % (HOST, vid),
                "%s/film/show_%s.html" % (HOST, vid),
            ])
        for u in detail_urls:
            html = self.fetch_text(u)
            if html and len(html) > 500 and "404" not in html[:200]:
                break

        name = vid
        pic = ""
        desc = ""
        if isinstance(data, dict):
            name = self._clean(data.get("title") or data.get("name") or name)
            pic = self._abs(data.get("cover") or data.get("pic") or "")
            desc = self._clean(data.get("desc") or data.get("description") or "")[:400]

        if html:
            m = re.search(r"<title>([^<]+)</title>", html, re.I)
            if m:
                name = self._clean(re.sub(r"\s*[-|_].*$", "", m.group(1))) or name
            m = re.search(r'property=["\']og:title["\'][^>]*content=["\']([^"\']+)', html, re.I)
            if m:
                name = self._clean(m.group(1))
            m = re.search(r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)', html, re.I)
            if m:
                pic = self._abs(m.group(1))
            m = re.search(r'property=["\']og:description["\'][^>]*content=["\']([^"\']+)', html, re.I)
            if m:
                desc = self._clean(m.group(1))[:400]

        play_parts = self._extract_play(html, data)
        if not play_parts:
            # 再试播放接口
            for u in (
                "%s/video/getPlayUrl?id=%s" % (HOST, urllib.parse.quote(vid)),
                "%s/video/play?id=%s" % (HOST, urllib.parse.quote(vid)),
            ):
                d = self.fetch_json(u, {"Accept": "application/json"})
                if d:
                    play_parts = self._extract_play("", d.get("data") if isinstance(d.get("data"), dict) else d)
                if play_parts:
                    break

        if not play_parts:
            page = detail_urls[0] if detail_urls else "%s/video/detail?id=%s" % (HOST, vid)
            play_parts = ["网页$%s" % page]

        return {"list": [{
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": desc or "酷6网视频",
            "vod_play_from": "酷6",
            "vod_play_url": "#".join(play_parts[:8]),
            "style": {"type": "rect", "ratio": 1.78},
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        header = {
            "User-Agent": self.userAgent,
            "Referer": HOST + "/",
            "Origin": HOST,
        }
        play = str(id or "").strip()
        if play.startswith("http") and re.search(r"\.(mp4|m3u8)(\?|$)", play, re.I):
            return {
                "parse": 0, "jx": 0, "url": play, "header": header,
                "format": "application/x-mpegURL" if ".m3u8" in play.lower() else "video/mp4",
            }
        if play.startswith("http"):
            # 可能是详情页
            html = self.fetch_text(play)
            parts = self._extract_play(html)
            if parts:
                u = parts[0].split("$")[-1]
                return {
                    "parse": 0, "jx": 0, "url": u, "header": header,
                    "format": "application/x-mpegURL" if ".m3u8" in u.lower() else "video/mp4",
                }
            d = self.fetch_json(play)
            if d:
                parts = self._extract_play("", d.get("data") if isinstance(d.get("data"), dict) else d)
                if parts:
                    u = parts[0].split("$")[-1]
                    return {"parse": 0, "jx": 0, "url": u, "header": header}
            return {"parse": 1, "jx": 1, "url": play, "header": header}
        # id
        d = self.fetch_json("%s/video/detail?id=%s" % (HOST, urllib.parse.quote(play)))
        if d:
            parts = self._extract_play("", d.get("data") if isinstance(d.get("data"), dict) else d)
            if parts:
                u = parts[0].split("$")[-1]
                return {"parse": 0, "jx": 0, "url": u, "header": header}
        page = "%s/video/detail?id=%s" % (HOST, play)
        return {"parse": 1, "jx": 1, "url": page, "header": header}

    def isVideoFormat(self, url):
        return bool(url and re.search(r"\.(mp4|m3u8|webm)(\?|$)", str(url), re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None


if __name__ == "__main__":
    sp = Spider()
    sp.init()
    print("home", [c["type_name"] for c in sp.homeContent()["class"]])
    r = sp.homeVideoContent()
    print("homeVod", len(r.get("list") or []))
    r2 = sp.categoryContent("home", 1, False, {})
    print("cat", len(r2.get("list") or []))
