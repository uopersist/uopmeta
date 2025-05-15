from pydantic import BaseModel


class EnumBaseModel(BaseModel):
    class Config:
        use_enum_values = True


BaseModel = EnumBaseModel
