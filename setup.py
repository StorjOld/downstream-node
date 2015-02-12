import sys
from setuptools import setup

with open('downstream_node/version.py','r') as f:
    exec(f.read())

# Reqirements for all versions of Python
install_requires = [
    'pymysql',
    'flask-sqlalchemy',
    'flask',
    'RandomIO>=0.20',
    'storj-heartbeat>=01.10',
    'base58',
    'maxminddb',
    'siggy>=0.1.0',
    'pymongo',
    'line_profiler',
    'ijson',
    'future'
]

dependencies = [
    'https://github.com/Storj/heartbeat/tarball/master#egg=storj-heartbeat-0.1.10',
    'https://github.com/Storj/RandomIO/tarball/master#egg=RandomIO-0.2.0',
    'https://github.com/Storj/siggy/tarball/master#egg=siggy-0.1.0'
]

if sys.version_info < (3,):
    extras = [
        'ipaddr',
    ]
    install_requires.extend(extras)

setup(
    name='downstream-node',
    version=__version__,
    packages=['downstream_node'],
    url='https://github.com/Storj/downstream-node',
    license='MIT',
    author='Storj Labs',
    author_email='info@storj.io',
    description='Verification node for the Storj network',
    dependency_links=dependencies,
    install_requires=install_requires
)
