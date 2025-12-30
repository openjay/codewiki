from setuptools import find_packages, setup

setup(
    name="codewiki",
    version="2.1.0",
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=[
        "pyyaml>=6.0",
        "requests>=2.28",
        # LIR dependencies (optional, for LIR integration)
        # Install LIR separately: pip install -e ../lir
    ],
    entry_points={"console_scripts": ["codewiki=codewiki.cli:main"]},
)

