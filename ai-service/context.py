from contextvars import ContextVar

# Context variable to store the JWT token of the current request
request_token: ContextVar[str] = ContextVar('request_token', default="")
