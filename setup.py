import sys
from setuptools import setup

from downstream_node import __version__

# Reqirements for all versions of Python
install_requires = [
    'flask',
    'pymysql',
    'flask-sqlalchemy',
    'heartbeat==0.1.2',
]

# Requirements for Python 2
if sys.version_info < (3,):
    extras = [
        'mysql-python',
    ]
    install_requires.extend(extras)

setup(
    name='downstream_node',
    version=__version__,
    packages=['downstream_node','downstream_node.config','downstream_node.lib'],
    url='https://github.com/Storj/downstream-node',
    license='MIT',
    author='Storj Labs',
    author_email='info@storj.io',
    description='Verification node for the Storj network',
    install_requires=install_requires,
    dependency_links=[
        'git+https://github.com/Storj/heartbeat.git@v0.1.2#egg=heartbeat-0.1.2'
    ],
)
