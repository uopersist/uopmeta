__author__ = 'samantha'

from sjautils import index
oid_sep = '_'
id_field = 'id'

_sequence_index = lambda bits=64: index.make_id(bits)


def has_uuid_form(str):
    legal_chars = lambda s: all([(x in index.radix.alphabet) for x in s])
    parts = str.split(oid_sep)
    return (len(parts) == 2) and all([legal_chars(p) for p in parts])

def make_oid(cls_id):
    seq = _sequence_index()
    return f'{seq}{oid_sep}{cls_id}' if cls_id else seq

def oid_class(oid):
    return oid.split(oid_sep)[-1]

def oid_class_matcher(cls_id):
    return lambda oid: oid_class(oid) == cls_id

