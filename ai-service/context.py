from contextvars import ContextVar

# Context variable to store the JWT token of the current request
request_token: ContextVar[str] = ContextVar('request_token', default="")

# Context variable to store the current user's DC ID (None for Super Admin)
request_dc_id: ContextVar[int | None] = ContextVar('request_dc_id', default=None)
