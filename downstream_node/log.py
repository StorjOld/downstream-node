import pymongo
import datetime


class mongolog(object):

    def __init__(self, uri):
        self.client = pymongo.MongoClient(uri)
        self.db = self.client.get_default_database()
        self.events = self.db.events

    def log_exception(self, ex, context=None):
        self.log_event('exception', {'type': type(ex).__name__,
                                     'value': str(ex),
                                     'context': context})

    def log_event(self, type, value):
        event = {'time': datetime.datetime.utcnow(),
                 'type': type,
                 'value': value}
        self.events.insert(event)
