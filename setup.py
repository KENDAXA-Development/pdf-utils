from os import path
from setuptools import setup


PATH_HERE = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(PATH_HERE, 'README.md')) as fp:
    long_description = fp.read()

# Get the list of required packages
with open(path.join(PATH_HERE, "requirements.txt")) as fp:
    requirements = [req.rstrip() for req in fp.readlines() if "-r" not in req]


setup(
    name='kx-pdf-tools',
    version='0.1',
    url='https://bitbucket.kendaya.net/projects/KXLAB/repos/pdf-tools/',
    author=u"Kendaxa",
    author_email="develop@kendaxa.com",

    description='tools for reading and processing pdf content',
    long_description=long_description,
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

    packages=["kx_pdf_tools"],
    include_package_data=True,
    python_requires='>=3.6',
    install_requires=requirements
)
