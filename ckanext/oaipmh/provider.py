"""OAI-PMH server-side exposure: CKAN datasets as an OAI-PMH repository.

This is the *server* direction of the protocol (other repositories harvest
metadata from us) - the opposite of harvester.py, which makes CKAN a
*client* harvesting other OAI-PMH repositories. Backed entirely by CKAN's
own package_search action, so it inherits CKAN's public/private
visibility rules for free: querying as an anonymous user (no 'user' key,
no ignore_auth) is exactly what package_search already restricts to
public, active datasets.
"""

import logging
from urllib.parse import urlparse

from ckan.lib.search.query import solr_literal
from ckan.plugins import toolkit
from oaipmh.common import Header, Identify, Metadata
from oaipmh.datestamp import datetime_to_datestamp
from oaipmh.error import CannotDisseminateFormatError, IdDoesNotExistError

log = logging.getLogger(__name__)

DC_PREFIX = "oai_dc"
OAI_ID_PREFIX = "oai"

# Dublin Core is deliberately minimal (15 fixed elements) and has no room
# for FAIR3R/FDF's own rich, domain-specific fields (genes, alleles,
# species...). ckanext-doi already builds a full DataCite XML record for
# every FDF dataset (to mint its DOI) - reusing it here, instead of
# reinventing a second metadata mapping, is both less code and the
# metadataPrefix a real DataCite-aware harvester actually expects
# (see support.datacite.org/docs/oai-pmh-schema-documentation).
DATACITE_PREFIX = "oai_datacite"
DATACITE_NAMESPACE = "http://schema.datacite.org/oai/oai-1.1/"
DATACITE_SCHEMA_VERSION = "4.5"

try:
    from datacite import schema45

    from ckanext.doi.lib.metadata import build_metadata_dict, build_xml_dict

    DOI_AVAILABLE = True
except ImportError:
    DOI_AVAILABLE = False


def _repository_id():
    """Stable namespace identifier for oai:<id>:<local-id> - a real
    domain name, not affected by ckan.site_url varying between dev,
    integration, validation and production (see ckan/lib/jobs.py-style
    envvars overrides elsewhere in this stack)."""
    configured = toolkit.config.get("ckanext.oaipmh.repository_id")
    if configured:
        return configured
    site_url = toolkit.config.get("ckan.site_url", "")
    return urlparse(site_url).netloc or "localhost"


def oai_identifier(package_id):
    return f"{OAI_ID_PREFIX}:{_repository_id()}:{package_id}"


def package_id_from_oai_identifier(identifier):
    prefix = f"{OAI_ID_PREFIX}:{_repository_id()}:"
    if not identifier.startswith(prefix):
        return None
    return identifier[len(prefix) :]


def _admin_email():
    # ckanext.contact.mail_to is the address fair3r's own contact form
    # actually delivers to (see ckan/scripts/entrypoint.sh's config-tool
    # call) - a more meaningful default here than the generic, usually
    # unset "email_to" core CKAN setting.
    return (
        toolkit.config.get("ckanext.oaipmh.admin_email")
        or toolkit.config.get("ckanext.contact.mail_to")
        or toolkit.config.get("email_to", "")
    )


def _parse_datestamp(value):
    # oaipmh.datestamp.datetime_to_datestamp asserts its input is
    # timezone-naive (see oaipmh/datestamp.py) - CKAN's own timestamps
    # ("2026-09-28T09:35:32.592456") already are, and already UTC, so
    # this is just a straight parse, no tzinfo attached.
    from datetime import datetime

    return datetime.fromisoformat(value)


def _dc_map(pkg):
    """Build the Dublin Core field map oaipmh.server.oai_dc_writer expects
    (a dict of DC element name -> list of string values)."""
    organization = pkg.get("organization") or {}
    author = pkg.get("author") or organization.get("title") or ""
    identifiers = [toolkit.url_for("dataset.read", id=pkg["name"], qualified=True)]
    doi = pkg.get("doi_identifier")
    if doi:
        identifiers.append(f"https://doi.org/{doi}")

    dc = {
        "title": [pkg["title"]],
        "identifier": identifiers,
        "type": ["Dataset"],
        "date": [pkg.get("metadata_modified", pkg.get("metadata_created", ""))[:10]],
    }
    if author:
        dc["creator"] = [author]
    if pkg.get("notes"):
        dc["description"] = [pkg["notes"]]
    if organization.get("title"):
        dc["publisher"] = [organization["title"]]
    tags = [t["name"] for t in pkg.get("tags", [])]
    if tags:
        dc["subject"] = tags
    license_title = pkg.get("license_title")
    if license_title:
        dc["rights"] = [license_title]
    return dc


def _datacite_map(pkg):
    """Build the map oaipmh_provider's own datacite writer (plugin.py)
    expects: the same DataCite XML ckanext-doi builds to mint this
    dataset's DOI, wrapped per the OAI-DataCite schema.

    Raises CannotDisseminateFormatError for a dataset that was never
    meant to carry DOI metadata in the first place (e.g. a dataset
    harvested from an OAI-PMH *source*, not created through FDF) -
    ckanext-doi's own build_metadata_dict requires fields like a
    properly formatted creator name that such datasets don't have
    (confirmed directly: ValueError: Creator name must be supplied,
    the same failure already known from harvest_source_update - see
    the migration doc's "Trouvaille annexe" section)."""
    try:
        metadata_dict = build_metadata_dict(pkg)
        xml_dict = build_xml_dict(metadata_dict)
        resource_xml = schema45.tostring(xml_dict)
    except (ValueError, KeyError) as e:
        raise CannotDisseminateFormatError(f"{DATACITE_PREFIX}: {e}")
    # lxml's fromstring() (used by the writer in plugin.py to re-parse
    # this) refuses a unicode str carrying an XML declaration - only
    # bytes are accepted in that case. tostring() returns either,
    # depending on datacite package version.
    if isinstance(resource_xml, str):
        resource_xml = resource_xml.encode("utf-8")
    return {
        "schemaVersion": DATACITE_SCHEMA_VERSION,
        "datacentreSymbol": toolkit.config.get("ckanext.doi.account_name", ""),
        "resource_xml": resource_xml,
    }


def _metadata_map(pkg, metadata_prefix):
    if metadata_prefix == DATACITE_PREFIX:
        if not DOI_AVAILABLE:
            raise CannotDisseminateFormatError(metadata_prefix)
        return _datacite_map(pkg)
    return _dc_map(pkg)


def _header(pkg):
    organization = pkg.get("organization") or {}
    setspec = [organization["name"]] if organization.get("name") else []
    return Header(
        None,
        oai_identifier(pkg["id"]),
        _parse_datestamp(pkg.get("metadata_modified", pkg.get("metadata_created"))),
        setspec,
        False,
    )


def _record(pkg, metadata_prefix):
    return (_header(pkg), Metadata(None, _metadata_map(pkg, metadata_prefix)), None)


class CKANOAIProvider:
    """Implements oaipmh.interfaces.IOAI, wrapped by oaipmh.server.Server
    (which adds resumptionToken-based pagination on top for free - this
    class just needs to answer each request in full, unpaginated)."""

    def identify(self):
        earliest = toolkit.get_action("package_search")(
            {"ignore_auth": False}, {"rows": 1, "sort": "metadata_created asc"}
        )
        results = earliest.get("results") or []
        earliest_datestamp = (
            _parse_datestamp(results[0]["metadata_created"])
            if results
            else _parse_datestamp("1970-01-01T00:00:00")
        )
        return Identify(
            repositoryName=toolkit.config.get("ckan.site_title", "CKAN"),
            baseURL=toolkit.url_for("oaipmh_provider.index", qualified=True),
            protocolVersion="2.0",
            adminEmails=[_admin_email()],
            earliestDatestamp=earliest_datestamp,
            deletedRecord="no",
            granularity="YYYY-MM-DDThh:mm:ssZ",
            compression=["identity"],
        )

    def listMetadataFormats(self, identifier=None):
        formats = [
            (
                DC_PREFIX,
                "http://www.openarchives.org/OAI/2.0/oai_dc.xsd",
                "http://www.openarchives.org/OAI/2.0/oai_dc/",
            )
        ]
        if DOI_AVAILABLE:
            formats.append(
                (
                    DATACITE_PREFIX,
                    "http://schema.datacite.org/oai/oai-1.1/oai.xsd",
                    DATACITE_NAMESPACE,
                )
            )
        return formats

    def listSets(self, cursor=0, batch_size=10):
        # BatchingResumption passes cursor/batch_size for ListSets too,
        # despite IBatchingOAI's own docstring only mentioning them for
        # listIdentifiers/listRecords (confirmed directly: omitting them
        # here raises "got an unexpected keyword argument 'cursor'").
        # CKAN organizations are always few enough to fetch in one go
        # and slice in Python - no Solr paging needed.
        organizations = toolkit.get_action("organization_list")(
            {"ignore_auth": False}, {"all_fields": True}
        )
        sets = [
            (org["name"], org["title"] or org["name"], None) for org in organizations
        ]
        return sets[cursor : cursor + batch_size]

    def _search_page(self, start, rows, set=None, from_=None, until=None):
        """One direct Solr page - no accumulation, no internal looping.
        Used as-is by listIdentifiers (IBatchingOAI's cursor/batch_size
        map straight onto Solr's own start/rows) and as the building
        block listRecords loops over below."""
        query_parts = ["*:*"]
        if set:
            # set is caller-controlled (the OAI-PMH `set` request param,
            # unauthenticated) and was going straight into a raw Solr
            # query string - a real Solr/Lucene query injection (a
            # crafted value could break out of the quoted term and
            # inject arbitrary query clauses, or just crash the request
            # with a syntax error, confirmed directly with
            # set=x" OR *:*"). solr_literal is the same escape CKAN's
            # own core uses for this exact class of value (a single
            # token being matched exactly, e.g. site_id).
            query_parts.append(f"organization:{solr_literal(set)}")
        if from_ or until:
            start_ts = datetime_to_datestamp(from_) if from_ else "*"
            end_ts = datetime_to_datestamp(until) if until else "*"
            query_parts.append(f"metadata_modified:[{start_ts} TO {end_ts}]")
        return toolkit.get_action("package_search")(
            {"ignore_auth": False},
            {"q": " AND ".join(query_parts), "rows": rows, "start": start},
        )

    def listIdentifiers(
        self, metadataPrefix, set=None, from_=None, until=None, cursor=0, batch_size=10
    ):
        # _header() never fails (every real CKAN package has an id and a
        # metadata_created/modified timestamp) - a direct, single Solr
        # page maps cleanly onto BatchingServer's cursor/batch_size with
        # no risk of the two falling out of sync.
        page = self._search_page(cursor, batch_size, set=set, from_=from_, until=until)
        return [_header(pkg) for pkg in page.get("results") or []]

    def listRecords(
        self, metadataPrefix, set=None, from_=None, until=None, cursor=0, batch_size=10
    ):
        # Unlike listIdentifiers, a record can fail to build in the
        # requested format (see _datacite_map: a dataset without DOI
        # metadata can't be disseminated as oai_datacite) and gets left
        # out - so a single direct Solr page could come back short even
        # though more matching datasets exist further in the catalog.
        # This loops through as many additional Solr pages as needed to
        # either fill this one batch or exhaust the catalog, keeping the
        # cost bounded to "one page worth of skips", not the whole
        # catalog (the previous, pre-batching behaviour). Advances
        # `position` past every dataset it looks at, success or skip, so
        # the next page picks up exactly where this one left off within
        # the underlying catalog ordering.
        #
        # Known limitation specific to this format: BatchingServer's own
        # resumptionToken always advances the cursor it hands back by a
        # fixed `batch_size`, not by how far `position` actually moved
        # here - so if a page's worth of skips pushes `position` past
        # `cursor + batch_size`, the *next* page's cursor (computed by
        # the library, not by this method) can undercount slightly.
        # Every dataset that can be disseminated as oai_datacite is
        # still reachable via ListRecords overall (nothing is
        # permanently hidden), but a harvester paginating through a
        # catalog with many non-DOI datasets mixed in could see a
        # handful of duplicate records across pages in this one format.
        # Not a concern for oai_dc, which every dataset can always be
        # disseminated as.
        records = []
        position = cursor
        while len(records) < batch_size:
            page = self._search_page(
                position, batch_size - len(records), set=set, from_=from_, until=until
            )
            results = page.get("results") or []
            if not results:
                break
            for pkg in results:
                position += 1
                try:
                    records.append(_record(pkg, metadataPrefix))
                except CannotDisseminateFormatError:
                    log.info(
                        "Skipping %s from ListRecords(%s): cannot disseminate",
                        pkg.get("name"),
                        metadataPrefix,
                    )
                if len(records) >= batch_size:
                    break
        return records

    def getRecord(self, metadataPrefix, identifier):
        package_id = package_id_from_oai_identifier(identifier)
        if not package_id:
            raise IdDoesNotExistError(identifier)
        try:
            pkg = toolkit.get_action("package_show")(
                {"ignore_auth": False}, {"id": package_id}
            )
        except (toolkit.ObjectNotFound, toolkit.NotAuthorized):
            raise IdDoesNotExistError(identifier)
        return _record(pkg, metadataPrefix)
