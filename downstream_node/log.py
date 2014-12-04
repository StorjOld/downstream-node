import pymongo
import datetime


class mongolog(object):

    def __init__(self, uri, server_alias = None):
        self.client = pymongo.MongoClient(uri)
        self.db = self.client.get_default_database()
        self.events = self.db.events
        self.server = server_alias

    def log_exception(self, ex, context=None):
        self.log_event('exception', {'type': type(ex).__name__,
                                     'value': str(ex),
                                     'context': context})

    def log_event(self, type, value):
        event = {'time': datetime.datetime.utcnow(),
                 'type': type,
                 'value': value,
                 'server': self.server}
        self.events.insert(event)
