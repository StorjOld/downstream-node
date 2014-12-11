import cProfile
import pstats
import json
import io
import pickle
import heartbeat
import datetime
from RandomIO import RandomIO

from mock import patch
from downstream_node.startup import app, db
from downstream_node import models
from downstream_node import node
from downstream_node import config

test_address = '19qVgG8C6eXwKMMyvVegsi3xCsKyk3Z3jV'

application = app.test_client()
app.config['MAX_TOKENS_PER_IP'] = 10000
app.config['TEST_FILE_SIZE'] = 100000

db.create_all()
if (models.Address.query.filter(models.Address.address == test_address).first() is None):
    db.session.add(models.Address(address=test_address,
                                  crowdsale_balance=10000))
db.session.commit()

pr = cProfile.Profile()


for i in range(0,100):
    with patch('downstream_node.routes.request') as request:
        request.remote_addr = '17.0.0.1'
        request.method = 'POST'
        request.get_json.return_value = dict({'signature': 'HyzVUenXXo4pa+kgm1vS8PNJM83eIXFC5r0q86FGbqFcdla6rcw72/ciXiEPfjli3ENfwWuESHhv6K9esI0dl5I=',
                                              'message': 'test message'})
        r = application.get('/new/{0}'.format(test_address))

    r_json = json.loads(r.data.decode('utf-8'))


    beat = app.config['HEARTBEAT'].fromdict(r_json['heartbeat'])

    r_token = r_json['token']

    with patch('downstream_node.routes.request') as request:
        request.remote_addr = '17.0.0.1'
        r = application.get('/chunk/{0}'.format(r_token))

    r_json = json.loads(r.data.decode('utf-8'))

    r_seed = r_json['seed']
    r_hash = r_json['file_hash']

    tag = app.config['HEARTBEAT'].tag_type().fromdict(r_json['tag'])

    contents = RandomIO(r_seed).read(r_json['size'])

    with patch('downstream_node.routes.request') as request:
        request.remote_addr = '17.0.0.1'
        r = application.get('/challenge/{0}/{1}'.format(r_token,r_hash))
    assert(r.status_code==200)    
    r_json = json.loads(r.data.decode('utf-8'))

    chal = app.config['HEARTBEAT'].challenge_type().fromdict(r_json['challenge'])

    f = io.BytesIO(contents)
    proof = beat.prove(f,chal,tag)

    with patch('downstream_node.routes.request') as request:
        request.remote_addr = '17.0.0.1'
        data = {"proof":proof.todict()}
        request.get_json.return_value = data
        r = application.post('/answer/{0}/{1}'.format(r_token,r_hash),
                             data=json.dumps(data),
                             content_type='application/json')
        assert(r.status_code==200)
        r_json = json.loads(r.data.decode('utf-8'))
        assert(r_json['status']=='ok')

    # force due date to have passed
    db_contract = node.lookup_contract(r_token,r_hash)
    db_contract.due = datetime.datetime.utcnow()-datetime.timedelta(seconds=1)
    db.session.commit()

pr.enable()

for i in range(0,10):
    with patch('downstream_node.routes.request') as request:
        r = application.get('/status/list/by/d/uptime')
    assert(r.status_code==200)


pr.disable()

ps = pstats.Stats(pr)
ps.print_stats()