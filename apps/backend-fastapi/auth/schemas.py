from pydantic import BaseModel


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None = None
    picture: str | None = None

    class Config:
        from_attributes = True
