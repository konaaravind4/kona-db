"""KonaDB — MySQL-compatible database engine with AI features."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="kona-db",
    version="1.0.0",
    author="Kona",
    author_email="kona@example.com",
    description="A MySQL-compatible database engine with AI features, "
                "supporting structured and unstructured data.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/konaaravind4/kona-db",
    packages=find_packages(),
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "kona=kona.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Database",
        "Topic :: Database :: Database Engines/Servers",
    ],
    extras_require={
        "ai": [],  # AI features use stdlib urllib, no extra deps needed
        "dev": ["pytest>=7.0"],
    },
)
