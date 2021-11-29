import pathlib

from setuptools import setup


def obtain_requirements(file_name):
    with open(file_name) as fd_in:
        for line in fd_in:
            if "#" not in line:
                yield line.strip()


requirements = list(obtain_requirements("requirements.txt"))
requirements_dev = list(obtain_requirements("requirements-dev.txt"))

HERE = pathlib.Path(__file__).parent

README = (HERE / "README.md").read_text()

# This call to setup() does all the work
setup(
    name="fastapi-injector",
    version="0.1.0",
    description="python-injector integration for FastAPI",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/matyasrichter/fastapi-injector",
    author="Matyas Richter",
    author_email="mail@mrichter.cz",
    license="BSD",
    packages=["fastapi_injector"],
    install_requires=requirements,
    extras_require={"dev": requirements_dev},
)
