from enum import Enum

class AssocsRequired(str, Enum):
    any = "any"
    all = "all"
    none = "none"

class AttributeOperation(str, Enum):
    gte = '>='
    gt = '>'
    lte = '<='
    lt = '<'
    eq = '=='
    neq = '!='
    like = 'like'
    not_like = 'not_like'

