import sys
from setuptools import setup
from setuptools.command.test import test as TestCommand

with open('downstream_node/version.py','r') as f:
    exec(f.read())

# Reqirements for all versions of Python
install_requires = [
    'pymysql',
    'flask-sqlalchemy',
    'flask',
    'RandomIO>=0.2.1',
    'storj-heartbeat>=0.1.10',
    'base58',
    'maxminddb',
    'siggy>=0.1.0',
    'pymongo',
    'line_profiler',
    'ijson',
    'future',
    'pygments'
]

test_requirements = [
    'base58',
    'mock',
    'pytest',
    'pytest-pep8',
    'pytest-cache',
    'coveralls'
]


class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = []

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # Import PyTest here because outside, the eggs are not loaded.
        import pytest
        import sys
        errno = pytest.main(self.pytest_args)
        sys.exit(errno)

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
    license=open('LICENSE').read(),
    author='Storj Labs',
    author_email='info@storj.io',
    description='Verification node for the Storj network',
    install_requires=install_requires,
    tests_require=test_requirements,
    cmdclass={'test': PyTest}
)
