from os import path
from typing import Union, List
from setuptools import setup
import io, os


PATH_HERE = path.abspath(path.dirname(__file__))
#
# # Get the long description from the README file
# with open(path.join(PATH_HERE, 'README.md'), encoding='utf-8') as fp:
#     long_description = fp.read()
#
# # Get the list of required packages
# with open(path.join(PATH_HERE, "requirements.txt"), encoding="utf-8") as fp:
#     requirements = [req.rstrip() for req in fp.readlines() if "-r" not in req]


def read(f_relative_path: str, read_lines: bool = False) -> Union[List[str], str]:
    """Return the contents of file f_relative_path as a string, or a list of strings if read_lines is True.

    :param f_relative_path: the file path relative to this script folder.
    :param read_lines: if True return list of lines, else return a single string.
    :return: the content of the file.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    with io.open(os.path.join(here, f_relative_path), mode="rt", encoding="utf8") as f:
        return f.readlines() if read_lines else f.read()


setup(
    name='pdf_tools',
    version='0.1',
    url='https://bitbucket.kendaya.net/projects/KXLAB/repos/pdf-tools/',
    author=u"Kendaxa",
    author_email="develop@kendaxa.com",

    description='tools for reading and processing pdf content',
    long_description=read("README.md"),
    long_description_content_type='text/x-rst',
    classifiers=[
        'Development Status :: 3 - Alpha',
        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],

    packages=["pdf_tools"],
    include_package_data=True,
    python_requires='>=3.6',
    install_requires=read("requirements.txt", read_lines=True),
)
