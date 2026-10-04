import contextvars

current_auth_token = contextvars.ContextVar('current_auth_token', default=None)
