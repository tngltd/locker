#!/usr/bin/env python3
"""
Setup script for Lock-Down Service
"""

from setuptools import setup, find_packages
import os

# Read the README file
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "Lock-Down Service for Ubuntu systems"

# Read requirements
def read_requirements():
    requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    if os.path.exists(requirements_path):
        with open(requirements_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []

setup(
    name="lock-service",
    version="1.0.0",
    author="Lock Service Team",
    author_email="admin@example.com",
    description="A security service for Ubuntu systems to lock down devices when lost/stolen",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/example/lock-service",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Security",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.6",
    install_requires=read_requirements(),
    entry_points={
        "console_scripts": [
            "lock-service=lock_service:main",
            "lock-cli=lock_cli:main",
        ],
    },
    data_files=[
        ("/etc/lock-service", [
            "config/init_config.json",
            "config/security_policies.json",
        ]),
        ("/usr/local/bin", [
            "lock-service.py",
            "lock-cli.py",
        ]),
        ("/usr/local/share/lock-service/scripts", [
            "scripts/install.sh",
            "scripts/setup.sh",
        ]),
        ("/usr/local/share/lock-service/docs", [
            "docs/user_manual.md",
            "docs/admin_guide.md",
        ]),
    ],
    include_package_data=True,
    zip_safe=False,
    keywords="security, lock, ubuntu, android, authentication",
    project_urls={
        "Bug Reports": "https://github.com/example/lock-service/issues",
        "Source": "https://github.com/example/lock-service",
        "Documentation": "https://github.com/example/lock-service/wiki",
    },
)
