from setuptools import setup

from downstream_node import __version__

setup(
    name='downstream-node',
    version=__version__,
    packages=['downstream_node'],
    url='',
    license='',
    author='Storj Labs',
    author_email='info@storj.io',
    description='',
    install_requires=[
        'flask',
        'mysql-python',
        'flask-sqlalchemy',
        'heartbeat==0.1.2',
    ],
    dependency_links=[
        'https://github.com/Storj/heartbeat/archive/v0.1.2.tar.gz#egg=heartbeat-0.1.2'
    ],
)
