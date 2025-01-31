# single_file_dev01/setup.py

from setuptools import setup, find_packages

setup(
    name='single_file_dev01',
    version='1.0.0',
    description='A tool for flattening and analyzing codebases with multiple output formats.',
    author='Your Name',
    author_email='your.email@example.com',
    packages=find_packages(),
    install_requires=[
        # List your dependencies here, e.g.,
        # 'requests>=2.25.1',
    ],
    entry_points={
        'console_scripts': [
            'flattenx=single_file_dev01.__main__:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
