"""CKAN plugin exposing this repository's datasets over OAI-PMH (the
server direction - see provider.py for why this is a separate concern
from harvester.py's OaipmhHarvester, which is the client direction)."""

import logging

import ckan.plugins as p
from flask import Blueprint, Response, request
from lxml import etree
from lxml.etree import SubElement
from oaipmh.error import ErrorBase
from oaipmh.metadata import MetadataRegistry
from oaipmh.server import BatchingServer, oai_dc_writer

from ckanext.oaipmh.provider import (
    DATACITE_NAMESPACE,
    DATACITE_PREFIX,
    DC_PREFIX,
    DOI_AVAILABLE,
    CKANOAIProvider,
)

log = logging.getLogger(__name__)

blueprint = Blueprint("oaipmh_provider", __name__)


def oai_datacite_writer(element, metadata):
    """Writer for the oai_datacite format: wraps the DataCite <resource>
    XML provider.py already built (via ckanext-doi's own DOI-minting
    metadata) in the OAI-DataCite envelope - see
    support.datacite.org/docs/oai-pmh-schema-documentation."""
    map = metadata.getMap()
    e_wrapper = SubElement(
        element,
        f"{{{DATACITE_NAMESPACE}}}oai_datacite",
        nsmap={None: DATACITE_NAMESPACE},
    )
    e_schema_version = SubElement(e_wrapper, "schemaVersion")
    e_schema_version.text = map["schemaVersion"]
    e_datacentre = SubElement(e_wrapper, "datacentreSymbol")
    e_datacentre.text = map["datacentreSymbol"]
    e_payload = SubElement(e_wrapper, "payload")
    e_payload.append(etree.fromstring(map["resource_xml"]))


def _server():
    registry = MetadataRegistry()
    registry.registerWriter(DC_PREFIX, oai_dc_writer)
    if DOI_AVAILABLE:
        registry.registerWriter(DATACITE_PREFIX, oai_datacite_writer)
    return BatchingServer(CKANOAIProvider(), metadata_registry=registry)


@blueprint.route("/oai", methods=["GET", "POST"])
def index():
    params = request.values.to_dict()
    try:
        xml = _server().handleRequest(params)
    except ErrorBase as e:
        # oaipmh's own Server.handleRequest already renders OAI-PMH
        # <error> elements into the response XML for protocol-level
        # errors (bad verb, bad argument, etc.) - this only catches
        # something unexpected escaping that.
        log.exception("Unhandled OAI-PMH error answering %r", params)
        return Response(str(e), status=500, mimetype="text/plain")
    except Exception:
        # oaipmh.server.XMLTreeServer.handleException re-raises anything
        # that isn't its own ErrorBase, so a genuine bug here (not a
        # protocol-level error) would otherwise reach Flask itself -
        # normally a generic 500, but the full interactive Werkzeug
        # debugger (source, local variables, an eval console) if this
        # ever ran with debug mode on, to a caller /oai never
        # authenticates. Catching broadly here and always returning a
        # flat message is what an anonymous, unauthenticated public
        # endpoint needs regardless of the app's own debug setting -
        # the real detail still goes to the log, not the response.
        log.exception("Unexpected error answering OAI-PMH request %r", params)
        return Response("Internal error", status=500, mimetype="text/plain")
    return Response(xml, mimetype="text/xml")


class OaipmhProviderPlugin(p.SingletonPlugin):
    p.implements(p.IBlueprint)

    def get_blueprint(self):
        return blueprint
