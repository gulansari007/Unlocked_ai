from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="unlocked-ai",
    version="0.1.0",
    description="Unlocked AI: Unified Agent Orchestrator & CLI Tool with Material 3 UI",
    author="Unlocked AI Contributors",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "server": ["static/*", "static/**/*"],
    },
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "unlocked=server.cli:main",
        ]
    },
    python_requires=">=3.10",
)
