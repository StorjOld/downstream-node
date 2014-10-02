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
    'storj-heartbeat'
]

# Requirements for Python 2
if sys.version_info < (3,):
    extras = [
        'mysql-python',
    ]
    install_requires.extend(extras)

setup(
    name='downstream-node',
    version=__version__,
    packages=['downstream_node','downstream_node.config','downstream_node.lib'],
    url='https://github.com/Storj/downstream-node',
    license='MIT',
    author='Storj Labs',
    author_email='info@storj.io',
    description='Verification node for the Storj network',
    install_requires=install_requires
)
