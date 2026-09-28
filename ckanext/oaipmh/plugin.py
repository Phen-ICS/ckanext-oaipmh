"""CKAN plugin exposing this repository's datasets over OAI-PMH (the
server direction - see provider.py for why this is a separate concern
from harvester.py's OaipmhHarvester, which is the client direction)."""

import logging

from flask import Blueprint, Response, request
from lxml import etree
from lxml.etree import SubElement

import ckan.plugins as p

from oaipmh.server import Server, oai_dc_writer
from oaipmh.metadata import MetadataRegistry
from oaipmh.error import ErrorBase

from ckanext.oaipmh.provider import (
    CKANOAIProvider,
    DC_PREFIX,
    DATACITE_PREFIX,
    DATACITE_NAMESPACE,
    DOI_AVAILABLE,
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
        element, "{{{}}}oai_datacite".format(DATACITE_NAMESPACE), nsmap={None: DATACITE_NAMESPACE}
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
    return Server(CKANOAIProvider(), metadata_registry=registry)


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
        log.exception("Unhandled error answering OAI-PMH request %r", params)
        return Response(str(e), status=500, mimetype="text/plain")
    return Response(xml, mimetype="text/xml")


class OaipmhProviderPlugin(p.SingletonPlugin):
    p.implements(p.IBlueprint)

    def get_blueprint(self):
        return blueprint
