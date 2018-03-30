# -*- coding: utf-8 -*-

"""
Special class designed for Jike
"""

from collections import deque
from collections.abc import Iterable, Sequence


class JikeSequenceBase(Sequence):
    """
    Base class for sequence data structure

    Has no size limit

    Intended for
    - Jike Collection
    - Jike User Post
    - Jike User Created Topic
    - Jike User Subscribed Topic
    - Jike User Following
    - Jike User Follower
    """

    def __init__(self):
        self.seq = []

    def __repr__(self):
        return f'JikeSequenceBase({len(self.seq)} items)'

    def __getitem__(self, item):
        return self.seq[item]

    def __contains__(self, item):
        return any((item['id'] == ele['id'] for ele in self.seq))

    def __len__(self):
        return len(self.seq)

    def __reversed__(self):
        return reversed(self.seq)

    def index(self, value, start=0, stop=None):
        assert hasattr(value, 'id')
        for idx, item in enumerate(self.seq[start:stop]):
            if item['id'] == value['id']:
                return idx
        else:
            raise ValueError(f'Value with id: {value["id"]} not found')

    def append(self, item):
        self.seq.append(item)

    def clear(self):
        self.seq.clear()

    def extend(self, items):
        assert isinstance(items, Iterable)
        self.seq.extend(list(items))


class JikeStreamBase:
    """
    Base class for stream data structure

    Has size limit specified by `maxlen`, default is 200

    Intended for
    - Jike News Feed
    - Jike Following Update
    """

    def __init__(self, maxlen=200):
        self.queue = deque(maxlen=maxlen)

    def __repr__(self):
        return f'JikeStreamBase({len(self.queue)} items)'

    def __getitem__(self, item):
        return self.queue[item]

    def __contains__(self, item):
        return any((item['id'] == ele['id'] for ele in self.queue))

    def __len__(self):
        return len(self.queue)

    def __reversed__(self):
        return reversed(self.queue)

    def index(self, value, start=0, stop=None):
        assert hasattr(value, 'id')
        for idx, item in enumerate(self.queue[start:stop]):
            if item['id'] == value['id']:
                return idx
        else:
            raise ValueError(f'Value with id: {value["id"]} not found')

    def append(self, item):
        self.queue.append(item)

    def clear(self):
        self.queue.clear()

    def extend(self, items):
        assert isinstance(items, Iterable)
        self.queue.extend(items)

    def popleft(self):
        self.queue.popleft()


class JikeFetcher:
    """
    Fetch Jike content in json format
    """

    def __init__(self, jike_session):
        self.jike_session = jike_session
        self.load_more_key = None

    def __repr__(self):
        return f'JikeFetcher({repr(self.jike_session)})'

    def fetch_more(self, endpoint, payload):
        res = self.jike_session.post(endpoint, json=payload)
        if res.status_code == 200:
            return res.json()
        res.raise_for_status()
