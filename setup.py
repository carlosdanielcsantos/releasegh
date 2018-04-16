from setuptools import setup

setup(
    name='releasegh',
    version='0.1.1',
    py_modules=['releasegh'],
    author = 'Carlos Daniel Santos',
    description = 'Bump and release to Github',
    install_requires = [
        "rst2ghmd >= 0.1.0",
        "requests >= 2.18.4, < 3.0",
    ],
    dependency_links=[
        'git+ssh://git@github.com/carlosdanielcsantos/rst2ghmd.git@v0.1.0'
        '#egg=rst2ghmd-0.1.0',
    ],
    entry_points={
        'console_scripts': ['releasegh=releasegh:cli']
    },
    platforms='any')
