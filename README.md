![CKAN](https://img.shields.io/badge/CKAN-2.12-orange)
![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-AGPL--3.0-blue)

# ckanext-oaipmh

[OAI-PMH](https://www.openarchives.org/pmh/) for CKAN, in both
directions - two independent plugins, enable either or both:

| Plugin | Direction | What it does |
|---|---|---|
| `oaipmh_provider` | **CKAN -> others** | Serves the catalogue's public datasets as an OAI-PMH 2.0 repository at `<ckan url>/oai`, for other catalogues and aggregators to harvest |
| `oaipmh_harvester` | **others -> CKAN** | Imports the records of any OAI-PMH repository (HAL, arXiv, Zenodo, institutional archives...) as CKAN datasets, with [ckanext-harvest](https://github.com/ckan/ckanext-harvest) |

> Fork of [mediasuitenz/ckanext-oaipmh](https://github.com/mediasuitenz/ckanext-oaipmh),
> maintained by [Phen-ICS](https://github.com/Phen-ICS) (CNRS/IGBMC) for
> the [FAIR3R](https://fair3r.fr) catalogue.

## What this fork changes

- **New: the OAI-PMH server** (`oaipmh_provider`), described below.
- **CKAN 2.12** (SQLAlchemy 2.0) harvester fixes, checked end to end
  against arXiv (gather, fetch and import):
  - a harvest source with an empty Configuration field no longer crashes;
  - `metadata_modified` is no longer copied into the extras, where it
    collided with CKAN's own field and made every record fail validation.
- Uses the maintained [`oaipmh`](https://pypi.org/project/oaipmh/) package
  ([eth-library/oaipmh](https://github.com/eth-library/oaipmh)) instead of
  the original `pyoai`, which crashes with current lxml.
- CI: ruff and bandit on every push.

## Installation

1. Install the OAI-PMH library, then the plugin, in CKAN's virtualenv:

   ```shell
   pip install oaipmh==3.2.1
   pip install -e "git+https://github.com/Phen-ICS/ckanext-oaipmh.git#egg=ckanext-oaipmh"
   ```

2. Enable the plugin(s) in `ckan.ini`:

   ```ini
   ckan.plugins = ... oaipmh_provider
   # and/or, with ckanext-harvest installed and enabled:
   ckan.plugins = ... harvest oaipmh_harvester
   ```

3. Restart CKAN.

## The OAI-PMH server (`oaipmh_provider`)

- **Endpoint**: `<ckan url>/oai` (`GET` or `POST`), with the six OAI-PMH
  verbs: `Identify`, `ListMetadataFormats`, `ListSets`, `ListIdentifiers`,
  `ListRecords`, `GetRecord`. Long lists are paged with `resumptionToken`.
  Try it: `<ckan url>/oai?verb=Identify`.
- **Only public datasets**: records come from `package_search` as an
  anonymous user, so a private dataset is invisible (`GetRecord` answers
  `idDoesNotExist`, as if it didn't exist).
- **Sets = organizations**: `ListRecords&set=<organization name>` lists
  one organization's datasets.
- **Metadata formats**:

  | Format | When | Content |
  |---|---|---|
  | `oai_dc` | always | Dublin Core: title, creator, description, date, publisher, subject, rights, identifier, type |
  | `oai_datacite` | when [ckanext-doi](https://github.com/Phen-ICS/ckanext-doi) is installed | The same DataCite XML as the dataset's DOI - with FAIR3R, the full FDF metadata (ORCID, ROR, genes, organisms...). A dataset without DOI metadata (e.g. a harvested one) is left out of this format |

- **Settings** (optional):

  | Setting | Default | Meaning |
  |---|---|---|
  | `ckanext.oaipmh.repository_id` | `ckan.site_url`'s host name | Namespace of the record ids, `oai:<this>:<dataset id>`. Set it when `ckan.site_url` differs between environments, so ids stay stable |
  | `ckanext.oaipmh.admin_email` | `ckanext.contact.mail_to`, then `email_to` | Contact address given by `Identify` |

  The repository name is `ckan.site_title`; the `oai_datacite` data centre
  symbol is `ckanext.doi.account_name`.

## The harvester (`oaipmh_harvester`)

Needs [ckanext-harvest](https://github.com/ckan/ckanext-harvest), its
queue (Redis) and a **sysadmin user named `harvest`**.

1. Go to `<ckan url>/harvest/new`.
2. **URL**: the OAI-PMH base URL of the source, e.g.
   `https://export.arxiv.org/oai2` (see the
   [registered repositories](https://www.openarchives.org/Register/BrowseSites)).
3. **Source type**: *OAI-PMH Harvester*.
4. **Configuration** (optional, JSON, keys can be combined):

   | Key | Use |
   |---|---|
   | `"set": "physics"` | Harvest one set only |
   | `"metadata_prefix": "oai_dc"` | Metadata format (`oai_dc` or `oai_ddi`) |
   | `"username": "...", "password": "..."` | Source with HTTP authentication |
   | `"force_http_get": true` | Source that doesn't accept POST |

5. Save, then **Reharvest**.

The harvest consumers must be running (FAIR3R runs them under
supervisor):

```shell
ckan -c /path/to/ckan.ini harvester gather-consumer
ckan -c /path/to/ckan.ini harvester fetch-consumer
ckan -c /path/to/ckan.ini harvester run    # start pending jobs
```

## Development

CI runs `ruff` and `bandit` (see `.github/workflows/`). The tests under
`ckanext/oaipmh/tests` come from the original project and are not
maintained; the server was checked against a real `oaipmh.client.Client`
on CKAN 2.12, every verb, paging and set filter included.

## Credits and license

Based on the [mediasuitenz](https://github.com/mediasuitenz/ckanext-oaipmh)
version of the harvester first written for the kata project (CSC - IT
Center for Science, Liip AG). Released under the GNU Affero
General Public License v3.0 - see [`LICENSE.txt`](LICENSE.txt).
