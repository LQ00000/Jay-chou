# -*- coding: utf-8 -*-
"""
321AV https://321av.net
列表 /vodtype/{id}.html  播放 player_aaaa → /private-getvideo/{code}
入口用 /index.php 或 /enter（根路径 / 会 500）
"""
import re
import json
import base64
from urllib.parse import quote, unquote

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
            o.content = r.content
            o.status_code = r.status_code
            o.url = r.url
            return o


HOST = 'https://321av.net'
UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
)

CLASS_LIST = [
    {'type_id': '20', 'type_name': '有码影片'},
    {'type_id': '21', 'type_name': '无码影片'},
    {'type_id': '22', 'type_name': '中文字幕'},
    {'type_id': 'home', 'type_name': '首页推荐'},
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
        return '321AV'

    def isVideoFormat(self, url):
        low = (url or '').lower()
        return any(k in low for k in ('.m3u8', '.mp4', '.flv', '.ts'))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass


    def _fix_txt(self, s):
        if not s:
            return ''
        s = str(s)
        # 字面 \uXXXX
        if re.search(r'\\u[0-9a-fA-F]{4}', s):
            try:
                s = s.encode('utf-8').decode('unicode_escape')
            except Exception:
                pass
        s = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), s)
        return s.strip()

    def _headers(self, referer=None):
        return {
            'User-Agent': self._ua,
            'Referer': referer or (self.host + '/index.php'),
            'Accept': 'text/html,application/xhtml+xml,application/json,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
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
        # 卡片: vodplay/{id}-1-1.html + img data-src + alt
        for m in re.finditer(
            r'href=["\']/vodplay/(\d+)-\d+-\d+\.html["\'][\s\S]{0,600}?'
            r'(?:data-src|src)=["\']([^"\']+)["\'][\s\S]{0,200}?alt=["\']([^"\']*)["\']',
            html, re.I
        ):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            pic = m.group(2)
            if pic.startswith('//'):
                pic = 'https:' + pic
            elif pic.startswith('/'):
                pic = self.host + pic
            title = re.sub(r'\s+', ' ', m.group(3) or '').strip()
            results.append({
                'vod_id': vid,
                'vod_name': title or vid,
                'vod_pic': pic if 'loading' not in pic else '',
                'vod_remarks': '',
            })
        if results:
            return results
        for m in re.finditer(r'/vodplay/(\d+)-\d+-\d+\.html', html):
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            results.append({
                'vod_id': vid,
                'vod_name': vid,
                'vod_pic': '',
                'vod_remarks': '',
            })
        return results


    def _parse_player_aaaa(self, html):
        if not html:
            return None
        # 1) 标准
        m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*;?\s*<', html, re.S)
        candidates = []
        if m:
            candidates.append(m.group(1))
        # 2) 反斜杠转义 \" 
        m = re.search(r'player_aaaa\s*=\s*(\{.*?\})', html, re.S)
        if m:
            candidates.append(m.group(1))
        # 3) 括号深度扫描
        m = re.search(r'player_aaaa\s*=\s*\{', html)
        if m:
            start = m.end() - 1
            depth = 0
            for i, c in enumerate(html[start:start + 5000]):
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        candidates.append(html[start:start + i + 1])
                        break
        for raw in candidates:
            for attempt in (raw, raw.replace('\\"', '"').replace("\\'", "'").replace('\\\\', '\\')):
                try:
                    data = json.loads(attempt)
                    if isinstance(data, dict) and ('url' in data or 'encrypt' in data):
                        return data
                except Exception:
                    continue
        return None

    def _decode_player_url(self, raw):
        if not raw:
            return ''
        s = unquote(str(raw).strip())
        try:
            pad = '=' * (-len(s) % 4)
            data = json.loads(base64.b64decode(s + pad).decode('utf-8', 'ignore'))
        except Exception:
            return ''
        # {"ss":[[0,"/cn/scop-763"]]}
        code = ''
        ss = data.get('ss') if isinstance(data, dict) else None
        if isinstance(ss, list):
            for row in ss:
                if isinstance(row, list) and len(row) >= 2:
                    path = str(row[1])
                    m = re.search(r'/cn/([^/?#]+)', path, re.I)
                    if m:
                        code = m.group(1)
                        break
                elif isinstance(row, str):
                    m = re.search(r'/cn/([^/?#]+)', row, re.I)
                    if m:
                        code = m.group(1)
                        break
        return code

    def _play_from_code(self, code):
        plays = []
        if not code:
            return plays
        url = '%s/private-getvideo/%s' % (self.host, quote(code))
        try:
            r = self.fetch(url, headers=self._headers(), timeout=20)
            text = getattr(r, 'text', '') or ''
            data = json.loads(text)
        except Exception:
            return plays
        playlist = data.get('playlist') if isinstance(data, dict) else None
        if not isinstance(playlist, list):
            return plays
        seen = set()
        for item in playlist:
            if not isinstance(item, dict):
                continue
            u = item.get('url') or ''
            if not u.startswith('http') or u in seen:
                continue
            if not re.search(r'\.(m3u8|mp4)(\?|$)', u, re.I):
                continue
            seen.add(u)
            name = 'HLS' if '.m3u8' in u else 'MP4'
            # 尝试从 url 提取清晰度
            qm = re.search(r'(\d{3,4})p', u, re.I)
            if qm:
                name = qm.group(1) + 'P'
            if item.get('playMode') == 'streampipe':
                name = '自适应'
            plays.append((name, u))
        return plays

    def homeContent(self, filter=False):
        return {'class': list(CLASS_LIST), 'list': [], 'filters': {}}

    def homeVideoContent(self):
        html = self._fetch(self.host + '/index.php')
        return {'list': self._parse_list(html)[:24]}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        try:
            page = max(1, int(str(pg) or 1))
        except Exception:
            page = 1
        tid = str(tid or 'home').strip()
        if tid == 'home':
            url = self.host + '/index.php'
            if page > 1:
                url = self.host + '/index.php?page=%d' % page
        else:
            url = '%s/vodtype/%s.html' % (self.host, tid)
            if page > 1:
                url = '%s/vodtype/%s-%d.html' % (self.host, tid, page)
                # 兼容 ?page=
                alt = '%s/vodtype/%s.html?page=%d' % (self.host, tid, page)
                html = self._fetch(url)
                if not self._parse_list(html):
                    html = self._fetch(alt)
                else:
                    vods = self._parse_list(html)
                    return {
                        'list': vods,
                        'page': page,
                        'pagecount': page + 1 if len(vods) >= 12 else page,
                        'limit': 24,
                        'total': 9999,
                    }
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
        q = quote(str(key or '').strip())
        url = '%s/index.php/vod/search.html?wd=%s' % (self.host, q)
        if page > 1:
            url += '&page=%d' % page
        html = self._fetch(url)
        vods = self._parse_list(html)
        return {
            'list': vods,
            'page': page,
            'pagecount': page + 1 if len(vods) >= 12 else page,
            'limit': 24,
            'total': 9999,
        }

    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, (list, tuple)) else ids
        vid = re.search(r'(\d+)', str(raw or ''))
        vid = vid.group(1) if vid else ''
        if not vid:
            return {'list': []}
        page = '%s/vodplay/%s-1-1.html' % (self.host, vid)
        html = self._fetch(page)
        name = ''
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.I)
        if not m:
            m = re.search(r'<h1[^>]*>([^<]+)', html, re.I)
        if m:
            name = self._fix_txt(m.group(1))
        if not name:
            m = re.search(r'<title>([^<]+)', html, re.I)
            if m:
                name = self._fix_txt(m.group(1))
                name = re.sub(r'\s*[-|].*$', '', name).strip()
                name = re.sub(r'^在线播放', '', name).strip()
        if not name:
            m = re.search(r'"vod_name"\s*:\s*"((?:[^"\\]|\\.)*)"', html)
            if m:
                try:
                    name = self._fix_txt(json.loads('"' + m.group(1) + '"'))
                except Exception:
                    name = self._fix_txt(m.group(1))
        pic = ''
        m = re.search(r'og:image["\']\s+content=["\']([^"\']+)', html, re.I)
        if m:
            pic = m.group(1)

        code = ''
        data = self._parse_player_aaaa(html)
        if data:
            code = self._decode_player_url(data.get('url') or '')
        if not code:
            # 从标题/正文兜底番号
            tm = re.search(r'([A-Z]{2,10}-?\d{2,5})', html or '', re.I)
            if tm:
                code = tm.group(1).lower().replace('_', '-')
        plays = self._play_from_code(code)
        if plays:
            play_from = '$$$'.join([n for n, _ in plays])
            play_url = '$$$'.join(['正片$%s' % u for _, u in plays])
        else:
            play_from = '321AV'
            play_url = '正片$%s' % page
        return {'list': [{
            'vod_id': vid,
            'vod_name': name or vid,
            'vod_pic': pic,
            'vod_play_from': play_from,
            'vod_play_url': play_url,
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id or '').strip()
        header = {
            'User-Agent': self._ua,
            'Referer': self.host + '/',
            'Origin': self.host,
        }
        if re.search(r'\.(m3u8|mp4)(\?|$)', url, re.I):
            return {'parse': 0, 'jx': 0, 'url': url, 'header': header}
        # vodplay 页面或纯 id：重新解 private-getvideo
        vid = ''
        m = re.search(r'/vodplay/(\d+)', url)
        if m:
            vid = m.group(1)
        elif re.match(r'^\d+$', url):
            vid = url
        if vid:
            d = self.detailContent([vid])
            item = (d.get('list') or [{}])[0]
            pu = item.get('vod_play_url') or ''
            for part in pu.split('$$$'):
                if '$' in part:
                    u = part.split('$', 1)[1]
                    if re.search(r'\.(m3u8|mp4)', u, re.I):
                        return {'parse': 0, 'jx': 0, 'url': u, 'header': header}
        return {'parse': 0, 'jx': 0, 'url': '', 'header': header}

if __name__ == '__main__':
    sp = Spider()
    sp.init()
    print(sp.homeContent(False))
    r = sp.categoryContent('20', 1)
    print('list', len(r.get('list') or []))
    if r.get('list'):
        d = sp.detailContent([r['list'][0]['vod_id']])
        print(d)
