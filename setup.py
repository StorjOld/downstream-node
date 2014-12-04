import sys
from setuptools import setup

with open('downstream_node/version.py','r') as f:
    exec(f.read())

# Reqirements for all versions of Python
install_requires = [
    'flask',
    'pymysql',
    'flask-sqlalchemy',
    'RandomIO',
    'storj-heartbeat',
    'base58',
    'maxminddb',
    'siggy',
    'pymongo'
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
    install_requires=install_requires
)
