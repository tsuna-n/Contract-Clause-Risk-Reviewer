"""User-facing shape of :class:`~app.models.user.User`."""

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    """The signed-in user as returned by ``GET /auth/me``."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str | None = None
    picture: str | None = None
