"""Push registration shapes."""

from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema


class PushDeviceRegister(BaseSchema):
    """Register or refresh one device. The token is the device identity."""

    token: str = Field(min_length=16, max_length=512)
    platform: Literal["android", "ios"] = "android"


class PushDeviceUnregister(BaseSchema):
    """Forget one device, named by its token."""

    token: str = Field(min_length=16, max_length=512)
