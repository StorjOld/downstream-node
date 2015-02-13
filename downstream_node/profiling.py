from flask import request, g, render_template, url_for, Response
from line_profiler import LineProfiler
import inspect
import os
import linecache
import pymongo
import pygments
import traceback
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter
import datetime

from .startup import app

from . import node, routes, utils


def get_object_function_info(object):
    functions = list()
    for item in inspect.getmembers(object, inspect.isfunction):
        # print('Inspecting member {0}'.format(item))
        try:
            functions.append(item[1])
        except:
            pass

    return functions


def collect_module_functions(modules):
    functions = list()
    for m in modules:
        # print('Inspecting {0}'.format(m))
        functions.extend(get_object_function_info(m))
    return functions


@app.before_request
def start_profiling():
    if (app.config['PROFILE'] and app.mongo_logger is not None):
        if (not hasattr(g, 'profiler') or g.profiler is None):
            setattr(g, 'profiler', LineProfiler())
            # print('Collecting function info')
            function_info = collect_module_functions([node, routes, utils])
            for f in function_info:
                # print('Adding profile framework for function {0}'.format(f))
                g.profiler.add_function(f)
            app.mongo_logger.db.profiling.create_index('path', unique=True)
        g.profiler.enable()


def timing_key_to_str(k):
    return '_'.join([k[0], str(k[1]), k[2]]).replace('.', '_')


@app.teardown_request
def finish_profiling(exception=None):
    if (app.config['PROFILE'] and app.mongo_logger is not None):
        g.profiler.disable()
        stats = g.profiler.get_stats()
        # stats is an object with these properties:
        # timings : dict
        #   Mapping from (filename, first_lineno, function_name) of the
        #   profiled
        #   function to a list of (lineno, nhits, total_time) tuples for each
        #   profiled line. total_time is an integer in the native units of the
        #   timer.
        # unit : float
        #   The number of seconds per timer unit.
        functions = list(stats.timings.keys())
        lines = list(stats.timings.values())

        app.mongo_logger.db.profiling.update(
            {'path': request.path},
            {'path': request.path,
             'functions': functions,
             'lines': lines,
             'unit': stats.unit,
             'time': datetime.datetime.utcnow()},
            upsert=True)


def get_function_source_hits(logged_function, line_hits, unit):
    filename = logged_function[0]
    if (not os.path.isfile(filename)):
        return (None, None)
    mod = datetime.datetime.fromtimestamp(os.path.getmtime(filename))
    source_hits = list()
    line_dict = {l[0]: l for l in line_hits}
    start_line = min(line_dict.keys())
    end_line = max(line_dict.keys())
    for lineno in range(logged_function[1], start_line):
        function_def = linecache.getline(filename, lineno)
        source_hits.append((function_def.rstrip(), None, None))

    for hit in range(start_line, end_line + 1):
        source_line = linecache.getline(filename, hit)
        if (hit in line_dict):
            source_hits.append(
                (source_line.rstrip(),
                 line_dict[hit][1],
                 float(line_dict[hit][2]) * float(unit)))
        else:
            source_hits.append((source_line.rstrip(), None, None))
    return (source_hits, mod)

@app.route('/profile/')
def profiling_recent():
    if (app.config['PROFILE'] and app.mongo_logger is not None):
        db_paths = app.mongo_logger.db.profiling.find().sort('time', pymongo.DESCENDING).limit(20)
        paths = [{'name': p['path'].strip('/'),
                  'link': url_for('profiling_profile', path=p['path'].strip('/')),
                  'time': p['time'] if 'time' in p else None}
                 for p in db_paths]
        return render_template('recent.html',
                               paths=paths)
    else:
        return 'Profiling is disabled.'
    
@app.route('/profile/<path:path>')
def profiling_profile(path):
    try:
        if (app.config['PROFILE'] and app.mongo_logger is not None):
            mod_path = '/' + path
            print('Showing profile for route: {0}'.format(mod_path))
            p = app.mongo_logger.db.profiling.find_one({'path': mod_path})
            if (p is None):
                return 'Path not found.'
            if ('time' in p):
                time = p['time']
            else:
                time = None
            request = dict(path=p['path'],
                           functions=list(),
                           time=time)
            lexer = PythonLexer()
            style = HtmlFormatter().get_style_defs()
            for i in range(0, len(p['functions'])):
                if any([len(l) > 0 for l in p['lines'][i]]):
                    (lines, mod) = get_function_source_hits(p['functions'][i],
                                                            p['lines'][i],
                                                            p['unit'])
                    formatter = HtmlFormatter(linenos='inline',
                                              linenostart=p['functions'][i][1])
                    if (lines is None):
                        continue
                    source_html = pygments.highlight(
                        '\n'.join([j[0] for j in lines]),
                        lexer,
                        formatter)
                    source_lines = source_html.split('\n')
                    timings = [(j[1], j[2]) for j in lines]
                    timings.append((None, None))
                    timed_lines = list(zip(source_lines, timings))
                    function = dict(
                        name=p['functions'][i][2],
                        filename=p['functions'][i][0],
                        timed_lines=timed_lines,
                        mod=mod)
                    request['functions'].append(function)

            return render_template('profile.html',
                                   path=path,
                                   request=request,
                                   style=style)
        else:
            return 'Profiling disabled.  Sorry!'
    except:
        return Response(traceback.format_exc(), mimetype='text/plain')

