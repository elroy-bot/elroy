#!/usr/bin/env python
from setuptools import find_packages, setup

setup(
    name="elroy-web-api",
    version="0.1.0",
    description="Web API for Elroy assistant",
    author="Elroy Bot",
    author_email="bot@elroy.ai",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn>=0.23.2",
        "python-jose>=3.3.0",
        "passlib>=1.7.4",
        "python-multipart>=0.0.6",
        "bcrypt>=4.0.1",
        "elroy",
    ],
    entry_points={
        "console_scripts": [
            "elroy-web-api=elroy.web_api.run:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.10",
)
