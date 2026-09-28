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

from ckan.plugins import toolkit
from oaipmh.common import Header, Metadata, Identify
from oaipmh.error import IdDoesNotExistError, NoRecordsMatchError
from oaipmh.datestamp import datetime_to_datestamp

log = logging.getLogger(__name__)

METADATA_PREFIX = "oai_dc"
OAI_ID_PREFIX = "oai"


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
    return "{}:{}:{}".format(OAI_ID_PREFIX, _repository_id(), package_id)


def package_id_from_oai_identifier(identifier):
    prefix = "{}:{}:".format(OAI_ID_PREFIX, _repository_id())
    if not identifier.startswith(prefix):
        return None
    return identifier[len(prefix):]


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
        identifiers.append("https://doi.org/{}".format(doi))

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


def _record(pkg):
    return (_header(pkg), Metadata(None, _dc_map(pkg)), None)


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
        return [
            (
                METADATA_PREFIX,
                "http://www.openarchives.org/OAI/2.0/oai_dc.xsd",
                "http://www.openarchives.org/OAI/2.0/oai_dc/",
            )
        ]

    def listSets(self):
        organizations = toolkit.get_action("organization_list")(
            {"ignore_auth": False}, {"all_fields": True}
        )
        return [
            (org["name"], org["title"] or org["name"], None)
            for org in organizations
        ]

    def _search(self, set=None, from_=None, until=None):
        query_parts = ["*:*"]
        if set:
            query_parts.append('organization:"{}"'.format(set))
        if from_ or until:
            start = datetime_to_datestamp(from_) if from_ else "*"
            end = datetime_to_datestamp(until) if until else "*"
            query_parts.append("metadata_modified:[{} TO {}]".format(start, end))

        rows = 1000
        start_row = 0
        while True:
            page = toolkit.get_action("package_search")(
                {"ignore_auth": False},
                {"q": " AND ".join(query_parts), "rows": rows, "start": start_row},
            )
            results = page.get("results") or []
            for pkg in results:
                yield pkg
            start_row += rows
            if start_row >= page.get("count", 0) or not results:
                return

    def listIdentifiers(self, metadataPrefix, set=None, from_=None, until=None):
        packages = list(self._search(set=set, from_=from_, until=until))
        if not packages:
            raise NoRecordsMatchError("No records match the given criteria")
        return [_header(pkg) for pkg in packages]

    def listRecords(self, metadataPrefix, set=None, from_=None, until=None):
        packages = list(self._search(set=set, from_=from_, until=until))
        if not packages:
            raise NoRecordsMatchError("No records match the given criteria")
        return [_record(pkg) for pkg in packages]

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
        return _record(pkg)
