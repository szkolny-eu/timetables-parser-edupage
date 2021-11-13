from pydantic import BaseModel


class Edupage(BaseModel):
    name: str
    country: str
    school_name: str

    def __str__(self) -> str:
        return self.name
