import pathlib
import setuptools


setuptools.setup(
    name='captain',
    version='0.0.1',
    description='core captain download manager',
    author='Jean-Edouard Boulanger',
    url='https://github.com/jean-edouard-boulanger/captain',
    author_email="jean.edouard.boulanger@gmail.com",
    license='MIT',
    packages=[
        'captain',
        'captain.core',
        'captain.server'
    ],
    install_requires=[
        'requests',
        'socketio',
        'aiohttp',
        'pyyaml'
    ]
)
