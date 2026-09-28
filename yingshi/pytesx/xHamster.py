#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xHamster https://zh.xhamster1.pw
分类对齐 JS：含欧美/日韩中意 复古·经典·自制 等
"""
import json
import re
import sys
import urllib.parse

try:
    import requests
except ImportError:
    requests = None

sys.path.append('../../')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""):
            pass


class Spider(BaseSpider):
    def __init__(self):
        self.siteUrl = 'https://zh.xhamster1.pw'
        self.userAgent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        self.channels = {
            'newest': {'name': '最新', 'path': '/newest'},
            'best': {'name': '最佳', 'path': '/best'},
            '4k': {'name': '4K超清', 'path': '/4k'},
            'hd': {'name': '高清HD', 'path': '/hd'},
            'vr': {'name': 'VR', 'path': '/vr'},
            'best-4k': {'name': '最佳4K', 'path': '/best/4k'},
            'best-hd': {'name': '最佳高清', 'path': '/best/hd'},
            'newest-4k': {'name': '最新4K', 'path': '/newest/4k'},
            'newest-hd': {'name': '最新高清', 'path': '/newest/hd'},
            'categories-amateur': {'name': '业余', 'path': '/categories/amateur'},
            'categories-asian': {'name': '亚洲', 'path': '/categories/asian'},
            'categories-japanese': {'name': '日本', 'path': '/categories/japanese'},
            'categories-japanese-vintage': {'name': '日本复古', 'path': '/search/japanese+vintage'},
            'japanese-vintage-tag': {'name': 'Japanese Vintage', 'path': '/search/japanese+vintage'},
            'categories-japanese-homemade': {'name': '日本自制', 'path': '/search/japanese+amateur'},
            'categories-japanese-classic': {'name': '日本经典', 'path': '/search/japanese+classic'},
            'tags-retro-asian': {'name': '复古亚洲', 'path': '/tags/retro-asian'},
            'categories-chinese': {'name': '中国', 'path': '/categories/chinese'},
            'categories-chinese-homemade': {'name': '中国自制', 'path': '/search/chinese+amateur'},
            'categories-chinese-classic': {'name': '中国经典', 'path': '/search/chinese+classic'},
            'categories-korean': {'name': '韩国', 'path': '/categories/korean'},
            'categories-korean-homemade': {'name': '韩国自制', 'path': '/search/korean+amateur'},
            'categories-korean-classic': {'name': '韩国经典', 'path': '/search/korean+classic'},
            'categories-european-vintage': {'name': '欧美复古', 'path': '/search/european+vintage'},
            'categories-european-classic': {'name': '欧美经典', 'path': '/search/european+classic'},
            'categories-italian-vintage': {'name': '意大利复古', 'path': '/search/italian+vintage'},
            'categories-italian-classic': {'name': '意大利经典', 'path': '/search/italian+classic'},
            'categories-milf': {'name': '熟女', 'path': '/categories/milf'},
            'categories-lesbian': {'name': '女同', 'path': '/categories/lesbian'},
            'categories-teen': {'name': '少女', 'path': '/categories/teen'},
            'categories-big-tits': {'name': '大胸', 'path': '/categories/big-tits'},
            'categories-anal': {'name': '肛交', 'path': '/categories/anal'},
            'categories-creampie': {'name': '内射', 'path': '/categories/creampie'},
            'categories-blowjob': {'name': '口交', 'path': '/categories/blowjob'},
            'categories-threesome': {'name': '3P', 'path': '/categories/threesome'},
            'categories-public': {'name': '公开', 'path': '/categories/public'},
            'categories-vintage': {'name': '复古', 'path': '/categories/vintage'},
        }

    def getName(self):
        return 'xHamster'

    def init(self, extend=""):
        try:
            if extend:
                ext = json.loads(extend) if isinstance(extend, str) else (extend or {})
                if isinstance(ext, dict) and ext.get('host'):
                    self.siteUrl = str(ext.get('host')).rstrip('/')
                elif isinstance(extend, str) and extend.startswith('http'):
                    self.siteUrl = extend.rstrip('/')
        except Exception:
            pass

    def fetch(self, url, headers=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Cookie': 'age_verified=1; cookie_accept=1; locale=zh; ts_popunder=1',
            }
        try:
            if requests:
                resp = requests.get(url, headers=headers, timeout=20, verify=False)
                if resp.status_code == 200:
                    return resp.text
            from urllib.request import Request, urlopen
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            raw = urlopen(Request(url, headers=headers), timeout=20, context=ctx).read()
            return raw.decode('utf-8', 'ignore')
        except Exception as e:
            print('请求失败: %s, %s' % (url, e))
            return ''

    def _abs(self, u):
        if not u:
            return ''
        if u.startswith('http'):
            return u
        if u.startswith('//'):
            return 'https:' + u
        return self.siteUrl + (u if u.startswith('/') else '/' + u)

    def _page_url(self, path, pg=1):
        path = path or '/newest'
        if not path.startswith('/'):
            path = '/' + path
        url = self.siteUrl + path
        if int(pg or 1) > 1:
            url += ('&' if '?' in url else '?') + 'page=' + str(pg)
        return url

    def _extract_initials(self, html):
        html = html or ''
        idx = html.find('window.initials')
        if idx < 0:
            return None
        # 定位第一个 {
        brace = html.find('{', idx)
        if brace < 0:
            return None
        depth = 0
        in_str = False
        esc = False
        quote = ''
        for i in range(brace, min(len(html), brace + 600000)):
            ch = html[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == quote:
                    in_str = False
                continue
            if ch in ('"', "'"):
                in_str = True
                quote = ch
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(html[brace:i+1].replace('\\/', '/'))
                    except Exception:
                        try:
                            return json.loads(html[brace:i+1])
                        except Exception:
                            return None
        return None

    def _videos_from_initials(self, data):
        videos, seen = [], set()
        if not data:
            return videos

        def push(slug, title, pic):
            if not slug or slug in seen or len(str(slug)) < 4:
                return
            if re.match(r'^(categories|channels|users|photos|creators|pornstars|tags|search)\b', str(slug), re.I):
                return
            seen.add(slug)
            videos.append({
                'vod_id': str(slug),
                'vod_name': (title or str(slug).replace('-', ' '))[:120],
                'vod_pic': self._abs(pic or ''),
                'vod_remarks': '',
            })

        # 优先 searchResult / videoThumbProps
        candidates = []
        sr = data.get('searchResult') or {}
        if isinstance(sr, dict) and isinstance(sr.get('videoThumbProps'), list):
            candidates.extend(sr['videoThumbProps'])
        # pages 其它列表
        for key in ('videoThumbProps', 'videos', 'videoList', 'relatedVideoProps'):
            for root in (data, data.get('entity') or {}, data.get('store') or {}):
                if not isinstance(root, dict):
                    continue
                val = root.get(key)
                if isinstance(val, list):
                    candidates.extend(val)
                if isinstance(val, dict) and isinstance(val.get('videoThumbProps'), list):
                    candidates.extend(val['videoThumbProps'])

        for obj in candidates:
            if not isinstance(obj, dict):
                continue
            pageURL = obj.get('pageURL') or obj.get('link') or obj.get('url') or ''
            title = obj.get('title') or obj.get('name') or ''
            slug = ''
            if isinstance(pageURL, str) and '/videos/' in pageURL:
                slug = pageURL.split('/videos/')[-1].split('?')[0].rstrip('/')
            if not slug:
                vid = obj.get('id') or obj.get('videoId')
                if vid:
                    slug = str(vid)
            pic = obj.get('thumbURL') or obj.get('previewThumbURL') or obj.get('image') or ''
            if slug:
                push(slug, title, pic)

        # 仍不足则全树 walk
        if len(videos) < 10:
            def walk(obj):
                if isinstance(obj, list):
                    for x in obj:
                        walk(x)
                    return
                if not isinstance(obj, dict):
                    return
                pageURL = obj.get('pageURL') or obj.get('link') or obj.get('url') or ''
                title = obj.get('title') or obj.get('name') or ''
                slug = ''
                if isinstance(pageURL, str) and '/videos/' in pageURL:
                    slug = pageURL.split('/videos/')[-1].split('?')[0].rstrip('/')
                if slug and (title or obj.get('thumbURL')):
                    pic = obj.get('thumbURL') or obj.get('previewThumbURL') or ''
                    push(slug, title, pic)
                for v in obj.values():
                    if isinstance(v, (dict, list)):
                        walk(v)
            walk(data)
        return videos

    def _parse_list(self, html):
        html = html or ''
        data = self._extract_initials(html)
        videos = self._videos_from_initials(data)
        if len(videos) >= 8:
            return videos
        # HTML 兜底：多套正则
        seen = {v['vod_id'] for v in videos}
        patterns = [
            r'href="((?:https?:)?//[^"]*?/videos/([^"?#]+))"[^>]*>[\s\S]{0,800}?(?:src|data-src|data-previewvideo)="((?:https?:)?//[^"]+)"[\s\S]{0,500}?(?:alt|title)="([^"]*)"',
            r'href="(/videos/([^"?#]+))"[^>]*>[\s\S]{0,600}?(?:src|data-src)="([^"]+)"[\s\S]{0,400}?(?:alt|title)="([^"]*)"',
            r'data-video-id="(\d+)"[\s\S]{0,1000}?href="[^"]*/videos/([^"?#]+)"[\s\S]{0,500}?(?:src|data-src)="([^"]+)"[\s\S]{0,300}?(?:alt|title)="([^"]*)"',
        ]
        for pat in patterns:
            for m in re.finditer(pat, html, re.I):
                g = m.groups()
                if len(g) == 4 and g[1] and not g[1].isdigit():
                    slug, pic, title = g[1], g[2], g[3]
                elif len(g) == 4 and g[0].isdigit():
                    slug, pic, title = g[1], g[2], g[3]
                else:
                    continue
                slug = slug.strip('/')
                if not slug or slug in seen or len(slug) < 4:
                    continue
                if re.match(r'^(categories|channels|users|photos|creators|pornstars|tags|search)\b', slug, re.I):
                    continue
                seen.add(slug)
                videos.append({
                    'vod_id': slug,
                    'vod_name': (title or slug.replace('-', ' '))[:120],
                    'vod_pic': self._abs(pic),
                    'vod_remarks': '',
                })
            if len(videos) >= 20:
                break
        if len(videos) < 8:
            for m in re.finditer(r'/videos/([a-z0-9][a-z0-9\-_]{5,})', html, re.I):
                slug = m.group(1)
                if slug in seen:
                    continue
                seen.add(slug)
                videos.append({
                    'vod_id': slug,
                    'vod_name': slug.replace('-', ' '),
                    'vod_pic': '',
                    'vod_remarks': '',
                })
        return videos

    def _pagecount_from(self, html, pg, nlist):
        data = self._extract_initials(html)
        if data and isinstance(data.get('pagination'), dict):
            pag = data['pagination']
            mx = int(pag.get('maxPage') or pag.get('maxPages') or 0)
            if mx > 0:
                return max(mx, pg)
        pages = [int(x) for x in re.findall(r'[?&]page=(\d+)', html or '')]
        if pages and max(pages) > pg:
            return max(max(pages), pg)
        # 分类页常无 pagination 字段，满页则继续可翻
        if nlist >= 24:
            return max(pg + 1, 80)
        if nlist >= 12:
            return pg + 1
        return pg

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        html = self.fetch(self._page_url('/newest', 1))
        return {'list': self._parse_list(html)[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        info = self.channels.get(str(tid), {'path': '/' + str(tid or 'newest')})
        html = self.fetch(self._page_url(info.get('path') or '/newest', pg))
        videos = self._parse_list(html)
        pagecount = self._pagecount_from(html, pg, len(videos))
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': 48,
            'total': pagecount * 48,
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        raw = str(key or '').strip()
        if not raw:
            return {'list': [], 'page': 1, 'pagecount': 1}
        q_plus = urllib.parse.quote(raw).replace('%20', '+')
        q_enc = urllib.parse.quote(raw)
        candidates = [
            '%s/search/%s' % (self.siteUrl, q_plus) + (('?page=%d' % pg) if pg > 1 else ''),
            '%s/search/%s' % (self.siteUrl, q_enc) + (('?page=%d' % pg) if pg > 1 else ''),
            '%s/search/?q=%s' % (self.siteUrl, q_enc) + (('&page=%d' % pg) if pg > 1 else ''),
        ]
        videos, html = [], ''
        for url in candidates:
            html = self.fetch(url)
            videos = self._parse_list(html)
            if videos:
                break
        pagecount = self._pagecount_from(html, pg, len(videos))
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': 48,
            'total': 9999,
        }

    def detailContent(self, ids):
        slug = str((ids or [''])[0]).lstrip('/')
        if slug.startswith('videos/'):
            slug = slug[7:]
        slug = slug.split('?')[0].split('#')[0]
        page = self.siteUrl + '/videos/' + slug
        html = self.fetch(page)
        title = slug.replace('-', ' ')
        pic = ''
        tm = re.search(r'og:title["\']\s+content=["\']([^"\']+)', html or '', re.I)
        if not tm:
            tm = re.search(r'<title>([^<]+)</title>', html or '', re.I)
        if tm:
            title = re.sub(r'\s*[-|].*$', '', tm.group(1)).strip() or title
        pm = re.search(r'og:image["\']\s+content=["\']([^"\']+)', html or '', re.I)
        if pm:
            pic = self._abs(pm.group(1))
        play = self._pick_play(html)
        return {
            'list': [{
                'vod_id': slug,
                'vod_name': title,
                'vod_pic': pic,
                'vod_content': title,
                'vod_play_from': 'xHamster',
                'vod_play_url': '正片$%s' % (play or slug),
            }]
        }

    def _pick_play(self, html):
        html = html or ''
        m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html)
        if m3:
            return m3.group(0).replace('\\/', '/')
        # initials
        m = re.search(r'window\.initials\s*=\s*(\{[\s\S]+?\})\s*;', html)
        if m:
            try:
                data = json.loads(m.group(1).replace('\\/', '/'))
                xps = (data.get('xplayerSettings') or {}).get('sources') or {}
                hls = xps.get('hls') or {}
                if isinstance(hls, dict):
                    u = hls.get('url') or hls.get('fallback') or ''
                    if u and self.isVideoFormat(u):
                        return u.replace('\\/', '/')
                elif isinstance(hls, str) and self.isVideoFormat(hls):
                    return hls
                std = xps.get('standard') or {}
                best, best_q = '', 0
                if isinstance(std, dict):
                    for k, lst in std.items():
                        if not isinstance(lst, list):
                            continue
                        for item in lst:
                            if not isinstance(item, dict):
                                continue
                            u = item.get('url') or item.get('fallback') or ''
                            q = int(re.sub(r'\D', '', str(item.get('quality') or item.get('label') or k)) or 0)
                            if u and self.isVideoFormat(u) and q >= best_q:
                                best, best_q = u, q
                if best:
                    return best.replace('\\/', '/')
                sources = (data.get('videoModel') or {}).get('sources') or {}
                for fmt in ('h264', 'av1', 'mp4'):
                    dict_q = sources.get(fmt) or {}
                    if not isinstance(dict_q, dict):
                        continue
                    for q in sorted(dict_q.keys(), key=lambda x: int(re.sub(r'\D', '', str(x)) or 0), reverse=True):
                        item = dict_q[q]
                        u = item if isinstance(item, str) else (item.get('url') or item.get('fallback') if isinstance(item, dict) else '')
                        if u and self.isVideoFormat(u):
                            return u.replace('\\/', '/')
            except Exception:
                pass
        for key in ('h264', 'av1', 'videoUrl', 'fallback', 'hls'):
            m = re.search(r'"%s"\s*:\s*"(https?:[^"]+)"' % key, html)
            if m:
                u = m.group(1).replace('\\/', '/')
                if self.isVideoFormat(u):
                    return u
        m = re.search(r'"url"\s*:\s*"(https?:[^"]+\.(?:mp4|m3u8)[^"]*)"', html)
        if m:
            return m.group(1).replace('\\/', '/')
        return ''

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
            'Origin': self.siteUrl,
        }
        play_id = str(id or '')
        if play_id.startswith('http') and self.isVideoFormat(play_id):
            return {'parse': 0, 'url': play_id, 'playUrl': play_id, 'header': header}
        slug = play_id.split('|')[0].split('$')[-1]
        if slug.startswith('videos/'):
            slug = slug[7:]
        slug = slug.split('?')[0].split('#')[0]
        if slug.startswith('http') and self.isVideoFormat(slug):
            return {'parse': 0, 'url': slug, 'playUrl': slug, 'header': header}
        page = self.siteUrl + '/videos/' + slug
        html = self.fetch(page)
        url = self._pick_play(html)
        if url:
            return {
                'parse': 0 if self.isVideoFormat(url) else 1,
                'url': url, 'playUrl': url, 'header': header,
            }
        return {'parse': 1, 'jx': '1', 'url': page, 'playUrl': page, 'header': header}

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        return any(x in u for x in ('.m3u8', '.mp4', '.webm', '/hls/'))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None


if __name__ == '__main__':
    spider = Spider()
    spider.init()
    print(json.dumps(spider.homeContent(True), ensure_ascii=False, indent=2)[:500])
