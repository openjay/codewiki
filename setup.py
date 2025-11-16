from setuptools import find_packages, setup

setup(
    name="codewiki",
    version="1.2.0",
    packages=find_packages(),
    install_requires=["pyyaml>=6.0", "requests>=2.28"],
    entry_points={"console_scripts": ["codewiki=codewiki.cli:main"]},
)

