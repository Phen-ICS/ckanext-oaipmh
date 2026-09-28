# CKAN OAI-PMH Harvester and Server

This is a [Phen-ICS](https://github.com/Phen-ICS) fork of
[mediasuitenz/ckanext-oaipmh](https://github.com/mediasuitenz/ckanext-oaipmh),
adding two fixes needed to run under **CKAN 2.12** (SQLAlchemy 2.0):
- `_set_config()` no longer crashes when a harvest source's Configuration
  field is left blank (a normal, supported case).
- `metadata_modified` is no longer duplicated into the generic extras list,
  where it collided with CKAN's own reserved `metadata_modified` field and
  made every harvested record fail validation.

It also expects the [`oaipmh`](https://pypi.org/project/oaipmh/) package
(the actively maintained [eth-library/oaipmh](https://github.com/eth-library/oaipmh)
fork of `pyoai`) rather than the original, unmaintained `pyoai` — the
original crashes under modern lxml (`XPathEvaluator.evaluate` was removed).

Verified end-to-end against a real OAI-PMH source (arXiv) under CKAN
2.12 + SQLAlchemy 2.0.51: gather, fetch and import all complete and real
datasets get created.

## OAI-PMH server (`oaipmh_provider`)

Added on top of the original fork: a second, independent plugin exposing
this CKAN instance's own **public** datasets as an OAI-PMH 2.0 repository,
so other systems can harvest *from* it (the opposite direction from
`oaipmh_harvester` above, which harvests *into* CKAN).

- Add `oaipmh_provider` to `ckan.plugins`.
- Endpoint: `<ckan url>/oai` (`GET` or `POST`), answering all six OAI-PMH
  verbs (`Identify`, `ListMetadataFormats`, `ListSets`, `ListIdentifiers`,
  `ListRecords`, `GetRecord`).
- Metadata format: Dublin Core (`oai_dc`) only, for now.
- **Sets = CKAN organizations** (one-to-one; use groups instead if a
  dataset ever needs to belong to more than one set at a time - CKAN
  organizations are exclusive, groups aren't).
- Backed by `package_search` in an anonymous context, so CKAN's own
  public/private visibility rules apply automatically - a private dataset
  is invisible to `ListRecords`/`ListIdentifiers` and `GetRecord` answers
  `idDoesNotExist` for one, exactly as if it didn't exist. Verified
  directly against a real private dataset, not just assumed from reading
  the code.
- `ckanext.oaipmh.repository_id` (optional): the namespace identifier
  used in `oai:<this>:<dataset-id>`. Defaults to `ckan.site_url`'s
  hostname, which is fine for a stable production URL but should be set
  explicitly if `ckan.site_url` varies between environments (as it does
  in this stack's own dev/integration/validation/production contexts).
- `ckanext.oaipmh.admin_email` (optional): defaults to
  `ckanext.contact.mail_to` (the address this stack's own contact form
  delivers to), falling back to core CKAN's `email_to`.

Verified against a real `oaipmh.client.Client` (the same library
`oaipmh_harvester` itself uses) round-tripping every verb, including
transparent multi-page `resumptionToken` pagination and a `set` filter,
against a real CKAN 2.12 instance.

## CKAN < 2.9 support
As of `1.1.0` this extention has been made to work with CKAN 2.9. While attempts have been made to maintain compatibility with prior version of CKAN, there may be issues. If any issues are discovered we are happy to accept PRs. Alternatively for compatibility <2.9 the `1.0.0` tag can be used.
## Instructions

### Installation

Use `pip` to install this plugin. This example installs it in `/var/www`

```bash
source /home/www-data/pyenv/bin/activate
pip install -e git+https://github.com/mediasuitenz/ckanext-oaipmh.git#egg=ckanext-oaipmh --src /var/www
cd /var/www/ckanext-oaipmh
pip install -r requirements.txt
python setup.py develop
```

Make sure the ckanext-harvest extension is installed as well.

**Important: You need to have a sysadmin user called "harvest" on your CKAN instance!**

### Setup the Harvester

- add `oaipmh_harvester` to `ckan.plugins` in `development.ini` (or `production.ini`)
- restart your webserver
- with the web browser go to `<your ckan url>/harvest/new`
- as URL fill in the base URL of an OAI-PMH conforming repository, e.g. http://boris.unibe.ch/cgi/oai2
for more see http://www.openarchives.org/Register/BrowseSites
- select **Source type** `OAI-PMH Harvester`
- if your OAI-PMH needs credentials, add the following to the "Configuration" section: `{"username": "foo", "password": "bar" } `
- if you only want to harvest a specific set, add the following to the "Configuration" section: `{"set": "baz"} `
- if you want to harvest data in a specific metadata format, add the following to the "Configuration" section: `{"metadata_prefix": "oai_dc"}` (currently `oai_dc` and `oai_ddi` are supported)
- if your OAI-PMH source does not support HTTP POST and you want to enforce HTTP GET, add the following to the "Configuration" section: `{"force_http_get": true}`  (defaults to `false`)
- Save
- on the harvest admin click **Reharvest**

### Run the Harvester

On the command line do this:

- activate the python environment
- `cd` to the ckan directory, e.g. `/usr/lib/ckan/default/src/ckan`
- start the consumers:

```bash
# ckan >= 2.9
ckan harvester gather-consumer
ckan harvester fetch-consumer

# ckan < 2.9
paster --plugin=ckanext-oaipmh harvester gather_consumer
paster --plugin=ckanext-oaipmh harvester fetch_consumer
```

- run the job:

```bash
# ckan >= 2.9
ckan harvester run

# ckan < 2.9
paster --plugin=ckanext-oaipmh harvester run
```

The harvester should now start and import the OAI-PMH metadata.

## Developing without running jobs manually

To make it easier to develop, tests are setup that allow to do that:

    . ~/default/bin/activate
    cd /var/www/ckanext-oaipmh

    nosetests --logging-filter=ckanext.oaipmh.harvester --ckan --with-pylons=test.ini ckanext/oaipmh/tests

In this example the logging filter is used to only show messages of the harvester.
