# -*- coding: utf-8 -*-
"""
AVJOY https://cn.avjoy.ws
列表 /videos  详情 /video/{id}/slug  直链 mp4 source
入口避免根路径 /（500），用 /videos 或 /enter
"""
import re
from urllib.parse import quote

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def fetch(self, url, headers=None, timeout=15, **kw):
            import requests as rq
            r = rq.get(url, headers=headers or {}, timeout=timeout, verify=False, **kw)
            class R:
                pass
            o = R()
            o.text = r.text
            o.status_code = r.status_code
            o.url = r.url
            return o


HOST = 'https://cn.avjoy.ws'
UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
)

CLASS_LIST = [
    {'type_id': 'videos', 'type_name': '最新视频'},
    {'type_id': 'search:中文字幕', 'type_name': '中文字幕'},
    {'type_id': 'search:无码', 'type_name': '无码'},
    {'type_id': 'search:有码', 'type_name': '有码'},
    {'type_id': 'search:自拍', 'type_name': '自拍'},
    {'type_id': 'search:探花', 'type_name': '探花'},
    {'type_id': 'search:国产', 'type_name': '国产'},
    {'type_id': 'search:FC2', 'type_name': 'FC2'},
    {'type_id': 'search:欧美', 'type_name': '欧美'},
    {'type_id': 'search:韩国', 'type_name': '韩国'},
]


class Spider(BaseSpider):

    def __init__(self):
        try:
            super(Spider, self).__init__()
        except Exception:
            pass
        self.host = HOST
        self._ua = UA

    def init(self, extend=''):
        if extend and str(extend).startswith('http'):
            self.host = str(extend).rstrip('/')
        return True

    def getName(self):
        return 'AVJOY'

    def isVideoFormat(self, url):
        low = (url or '').lower()
        return any(k in low for k in ('.m3u8', '.mp4', '.flv', '.ts'))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def _headers(self):
        return {
            'User-Agent': self._ua,
            'Referer': self.host + '/videos',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }

    def _fetch(self, url, timeout=20):
        if url.startswith('/'):
            url = self.host + url
        try:
            r = self.fetch(url, headers=self._headers(), timeout=timeout)
            return getattr(r, 'text', '') or ''
        except Exception:
            return ''

    def _parse_list(self, html):
        results, seen = [], set()
        if not html:
            return results
        for m in re.finditer(
            r'href=["\'](/video/(\d+)/([^"\']+))["\']',
            html, re.I
        ):
            path, vid, slug = m.group(1), m.group(2), m.group(3)
            if vid in seen:
                continue
            seen.add(vid)
            block = html[max(0, m.start() - 100): m.start() + 500]
            pic = ''
            pm = re.search(r'(?:data-src|src)=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', block, re.I)
            if not pm:
                pm = re.search(r'(?:data-src|src)=["\'](/[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', block, re.I)
            if pm:
                pic = pm.group(1)
                if pic.startswith('/'):
                    pic = self.host + pic
            title = slug.replace('-', ' ')
            tm = re.search(r'(?:alt|title)=["\']([^"\']{2,120})["\']', block)
            if tm:
                title = tm.group(1).strip()
            results.append({
                'vod_id': path,
                'vod_name': title[:120],
                'vod_pic': pic,
                'vod_remarks': '',
            })
        return results

    def homeContent(self, filter=False):
        return {'class': list(CLASS_LIST), 'list': [], 'filters': {}}

    def homeVideoContent(self):
        return {'list': self._parse_list(self._fetch(self.host + '/videos'))[:24]}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        try:
            page = max(1, int(str(pg) or 1))
        except Exception:
            page = 1
        tid = str(tid or 'videos').strip()
        if tid.startswith('search:'):
            key = tid.split(':', 1)[1]
            url = '%s/search/videos/%s' % (self.host, quote(key))
            if page > 1:
                url += '?page=%d' % page
        else:
            url = self.host + '/videos'
            if page > 1:
                url += '?page=%d' % page
        html = self._fetch(url)
        vods = self._parse_list(html)
        return {
            'list': vods,
            'page': page,
            'pagecount': page + 1 if len(vods) >= 12 else page,
            'limit': 24,
            'total': 9999,
        }

    def searchContent(self, key, quick=False, pg='1'):
        try:
            page = max(1, int(str(pg) or 1))
        except Exception:
            page = 1
        url = '%s/search/videos/%s' % (self.host, quote(str(key or '').strip()))
        if page > 1:
            url += '?page=%d' % page
        vods = self._parse_list(self._fetch(url))
        return {
            'list': vods,
            'page': page,
            'pagecount': page + 1 if len(vods) >= 12 else page,
            'limit': 24,
            'total': 9999,
        }

    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, (list, tuple)) else ids
        path = str(raw or '').strip()
        if not path.startswith('http'):
            path = self.host + (path if path.startswith('/') else '/video/' + path)
        html = self._fetch(path)
        name = ''
        m = re.search(r'<title>([^<]+)', html, re.I)
        if m:
            name = re.sub(r'\s*[-|].*AVJOY.*$', '', m.group(1), flags=re.I).strip()
        pic = ''
        m = re.search(r'og:image["\']\s+content=["\']([^"\']+)', html, re.I)
        if m:
            pic = m.group(1)
        plays = []
        seen = set()
        for m in re.finditer(r'<source[^>]+src=["\']([^"\']+)["\']', html, re.I):
            u = m.group(1)
            if u in seen or not u.startswith('http'):
                continue
            seen.add(u)
            label = 'MP4'
            qm = re.search(r'(\d{3,4})p', u, re.I)
            if qm:
                label = qm.group(1) + 'P'
            plays.append((label, u))
        for m in re.finditer(r'(https?://[^"\'\s<>]+\.(?:mp4|m3u8)[^"\'\s<>]*)', html, re.I):
            u = m.group(1)
            if u in seen:
                continue
            seen.add(u)
            plays.append(('直链', u))
        if plays:
            play_from = '$$$'.join([n for n, _ in plays])
            play_url = '$$$'.join(['正片$%s' % u for _, u in plays])
        else:
            play_from = 'AVJOY'
            play_url = '正片$%s' % path
        return {'list': [{
            'vod_id': path,
            'vod_name': name or 'AVJOY',
            'vod_pic': pic,
            'vod_play_from': play_from,
            'vod_play_url': play_url,
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id or '').strip()
        header = {
            'User-Agent': self._ua,
            'Referer': self.host + '/',
        }
        if re.search(r'\.(m3u8|mp4)(\?|$)', url, re.I):
            return {'parse': 0, 'jx': 0, 'url': url, 'header': header}
        return {'parse': 0, 'jx': 0, 'url': '', 'header': header}


if __name__ == '__main__':
    sp = Spider()
    sp.init()
    r = sp.categoryContent('videos', 1)
    print('list', len(r.get('list') or []))
    if r.get('list'):
        d = sp.detailContent([r['list'][0]['vod_id']])
        print(d)
