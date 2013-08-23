import sys
import setuptools

setuptools.setup(
    license="MIT",
    name="sc2bnet",
    version='1.0.0',
    keywords=["starcraft 2", "sc2", "battle.net", "bnet", "api"],
    description="Utility for querying the Starcraft II Battle.net API",
    long_description=open("README.rst").read()+"\n\n"+open("CHANGELOG.rst").read(),

    author="Graylin Kim",
    author_email="graylin.kim@gmail.com",
    url="https://github.com/GraylinKim/sc2bnet",

    platforms=["any"],

    classifiers=[
            "Development Status :: 5 - Production/Stable",
            "Environment :: Console",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: MIT License",
            "Natural Language :: English",
            "Operating System :: OS Independent",
            "Programming Language :: Python",
            "Programming Language :: Python :: 2.6",
            "Programming Language :: Python :: 2.7",
            "Programming Language :: Python :: 3.2",
            "Programming Language :: Python :: 3.3",
            "Programming Language :: Python :: Implementation :: PyPy",
            "Programming Language :: Python :: Implementation :: CPython",
            "Topic :: Games/Entertainment",
            "Topic :: Games/Entertainment :: Real Time Strategy",
            "Topic :: Software Development",
            "Topic :: Software Development :: Libraries",
            "Topic :: Utilities",
    ],
    py_modules=['sc2bnet'],
    entry_points={
        'console_scripts': ['sc2bnet = sc2bnet:main']
    },
    install_requires=['argparse','unittest2','requests']  if float(sys.version[:3]) < 2.7 else ['requests'],
)
