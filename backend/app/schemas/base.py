from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    sort_by: str | None = None
    sort_order: str = Field(default="asc", pattern="^(asc|desc)$")


class PaginationMeta(BaseModel):
    total: int
    page: int
    per_page: int
    total_pages: int


class DataResponse[T](BaseModel):
    data: T


class ListResponse[T](BaseModel):
    data: list[T]
    meta: PaginationMeta


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str


class ErrorResponse(BaseModel):
    error: dict[str, str]
    details: list[ErrorDetail] | None = None


class HealthResponse(BaseModel):
    status: str
    version: str | None = None
    checks: dict[str, str] | None = None
