# -*- coding: utf-8 -*-
"""
AVJOY https://cn.avjoy.ws  兼容影视仓/OK影视
"""
import re
import json
from urllib.parse import quote

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

try:
    import requests as req_lib
except Exception:
    req_lib = None

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
            o.content = getattr(r, 'content', b'')
            o.status_code = r.status_code
            o.url = r.url
            return o


HOSTS = [
    'https://cn.avjoy.ws',
    'https://www.avjoy.ws',
    'https://avjoy.ws',
]
UA = (
    'Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36'
)

CLASS_LIST = [
    {'type_id': 'videos', 'type_name': '全部影片'},
    {'type_id': 'videos/amateur', 'type_name': 'Amateur・素人'},
    {'type_id': 'videos/anal', 'type_name': 'Anal・アナル・肛交'},
    {'type_id': 'videos/asian', 'type_name': 'Asian・アジア'},
    {'type_id': 'videos/japan', 'type_name': 'Japan・日本'},
    {'type_id': 'videos/jav', 'type_name': 'JAV・日本AV'},
    {'type_id': 'videos/china', 'type_name': 'China・中國'},
    {'type_id': 'videos/korea', 'type_name': 'Korea・韓國'},
    {'type_id': 'videos/big-tits', 'type_name': 'Big Tits・巨乳'},
    {'type_id': 'videos/mature', 'type_name': 'Mature・熟女'},
    {'type_id': 'videos/wife', 'type_name': 'Wife・人妻'},
    {'type_id': 'videos/teen', 'type_name': 'Teen・少女'},
    {'type_id': 'videos/uncensored', 'type_name': '無碼'},
    {'type_id': 'videos/sm', 'type_name': 'SM'},
]


class Spider(BaseSpider):

    def __init__(self):
        try:
            super(Spider, self).__init__()
        except Exception:
            pass
        self.host = HOSTS[0]
        self._ua = UA

    def init(self, extend=''):
        if extend and str(extend).startswith('http'):
            self.host = str(extend).rstrip('/')
        return self

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
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

    def _fetch(self, url, timeout=25):
        if url.startswith('/'):
            url = self.host + url
        # 禁止根路径
        for h in HOSTS:
            if url.rstrip('/') == h.rstrip('/'):
                url = h + '/videos'
                break
        hosts_try = [self.host] + [x for x in HOSTS if x != self.host]
        path = url
        for h in hosts_try:
            if url.startswith('http'):
                # 换 host
                for hh in HOSTS:
                    if url.startswith(hh):
                        path = h + url[len(hh):]
                        break
                else:
                    path = url
            else:
                path = h + (url if url.startswith('/') else '/' + url)
            text = ''
            if req_lib is not None:
                try:
                    r = req_lib.get(path, headers=self._headers(), timeout=timeout, verify=False)
                    if r.status_code == 200 and len(r.text) > 800:
                        self.host = h
                        text = r.text
                except Exception:
                    text = ''
            if not text:
                try:
                    r = self.fetch(path, headers=self._headers(), timeout=timeout)
                    text = getattr(r, 'text', '') or ''
                    if len(text) > 800:
                        self.host = h
                except Exception:
                    text = ''
            if text and len(text) > 800:
                if '\\/video' in text or 'href=\\"' in text:
                    text = text.replace('\\/', '/').replace('\\"', '"').replace('\\n', '\n')
                return text
        return ''

    def _parse_list(self, html):
        results, seen = [], set()
        if not html:
            return results
        for m in re.finditer(r'href=["\'](/video/(\d+)/([^"\'?#]+))["\']', html, re.I):
            path, vid, slug = m.group(1), m.group(2), m.group(3)
            if vid in seen:
                continue
            seen.add(vid)
            block = html[max(0, m.start() - 200): m.start() + 700]
            pic = ''
            pm = re.search(
                r'(?:data-src|src)=["\']((?:https?:)?//?[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
                block, re.I
            )
            if pm:
                pic = pm.group(1)
                if pic.startswith('//'):
                    pic = 'https:' + pic
                elif pic.startswith('/'):
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
        # 同时带一页列表，部分壳只读 list
        try:
            lst = self._parse_list(self._fetch(self.host + '/videos'))[:20]
        except Exception:
            lst = []
        return {'class': list(CLASS_LIST), 'list': lst, 'filters': {}}

    def homeVideoContent(self):
        return {'list': self._parse_list(self._fetch(self.host + '/videos'))[:24]}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        try:
            page = max(1, int(str(pg) or 1))
        except Exception:
            page = 1
        tid = str(tid or 'videos').strip().lstrip('/')
        if tid.startswith('search:'):
            key = tid.split(':', 1)[1]
            url = '%s/search/videos/%s' % (self.host, quote(key))
        elif tid in ('videos', 'all', '全部', '全部影片'):
            url = self.host + '/videos'
        elif tid.startswith('videos/'):
            url = self.host + '/' + tid
        else:
            url = self.host + '/videos/' + tid
        if page > 1:
            url += ('&' if '?' in url else '?') + 'page=%d' % page
        html = self._fetch(url)
        vods = self._parse_list(html)
        if len(vods) < 2:
            html = self._fetch(self.host + '/videos')
            vods = self._parse_list(html)
        return {
            'list': vods or [],
            'page': page,
            'pagecount': page + 1 if len(vods) >= 12 else max(page, 1),
            'limit': 24,
            'total': max(len(vods), 1) * 50 if vods else 0,
        }

    def searchContent(self, key, quick=False, pg=1):
        try:
            page = max(1, int(str(pg) or 1))
        except Exception:
            page = 1
        url = '%s/search/videos/%s' % (self.host, quote(str(key or '').strip()))
        if page > 1:
            url += '?page=%d' % page
        vods = self._parse_list(self._fetch(url))
        return {
            'list': vods or [],
            'page': page,
            'pagecount': page + 1 if len(vods) >= 12 else page,
            'limit': 24,
            'total': 9999 if vods else 0,
        }

    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, (list, tuple)) else ids
        path = str(raw or '').strip()
        if not path.startswith('http'):
            path = self.host + (path if path.startswith('/') else '/video/' + path)
        html = self._fetch(path)
        name = ''
        m = re.search(r'<title>([^<]+)', html or '', re.I)
        if m:
            name = re.sub(r'\s*[-|].*AVJOY.*$', '', m.group(1), flags=re.I).strip()
        pic = ''
        m = re.search(r'og:image["\']\s+content=["\']([^"\']+)', html or '', re.I)
        if m:
            pic = m.group(1)
        plays = []
        seen = set()
        for m in re.finditer(r'<source[^>]+src=["\']([^"\']+)["\']', html or '', re.I):
            u = m.group(1)
            if not u.startswith('http') or u in seen:
                continue
            seen.add(u)
            label = 'MP4'
            qm = re.search(r'(\d{3,4})p|_([Hh][Dd])', u)
            if qm:
                label = (qm.group(1) or qm.group(2) or 'HD').upper()
                if label == 'HD':
                    label = '高清'
            plays.append((label, u))
        for m in re.finditer(r'(https?://[^"\'\s<>]+\.(?:mp4|m3u8)[^"\'\s<>]*)', html or '', re.I):
            u = m.group(1)
            if u in seen:
                continue
            seen.add(u)
            plays.append(('直链', u))
        if plays:
            # 单线路多清晰度用 # 分隔，兼容部分壳
            if len(plays) == 1:
                play_from = 'AVJOY'
                play_url = '正片$%s' % plays[0][1]
            else:
                play_from = 'AVJOY'
                play_url = '#'.join(['%s$%s' % (n, u) for n, u in plays])
        else:
            play_from = 'AVJOY'
            play_url = '正片$%s' % path
        return {'list': [{
            'vod_id': path,
            'vod_name': name or 'AVJOY',
            'vod_pic': pic,
            'vod_content': name or '',
            'vod_play_from': play_from,
            'vod_play_url': play_url,
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id or '').strip()
        if '$' in url and not url.startswith('http'):
            url = url.split('$')[-1]
        header = {
            'User-Agent': self._ua,
            'Referer': self.host + '/',
            'Origin': self.host,
        }
        if re.search(r'\.(m3u8|mp4)(\?|$)', url, re.I):
            return {'parse': 0, 'jx': 0, 'url': url, 'playUrl': '', 'header': header}
        if '/video/' in url:
            d = self.detailContent([url])
            item = (d.get('list') or [{}])[0]
            pu = item.get('vod_play_url') or ''
            # 支持 # 与 $$$
            for part in re.split(r'\$\$\$|#', pu):
                if '$' in part:
                    u = part.split('$', 1)[-1]
                    if re.search(r'\.(m3u8|mp4)', u, re.I):
                        return {'parse': 0, 'jx': 0, 'url': u, 'playUrl': '', 'header': header}
        return {'parse': 0, 'jx': 0, 'url': '', 'playUrl': '', 'header': header}


if __name__ == '__main__':
    sp = Spider()
    sp.init()
    print('home', len(sp.homeContent().get('class') or []))
    for tid in ['videos', 'videos/amateur', 'amateur']:
        r = sp.categoryContent(tid, 1)
        print(tid, len(r.get('list') or []))
        if r.get('list'):
            d = sp.detailContent([r['list'][0]['vod_id']])
            print('  play', d['list'][0].get('vod_play_url', '')[:80])
