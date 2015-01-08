from flask import jsonify, request
from line_profiler import LineProfiler
from pymongo import MongoClient
import inspect

def get_module_function_info(module):
    functions = list()
    for item in inspect.getmembers(module,inspect.isfunction):
        try:
            functions.append(item[0], inspect.getfile(item[1]), inspect.getsourcelines(item[1])[-1])
        except:
            pass

    return functions    
    

    
@app.before_request
def start_profiling():
    if (app.config['PROFILE'] and app.mongo_logger is not None):
        if (g.profiler is None):
            g.profiler = LineProfiler()        
        g.profiler.enable()

@app.teardown_request
def finish_profiling():
    if (app.config['PROFILE'] and app.mongo_logger is not None):        
        g.profiler.disable()
        stats = g.profiler.get_stats()
        app.mongo_logger.db.profile.insert(

        
        