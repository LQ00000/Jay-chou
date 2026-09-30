# coding=utf-8
"""
StripChat 直播 · 修复播放地址
多域名 failover + 直出 master/清晰度 m3u8
"""
import base64
import json
import re
import sys
import threading
import time
from datetime import datetime, timedelta
from functools import lru_cache
from urllib.parse import quote, urlparse

import requests
from urllib3.util.retry import Retry

sys.path.append("..")
try:
    from base.spider import Spider
except ImportError:
    class Spider(object):
        def getProxyUrl(self):
            return "http://127.0.0.1:9978/proxy?do=py"


class Spider(Spider):
    def init(self, extend="{}"):
        self.create_session_with_retry()
        self.dynamic_urls = [
            "https://zh.stripchat.com",
            "https://zh.stripchat.global",
            "https://zh.stripol.com",
            "https://stripchat.com",
        ]
        self.Doppiocdn = "doppiocdn.org"
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:153.0) Gecko/20100101 Firefox/153.0"
        self.headers = {"User-Agent": ua, "Accept-Language": "zh,en;q=0.5"}
        self.host = self.dynamic_urls[0]
        self._update_headers_for_host(self.host)
        self.stripchat_key = "YzWScuyQRGAGcxx1KIJmiQ7BY9Vi35ftwLqUOVO8uoo="
        self.danmu_cache, self.danmu_threads, self.danmu_lock = {}, {}, threading.Lock()
        self.base_url = ""

    def _update_headers_for_host(self, host_url):
        self.host = host_url
        self.headers["Origin"] = host_url
        self.headers["Referer"] = f"{host_url}/"
        self.json_headers = {**self.headers, "Accept": "application/json, text/plain, */*"}

    def _request_with_failover(self, path, timeout=(5, 12)):
        urls_to_try = list(self.dynamic_urls)
        if self.host in urls_to_try:
            urls_to_try.remove(self.host)
            urls_to_try.insert(0, self.host)
        for domain in urls_to_try:
            clean = domain.strip().rstrip("/")
            full_url = f"{clean}{path}" if path.startswith("/") else f"{clean}/{path}"
            headers = {
                "User-Agent": self.headers.get("User-Agent"),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Origin": clean,
                "Referer": f"{clean}/",
            }
            try:
                r = self.session_get(full_url, headers=headers, timeout=timeout)
                if r and r.status_code == 200:
                    ct = r.headers.get("Content-Type", "")
                    if "application/json" in ct or r.text.strip().startswith("{"):
                        data = r.json()
                        if isinstance(data, dict) and data:
                            if self.host != clean:
                                self._update_headers_for_host(clean)
                            return data
            except Exception:
                pass
        return {}

    def getName(self):
        return "StripChat"

    def isVideoFormat(self, url):
        return bool(url and ".m3u8" in str(url))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def homeVideoContent(self):
        return {"list": []}

    def homeContent(self, filter):
        CLASSES = [
            {"type_name": "女主播", "type_id": "girls"},
            {"type_name": "情侣", "type_id": "couples"},
            {"type_name": "男主播", "type_id": "men"},
            {"type_name": "跨性别", "type_id": "trans"},
        ]
        VALUE = [
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
        VALUE_MEN = [
            {"n": "情侣", "v": "sexGayCouples"},
            {"n": "直男", "v": "orientationStraight"},
        ]
        filters = {
            tid: [{"key": "tag", "name": "标签", "value": (VALUE_MEN + VALUE if tid == "men" else VALUE)}]
            for tid in ("girls", "couples", "men", "trans")
        }
        return {"class": CLASSES, "filters": filters}

    def _parse_status_remark(self, is_live, status, viewers=0):
        if not is_live or status == "off":
            st = "⚫已下播"
        elif status == "public":
            st = "🔴直播中"
        elif status == "groupShow":
            st = "🎫门票房"
        elif status == "ticket":
            st = "🎫购票房"
        else:
            st = f"🎫{status}"
        return f"{st} 👤{viewers}人" if viewers else st

    def _to_vod(self, u):
        status = u.get("status", "off")
        is_live = u.get("isLive", False) or status in ("public", "groupShow", "ticket")
        viewers = u.get("viewersCount", 0)
        uid = str(u.get("id") or "")
        return {
            "vod_id": uid,
            "vod_name": f"{self.country_code_to_flag(str(u.get('country', '')))}{u.get('username', uid)}",
            "vod_pic": f"https://img.{self.Doppiocdn}/snapshot/{uid}/{u.get('snapshotTimestamp', '')}",
            "style": {"type": "rect", "ratio": 1.78},
            "vod_remarks": self._parse_status_remark(is_live, status, viewers),
        }

    def categoryContent(self, tid, pg, filter, extend):
        try:
            extend = extend if isinstance(extend, dict) else {}
            pg_str, page_num = str(pg), int(pg or 1)
            if str(tid).startswith("search "):
                parts = str(tid).split(maxsplit=2)
                tag = parts[1] if len(parts) > 1 else "girls"
                key = parts[2] if len(parts) > 2 else ""
                path = f"/api/front/v4/models/search/group/username?query={quote(key)}&limit=100&primaryTag={tag}"
                rsp = self._request_with_failover(path)
                videos = [self._to_vod(u) for u in rsp.get("models", [])]
                return {
                    "list": videos,
                    "page": pg_str,
                    "pagecount": "1",
                    "limit": "100",
                    "total": str(len(videos)),
                }
            limit, offset = 60, 60 * (page_num - 1)
            path = (
                f"/api/front/models?improveTs=false&removeShows=false&limit={limit}"
                f"&offset={offset}&primaryTag={tid}&sortBy=stripRanking&rcmGrp=A"
                f"&rbCnGr=true&prxCnGr=false&nic=false"
            )
            if extend.get("tag"):
                path += f'&filterGroupTags=[["{extend["tag"]}"]]'
            rsp = self._request_with_failover(path)
            videos = [self._to_vod(v) for v in rsp.get("models", [])]
            total = int(rsp.get("filteredCount", 0) or len(videos))
            return {
                "list": videos,
                "page": pg_str,
                "pagecount": str(max(1, (total + limit - 1) // limit)),
                "limit": str(limit),
                "total": str(total),
            }
        except Exception:
            return {"list": [], "page": str(pg), "pagecount": "1", "limit": "60", "total": "0"}

    def detailContent(self, array):
        if not array:
            return {"list": []}
        uid = str(array[0]).strip()
        # 多条线路，播放时实时解析清晰度
        return {
            "list": [
                {
                    "vod_id": uid,
                    "vod_name": f"StripChat {uid}",
                    "vod_pic": f"https://img.{self.Doppiocdn}/snapshot/{uid}/",
                    "vod_content": "Stripchat 直播流",
                    "vod_remarks": "🔴 直播中",
                    "vod_play_from": "doppio$$$sacf$$$直连",
                    "vod_play_url": f"自动${uid}$$$自动$sacf_{uid}$$$自动$direct_{uid}",
                }
            ]
        }

    def searchContent(self, key, quick, pg="1"):
        if int(pg or 1) > 1:
            return {"list": []}
        return {
            "list": [
                {
                    "vod_id": f'search {t["type_id"]} {key}',
                    "vod_name": t["type_name"] + " · " + str(key),
                    "vod_tag": "folder",
                }
                for t in self.homeContent(False).get("class", [])
            ]
        }

    def _master_urls(self, sid):
        return [
            f"https://edge-hls.doppiocdn.org/hls/{sid}/master/{sid}_auto.m3u8?playlistType=lowLatency",
            f"https://edge-hls.doppiocdn.com/hls/{sid}/master/{sid}_auto.m3u8?playlistType=lowLatency",
            f"https://edge-hls.sacfedge.com/hls/{sid}/master/{sid}_auto.m3u8?playlistType=lowLatency",
            f"https://edge-hls.doppiocdn.org/hls/{sid}/master/{sid}.m3u8",
        ]

    def _parse_master(self, text, headers):
        """解析 master，返回 [(name, url), ...]"""
        out = []
        if not text or "#EXTM3U" not in text:
            return out
        lines = text.strip().split("\n")
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
            nxt = (lines[i + 1] if i + 1 < len(lines) else "").strip()
            if nxt and nxt.startswith("http"):
                out.append((qn, nxt))
        return out

    def playerContent(self, flag, id, vipFlags):
        sid = str(id or "").strip()
        if "_" in sid:
            sid = sid.split("_")[-1]
        headers = {
            "User-Agent": self.headers.get("User-Agent"),
            "Origin": self.host,
            "Referer": f"{self.host}/",
            "Accept": "*/*",
        }
        # 按线路选择 CDN 顺序
        masters = self._master_urls(sid)
        fl = str(flag or "").lower()
        if "sacf" in fl or str(id).startswith("sacf"):
            masters = [
                f"https://edge-hls.sacfedge.com/hls/{sid}/master/{sid}_auto.m3u8?playlistType=lowLatency",
            ] + masters

        # 1) 尝试解析清晰度列表
        qualities = []
        best_master = masters[0]
        for mu in masters:
            try:
                r = self.session_get(mu, headers=headers, timeout=10)
                if r and r.status_code == 200 and "#EXTM3U" in r.text:
                    best_master = mu
                    qualities = self._parse_master(r.text, headers)
                    if qualities:
                        break
            except Exception:
                continue

        # 2) 有清晰度：返回多清晰度（直链，不强制代理）
        if qualities:
            urls = []
            for name, u in qualities:
                urls.extend([name, u])
            return {
                "parse": 0,
                "jx": 0,
                "url": urls,
                "header": headers,
                "format": "application/x-mpegURL",
            }

        # 3) 无清晰度：直接返回 master（避免空数组导致「暂无播放数据」）
        return {
            "parse": 0,
            "jx": 0,
            "url": best_master,
            "header": headers,
            "format": "application/x-mpegURL",
        }

    # ---------- 代理（可选，解密 MOUFLON）----------
    def localProxy(self, param):
        url = (param or {}).get("url", "")
        type_ = (param or {}).get("type", "")
        headers = {
            "User-Agent": self.headers.get("User-Agent"),
            "Origin": self.host,
            "Referer": f"{self.host}/",
        }
        if type_ == "media":
            try:
                data = self.session_get(url, headers=headers, timeout=(5, 15))
                if data and data.status_code == 200:
                    return [200, "video/mp4", data.content]
            except Exception:
                pass
            return [404, "text/plain", b""]
        try:
            rsp = self.session_get(url, headers=headers, timeout=(5, 15))
            if not rsp or rsp.status_code != 200:
                return [404, "text/plain", b""]
            data = rsp.text
            if "#EXT-X-MOUFLON:URI:" in data:
                data = self.process_m3u8(data)
            return [200, "application/vnd.apple.mpegurl", data]
        except Exception:
            return [404, "text/plain", b""]

    def process_m3u8(self, content):
        lines = content.strip().split("\n")
        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-MOUFLON:URI:") and i + 1 < len(lines) and "media.mp4" in lines[i + 1]:
                mouflon = line.split(":", 2)[2].strip()
                try:
                    encrypted = re.sub(r"(_part\d+)?\.mp4$", "", mouflon).rsplit("_", 2)[1]
                    new_url = mouflon.replace(
                        encrypted, self._decode(encrypted[::-1], self.stripchat_key)
                    )
                    lines[i + 1] = re.sub(
                        r"https://media-hls\.doppiocdn\.\w+/b-hls-\d+/media\.mp4",
                        f"{self.getProxyUrl()}&type=media&url={quote(new_url)}",
                        lines[i + 1],
                    )
                except Exception:
                    pass
            elif line.startswith("#EXT-X-MAP:URI"):
                match = re.search(r'URI=["\']?(https?://[^\s"\'<>]+)["\']?', line)
                if match:
                    original_url = match.group(1)
                    lines[i] = line.replace(
                        original_url,
                        f"{self.getProxyUrl()}&type=media&url={quote(original_url)}",
                    )
        return "\n".join(lines)

    def country_code_to_flag(self, code):
        code = str(code or "")
        if len(code) == 2 and code.isalpha():
            return "".join(chr(ord(c.upper()) - ord("A") + 0x1F1E6) for c in code)
        return code

    @staticmethod
    @lru_cache(maxsize=20)
    def _decode(encrypted_b64, key_b64):
        encrypted_b64 += "=" * ((4 - len(encrypted_b64) % 4) % 4)
        key_bytes = base64.b64decode(key_b64)
        encrypted = base64.b64decode(encrypted_b64)
        decrypted = bytearray(len(encrypted))
        for i in range(len(encrypted)):
            decrypted[i] = encrypted[i] ^ (key_bytes[i % len(key_bytes)] & 0xFF)
        return decrypted.decode("utf-8")

    def create_session_with_retry(self):
        self.session = requests.Session()
        retry = Retry(
            total=2,
            backoff_factor=0.2,
            status_forcelist=[408, 429, 500, 502, 503, 504],
        )
        adapter = requests.adapters.HTTPAdapter(
            max_retries=retry, pool_connections=20, pool_maxsize=50
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def session_get(self, url, headers=None, stream=False, timeout=(5, 12)):
        return self.session.get(
            url,
            headers=self.headers if headers is None else headers,
            timeout=timeout,
            stream=stream,
            allow_redirects=True,
        )


