import cProfile
from line_profiler import LineProfiler
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
from downstream_node import routes

application = app.test_client()

#pr = cProfile.Profile()
pr = LineProfiler(routes.api_downstream_status_list)


for i in range(0,1):
    pr.enable()

    with patch('downstream_node.routes.request') as request:
        r = application.get('/status/list/by/d/uptime')
    assert(r.status_code==200)

    pr.disable()
    
    r_json = json.loads(r.data.decode('utf-8'))
    with open('status.txt','a') as f:
        f.write(r.data.decode('utf-8'))


#ps = pstats.Stats(pr)
#ps.print_stats()
pr.print_stats()