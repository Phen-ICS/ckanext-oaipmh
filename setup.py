from setuptools import setup, find_packages

version = '1.4.0'

setup(
    name='ckanext-oaipmh',
    version=version,
    description="OAI-PMH Harvester for CKAN",
    long_description="",
    classifiers=[],
    keywords='',
    author='Liip AG',
    author_email='ogd@liip.ch',
    url='http://www.liip.ch',
    license='AGPL',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    namespace_packages=['ckanext'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        # -*- Extra requirements: -*-
    ],
    entry_points='''
        [ckan.plugins]
        oaipmh_harvester=ckanext.oaipmh.harvester:OaipmhHarvester
        oaipmh_provider=ckanext.oaipmh.plugin:OaipmhProviderPlugin
    ''',
)
