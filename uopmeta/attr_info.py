import random, time
from uopmeta import oid
from sjautils import index, date_time
import datetime



uuid_attr_id = '1'

crud_kinds = ['objects', 'classes', 'attributes', 'roles', 'tags',
              'groups', 'queries']

meta_kinds = crud_kinds[1:]

assoc_kinds = ['tagged', 'grouped', 'related']

kinds = crud_kinds + assoc_kinds


def random_pick(lst):
    return lst[random.randint(0, len(lst) - 1)]


def make_meta_id():
    return index.make_id(32)

def random_int():
    return random.getrandbits(32)

def random_float():
    return float(random_int() / random_int())

def random_date():
    return date_time.epoch_to_datetime(time.time() - random_float())

def random_string():
    return "str%d" % random_int()

def random_uuid(cls_id):
    return oid.make_oid(cls_id)

def random_email():
    return 'sjatkins+%s@gmail.com' % random_string()

class AttrType:
    def __init__(self, html5='txt'):
        self.html5 = html5

    def default(self):
        return ''

    def random_instance(self, *args):
        return ''

class IntType(AttrType):
    def random_instance(self):
        return random_int()

    def default(self):
        return 0

class FloatType(AttrType):
    def default(self):
        return 0.0

    def random_instance(self):
        return random_float()

class EpochType(FloatType):
    def random_instance(self):
        return time.time() - random_float()

class UUIDType(AttrType):
    def random_instance(self, clsid):
        return random_uuid(clsid)

class PhoneType(AttrType):
    def __init__(self):
        super().__init__(html5='tel')

    def random_instance(self):
        super().random_instance()

    def default(self):
        return '1-999-999-9999'

class StringType(AttrType):
    def random_instance(self):
        return random_string()

    def default(self):
        return ''

class TextType(StringType):
    pass

class EmailType(AttrType):
    def __init__(self):
        super().__init__(html5='email')

    def random_instance(self, *args):
        return 'sjatkins+%s@gmail.com' % random_string()

class DateType(AttrType):
    def __init__(self):
        super().__init__(html5='date')

    def default(self):
        return datetime.datetime.now().date()

    def random_instance(self, *args):
        return date_time.epoch_to_datetime(time.time() - random_float()).date()


random_time = lambda: time.time()

attribute_types = {
    'uuid': UUIDType(),
    'int':  IntType(),
    'long':  IntType(),
    'float': FloatType(),
    'phone': PhoneType(),
    'email': EmailType(),
    'string': StringType(),
    'text': TextType(),
    'date': EpochType(),
    'datetime': EpochType(),
    'json': StringType(),
    'epoch': EpochType(),
}
