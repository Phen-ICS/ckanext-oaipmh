from oaipmh.metadata import MetadataReader

oai_ddi_reader = MetadataReader(
    fields={
        'title':        ('textList', 'oai_ddi:codeBook/stdyDscr/citation/titlStmt/titl/text()'),
        'creator':      ('textList', 'oai_ddi:codeBook/stdyDscr/citation/rspStmt/AuthEnty/text()'),
        'subject':      ('textList', 'oai_ddi:codeBook/stdyDscr/stdyInfo/subject/keyword/text()'),
        'description':  ('textList', 'oai_ddi:codeBook/stdyDscr/stdyInfo/abstract/text()'),
        'publisher':    ('textList', 'oai_ddi:codeBook/stdyDscr/citation/distStmt/contact/text()'),
        'contributor':  ('textList', 'oai_ddi:codeBook/stdyDscr/citation/contributor/text()'),
        'date':         ('textList', 'oai_ddi:codeBook/stdyDscr/citation/prodStmt/prodDate/text()'),
        'series':       ('textList', 'oai_ddi:codeBook/stdyDscr/citation/serStmt/serName/text()'),
        'type':         ('textList', 'oai_ddi:codeBook/stdyDscr/stdyInfo/sumDscr/dataKind/text()'),
        'format':       ('textList', 'oai_ddi:codeBook/fileDscr/fileType/text()'),
        'identifier':   ('textList', "oai_ddi:codeBook/stdyDscr/citation/titlStmt/IDNo/text()"),
        'source':       ('textList', 'oai_ddi:codeBook/stdyDscr/dataAccs/setAvail/accsPlac/@URI'),
        'language':     ('textList', 'oai_ddi:codeBook/@xml:lang'),
        'tempCoverage': ('textList', 'oai_ddi:codeBook/stdyDscr/stdyInfo/sumDscr/timePrd/text()'),
        'geoCoverage':  ('textList', 'oai_ddi:codeBook/stdyDscr/stdyInfo/sumDscr/geogCover/text()'),
        'rights':       ('textList', 'oai_ddi:codeBook/stdyInfo/citation/prodStmt/copyright/text()')
    },
    namespaces={
        'oai_ddi': 'http://www.icpsr.umich.edu/DDI',
    }
)

# Note: maintainer_email is not part of Dublin Core
oai_dc_reader = MetadataReader(
    fields={
        'title':            ('textList', 'oai_dc:dc/dc:title/text()'),
        'creator':          ('textList', 'oai_dc:dc/dc:creator/text()'),
        'subject':          ('textList', 'oai_dc:dc/dc:subject/text()'),
        'description':      ('textList', 'oai_dc:dc/dc:description/text()'),
        'publisher':        ('textList', 'oai_dc:dc/dc:publisher/text()'),
        'maintainer_email': ('textList', 'oai_dc:dc/oai:maintainer_email/text()'),
        'contributor':      ('textList', 'oai_dc:dc/dc:contributor/text()'),
        'date':             ('textList', 'oai_dc:dc/dc:date/text()'),
        'type':             ('textList', 'oai_dc:dc/dc:type/text()'),
        'format':           ('textList', 'oai_dc:dc/dc:format/text()'),
        'identifier':       ('textList', 'oai_dc:dc/dc:identifier/text()'),
        'source':           ('textList', 'oai_dc:dc/dc:source/text()'),
        'language':         ('textList', 'oai_dc:dc/dc:language/text()'),
        'relation':         ('textList', 'oai_dc:dc/dc:relation/text()'),
        'coverage':         ('textList', 'oai_dc:dc/dc:coverage/text()'),
        'rights':           ('textList', 'oai_dc:dc/dc:rights/text()')
    },
    namespaces={
        'oai_dc': 'http://www.openarchives.org/OAI/2.0/oai_dc/',
        'oai': 'http://www.openarchives.org/OAI/2.0/',
        'dc': 'http://purl.org/dc/elements/1.1/'}
)
