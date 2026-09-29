#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
酷6网 Spider（按 drpy 可用规则修复）
https://www.ku6.com
列表: /video/feed 字段 title/picPath/publisher/playUrl
播放: playUrl 直链；detail.html 走 news-stream.lsttnews.com 取 src
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
PLAY_API = "https://news-stream.lsttnews.com/topic/recommend/vinfo?vid="
UA_MOBILE = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# 与可用 drpy 规则一致
CHANNELS = [
    ("69", "资讯"),
    ("70", "娱乐"),
    ("76", "搞笑"),
    ("73", "少儿"),
    ("71", "自制节目"),
    ("72", "影视"),
    ("74", "音乐"),
    ("75", "原创"),
    ("80", "生活"),
    ("93", "游戏"),
    ("81", "健康"),
    ("47", "汽车"),
    ("149", "时事"),
]


class Spider(BaseSpider):
    def getName(self):
        return "酷6网"

    def init(self, extend=""):
        pass

    def _headers(self, mobile=True):
        return {
            "User-Agent": UA_MOBILE if mobile else UA,
            "Referer": HOST + "/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        }

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

    def fetch_text(self, url, mobile=True):
        try:
            if requests is not None:
                r = requests.get(
                    url, headers=self._headers(mobile), timeout=15,
                    verify=False, allow_redirects=True,
                )
                return r.text or ""
            req = urllib.request.Request(url, headers=self._headers(mobile))
            with urllib.request.urlopen(req, timeout=15) as resp:
                return self._decode(resp.read())
        except Exception as e:
            print("fetch err", url, e)
            return ""

    def fetch_json(self, url, mobile=True):
        txt = self.fetch_text(url, mobile)
        if not txt:
            return None
        try:
            return json.loads(txt)
        except Exception:
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
        return re.sub(r"\s+", " ", t).strip()

    def _pick(self, it, *keys):
        for k in keys:
            v = it.get(k) if isinstance(it, dict) else None
            if v is not None and str(v).strip():
                return v
        return ""

    def _item(self, it):
        """json:data;title;picPath;publisher;playUrl"""
        if not isinstance(it, dict):
            return None
        title = self._clean(self._pick(it, "title", "name", "videoName"))
        pic = self._abs(self._pick(it, "picPath", "pic", "cover", "img", "poster", "thumb"))
        play = str(self._pick(it, "playUrl", "play_url", "url", "mp4", "videoUrl") or "").replace("\\/", "/")
        pub = self._clean(self._pick(it, "publisher", "author", "userName"))
        vid = str(self._pick(it, "id", "vid", "videoId", "rid") or "")

        # playUrl 里可能带 detail.html~vid
        if not vid and play:
            m = re.search(r"[?&]vid=([^&]+)", play) or re.search(r"~(\w+)$", play)
            if m:
                vid = m.group(1)
            elif re.search(r"\.(mp4|m3u8)(\?|$)", play, re.I):
                vid = play
            else:
                vid = play

        if not title:
            return None
        if not vid:
            vid = title

        # 详情 id：优先可解析的 play 信息
        # 存 play 到 remarks 旁：用 vod_id 编码 play 信息
        # 格式： 若 play 是直链 -> vod_id=play；若是 detail -> vod_id=detail~vid
        if play and "detail.html" in play:
            # 保证带 ~vid
            if "~" not in play and vid and vid != play:
                play = play.rstrip("/") + "~" + vid
            vod_id = play
        elif play and re.search(r"\.(mp4|m3u8)(\?|$)", play, re.I):
            vod_id = play
        else:
            vod_id = vid if vid else play

        remarks = pub[:20] if pub else ""
        return {
            "vod_id": vod_id,
            "vod_name": title[:120],
            "vod_pic": pic,
            "vod_remarks": remarks,
            "style": {"type": "rect", "ratio": 1.78},
        }

    def _feed(self, subject="", page=0, size=20):
        page = max(0, int(page or 0))
        size = int(size or 20)
        if subject and str(subject).isdigit():
            url = "%s/video/feed?subjectId=%s&pageNo=%d&pageSize=%d" % (HOST, subject, page, size)
        else:
            url = "%s/video/feed?pageNo=%d&pageSize=%d" % (HOST, page, size)
        d = self.fetch_json(url)
        arr = []
        if isinstance(d, dict):
            data = d.get("data")
            if isinstance(data, list):
                arr = data
            elif isinstance(data, dict):
                arr = data.get("list") or data.get("records") or []
            else:
                arr = d.get("list") or []
        elif isinstance(d, list):
            arr = d
        out = []
        for it in arr:
            v = self._item(it)
            if v:
                out.append(v)
        return out

    def homeContent(self, filter=False):
        classes = [{"type_id": c[0], "type_name": c[1]} for c in CHANNELS]
        return {"class": classes, "filters": {}, "list": []}

    def homeVideoContent(self):
        return {"list": self._feed("", 0, 20)}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg or 1)
        tid = str(tid or "76")
        # drpy: pageNo=fypage 通常从 0 或 1；原规则 fypage 多为 0 起
        videos = self._feed(tid if tid.isdigit() else "", max(pg - 1, 0), 20)
        return {
            "list": videos,
            "page": pg,
            "pagecount": pg + 1 if len(videos) >= 10 else max(pg, 1),
            "limit": 20,
            "total": 9999 if videos else 0,
        }

    def searchContent(self, key, quick=False, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick=False, pg=1):
        # 原规则 searchable:0，保留空搜
        return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}

    def _resolve_play(self, raw):
        """对应 lazy 逻辑"""
        raw = str(raw or "").strip()
        if not raw:
            return ""
        # 已是媒体直链
        if re.search(r"\.(mp4|m3u8|flv)(\?|$)", raw, re.I) and raw.startswith("http"):
            return raw
        # detail.html~vid
        if "detail.html" in raw or "~" in raw:
            vid = ""
            if "~" in raw:
                vid = raw.split("~")[-1].strip()
            if not vid:
                m = re.search(r"[?&]vid=([^&]+)", raw)
                if m:
                    vid = m.group(1)
            if vid:
                d = self.fetch_json(PLAY_API + urllib.parse.quote(vid))
                if isinstance(d, dict):
                    data = d.get("data") or {}
                    video = data.get("video") if isinstance(data, dict) else {}
                    if isinstance(video, dict):
                        src = video.get("src") or video.get("url") or video.get("playUrl") or ""
                        if src:
                            return str(src).replace("\\/", "/")
                    # 兼容其它字段
                    for k in ("src", "url", "playUrl", "mp4"):
                        if data.get(k):
                            return str(data[k]).replace("\\/", "/")
        # 尝试当 vid 查
        if re.match(r"^[\w\-]+$", raw) and not raw.startswith("http"):
            d = self.fetch_json(PLAY_API + urllib.parse.quote(raw))
            if isinstance(d, dict):
                data = d.get("data") or {}
                video = data.get("video") if isinstance(data, dict) else {}
                if isinstance(video, dict) and video.get("src"):
                    return str(video["src"]).replace("\\/", "/")
        if raw.startswith("http"):
            return raw
        return ""

    def detailContent(self, ids):
        raw = str((ids or [""])[0]).strip()
        if not raw:
            return {"list": []}

        play = self._resolve_play(raw)
        name = "酷6视频"
        pic = ""
        # 若是直链，用文件名；若是 detail，保留
        if "detail.html" in raw or "~" in raw:
            name = "酷6网视频"
        elif re.search(r"\.(mp4|m3u8)", raw, re.I):
            name = "酷6视频"

        # 再拉一次 feed 信息意义不大，直接出播放
        if not play:
            play = raw if raw.startswith("http") else ""

        if not play:
            return {"list": [{
                "vod_id": raw,
                "vod_name": name,
                "vod_pic": pic,
                "vod_content": "酷6网视频",
                "vod_play_from": "酷6",
                "vod_play_url": "播放$%s" % raw,
            }]}

        return {"list": [{
            "vod_id": raw,
            "vod_name": name if name else "酷6视频",
            "vod_pic": pic,
            "vod_content": "酷6网视频",
            "vod_play_from": "酷6",
            "vod_play_url": "播放$%s" % play,
            "style": {"type": "rect", "ratio": 1.78},
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        header = {
            "User-Agent": UA_MOBILE,
            "Referer": HOST + "/",
            "Origin": HOST,
        }
        raw = str(id or "").strip()
        if "$" in raw:
            raw = raw.split("$")[-1].strip()
        play = self._resolve_play(raw)
        if not play:
            play = raw
        if play and re.search(r"\.(mp4|m3u8|flv)(\?|$)", play, re.I):
            return {
                "parse": 0, "jx": 0, "url": play, "header": header,
                "format": "application/x-mpegURL" if ".m3u8" in play.lower() else "video/mp4",
            }
        if play.startswith("http"):
            return {"parse": 0, "jx": 0, "url": play, "header": header}
        return {"parse": 1, "jx": 1, "url": play or raw, "header": header}

    def isVideoFormat(self, url):
        return bool(url and re.search(r"\.(mp4|m3u8|flv)(\?|$)", str(url), re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None


if __name__ == "__main__":
    sp = Spider()
    sp.init()
    print("classes", [c["type_name"] for c in sp.homeContent()["class"]])
    print("feed home", len(sp.homeVideoContent().get("list") or []))
    print("cat 76", len(sp.categoryContent("76", 1, False, {}).get("list") or []))
