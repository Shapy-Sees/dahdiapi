# dahdi-phone-api/setup.py

from setuptools import setup, find_packages

setup(
    name="dahdi_phone",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "fastapi==0.68.0",
        "uvicorn==0.15.0",
        "websockets==10.1",
        "pydantic==1.8.2",
        "PyYAML==6.0",
        "python-multipart==0.0.5",
        "asyncio==3.4.3",
        "aiofiles==0.8.0",
        "typing-extensions==4.0.1",
        "structlog==21.5.0",
        "python-json-logger==2.0.7"
    ],
    python_requires=">=3.9",
        entry_points={
        "console_scripts": [
            "dahdi-phone-api=dahdi_phone.api.server:run_server"
        ]
    },
    description="REST and WebSocket API for DAHDI telephony hardware",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
    ],
)