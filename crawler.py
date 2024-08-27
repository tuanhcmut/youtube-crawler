import json
import re
import asyncio
import httpx
from typing import Dict, Any, List

# Constants
YOUTUBE_VIDEO_URL = 'https://www.youtube.com/watch?v={youtube_id}'
YOUTUBE_CONSENT_URL = 'https://consent.youtube.com/save'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36'

YT_CFG_RE = r'ytcfg\.set\s*\(\s*({.+?})\s*\)\s*;'
YT_INITIAL_DATA_RE = r'(?:window\s*\[\s*["\']ytInitialData["\']\s*\]|ytInitialData)\s*=\s*({.+?})\s*;\s*(?:var\s+meta|</script|\n)'
YT_HIDDEN_INPUT_RE = r'<input\s+type="hidden"\s+name="([A-Za-z0-9_]+)"\s+value="([A-Za-z0-9_\-\.]*)"\s*(?:required|)\s*>'

class YoutubeCrawler:
    def __init__(self, video_id: str):
        self.video_id = video_id
        self.url = 'https://www.youtube.com/youtubei/v1/player'
        self.headers = {'Content-Type': 'application/json'}
        self.data = {
            "context": {
                "cl": "en",
                "client": {
                    "clientName": "WEB",
                    "clientVersion": "2.20210721.00.00",
                    "mainAppWebInfo": {
                        "graftUrl": f"/watch?v={self.video_id}"
                    }
                }
            },
            "videoId": self.video_id
        }
        self.response = None
        self.ytCfg = None
        self.ytInitial = None
        self.session = httpx.AsyncClient()
        self.session.headers['User-Agent'] = USER_AGENT
        self.session.cookies.set('CONSENT', 'YES+cb', domain='.youtube.com')
        self.stop_immediately = False
        self.all_comments = None
        
    async def new_session():
        self.session = httpx.AsyncClient()
        self.session.headers['User-Agent'] = USER_AGENT
        self.session.cookies.set('CONSENT', 'YES+cb', domain='.youtube.com')

    async def _fetch_data(self) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.post(self.url, json=self.data, headers=self.headers)
            if response.status_code == 200:
                self.response = response.json()
                return self.response
            else:
                raise httpx.HTTPStatusError(f"Failed to fetch data with status code {response.status_code}")

    async def get_video_details(self) -> Dict[str, Any]:
        if not self.response:
            await self._fetch_data()
        return self.response.get('videoDetails', {})

    async def get_captions(self) -> List[Dict[str, Any]]:
        if not self.response:
            await self._fetch_data()
        captions = self.response.get('captions')
        if captions:
            return captions.get('playerCaptionsTracklistRenderer', {}).get('captionTracks', [])
        return []

    async def _fetch_and_handle_page(self, youtube_url):
        response = await self.session.get(youtube_url)
        if 'consent' in str(response.url):
            params = dict(re.findall(YT_HIDDEN_INPUT_RE, response.text))
            params.update({'continue': youtube_url, 'set_eom': False, 'set_ytc': True, 'set_apyt': True})
            response = await self.session.post(YOUTUBE_CONSENT_URL, params=params)

        html = response.text
        self.ytCfg = self._regex_search(html, YT_CFG_RE, default='')
        if not self.ytCfg:
            raise RuntimeError("Failed to fetch ytcfg")
        self.ytCfg = json.loads(self.ytCfg)

        self.ytInitial = self._regex_search(html, YT_INITIAL_DATA_RE, default='')
        if not self.ytInitial:
            raise RuntimeError("Failed to fetch ytInitialData")
        self.ytInitial = json.loads(self.ytInitial)

    async def _ajax_request(self, endpoint, retries=5, sleep=20, timeout=60):
        url = 'https://www.youtube.com' + endpoint['commandMetadata']['webCommandMetadata']['apiUrl']
        data = {'context': self.ytCfg['INNERTUBE_CONTEXT'],
                'continuation': endpoint['continuationCommand']['token']}
        for _ in range(retries):
            try:
                response = await self.session.post(url, params={'key': self.ytCfg['INNERTUBE_API_KEY']}, json=data, timeout=timeout)
                if response.status_code == 200:
                    return response.json()
                if response.status_code in [403, 413]:
                    return {}
            except httpx.RequestError:
                pass
            await asyncio.sleep(sleep)
        return {}

    async def stop_fetching_comments(self):
        self.stop_immediately = True
    
    def count_fetching_comments(self):
        return len(self.all_comments) if self.all_comments else 0 

    async def get_comments(self, all_comments = [], language=None, sleep=.1, newest_first=False, limit=None):
        self.all_comments = all_comments
        youtube_url = YOUTUBE_VIDEO_URL.format(youtube_id=self.video_id)
        await self._fetch_and_handle_page(youtube_url)
        self._set_language(language)
        sort_menu = await self._get_sort_menu()
        sort_by = 1 if newest_first else 0

        if not sort_menu:
            raise RuntimeError('Failed when getting comments')

        continuations = [sort_menu[sort_by]['serviceEndpoint']]

        while continuations:
            if self.stop_immediately or (limit and len(all_comments) >= limit):
                break
            continuation = continuations.pop()
            response = await self._ajax_request(continuation)
            if not response:
                break
            comments = self._handle_response(response, continuations)
            will_continue = self._handle_comments(comments, all_comments, limit)
            if self.stop_immediately or not will_continue:
                break
            await asyncio.sleep(sleep)

        return all_comments

    def _set_language(self, language):
        if language:
            self.ytCfg['INNERTUBE_CONTEXT']['client']['hl'] = language

    def _handle_comments(self, comments, all_comments, limit):
        if limit:
            while len(all_comments) < limit and comments:
                all_comments.append(comments.pop())
            return len(all_comments) < limit
        else:
            all_comments.extend(comments)
            return True

    async def _get_sort_menu(self):
        sort_menu = next(self._search_dict(self.ytInitial, 'sortFilterSubMenuRenderer'), {}).get('subMenuItems', [])
        if not sort_menu:
            section_list = next(self._search_dict(self.ytInitial, 'sectionListRenderer'), {})
            continuations = list(self._search_dict(section_list, 'continuationEndpoint'))
            self.ytInitial = await self._ajax_request(continuations[0]) if continuations else {}
            sort_menu = next(self._search_dict(self.ytInitial, 'sortFilterSubMenuRenderer'), {}).get('subMenuItems', [])
        return sort_menu

    def _handle_response(self, response, continuations):
        error = next(self._search_dict(response, 'externalErrorMessage'), None)
        if error:
            raise RuntimeError(f'Error returned from server: {error}')

        actions = list(self._search_dict(response, 'reloadContinuationItemsCommand')) + \
                  list(self._search_dict(response, 'appendContinuationItemsAction'))

        comments = []
        for action in actions:
            for item in action.get('continuationItems', []):
                if action['targetId'] in ['comments-section', 'engagement-panel-comments-section', 'shorts-engagement-panel-comments-section']:
                    continuations.extend(ep for ep in self._search_dict(item, 'continuationEndpoint'))
                if action['targetId'].startswith('comment-replies-item') and 'continuationItemRenderer' in item:
                    button_renderer = next(self._search_dict(item, 'buttonRenderer'), {})
                    if 'command' in button_renderer:
                        continuations.append(button_renderer['command'])

        comments.extend(self._parse_comments(response))
        return comments

    def _parse_comments(self, response):
        toolbar_states = {payload['key']: payload for payload in self._search_dict(response, 'engagementToolbarStateEntityPayload')}
        for comment in reversed(list(self._search_dict(response, 'commentEntityPayload'))):
            properties = comment['properties']
            cid = properties['commentId']
            author = comment['author']
            toolbar = comment['toolbar']
            toolbar_state = toolbar_states.get(properties['toolbarStateKey'], {})
            result = {
                'cid': cid,
                'vid': self.video_id,
                'text': properties['content']['content'],
                'time': properties['publishedTime'],
                'author': author['displayName'],
                'channel': author['channelId'],
                'votes': toolbar['likeCountNotliked'].strip() or "0",
                'replies': toolbar['replyCount'],
                'photo': author['avatarThumbnailUrl'],
                'heart': toolbar_state.get('heartState', '') == 'TOOLBAR_HEART_STATE_HEARTED',
                'reply': '.' in cid
            }
            yield result

    @staticmethod
    def _regex_search(text, pattern, group=1, default=None):
        match = re.search(pattern, text)
        return match.group(group) if match else default

    @staticmethod
    def _search_dict(partial, search_key):
        stack = [partial]
        while stack:
            current_item = stack.pop()
            if isinstance(current_item, dict):
                for key, value in current_item.items():
                    if key == search_key:
                        yield value
                    else:
                        stack.append(value)
            elif isinstance(current_item, list):
                stack.extend(current_item)
