# -*- coding: utf-8 -*-

"""
Client that Jikers play with
"""

import webbrowser
from threading import Timer
from .session import JikeSession
from .objects import List, Stream, User, Topic, JikeEmitter
from .utils import *
from .constants import ENDPOINTS, URL_VALIDATION_PATTERN, CHECK_UNREAD_COUNT_PERIOD


def check_unread_count_periodically(obj):
    """
    Run periodical task to check unread count and do some automatic task
    """
    obj.get_news_feed_unread_count()
    unread = auto_load_unread(obj)
    notify_update(obj, unread)
    Timer(
        CHECK_UNREAD_COUNT_PERIOD,
        check_unread_count_periodically,
        args=(obj,)
    ).start()


def auto_load_unread(obj):
    unread_news_feed = obj._load_unread('news_feed')
    unread_following_update = obj._load_unread('following_update')
    return unread_news_feed, unread_following_update


def notify_update(obj, unread):
    for t in unread:
        for message in t:
            assert hasattr(message, 'type') and hasattr(message, 'content')
            if message.type == 'OFFICIAL_MESSAGE' and (message.topic['content'] in obj.notified_topics or 'all' in obj.notified_topics):
                title = '{} 更新了'.format(message.topic['content'])
                msg = message.content
                notify(title, msg)
            elif message.type == 'ORIGINAL_POST' and (message.user['screenName'] in obj.notified_users or 'all' in obj.notified_users):
                title = '{} 发动态了'.format(message.user['screenName'])
                msg = message.content
                notify(title, msg)


class JikeClient:
    def __init__(self, sync_unread=False):
        self.auth_token = read_token()
        if self.auth_token is None:
            self.auth_token = login()
            try:
                write_token(self.auth_token)
            except IOError:
                pass
        self.jike_session = JikeSession(self.auth_token)

        self.collection = None
        self.news_feed = None
        self.following_update = None

        self.unread_count = 0
        self.timer = None
        if sync_unread:
            self.timer = Timer(
                CHECK_UNREAD_COUNT_PERIOD,
                check_unread_count_periodically,
                args=(self,)
            ).start()

        self.notified_topics = ['all']
        self.notified_users = ['all']

    def __del__(self):
        if self.timer:
            self.timer.cancel()

    def get_my_profile(self):
        return self.get_user_profile(username=None)

    def get_my_collection(self):
        if self.collection is None:
            self.collection = List(self.jike_session, ENDPOINTS['my_collections'])
            self.collection.load_more()
        return self.collection

    def get_news_feed_unread_count(self):
        res = self.jike_session.get(ENDPOINTS['news_feed_unread_count'])
        if res.status_code == 200:
            result = res.json()
            self.unread_count = result['newMessageCount']
            return self.unread_count
        res.raise_for_status()

    def get_news_feed(self):
        if self.news_feed is None:
            self.news_feed = Stream(self.jike_session, ENDPOINTS['news_feed'])
            self.news_feed.load_more()
        return self.news_feed

    def get_following_update(self):
        if self.following_update is None:
            self.following_update = Stream(self.jike_session, ENDPOINTS['following_update'])
            self.following_update.load_more()
        return self.following_update

    def get_user_profile(self, username):
        res = self.jike_session.get(ENDPOINTS['user_profile'], {
            'username': username
        })
        if res.status_code == 200:
            result = res.json()
            result['user'].update(result['statsCount'])
            return User(**result['user'])
        res.raise_for_status()

    def get_user_post(self, username, limit=20):
        posts = List(self.jike_session, ENDPOINTS['user_post'], {'username': username})
        posts.load_more(limit)
        return posts

    def get_user_created_topic(self, username, limit=20):
        created_topics = List(self.jike_session, ENDPOINTS['user_created_topic'], {'username': username}, Topic)
        created_topics.load_more(limit)
        return created_topics

    def get_user_subscribed_topic(self, username, limit=20):
        subscribed_topics = List(self.jike_session, ENDPOINTS['user_subscribed_topic'], {'username': username}, Topic)
        subscribed_topics.load_more(limit)
        return subscribed_topics

    def get_user_following(self, username, limit=20):
        user_followings = List(self.jike_session, ENDPOINTS['user_following'], {'username': username}, User)
        user_followings.load_more(limit)
        return user_followings

    def get_user_follower(self, username, limit=20):
        user_followers = List(self.jike_session, ENDPOINTS['user_follower'], {'username': username}, User)
        user_followers.load_more(limit)
        return user_followers

    def get_comment(self, message):
        assert hasattr(message, 'id') and hasattr(message, 'type')
        comments = Stream(self.jike_session, ENDPOINTS['list_comment'], {
            'targetId': message.id,
            'targetType': message.type
        })
        comments.load_more()
        return comments

    def get_topic_selected(self, topic_id):
        topic_selected = Stream(self.jike_session, ENDPOINTS['topic_selected'], {
            'topic': topic_id
        })
        topic_selected.load_more()
        return topic_selected

    def get_topic_square(self, topic_id):
        topic_square = Stream(self.jike_session, ENDPOINTS['topic_square'], {
            'topicId': topic_id
        })
        topic_square.load_more()
        return topic_square

    @staticmethod
    def open_in_browser(url_or_message):
        if isinstance(url_or_message, str):
            url = url_or_message
        elif hasattr(url_or_message, 'linkInfo'):
            url = url_or_message.linkInfo['linkUrl']
        elif 'linkInfo' in url_or_message:
            url = url_or_message['linkInfo']['linkUrl']
        elif hasattr(url_or_message, 'content'):
            urls = extract_url(url_or_message.content)
            if urls:
                for url in urls:
                    webbrowser.open(url)
                return
        else:
            raise ValueError('No url found')

        if not URL_VALIDATION_PATTERN.match(url):
            raise ValueError('Url invalid')
        else:
            webbrowser.open(url)

    def create_my_post(self, content, link=None, topic_id=None, pictures=None):
        assert isinstance(content, str)
        if link and pictures:
            raise ValueError('Jike cannot post thought with both pictures and link')

        payload = {
            'content': content
        }
        if link:
            assert URL_VALIDATION_PATTERN.match(link), 'Invalid link'
            payload.update({'linkInfo': extract_link(self.jike_session, link)})
        if topic_id:
            payload.update({'submitToTopic': topic_id})
        if pictures:
            uploaded_picture_keys = upload_pictures(pictures)
            payload.update({'pictureKeys': uploaded_picture_keys})

        res = self.jike_session.post(ENDPOINTS['create_post'], json=payload)
        post = None
        if res.status_code == 200:
            result = res.json()
            if result['success']:
                post = OriginalPost(**result['data'])
            else:
                raise RuntimeError('Post fail')
        res.raise_for_status()
        return post

    def delete_my_post(self, post):
        assert hasattr(post, 'type') and hasattr(post, 'id')
        res = self.jike_session.post(ENDPOINTS['delete_post'], json={
            'id': post.id,
        })
        if res.status_code == 200:
            return res.json()['success']
        res.raise_for_status()

    def _like_action(self, message, action):
        assert hasattr(message, 'type') and hasattr(message, 'id')
        assert message.type in converter, 'Unsupported message type'
        assert action in ['like_it', 'unlike_it']
        message_type = ''.join([w.title() if i != 0 else w.lower()
                                for i, w in enumerate(message.type.split('_'))]) + 's'
        endpoint = ENDPOINTS[action].format(t=message_type)
        payload = {
            'id': message.id,
        }
        if hasattr(message, 'targetType'):
            payload.update({'targetType': message.targetType})
        res = self.jike_session.post(endpoint, json=payload)
        if res.status_code == 200:
            return res.json()['success']
        res.raise_for_status()

    def like_it(self, message):
        return self._like_action(message, 'like_it')

    def unlike_it(self, message):
        return self._like_action(message, 'unlike_it')

    def _collect_action(self, message, action):
        assert hasattr(message, 'type') and hasattr(message, 'id')
        assert message.type in converter, 'Unsupported message type'
        assert action in ['collect_it', 'uncollect_it']
        message_type = ''.join([w.title() if i != 0 else w.lower()
                                for i, w in enumerate(message.type.split('_'))]) + 's'
        endpoint = ENDPOINTS[action].format(t=message_type)
        payload = {
            'id': message.id,
        }
        res = self.jike_session.post(endpoint, json=payload)
        if res.status_code == 200:
            return res.json()['success']
        res.raise_for_status()

    def collect_it(self, message):
        return self._collect_action(message, 'collect_it')

    def uncollect_it(self, message):
        return self._collect_action(message, 'uncollect_it')

    def repost_it(self, content, message, sync_comment=True):
        assert isinstance(content, str)
        assert hasattr(message, 'type') and hasattr(message, 'id')
        assert message.type in converter, 'Unsupported message type'
        payload = {
            'content': content,
            'syncComment': sync_comment,
            'targetId': message.id,
            'targetType': message.type,
        }
        res = self.jike_session.post(ENDPOINTS['repost_it'], json=payload)
        repost = None
        if res.status_code == 200:
            result = res.json()
            if result['success']:
                repost = Repost(**result['data'])
            else:
                raise RuntimeError('Repost fail')
        res.raise_for_status()
        return repost

    def comment_it(self, content, message, pictures=None, sync2personal_updates=True):
        assert isinstance(content, str)
        assert hasattr(message, 'type') and hasattr(message, 'id')
        assert message.type in converter, 'Unsupported message type'
        payload = {
            'content': content,
            'pictureKeys': [],
            'syncToPersonalUpdates': sync2personal_updates,
            'targetId': message.id,
            'targetType': message.type,
        }
        if pictures:
            uploaded_picture_keys = upload_pictures(pictures)
            payload.update({'pictureKeys': uploaded_picture_keys})
        res = self.jike_session.post(ENDPOINTS['comment_it'], json=payload)
        comment = None
        if res.status_code == 200:
            result = res.json()
            if result['success']:
                comment = Comment(**result['data'])
            else:
                raise RuntimeError('Comment fail')
        res.raise_for_status()
        return comment

    def search_topic(self, keywords):
        assert isinstance(keywords, str)
        topics = List(self.jike_session, ENDPOINTS['search_topic'], type_converter=Topic, fixed_extra_payload={
            'keywords': keywords,
            'onlyUserPostEnabled': False,
            'type': 'ALL'
        })
        topics.load_more()
        return topics

    def search_collection(self, keywords):
        assert isinstance(keywords, str)
        messages = List(self.jike_session, ENDPOINTS['search_collection'], fixed_extra_payload={
            'keywords': keywords,
        })
        messages.load_more()
        return messages

    def get_recommended_topic(self):
        topics = List(self.jike_session, ENDPOINTS['recommended_topic'], type_converter=Topic, fixed_extra_payload={
            'categoryAlias': 'RECOMMENDATION',
        })
        topics.load_more()
        return topics

    def create_emitter(self, endpoint, fixed_extra_payload=()):
        """
        BOOM! You find easter egg in this project, now you can use this function to crawl Jike.

        USE IT WISELY !
        """
        assert endpoint in ENDPOINTS.values()
        return JikeEmitter(self.jike_session, endpoint, fixed_extra_payload)

    def schedule_my_post(self, content, link=None, topic_id=None, pictures=None, *, delay=None):
        assert isinstance(delay, int) and delay > 0, 'Please provide a delay time'
        post_fn = self.create_my_post
        timer = Timer(delay, post_fn, args=(content, link, topic_id, pictures))
        timer.start()
        return timer

    def _load_unread(self, choice):
        if choice == 'news_feed':
            if self.news_feed:
                return self.news_feed.load_update(unread_count=self.unread_count+3)
        elif choice == 'following_update':
            if self.following_update:
                return self.following_update.load_update(unread_count=self.unread_count+3)
        else:
            raise ValueError('choice only can be "news_feed" or "following_update"')
        return []

    def set_automatic_rules(self, notified_topics, notified_users):
        self.notified_topics = notified_topics
        self.notified_users = notified_users

    def _create_new_jike_session(self):
        """
        Create a new session of `requests.Session`

        CAUTION: Could be used for concurrency http request, but not tested and verified by author
        """
        return JikeSession(self.auth_token)

    def relogin(self):
        """
        Re-login in case any problem related to auth_token
        """
        self.auth_token = login()
        write_token(self.auth_token)
        self.jike_session.session.close()
        self.jike_session = JikeSession(self.auth_token)
