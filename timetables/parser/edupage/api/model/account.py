from typing import Optional, Union

from pydantic import BaseModel, Field

from .edupage import Edupage


class Account(BaseModel):
    edupage: Union[Edupage, str]
    username: str = Field(alias="login")
    password_hash: str = Field(alias="password")
    portal_id: Optional[int] = None
    portal_email: Optional[str] = None

    class Config:
        allow_population_by_field_name = True

    def edupage_name(self) -> str:
        if isinstance(self.edupage, Edupage):
            return self.edupage.name
        return self.edupage

    def has_portal(self) -> bool:
        return not not (self.portal_id or self.portal_email)

    def dict(self, by_alias: bool = True, **kwargs) -> dict:
        return super().dict(by_alias=by_alias, **kwargs)
