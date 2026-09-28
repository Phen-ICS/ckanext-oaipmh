"""CKAN plugin exposing this repository's datasets over OAI-PMH (the
server direction - see provider.py for why this is a separate concern
from harvester.py's OaipmhHarvester, which is the client direction)."""

import logging

from flask import Blueprint, Response, request

from ckan.plugins import toolkit
import ckan.plugins as p

from oaipmh.server import Server, oai_dc_writer
from oaipmh.metadata import MetadataRegistry
from oaipmh.error import ErrorBase

from ckanext.oaipmh.provider import CKANOAIProvider, METADATA_PREFIX

log = logging.getLogger(__name__)

blueprint = Blueprint("oaipmh_provider", __name__)


def _server():
    registry = MetadataRegistry()
    registry.registerWriter(METADATA_PREFIX, oai_dc_writer)
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
