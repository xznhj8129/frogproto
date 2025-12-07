import sys
from setuptools import setup, find_packages

if sys.version_info < (3, 8):
    sys.exit("Sorry, Python < 3.8 is not supported.")

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="frogproto",
    packages=[package for package in find_packages()],
    version="0.1",
    license="GPL",
    description="Runtime protocol payload helpers from JSON schema",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Frogmane",
    author_email="",
    url="https://github.com/xznhj8129/frogproto",
    download_url="",
    include_package_data=True,
    keywords=["protocol", "msgpack"],
    install_requires=["msgpack", "pydantic"],
    package_data={"frogproto": ["protocol/*.json"]},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries",
    ],
)
