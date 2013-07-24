from distutils.core import setup

setup(
    name='django-time-tracking',
    version='0.9.0',
    author='Samuel Luescher',
    author_email='sam@luescher.org',
    packages=['time_tracking'],
    scripts=[],
    url='http://github.com/samluescher/django-time-tracking',
    license='LICENSE',
    description='',
    long_description=open('README.md').read(),
    install_requires=[
        "Django >= 1.3"
    ],
)