# coding=utf-8
"""
StripChat 直播 · 修复播放（详情直出清晰度 m3u8，对齐可用 JS）
"""
import re
import sys
from urllib.parse import quote

import requests
from urllib3.util.retry import Retry

sys.path.append("..")
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def getProxyUrl(self, *a, **k):
            return "http://127.0.0.1:9978/proxy?do=py"


class Spider(BaseSpider):
    def init(self, extend="{}"):
        self.dynamic_urls = [
            "https://zh.stripchat.com",
            "https://zh.stripchat.global",
            "https://zh.stripol.com",
            "https://stripchat.com",
        ]
        self.Doppiocdn = "doppiocdn.org"
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:153.0) Gecko/20100101 Firefox/153.0"
        self.host = self.dynamic_urls[0]
        self.headers = {
            "User-Agent": self.ua,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Origin": self.host,
            "Referer": self.host + "/",
        }
        self.session = requests.Session()
        retry = Retry(total=2, backoff_factor=0.2, status_forcelist=[408, 429, 500, 502, 503, 504])
        ad = requests.adapters.HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=50)
        self.session.mount("http://", ad)
        self.session.mount("https://", ad)

    def getName(self):
        return "StripChat"

    def isVideoFormat(self, url):
        return bool(url and ".m3u8" in str(url))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def _update_host(self, host_url):
        self.host = host_url.rstrip("/")
        self.headers["Origin"] = self.host
        self.headers["Referer"] = self.host + "/"

    def _api(self, path, timeout=12):
        order = [self.host] + [h for h in self.dynamic_urls if h.rstrip("/") != self.host.rstrip("/")]
        for domain in order:
            clean = domain.strip().rstrip("/")
            url = clean + (path if path.startswith("/") else "/" + path)
            headers = {
                "User-Agent": self.ua,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Origin": clean,
                "Referer": clean + "/",
            }
            try:
                r = self.session.get(url, headers=headers, timeout=timeout, verify=False)
                if r is not None and r.status_code == 200:
                    ct = r.headers.get("Content-Type", "")
                    if "json" in ct or (r.text and r.text.strip()[:1] == "{"):
                        data = r.json()
                        if isinstance(data, dict) and data:
                            if self.host != clean:
                                self._update_host(clean)
                            return data
            except Exception:
                continue
        return {}

    def _get_text(self, url, timeout=10):
        headers = {
            "User-Agent": self.ua,
            "Origin": self.host,
            "Referer": self.host + "/",
            "Accept": "*/*",
        }
        try:
            r = requests.get(url, headers=headers, timeout=timeout, verify=False, allow_redirects=True)
            if r is not None and r.status_code == 200:
                return r.text or ""
        except Exception:
            pass
        try:
            r = self.session.get(url, headers=headers, timeout=timeout, verify=False)
            if r is not None and r.status_code == 200:
                return r.text or ""
        except Exception:
            pass
        return ""

    def homeContent(self, filter):
        classes = [
            {"type_name": "女主播", "type_id": "girls"},
            {"type_name": "情侣", "type_id": "couples"},
            {"type_name": "男主播", "type_id": "men"},
            {"type_name": "跨性别", "type_id": "trans"},
        ]
        value = [
            {"n": "新主播", "v": "autoTagNew"},
            {"n": "推荐", "v": "recommended"},
            {"n": "炮机", "v": "fuckMachine"},
            {"n": "青年", "v": "ageTeen"},
            {"n": "VR", "v": "autoTagVr"},
            {"n": "亚洲人", "v": "ethnicityAsian"},
            {"n": "🇨🇳中国", "v": "tagLanguageChinese"},
            {"n": "🇯🇵日本", "v": "tagLanguageJapanese"},
            {"n": "🇰🇷韩国", "v": "tagLanguageKorean"},
            {"n": "白人", "v": "ethnicityWhite"},
            {"n": "拉丁", "v": "ethnicityLatino"},
            {"n": "黑人", "v": "ethnicityEbony"},
            {"n": "口交", "v": "doBlowjob"},
            {"n": "自慰", "v": "doMasturbation"},
            {"n": "肛交", "v": "doAnal"},
            {"n": "Cosplay", "v": "doCosplay"},
        ]
        filters = {
            tid: [{"key": "tag", "name": "标签", "value": value}]
            for tid in ("girls", "couples", "men", "trans")
        }
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        return self.categoryContent("girls", "1", False, {})

    def country_code_to_flag(self, code):
        code = str(code or "")
        if len(code) == 2 and code.isalpha():
            return "".join(chr(ord(c.upper()) - ord("A") + 0x1F1E6) for c in code)
        return code

    def _remark(self, is_live, status, viewers=0):
        if not is_live or status == "off":
            st = "⚫已下播"
        elif status == "public":
            st = "🔴直播中"
        elif status in ("groupShow", "ticket"):
            st = "🎫门票房"
        else:
            st = "🎫" + str(status)
        return ("%s 👤%d人" % (st, viewers)) if viewers else st

    def _to_vod(self, u):
        status = u.get("status", "off")
        is_live = u.get("isLive", False) or status in ("public", "groupShow", "ticket")
        viewers = int(u.get("viewersCount") or 0)
        uid = str(u.get("id") or "")
        return {
            "vod_id": uid,
            "vod_name": "%s%s" % (self.country_code_to_flag(str(u.get("country", ""))), u.get("username", uid)),
            "vod_pic": "https://img.%s/snapshot/%s/%s" % (self.Doppiocdn, uid, u.get("snapshotTimestamp", "")),
            "style": {"type": "rect", "ratio": 1.78},
            "vod_remarks": self._remark(is_live, status, viewers),
        }

    def categoryContent(self, tid, pg, filter, extend):
        try:
            extend = extend if isinstance(extend, dict) else {}
            page_num = int(pg or 1)
            tid = str(tid or "girls")
            if tid.startswith("search "):
                parts = tid.split(maxsplit=2)
                tag = parts[1] if len(parts) > 1 else "girls"
                key = parts[2] if len(parts) > 2 else ""
                path = "/api/front/v4/models/search/group/username?query=%s&limit=100&primaryTag=%s" % (
                    quote(key), quote(tag)
                )
                rsp = self._api(path)
                videos = [self._to_vod(u) for u in (rsp.get("models") or [])]
                return {"list": videos, "page": page_num, "pagecount": 1, "limit": 100, "total": len(videos)}

            limit, offset = 60, 60 * (page_num - 1)
            path = (
                "/api/front/models?improveTs=false&removeShows=false&limit=%d&offset=%d"
                "&primaryTag=%s&sortBy=stripRanking&rcmGrp=A&rbCnGr=true&prxCnGr=false&nic=false"
            ) % (limit, offset, quote(tid))
            if extend.get("tag"):
                path += "&filterGroupTags=[[\"%s\"]]" % str(extend["tag"]).replace('"', "")
            rsp = self._api(path)
            models = rsp.get("models") or []
            videos = [self._to_vod(v) for v in models]
            total = int(rsp.get("filteredCount") or len(videos) or 0)
            return {
                "list": videos,
                "page": page_num,
                "pagecount": max(1, (total + limit - 1) // limit) if total else (page_num + 1 if videos else 1),
                "limit": limit,
                "total": total or len(videos),
            }
        except Exception:
            return {"list": [], "page": int(pg or 1), "pagecount": 1, "limit": 60, "total": 0}

    def searchContent(self, key, quick, pg="1"):
        if int(pg or 1) > 1:
            return {"list": []}
        return {
            "list": [
                {
                    "vod_id": "search %s %s" % (t["type_id"], key),
                    "vod_name": "%s · %s" % (t["type_name"], key),
                    "vod_tag": "folder",
                    "vod_remarks": "搜索",
                }
                for t in self.homeContent(False).get("class", [])
            ]
        }

    def _master_urls(self, sid):
        return [
            "https://edge-hls.sacfedge.com/hls/%s/master/%s_auto.m3u8?playlistType=lowLatency" % (sid, sid),
            "https://edge-hls.doppiocdn.org/hls/%s/master/%s_auto.m3u8?playlistType=lowLatency" % (sid, sid),
            "https://edge-hls.doppiocdn.com/hls/%s/master/%s_auto.m3u8?playlistType=lowLatency" % (sid, sid),
            "https://edge-hls.doppiocdn.org/hls/%s/master/%s.m3u8" % (sid, sid),
        ]

    def _parse_master(self, text):
        out = []
        if not text or "#EXTM3U" not in text:
            return out
        lines = text.replace("\r", "").split("\n")
        for i, line in enumerate(lines):
            if "#EXT-X-STREAM-INF" not in line:
                continue
            qn = "HD"
            m = re.search(r'NAME="([^"]+)"', line)
            if m:
                qn = m.group(1)
            else:
                m = re.search(r"RESOLUTION=(\d+x\d+)", line)
                if m:
                    qn = m.group(1)
                else:
                    m = re.search(r"BANDWIDTH=(\d+)", line)
                    if m:
                        qn = "%sk" % (int(m.group(1)) // 1000)
            nxt = (lines[i + 1] if i + 1 < len(lines) else "").strip()
            if nxt.startswith("http"):
                out.append((qn, nxt))
        return out

    def _resolve_qualities(self, sid):
        """返回 [(name, url), ...] 优先高清"""
        for mu in self._master_urls(sid):
            text = self._get_text(mu, timeout=10)
            quals = self._parse_master(text)
            if quals:
                return quals, mu
        # 无清晰度时退 master
        masters = self._master_urls(sid)
        return [("自动", masters[0])], masters[0]

    def detailContent(self, array):
        if not array:
            return {"list": []}
        uid = str(array[0]).strip()
        if "_" in uid and not uid.isdigit():
            # lemon_xxx / sacf_xxx
            uid = uid.split("_")[-1]
        quals, master = self._resolve_qualities(uid)
        # 多线路：每条 CDN 一组；清晰度用 # 分隔，方便壳直接播
        # 线路一：各清晰度直链
        line1 = "#".join("%s$%s" % (n, u) for n, u in quals) if quals else ("自动$%s" % master)
        # 线路二/三：其它 master 兜底
        masters = self._master_urls(uid)
        line2 = "自动$%s" % masters[1] if len(masters) > 1 else line1
        line3 = "自动$%s" % masters[0]
        return {
            "list": [{
                "vod_id": uid,
                "vod_name": "StripChat %s" % uid,
                "vod_pic": "https://img.%s/snapshot/%s/" % (self.Doppiocdn, uid),
                "vod_content": "Stripchat 直播流",
                "vod_remarks": "🔴 直播",
                "vod_play_from": "清晰度$$$线路二$$$线路三",
                "vod_play_url": "%s$$$%s$$$%s" % (line1, line2, line3),
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        sid = str(id or "").strip()
        # 可能是 480p$url 或 纯 url 或 纯 id
        if "$" in sid:
            sid = sid.split("$")[-1].strip()
        if sid.startswith("http") and ".m3u8" in sid:
            headers = {
                "User-Agent": self.ua,
                "Origin": self.host,
                "Referer": self.host + "/",
                "Accept": "*/*",
            }
            # 媒体 CDN 用自身 origin 更稳
            m = re.match(r"https?://([^/]+)", sid)
            if m:
                cdn = m.group(1)
                if "doppio" in cdn or "sacf" in cdn:
                    headers["Origin"] = "https://" + cdn
                    headers["Referer"] = "https://" + cdn + "/"
            return {"parse": 0, "jx": 0, "url": sid, "header": headers}

        if "_" in sid:
            sid = sid.split("_")[-1]
        headers = {
            "User-Agent": self.ua,
            "Origin": self.host,
            "Referer": self.host + "/",
            "Accept": "*/*",
        }
        quals, master = self._resolve_qualities(sid)
        if quals:
            best = quals[0][1]
            m = re.match(r"https?://([^/]+)", best)
            if m:
                cdn = m.group(1)
                headers["Origin"] = "https://" + cdn
                headers["Referer"] = "https://" + cdn + "/"
            return {"parse": 0, "jx": 0, "url": best, "header": headers}
        return {"parse": 0, "jx": 0, "url": master, "header": headers}

    def localProxy(self, param):
        return None
