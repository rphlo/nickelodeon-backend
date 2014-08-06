import os

#from distutils.core import setup
from setuptools import setup
from distutils.command.install import INSTALL_SCHEMES
import importlib

package_name = 'nickelodeon'

for scheme in INSTALL_SCHEMES.values():
    scheme['data'] = scheme['purelib']


os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

packages, data_files = [], []
for dirpath, dirnames, filenames in os.walk(package_name, followlinks=True):
    # Ignore dirnames that start with '.'
    for i, dirname in enumerate(dirnames):
        if dirname.startswith('.') or dirname == 'tests':
            del dirnames[i]
    if '__init__.py' in filenames:
        packages.append('.'.join(dirpath.split(os.path.sep)))
    elif filenames:
        data_files.append([dirpath,
                           [os.path.join(dirpath, f) for f in filenames]])
mod = importlib.import_module(package_name)
setup(
    name=package_name,
    version='.'.join(str(x) for x in mod.__version__),
    license="MIT License",
    description='Django project for music streaming',
    long_description='',
    url='',
    author='Raphael Stefanini',
    author_email='rphl@rphl.net',
    packages = packages,
    data_files = data_files,
    classifiers=[
      'Development Status :: Beta',
      'Environment :: Web Environment',
      'Framework :: Django',
      'Intended Audience :: Developers',
      'License :: OSI Approved :: BSD License',
      'Operating System :: OS Independent',
      'Programming Language :: Python',
    ],
    install_requires=[
        'common_base',
        'djangorestframework',
        'celery',
        'scandir',
    ],
)
