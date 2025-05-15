from pydantic import BaseModel
from typing import List, Optional, Any, Dict, ClassVar
from pydantic import Field, root_validator
from uopmeta.oid import oid_sep, make_oid, oid_class
from uopmeta.attr_info import attribute_types, meta_kinds
from uopmeta.schemas.enums import AssocsRequired, AttributeOperation
from sjautils import index
from sjautils.dicts import first_kv, DictObject
from sjautils.string import after
import random
from functools import partial
from collections import defaultdict
make_app_id = lambda: index.make_id(48)

def legal_chars(s):
    return all([(x in index.radix.alphabet) for x in s])

get_field = lambda d, f: d.get(f) if isinstance(d, dict) else getattr(d, f, None)

as_dict = lambda d: d if isinstance(d, dict) else d.dict()
as_object = lambda d: d if isinstance(d, BaseModel) else DictObject(d)

def as_tuple(d):
    if isinstance(d, tuple):
        return d
    return tuple(as_dict(d).items())

def dict_or_tuple(d):
    if isinstance(d, dict):
        return d
    if isinstance(d, tuple):
        return d
    return as_dict(d)

base_types = {
    'uuid': None,
    'int': None,
    'long': None,
    'float': None,
    'string': None,
    'datetime': None,
    'blob': None}

def random_attribute_type():
    type_list = list(base_types.keys())
    return random.choice(type_list[:-1])

def as_dict(data):
    if isinstance(data, BaseModel):
        return data.dict()
    return data

class OID(BaseModel):
    class_id: Optional[str]
    sequence: str

    @classmethod
    def from_(cls, sequence):
        if isinstance(sequence, cls):
            return sequence
        elif isinstance(sequence, str):
            parts = sequence.split(oid_sep)
            if parts and len(parts) < 3:
                args = dict(zip(('sequence', 'class_id'), parts[::-1]))
                return cls(**args)

    @classmethod
    def instance(cls, class_id):
        return cls(class_id=class_id, sequence=index.make_id(64))

    @classmethod
    def meta(cls):
        return cls(sequence=index.make_id(32))

    def __str__(self):
        return f'{self.class_id}{oid_sep}{self.sequence}' if self.class_id else self.sequence


class MetaPermissions(BaseModel):
    sys_defined: bool = False
    app_defined: bool = False
    modifiable: bool = True
    deletable: bool = True

    @root_validator
    def adjust_perms(cle, values):
        values['modifiable'] = values['deletable'] = False
        if values['sys_defined']:
            values['app_defined'] = False
        elif values['app_defined']:
            values['sys_defined'] = False
        else:
            values['modifiable'] = values['deletable'] = True
        return values


class SystemPermissions(MetaPermissions):
    sys_defined: bool =  True


class AppPermissions(MetaPermissions):
    app_defined = True

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(
        make_oid('')), description='primary id ')
    name: str
    email: str = ''
    tenant_id: str = ''
    is_superuser: bool = False
    is_admin: bool = False

class Tenant(BaseModel):
    id: str = Field(default_factory=lambda: str(
        make_oid('')), description='primary id ')
    name: str
    base_collections: Dict[str, str]   # kind -> collection_name
    cls_extensions: Dict[str, str]  # cls.id -> extension collection_name

class ByNameId(BaseModel):
    by_id: dict = {}
    by_name: dict = {}

    def clear(self):
        self.by_id.clear()
        self.by_name.clear()

    def get_id(self, an_id):
        return self.by_id.get(an_id)

    def get_name(self, name):
        return self.by_name.get(name)

    def name_to_id(self, name):
        meta = self.by_name.get(name)
        if meta:
            return meta.id

    def id_to_name(self, an_id):
        meta = self.by_id.get(an_id)
        if meta:
            return meta.name

    def ids_to_names(self, *ids):
        return [self.id_to_name(i) for i in ids]

    def names_to_ids(self, *names):
        return [self.name_to_id(n) for n in names]

    def is_named(self, item):
        return hasattr(item, 'name') or item.get('name')

    def add_item(self, item):
        self.by_id[item.id] = item
        if self.is_named(item):
            self.by_name[item.name] = item

    def remove_item(self, item):
        self.by_id.pop(item.id, None)
        if self.is_named(item):
            self.by_name.pop(item.name, None)



class NameWithId(BaseModel):
    kind = ''
    id: str = Field(default_factory=lambda: str(
        make_oid('')), description='primary id ')
    description: str = ''
    name: str = Field(...)
    permissions: MetaPermissions = Field(default_factory=MetaPermissions)

    def without_kind(self):
        data = self.dict()
        data.pop('kind', None)
        return data

    @classmethod
    def create_random(cls, **kwargs):
        return cls(name='ChangeME!', **kwargs)



    def modifiable(self):
        return self.permissions.modifiable

    def deletable(self):
        return self.permissions.deletable


    def __hash__(self):
        return hash(self.id)

    def get_changes(self, other, changes):
        if self.name != other.name:
            changes.modify(self.id, dict(name=other.name))
        if self.description != other.description:
            changes.modify(self.id, dict(description=other.description))

    def random_instance(self):
        pass

class MetaAttribute(NameWithId):
    kind = 'attributes'
    type: str
    class_name: Optional[str] = Field(
        None, description='name of class that defines this attribute')
    required: bool = False

    def default_value(self):
        info = attribute_types[self.type]
        return info.default()

    @classmethod
    def random_attribute(cls, in_class_id=None):
        my_type = random_attribute_type()
        name = f'attr_{random.randint(1000,9999)}'
        args = {'type': my_type, 'name': name}
        if in_class_id:
            args['class_id'] = in_class_id
        return cls(**args)


    def get_changes(self, other, changes):
        super().get_changes(other, changes.attributes)
        if self.type != other.type:
            changes.attributes.modified(self.id, dict(type = other.type))

    def random_instance(self, *args):
        return attribute_types[self.type].random_instance(*args)


class MetaClass(NameWithId):
    kind = 'classes'
    superclass: str = Field(default='root', description='name of superclass')
    attrs: Optional[List[str]] = Field(description='list of attribute ids')
    attributes: Optional[List[MetaAttribute]]
    short_form: Optional[List[str]]
    instance_collection: str = ''
    is_abstract: bool = False
    mandatory_attributes: List[str] = []

    @classmethod
    def random_class(cls, super_name='PersistentObject'):
        """
        Produce a random MetaClass.  This can be particularly useful
        during testing when there is a need to control things like
        inheritance.
        :param super_name: name of superclass
        :return:  the newly created MetaClass
        """
        num_attrs = random.randint(2, 8)
        name = f'Class_{random.randint(1000, 9999)}'
        attributes = [MetaAttribute.random_attribute() for _ in range(num_attrs)]
        return cls(superclass=super_name, name=name, attributes=attributes)

    @classmethod
    def create_random(cls, **kwargs):
        return cls.random_class(**kwargs)

    @classmethod
    def root(cls):
        return cls(id='r00t', name='PersistentObject', superclass='',
                 attributes=[MetaAttribute(
                     name='id', type='uuid', permissions=SystemPermissions())],
                 description='root supperclass',
                 permissions=SystemPermissions(),
                 is_abstract=True)

    def get_changes(self, other, changes):
        super().get_changes(other, changes.classes)
        diffs = {}
        def if_diff(key):
            other_val = getattr(other, key)
            if getattr(self, key) != other_val:
                diffs[key] = other_val

        def diff_attrs():
            if other.attributes:
                attrs = self.attrs
                others = {a.name: a.id for a in other.attributes}
                mine = {a.name: a.id for a in self.attributes}
                for name, an_id in others.items():
                    if name not in mine:
                        if an_id not in attrs:
                            attrs.append(an_id)
                if attrs != self.attrs:
                    diffs['attrs'] = attrs


        diff_attrs()
        if_diff('superclass')
        if_diff('short_form')
        if diffs:
            changes.classes.modify(self.id, diffs)

    def validate_instance(self, instance_dict):
        exceptions = []
        missing_mandatory = [m for m in self.mandatory_attributes if m not in instance_dict]
        if missing_mandatory:
            exceptions.append(Exception(f'missing mandatory attributes: {missing_mandatory}'))
        return (False, exceptions) if exceptions else (True, [])

    def default_attribute_values(self):
        attr_vals = {}
        for attr in self.attributes:
            a_type = attribute_types[attr.type]
            attr_vals[attr.name] = a_type.default()

        return attr_vals

    def make_default_instance(self):
        self.make_instance(**self.default_attribute_values())

    def make_instance(self, use_defaults=False, **attr_values):
        by_name = [a.name for a in self.attributes]
        # bad_names = [k for k in attr_values if k not in by_name]
        # if bad_names:
        #     raise Exception(f'attributes not in class {self.name}: {bad_names}')
        if not 'id' in attr_values:
            attr_values['id'] = make_oid(self.id)
        if use_defaults:
            defaults = self.default_attribute_values()
            for k,v in defaults.items():
                if k not in attr_values:
                    attr_values[k] = v

        valid, exceptions = self.validate_instance(attr_values)
        if valid:
            return attr_values
        else:
            raise Exception(f'instance errors: {exceptions}')

    def random_instance(self):
        instance = dict()
        for attr in self.attributes:
            k = attr.name
            args = []
            if attr.type == 'uuid':
                args.append(self.id)

            instance[k] = attr.random_instance(*args)
        return self.make_instance(**instance) # ensure id

    def add_attribute(self, name, type, description='', required=False):
        if self.attributes and self.permissions.modifiable:
            known = [a.name for a in self.attributes]
            if name in known:
                raise Exception(f'Class {self.name} alnead contain an attribute named {name}')
            attr = MetaAttribute(name=name, type=type, required=required, description=description,
                                 class_name=self.name)
            self.attrs.append(attr.id)
            self.attributes.append(attr)
        return attr

class MetaTag(NameWithId):
    kind = 'tags'

    @classmethod
    def create_random(cls):
        return cls(name=f'tag_{random.randint(1000, 9999)}')


class MetaRole(NameWithId):
    kind = 'roles'
    reverse_name: str = ''

    @root_validator
    def validate(cls, values):
        if not values.get('reverse_name'):
            values['reverse_name'] = f'{values.get("name")}*'
        return values

    @classmethod
    def create_random(cls):
        return cls(name=f'role_{random.randint(1000, 9999)}')


class MetaGroup(NameWithId):
    kind = 'groups'
    contained_in: List[str] = Field(default=[], description='list of directly containing group names')

    @classmethod
    def create_random(cls):
        return cls(name=f'group_{random.randint(1000, 9999)}')


class QueryComponent(BaseModel):
    kind = ''


    def safisfies(self, dbi, obj_ids=None):
        pass

    def simplify(self):
        pass

    def dict_contents(self):
        return {}

    def to_dict(self):
        if self.kind:
            return {self.kind: self.dict_contents()}


class MetaQuery(NameWithId):
    kind = 'query'
    query: QueryComponent = None

    @classmethod
    def standard_dict_form(cls, data):
        if isinstance(data, cls):
            return data.to_dict()
        elif isinstance(data, dict):
            working = dict(data)
            q = working['query']
            kind, k_data = first_kv(q)
            if isinstance(q, QueryComponent):
                working['query'] = q.to_dict()
            elif kind not in ('class', 'attr', 'tags', 'groups', 'related', 'and', 'or'):
                raise Exception(f'{q} is not legal form of QueryComponent')
            return working

    @classmethod
    def from_dict(cls, d):
        d_s = cls.standard_dict_form(d)
        qc = qc_dict_to_component(d_s['query'])
        d['query'] = qc
        return cls(**d)

    def to_dict(self):
        d = self.dict()
        d['query'] = self.query.to_dict()
        return d

sys_permissioned = partial(MetaClass, permissions=SystemPermissions())

app_permissioned = partial(MetaClass, permissions=AppPermissions())

def app_class(name, superclass, *attributes, description='',  abstract=False,
              **field_values):
    for attribute in attributes:
        attribute.class_name = name
    return app_permissioned(name=name, superclass=superclass,
                         description=description, is_abstrat=abstract,
                         attributes=attributes,
                         **field_values)

def sys_class(name, superclass, *attributes, description='',  abstract=False,
              **field_values):
    for attribute in attributes:
        attribute.class_name = name
    return sys_permissioned(name=name, superclass=superclass,
                         description=description, is_abstrat=abstract,
                         attributes=attributes,
                         **field_values)

class BaseSchema(BaseModel):
    name: str
    classes: List[MetaClass] = []
    attributes: List[MetaAttribute] = []
    roles: List[MetaRole] = []
    tags: List[MetaTag] = []
    groups: List[MetaGroup] = []
    queries: List[MetaQuery] = []

class DBFormSchema(BaseSchema):
    uses_schemas: List[str] = []
    requires_schemas: List[str] = []


class Schema(BaseSchema):
    uses_schemas: List['Schema'] = []
    requires_schemas: List['Schema'] = []

    @classmethod
    def core_schema(cls):
        return cls(
        name='uop_core',
        classes = [root,
                   sys_class('DescribedComponent', 'PersistentObject',
                                  app_attr('createdAt', 'epoch'),
                                  app_attr('description', 'string'),
                                  description='root of all described content', abstract=True),
                   ]

        )

    @classmethod
    def schemas_from_db(cls, db_schemas: List[dict]):
        # shouldn't this be actually in uop.database?
        db_form_schemas = {s['name']:DBFormSchema(**s) for s in db_schemas}
        schemas = {}
        def transformed(name):
            known = schemas.get(name)
            if not known:
                db_schema:DBFormSchema = db_form_schemas.get(name)
                if db_schema:
                    transform = dict(
                        uses_schemas = [transformed(n) for n in db_schema.uses_schemas],
                        requires_schemas = [transformed(n) for n in db_schema.requires_schemas])
                    data = db_schema.dict()
                    data.update(transform)
                    known = schemas[name] = cls(**data)
                else:
                    raise Exception(f'unknown schema named {name}')
            return known

        transformed_schemas = [transformed(d['name']) for d in db_schemas]
        return schemas


    def sub_schemas(self):
        subs = {}
        def add_subs(sub_list):
            for s in sub_list:
                if s.name not in subs:
                    subs[s.name] = s
                    subs.update(s.sub_schemas())
        add_subs(self.uses_schemas)
        add_subs(self.requires_schemas)
        return subs

    def db_form(self):
        uses = [u.name for u in self.uses_schemas]
        requires = [r.name for r in self.requires_schemas]
        data = self.dict()
        data['uses_schemas'] = uses
        data['requires_schemas'] = requires
        return DBFormSchema(**data)

    @root_validator
    def root_validate(cls, values):
        attr_map = {a.id: a for a in values['attributes']}

        for c in values['classes']:
            for attr in c.attributes:
                if attr.id not in attr_map:
                    attr_map[attr.id] = attr
            c.attrs = [a.id for a in c.attributes]
        values['attributes'] = list(attr_map.values())

        if not values['requires_schemas']:
            if values['name'] != 'uop_core':
                values['requires_schemas'] = [cls.core_schema()]

        return values

class MetaContext(BaseModel):
    classes: ByNameId = ByNameId()
    attributes: ByNameId = ByNameId()
    roles: ByNameId = ByNameId()
    tags: ByNameId = ByNameId()
    groups: ByNameId = ByNameId()
    queries: ByNameId = ByNameId()
    group_children: dict = {}
    class_children: dict = {}

    def get_class_children(self):
        if not self.class_children:
            by_name = self.classes.by_name
            res = defaultdict(set)
            for cls in by_name.values():
                cid = cls.id
                if cls.superclass:
                    sid = by_name[cls.superclass].id
                    res[sid].add(cid)
            self.class_children = res


    def deep_copy(self):
        instance = self.__class__()
        for kind in kind_map:
            instance.load_objects(self.metas_of_kind(kind))
        instance.complete()
        return instance


    def metas_of_kind(self, kind):
        return list(self.by_id(kind).values())

    def _by_name_id(self, kind):
        what = getattr(self, kind)
        if isinstance(what, ByNameId):
            return what

    def ids_to_names(self, kind):
        return self._by_name_id(kind).ids_to_names

    def names_to_ids(self, kind):
        return self._by_name_id(kind).names_to_ids

    def name_map(self, kind):
        return getattr(self, kind).by_name

    def id_map(self, kind):
        return getattr(self, kind).by_id

    def id_to_name(self, kind):
        return self._by_name_id(kind).id_to_name

    def name_to_id(self, kind):
        return self._by_name_id(kind).name_to_id


    def dict(self, *args, **kwargs):
        excluded = kwargs.get('exclude') or set()
        excluded.update({'group_children', 'class_children'})
        kwargs['exclude'] = excluded
        return super().dict(*args, **kwargs)

    def load_objects(self, objects):
        for obj in objects:
            self.add(obj)


    @classmethod
    def from_kind_objects(cls, kind_map):
        instance = cls()
        for kind, objects in kind_map.items():
            instance.load_objects(objects)
        return instance

    @classmethod
    def from_data(cls, data_dict):
        instance = cls()
        for kind, items in data_dict.items():
            target_class = kind_map.get(kind)
            objects = [target_class(**item) for item in items]
            instance.load_objects(objects)
        instance.complete()
        return instance

    @classmethod
    def from_schema(cls, schema: Schema):
        instance = cls()
        def add_schema(a_schema:Schema):
            for c in a_schema.classes:
                instance.add(MetaClass(**c.dict()))
            for attr in a_schema.attributes:
                instance.add(MetaAttribute(**attr.dict()))
            for group in a_schema.groups:
                instance.add(MetaGroup(**group.dict()))
            for tag in a_schema.tags:
                instance.add(MetaTag(**tag.dict()))
            for role in a_schema.roles:
                instance.add(MetaRole(**role.dict()))
            for query in a_schema.queries:
                instance.add(MetaQuery(**query.dict()))
        def add_schemas(schema_list):
            for s in schema_list:
                add_schema(s)
        add_schemas(schema.uses_schemas)
        # TODO uses_schemas needs to be more refined. could make derived schem of all needed
        add_schemas(schema.requires_schemas)
        add_schema(schema)
        instance.complete()
        return instance

    def complete(self):
        # TODOa  maybe mae this a root validator?
        self.complete_classes()
        self.complete_groups()

    def gather_schema_changes(self, a_schema: Schema, changes):
        def handle_kind(kind):
            change_kind = getattr(changes, kind)
            context_kind = getattr(self, kind).by_name
            instances = getattr(a_schema, kind)
            names = [i.name for i in instances]
            # DO NOT delete things outside the schema!!
            # missing = [v.id for k,v in context_kind.items() if k not in names]
            # for an_id in missing:
            #     change_kind.delete(an_id)

            for instance in instances:
                c_instance = context_kind.get(instance.name)
                if c_instance:
                    c_instance.get_changes(instance, changes)
                else:
                    data = instance.dict()
                    data.pop('kind', None)
                    change_kind.insert(data)

        subschemas = a_schema.uses_schemas +  a_schema.requires_schemas
        for sub in subschemas:
            self.gather_schema_changes(sub, changes)

        handle_kind('attributes')
        remaining = [k for k in meta_kinds if k != 'attributes']
        for kind in remaining:
            handle_kind(kind)

        class_mods = changes.classes.modified




    def complete_classes(self):
        """
        1) ensures both attr_ids and attributes exist in classes
        2) ensures each class' attributes includs suppeclass attributes
        3) ensures self.attributes is filled in from attributes of classes
        """
        from collections import deque
        processed = set()
        by_name = self.classes.by_name
        attr_by_id = self.attributes.by_id
        def process_class(cls):
            c_attrs = deque()
            c_attributes = deque()
            working = cls
            while working:
                for a_id in working.attrs[::-1]:
                    if a_id not in c_attrs:
                        c_attrs.appendleft(a_id)
                        c_attributes.appendleft(attr_by_id[a_id])
                working = by_name[working.superclass] if working.superclass else None

            cls.attrs = list(c_attrs)
            cls.attributes = list(c_attributes)

        for cls in self.classes.by_id.values():
            process_class(cls)


    def by_name_id(self, kind):
        return getattr(self, kind)

    def by_id(self, kind):
        return self._by_name_id(kind).by_id

    def by_name(self, kind):
        return self._by_name_id(kind).by_name

    def get_meta(self, kind, an_id):
        return self.by_id(kind).get(an_id)

    def get_meta_named(self, kind, name):
        res = self.by_name(kind).get(name)
        if (kind == 'roles') and not res:
            named = self.by_name('roles')
            if name.endswith('*'):
                return named.get(name[:-1])
            for v in named.values():
                if v.reverse_name == name:
                    return v
        return res


    def add_many(self, objects: List[NameWithId]):
        for object in objects:
            self.add(object)

    def add(self, object: NameWithId):
        kind = object.kind
        self.by_id(kind)[object.id] = object
        self.by_name(kind)[object.name] = object

    def remove(self, object: NameWithId):
        kind = object.kind
        self.by_id(kind).pop(object.id, None)
        self.by_name(kind).pop(object.name, None)

    def complete_groups(self):
        by_name = self.groups.by_name
        name_id = lambda n: by_name[n].id
        group_kids = self.group_children
        def child_set(gid):
            known = group_kids.get(gid)
            if not known:
                known = group_kids[gid] = set()
            return known

        for group in by_name.values():
            cid = group.id
            for cname in group.contained_in:
                pid = by_name[cname].id
                child_set(pid).add(cid)

    def subtags(self, tid):
        by_id = self.by_id('tags')
        if tid in by_id:
            name = self.by_id('tags')[tid].name + '.'
            subnames = [n for n in self.by_name('tags').keys() if n.startswith(name)]
            return [self.by_name('tags')[n].id for n in subnames]
        return []
    def get_group_children(self, gid, recursive=True):
        children = self.group_children.get(gid)
        if children is None:
            children = set()
            for group in self.metas_of_kind('groups'):
                group_id = group.id
                if group_id == gid:
                    continue
                if gid is group.contained_in:
                    children.add(group_id)
                    if recursive:
                        children |= self.get_group_children(group_id, recursive=True)
                    self.group_children[gid] = children
        return children

    def possible_group_parents(self, gid):
        """
        Computes and returns ids of groups that are not yet parents or children of the given group
        :return: possible parent set
        """
        group: MetaGroup = self.by_id('groups').get(gid)
        children = set(self.get_group_children(gid))
        all_groups = set(self.by_id('groups').keys())
        all_groups.discard(gid)
        return all_groups - (children | set(group.contained_in))

    def subgroups(self, gid):
        res = set()
        child_map = self.group_children
        def do_group(gid):
            res.add(gid)
            kids = child_map.get(gid, [])
            for kid in kids:
                if kid not in res:
                    do_group(kid)
        do_group(gid)
        return res

    def subclasses(self, clsid):
        res = set()
        self.get_class_children()
        def do_class(cid):
            res.add(cid)
            for ccid in self.class_children.get(cid, set()):
                if ccid not in res:
                    do_class(ccid)
        do_class(clsid)
        return res

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        pass


NameWithId.update_forward_refs()

def contains_deleted_fn(deleted_objects, deleted_classes):
    return lambda obj_id: (obj_id in deleted_objects) or (oid_class(obj_id) in deleted_classes)

class SecondaryIndex(BaseModel):
    name: str
    unique: bool = False
    fields: List[str]
    
def make_secondary_indices(collection_name, *field_lists):
    res = []
    for fields in field_lists:
        f_name = '_'.join(fields)
        name = f'{collection_name}_{f_name}'  
        res.append(SecondaryIndex(name=name, fields=fields))
    return res

class Associated(BaseModel):
    kind = ''
    assoc_id: str = Field(..., description='id of association')
    object_id: str = Field(..., description='id of object associated')

    @classmethod
    def secondary_indices(cls, name):
        return make_secondary_indices(name,['assoc_id'], ['object_id'])

    def contains_deleted(self, deleted_objects, deleted_classes):
        return contains_deleted_fn(deleted_objects, deleted_classes)(self.object_id)

    def hash_string(self):
        return f'{self.assoc_id}:{self.object_id}'

    def as_tuple(self):
        return tuple(self.dict().items())

    def __eq__(self, other):
        if self.__class__ != other.__class__:
            return False
        return self.as_tuple() == other.as_tuple()

    def __hash__(self):
        return hash(self.as_tuple())

    def without_kind(self):
        data = self.dict()
        data.pop('kind', None)
        return data

    def __hash__(self):
        return hash(self.hash_string())

    def persist(self, dbi):
        if dbi:
            dbi.meta_insert(self.dict())

class Tagged(Associated):
    kind='tagged'
    @classmethod
    def make(cls, group_id, object_id):
        return cls(assoc_id=group_id, object_id=object_id)

    @property
    def tag_id(self):
        return self.assoc_id

    @classmethod
    def create_random(cls):
        cls(name=f'tag_{random.randint(10000, 99999)}')


class Grouped(Associated):
    kind = "grouped"

    @classmethod
    def make(cls, group_id, object_id):
        return cls(assoc_id=group_id, object_id=object_id)

    @property
    def contained_group(self):
        return oid_class(self.object_id) is None


    @property
    def group_id(self):
        return self.assoc_id



class Related(Associated):
    kind='related'
    subject_id: str = Field(..., description='subject of relationship')

    @classmethod
    def make(cls, subject_id, role_id, object_id):
        return cls(assoc_id=role_id, object_id=object_id, subject_id=subject_id)

    @classmethod
    def secondary_indices(cls, name):
        return make_secondary_indices(name,
                                      ['assoc_id'],
                                      ['object_id'],
                                      ['subject_id'],
                                      ['assoc_id', 'object_id'],
                                      ['assoc_id', 'subject_id'])

    @property
    def role_id(self):
        return self.assoc_id

    def contains_deleted(self, deleted_objects, deleted_classes):
        checker = contains_deleted_fn(deleted_objects, deleted_classes)
        return checker(self.object_id) or checker(self.subject_id)

    def hash_string(self):
        return f'{super().hash_string()}:{self.subject_id}'




def app_attr(name, type_, modifiable=True, **kwargs):
    perms = AppPermissions()
    perms.modifiable=modifiable
    return MetaAttribute(name=name, type=type_, permissions=perms, **kwargs)




class ClassComponent(QueryComponent):
    kind = 'class'
    cls_name: str = Field(..., description='name of class')
    include_subclasses: bool  = True
    positive: bool = True

    @classmethod
    def from_dict(cls, d):
        name, rest = first_kv(d)
        return cls(cls_name=name, **rest)


    def dict_contents(self):
        d = self.dict()
        name = d.pop('cls_name')
        return {name : d}

    def negated(self):
        return self.__class__(
            cls_name=self.cls_name,
            include_subclasses = self.include_subclasses,
            positive = not self.positive
        )


def reverse_application(application):
    reversed = dict(
        all='none',
        none='any',
        any='none'
    )
    return reversed[application]

class AssociatedComponent(QueryComponent):
    kind = ''
    names: List[str] = Field(..., description='name of association meta bojects')
    application: AssocsRequired = AssocsRequired.all

    @classmethod
    def from_dict(cls, d):
        app_type, names = first_kv(d)
        return cls(names=names, application=app_type)

    def dict_contents(self):
        return {self.application.value: self.names}

    def negated(self):
        return self.__class__(groups=self.names,
                   application=reverse_application(self.application))

class TagsComponent(AssociatedComponent):
    kind = 'tags'



class GroupsComponent(AssociatedComponent):
    kind = 'groups'
    include_subgroups: bool = True

    def negated(self):
        return self.__class__(names=self.names,
                              include_subgroups=self.include_subgroups,
                   application=reverse_application(self.application))

def assoc_component_from_dict(d):
    pass

class AttributeComponent(QueryComponent):
    kind = 'attribute'
    attr_name: str = 'createdAt'
    operate: AttributeOperation = '>'
    value: Any

    @classmethod
    def from_dict(cls, d):
        name, rest = first_kv(d)
        operate, value = first_kv(rest)
        return cls(attr_name=name, operate=operate, value=value)

    def dict_contents(self):
        return {self.attr_name: {self.operate.value: self.value}}

    def negated(self):
        reverse_op = {
            '>=': '<',
            '>': '<=',
            '<=': '>',
            '<': '>=',
            '==': '!=',
            '!=': '=='
        }
        return self.__class__(
            attr_name = self.attr_name,
            operate = reverse_op[self.operate],
            value = self.value
        )

    def value_like(self, val, criteria):
        # TODO use regex instead?
        star_sep = criteria.split('*')
        for part in star_sep:
            rest = after(part, val)
            if rest == val:
                return False
            val = rest
        return True

    def eval_like(self, obj, criteria):
        val = obj[self.attr_name]
        return self.value_like(val, criteria)

    def obj_eval(self):
        # TODO fix to include string like functions and range and clean up
        if self.operate == '>=':
            return lambda obj: obj[self.attr_name] >= self.value
        if self.operate == '>':
            return lambda obj: obj[self.attr_name] > self.value
        if self.operate == '<=':
            return lambda obj: obj[self.attr_name] <= self.value
        if self.operate == '<':
            return lambda obj: obj[self.attr_name] < self.value
        if self.operate == '==':
            return lambda obj: obj[self.attr_name] == self.value
        if self.operate == '!=':
            return lambda obj: obj[self.attr_name] != self.value
        if self.operate == 'like':
            return partial(self.eval_like, criteria= self.value)
        if self.operate == 'not_like':
            return lambda obj: not self.eval_like(obj, self.value)

    def propval(self):
        return {self.operate: {self.attr_name: self.value}}


class InComponent(BaseModel):
    object_ids: List[str]
    negated: bool = False

class RelatedTo(QueryComponent):
    kind = 'related'
    obj_id: str = Field(..., description='object objects are related to')
    role: Optional[str] = None
    negated: bool = False

    def dict_contents(self):
        d = self.dict()
        role = d.pop('role')
        return {role: d}

    @classmethod
    def from_dict(cls, d):
        role, rest = first_kv(d)
        return cls(role=role, **rest)

class CompositeQuery(QueryComponent):
    kind = ''
    components: List[QueryComponent] = []
    negated: bool = False

    def dict_contents(self):
        comps = [c.to_dict() for c in self.components]
        return dict(
            components = comps,
            negated = self.negated
        )
    def add_component(self, a_component: QueryComponent):
        self.components.append(a_component)

    def simplify(self):
        for component in self.components:
            component.simplify()

def qc_dict_to_component(d):
    kind, data = first_kv(d)
    if kind in ('and', 'or'):
        cls = AndQuery if (kind == 'and') else OrQuery
        d_comps = data.pop('components')
        components = [qc_dict_to_component(c) for c in d_comps]
        return cls(components=components, **d)
    elif kind == 'class':
        return ClassComponent.from_dict(data)
    elif kind == 'attribute':
        return AttributeComponent.from_dict(data)
    elif kind == 'tags':
        return TagsComponent.from_dict(data)
    elif kind == 'groups':
        return GroupsComponent.from_dict(data)
    elif kind == 'related':
        return RelatedTo.from_dict(data)
    elif kind:
        raise Exception(f'no handler for {kind} query component')
class AndQuery(CompositeQuery):
    kind = 'and'
    def simplify(self):
        super().simplify()
        new_components = []
        for component in self.components:
            if isinstance(component, AndQuery):
                new_components.extend(component.components)
            else:
                new_components.append(component)
        self.components = new_components


class OrQuery(CompositeQuery):
    kind = 'or'
    def simplify(self):
        super().simplify()
        new_components = []
        for component in self.components:
            if isinstance(component, OrQuery):
                new_components.extend(component.components)
            else:
                new_components.append(component)
        self.components = new_components


class WorkingContext(MetaContext):
    tagged: List[Tagged] = []
    grouped: List[Grouped] = []
    related: List[Related] = []
    instances: list = []
    persist_to: Any = None

    def assoc_oids(self):
        def objects(assoc, *fields):
            res = set()
            for field in fields:
                res |= {getattr(a, field) for a in assoc}
            return res


        return  (objects(self.tagged, 'object_id')  |
                 objects(self.grouped, 'object_id') |
                 objects(self.related, 'object_id', 'subject_id'))
    @classmethod
    def from_metadata(cls, metadata: MetaContext):
        data = {k: getattr(metadata, k) for k in metadata.dict()}
        return cls(**data)

    @classmethod
    def from_schema(cls, schema:Schema):
        return cls.from_metadata(MetaContext.from_schema(schema))

    def add(self, object: NameWithId):
        super().add(object)
        if self.persist_to:
            self.persist_to.meta_insert(object)

    def ensure_metas(self, num, meta_class:NameWithId):
        kind = meta_class.__fields__['kind'].default
        existing = list(getattr(self, kind).by_id.values())
        for _ in range(len(existing), num):
            self.add(meta_class.create_random())

    def ensure_assocs(self, num, assoc_fn, lst):
        needed = num - len(lst)
        lst += [assoc_fn() for _ in range(needed)]

    def configure(self, num_assocs=4, num_instances=10, persist_to=None):
        """
        Ensures a given number of associations and instances exist creating
        randomized ones if they do not. Optionally adds these instances
        to some form of in memory or database persistence, e.g. a db interface.


        :param num_assocs: ther minimum number of associations of each type
        :param num_instances: the minimum number of meta instances of each meta kind to ensure
        :param persist_to: object able ta
        :return:
        """
        self.persist_to = persist_to
        for _ in range(len(self.instances), num_instances):
            instance = self.random_class().random_instance()
            if persist_to:
                persist_to.add_object(instance)
            self.instances.append(instance)

        self.ensure_metas(num_instances, MetaTag)
        self.ensure_metas(num_instances, MetaGroup)
        self.ensure_metas(num_instances, MetaRole)

        self.ensure_assocs(num_assocs, self.random_tagged, self.tagged)
        self.ensure_assocs(num_assocs, self.random_grouped, self.grouped)
        self.ensure_assocs(num_assocs, self.random_related, self.related)

    def random_class_instance(self, cls:MetaClass):
        "creates and returns a raandomly generated instances of the cls"
        instance =  cls.random_instance()
        return instance

    def random_instance(self):
        return random.choice(self.instances)

    def random_new_class(self):
        return MetaClass.random_class()

    def random_class(self):
        "returns crandom cls id from existing classes"
        vals = [v for v in self.classes.by_id.values() if not v.is_abstract]
        return random.choice(vals)

    def random_tag(self):
        return random.choice(list(self.tags.by_id.values()))

    def random_group(self):
        return random.choice(list(self.groups.by_id.values()))

    def random_role(self):
        return random.choice(list(self.roles.by_id.values()))

    def random_kind(self, kind):
        return getattr(self, f'random_{kind}')

    def distinct_pair(self, kind, constraint=None):
        all_available = self.all_of_kind(kind)
        if constraint: # TODO fix this
            all_available = [a for a in all_available if constraint(a)]
        first = random.choice(all_available)
        rest = [a for a in all_available if a.id != first.id]
        return first, random.choice(rest)

    def random_tagged(self, tag_id=None, obj_id=None):
        assoc = Tagged(
            assoc_id= tag_id or self.random_tag().id,
            object_id= obj_id or self.random_instance()['id']
        )
        assoc.persist(self.persist_to)
        return assoc

    def random_grouped(self, group_id=None, obj_id=None):
        assoc =  Grouped(
            assoc_id= group_id or self.random_group().id,
            object_id= obj_id or self.random_instance()['id']
        )
        assoc.persist(self.persist_to)
        return assoc


    def random_related(self, role_id=None, object_id=None,
                       subject_id=None):
        subject = subject_id or self.random_instance()['id']
        object = object_id or self.random_instance()['id']
        role = role_id or self.random_role().id
        assoc =  Related(
            assoc_id = role,
            object_id = object,
            subject_id = subject
        )
        assoc.persist(self.persist_to)
        return assoc

    def all_of_kind(self, kind):
        if kind == 'objects':
            return self.instances
        elif kind == 'tagged':
            return self.tagged
        elif kind == 'grouped':
            return self.grouped
        elif kind == 'related':
            return self.related
        else:
            return list(getattr(self, kind).by_id.values())



class Database(BaseModel):
    id: str = Field(default_factory=lambda: str(
        make_oid('')), description='primary id ')
    name: Optional[str]
    tenancy: str
    host: Optional[str]
    port: Optional[int]
    args: dict = {}





def cls_data(name, superclass, *attributes, description='', abstract=False,
             **field_values):
    pass

class MetaChanges(BaseModel):
    timestamp: float
    changes: dict

kind_map = dict(
    classes=MetaClass,
    attributes=MetaAttribute,
    groups=MetaGroup,
    roles=MetaRole,
    tags=MetaTag,
    queries=MetaQuery,
    tagged=Tagged,
    grouped=Grouped,
    related=Related,
    users=User,
    databases=Database,
    schemas=DBFormSchema,  # TODO ferret out how these load
    tenants=Tenant,
    changes=MetaChanges,
)

def as_meta(kind, data):
    if isinstance(data, BaseModel):
        return data
    meta_cls = kind_map[kind]
    if isinstance(data, tuple):
        data = dict(data)
    return meta_cls(**data)

def create_new(kind):
    cls = kind_map[kind]
    return cls.create_random()

secondary_indices = dict(
    tagged = Tagged.secondary_indices('tagged'),
    grouped = Grouped.secondary_indices('grouped'),
    related = Related.secondary_indices('related')
)

root = MetaClass(id='r00t', name='PersistentObject', superclass='',
                 attributes=[MetaAttribute(
                     name='id', type='uuid', permissions=SystemPermissions())],
                 description='root supperclass',
                 permissions=SystemPermissions(),
                 is_abstract=True)



core_schema = Schema(
    name='uop_core',
    classes = [root,
               sys_class('DescribedComponent', 'PersistentObject',
               app_attr('createdAt', 'epoch', modifiable=False),
                         app_attr('description', 'string'),
                         abstract=True,
                         description='root of all described content'),
               ]

)



