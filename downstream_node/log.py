import pymongo
import datetime


class mongolog(object):

    def __init__(self, host='localhost', port=27017):
        self.client = pymongo.MongoClient(host, port)
        self.db = client.log_database
        self.events = self.db.events

    def log_exception(self, ex):
        self.log_event('exception', {'type': type(ex), 'value': str(ex)})

    def log_event(self, type, value):
        event = {'time': datetime.datetime.utcnow(),
                 'type': type,
                 'value': value}
        self.events.insert(event)
