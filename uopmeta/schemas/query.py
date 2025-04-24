from pydantic import BaseModel
from typing import Dict, List, Optional
from pydantic import Field
from uopmeta.schemas.enums import AssocsRequired
from uopmeta.oid import oid_class
from functools import reduce


class QueryComponent(BaseModel):
    def safisfies(self, dbi, obj_ids=None):
        pass

def filter_obj_ids(obj_ids: set, test):
    return {s for s in obj_ids if test(s)}

class ClassComponent(QueryComponent):
    cls_name: str = Field(..., description='name of class')
    include_instances: bool = True
    include_subclasses: bool = True

    def satisfies(self, dbi,  obj_ids):
        context = dbi.meta_context
        cls = context.classes.by_name[self.cls_name]
        cls_ids = {cls.id}
        if self.include_subclasses:
            subclasses = dbi.meta_context.subclasses(cls.id)
            ids = {c.id for c in subclasses}
            cls_ids |= ids

        def test_in(obj_id):
            return oid_class(obj_id) in cls_ids

        def test_not_in(obj_id):
            return oid_class(obj_id) not in cls_ids

        if obj_ids:
            test = test_in if self.include_instances else test_not_in
            return filter_obj_ids(obj_ids, test)
        elif self.include_instances:
            res = set(dbi.class_instance_ids(self.cls_name))
            if self.include_subclasses:
                sub_names = [c.name for c in context.subcleasses_of(self.cls_name)]
                return reduce(lambda a,b: a | b,
                              [dbi.class_instance_ids(name) for name in sub_names],
                              res)


class TagsComponent(QueryComponent):
    tag_names: List[str] = Field(..., description='name of tags')
    application: AssocsRequired = 'all'

    def satisfies(self, dbi,  obj_ids):
        '''
        Question: how to compute whether intersetion of tagsets
        if cheaper to compute or intersetion of object tags
        depending on number of obj_ids? For now if obj_ids use
        the latter
        '''
        context = dbi.meta_context()
        by_names = context.tags.by_name
        tags = [context.tags[n] for n in by_names if n in by_names]
        if len(tags) < len(self.tag_names) and self.application == 'all':
            return set()
        tag_ids = [t.id for t in tags]
        if obj_ids is None: # from db case
            if  self.application == 'all':
                res = dbi.get_tagset(tag_ids[0])
                for t_id in tag_ids[1:]:
                    if not res:
                        return set()
                    res &= dbi.get_tagset(t_id)
                return res
            elif self.application == 'any':
                return reduce(lambda a,b: a | b,
                             (dbi.get_tagset(t_id) for t_id in tag_ids),
                             set())
            else:
                raise Exception('Computing all object that have none of the tags is too expensive')
        else:
            pass





class GroupsComponent(QueryComponent):
    grqups: List[str] = Field(...)
    application: AssocsRequired = 'all'
    include_subgroups: bool = True

class RelatedTo(BaseModel):
    obj_id: str = Field(..., description='object objects are related to')
    role: Optional[str] = None
    related: bool = True

class CompositeQuery(QueryComponent):
    components: List[QueryComponent] = []

class AndQuery(CompositeQuery):
    pass

class OrQuery(CompositeQuery):
    pass


