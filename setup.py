# encoding=utf8
import os
from setuptools import setup, find_packages

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

README = read('README.md')

setup(
    name = "django-time-tracking",
    version = "0.7.0",
    url = 'http://github.com/samluescher/django-time-tracking',
    license = 'BSD',
    description = "",
    long_description = README,

    author = u'Samuel Luescher',
    author_email = 'sam at luescher dot org',
    
    packages = find_packages(),
    include_package_data=True,

    classifiers = [
        'Development Status :: 4 - Beta',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP',
    ]
)

print find_packages()