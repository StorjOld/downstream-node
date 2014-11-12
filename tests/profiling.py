import cProfile
import pstats
import json
import heartbeat
import RandomIO

from mock import patch
from downstream_node.startup import app, db
from downstream_node import models
from downstream_node import node
from downstream_node import config


application = app.test_client()

pr = cProfile.Profile()

pr.enable()

with patch('downstream_node.routes.request') as request:
    request.remote_addr = '17.0.0.1'
    request.method = 'POST'
    request.get_json.return_value = dict({'signature': 'HyzVUenXXo4pa+kgm1vS8PNJM83eIXFC5r0q86FGbqFcdla6rcw72/ciXiEPfjli3ENfwWuESHhv6K9esI0dl5I=',
                                          'message': 'test message'})
    r = application.get('/new/{0}'.format('19qVgG8C6eXwKMMyvVegsi3xCsKyk3Z3jV'))

r_json = json.loads(r.data.decode('utf-8'))

beat = app.config['HEARTBEAT'].fromdict(r_json['heartbeat'])

r_token = r_json['token']

with patch('downstream_node.routes.request') as request:
    request.remote_addr = '17.0.0.1'
    r = application.get('/chunk/{0}'.format(r_token))

r_json = json.loads(r.data.decode('utf-8'))

r_seed = r_json['seed']
r_hash = r_json['file_hash']

contents = RandomIO(r_seed).read(app.config['TEST_FILE_SIZE'])

chal = app.config['HEARTBEAT'].challenge_type().fromdict(r_json['challenge'])

tag = app.config['HEARTBEAT'].tag_type().fromdict(r_json['tag'])

f = io.BytesIO(contents)
proof = beat.prove(f,chal,tag)

with patch('downstream_node.routes.request') as r:
    r.remote_addr = '17.0.0.1'
    data = {"proof":proof.todict()}
    r.get_json.return_value = data
    p.return_value = dict()
    r = application.post('/answer/{0}/{1}'.format(r_token,r_hash),
                      data=json.dumps(data),
                      content_type='application/json')

pr.disable()

ps = pstats.Stats(pr)
ps.print_stats()
