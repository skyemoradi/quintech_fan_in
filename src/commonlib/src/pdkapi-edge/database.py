# (c) 2022 The MITRE Corporation, All Rights Reserved
import logging
import json
import os
from io import IOBase
from abc import ABC, abstractmethod

from redis import Redis


class Database(ABC):

    @abstractmethod
    def connect(self, addr: str): pass

    @abstractmethod
    def close(self): pass

    @abstractmethod
    def put(self, k: str, v, timeout: float = 0.0): pass

    @abstractmethod
    def put_m(self, d: dict): pass

    @abstractmethod
    def get(self, k: str): pass

    @abstractmethod
    def get_m(self, ks: list): pass

    @abstractmethod
    def delete(self, k: str): pass

    @abstractmethod
    def delete_m(self, ks: list): pass

    @abstractmethod
    def publish(self, k: str, v): pass

    @abstractmethod
    def subscribe(self, pattern: str, action): pass

    @abstractmethod
    def unsubscribe(self, client: str, pattern: str = ''): pass

    @abstractmethod
    def dump(self, stream: IOBase): pass


#################
# Redis Database
###############

# NOTE: hiredis (C implementation of response parser with Python wrapper) can
# be installed if performance is a problem. This is automatically detected by
# the Python redis package, so no code change is required.

class RedisDatabase(Database):
    """
    Redis implementation of Database. All data is stored in JSON form.
    """
    def __init__(self, client_name: str):
        # Redis client name
        self._client_name = client_name
        self._subscriptions = {}
        import redis  # noqa
        # print(redis.connection.HIREDIS_AVAILABLE)

    def connect(self, addr: str):
        "Create client connection and add a pubsub subscriber"

        # Check environment variables to retrieve password
        redis_pw = os.getenv('DBPASS')

        # Create Redis instance without password if DBPASS is not set
        if redis_pw is None or redis_pw == "":
            self._rcli = Redis(addr, decode_responses=True, client_name=self._client_name)
        else:
            self._rcli = Redis(addr, password=redis_pw, decode_responses=True,
                               client_name=self._client_name)

        # Connection is not made until the first command, test with a ping.
        try:
            self._rcli.ping()
        except Exception as e:
            raise IOError(str(e))

        # This would enable subscription to key event (e.g., value changes).
        # Not needed if explicit messages are used to notify client.
        # self._rcli.config_set('notify-keyspace-events', 'EA')

        # Create the sub handler client. Run it in a separate thread. There has
        # to be at least on subscription before the thread is started. Some
        # sort of broadcast could be useful.
        # TODO: what is broadcast, or what else would work here?
        self._rsub = self._rcli.pubsub()
        self._rsub.subscribe(**{'/broadcast': self._handle_broadcast})
        self._rsub_thread = self._rsub.run_in_thread(sleep_time=1.0,
                                                     daemon=True)

    def close(self):
        self._rsub_thread.stop()
        self._rsub_thread.join()
        self._rcli.close()

    # Put a single value in json form. If a timeout is non-zero, set expiration
    def put(self, k: str, v, timeout: float = 0.0):
        j = json.dumps(v)
        if timeout == 0.0:
            px = None
        else:
            px = int(timeout * 1000)
        self._rcli.set(k, j, px=px)

    # Put multiple values in json form
    def put_m(self, d: dict):
        j = dict([(k, json.dumps(v)) for k, v in d.items()])
        self._rcli.mset(j)

    # Load JSON value. Translate missing values to None.
    @staticmethod
    def json_loads_or_none(j):
        if j is None:
            return None
        return json.loads(j)

    # Get a single value and convert from json
    def get(self, k: str):
        j = self._rcli.get(k)
        return self.json_loads_or_none(j)

    # Get multiple values and convert from json
    def get_m(self, ks: list):
        j = self._rcli.mget(ks)
        # return dict(zip(ks, map(self.json_loads_or_none, j)))
        return dict(zip(ks, map(json.loads, j)))

    def keys(self, pattern):
        return self._rcli.keys(pattern)

    def delete(self, k: str):
        self._rcli.delete(k)

    def delete_m(self, ks: list):
        self._rcli.delete(*ks)

    # Publish a message in json form
    def publish(self, k: str, msg):
        j = json.dumps(msg)
        self._rcli.publish(k, j)

    def _handle_sub(self, msg):
        pattern = msg['pattern']
        action = self._subscriptions.get(pattern)
        if action:
            channel = msg['channel']
            # Redis key messages have string data
            if channel.startswith('__'):
                data = msg['data']
            # Other data is JSON
            else:
                data = self.json_loads_or_none(msg['data'])
            action(pattern, channel, data)
        else:
            logging.error(f'DB sub handler: pattern "{pattern}"" not found')

    # TODO: raw message handler for future use
    def _handle_broadcast(self, msg: dict):
        data = self.json_loads_or_none(msg['data'])
        logging.debug(f'{self._client_name} received broadcast: {data}')

    # NOTE: always using psubscribe (vs. subscribe)
    def subscribe(self, pattern: str, action):
        """Add/replace the (single) action for a subscription"""
        # Can not replace broadcast handler - ignore
        if pattern == '/broadcast':
            logging.error('Attempt to modify DB broadcast handler')
            return
        if type(pattern) is not str:
            raise TypeError('pattern')
        if not callable(action):
            raise TypeError('action')

        self._subscriptions[pattern] = action
        self._rsub.psubscribe(**{pattern: self._handle_sub})

    def unsubscribe(self, pattern: str = None):
        """Remove one or all subscriptions by pattern"""
        # Can not unsubscribe from broadcasts - ignore
        if pattern == '/broadcast':
            logging.error('Attempt to remove DB broadcast handler')
            return
        # Unsubscribe all
        if pattern is None:
            self._rsub.punsubscribe()
            self._subscriptions.clear()
        elif pattern in self._subscriptions:
            self._subscriptions.pop(pattern)
            self._rsub.punsubscribe(pattern)
        else:
            logging.error(f'DB unsubscribe: pattern "{pattern}"" not found')

    def dump(self, stream: IOBase):
        def _print_k_dots_v(k, v, width, stream):
            print(f'{k} {"." * (width-len(k))} {v}', file=stream)

        print('=== DB data ===', file=stream)
        ks = self.keys('/*')
        vals = self.get_m(ks)
        for (k, v) in sorted(vals.items()):
            _print_k_dots_v(k, v, 40, stream)
        print(file=stream)
        print('=== DB subscriptions ===', file=stream)
        for (pattern, action) in sorted(self._subscriptions.items()):
            _print_k_dots_v(pattern, action.__name__, 40, stream)


# TODO: always a RedisDatabase. Make configurable or get rid of ABC.
def make_database(client_name, addr: str = 'localhost') -> Database:
    db = RedisDatabase(client_name)
    db.connect(addr)
    return db
