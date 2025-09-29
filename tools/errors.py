
class ToolError(Exception):
    pass

class ProviderError(ToolError):
    def __init__(self, message, *, provider=None, details=None):
        super().__init__(message)
        self.provider = provider
        self.details = details

class RateLimitError(ToolError):
    pass

class TimeoutError(ToolError):
    pass

class FetchError(ToolError):
    def __init__(self, url, status=None, message="fetch failed"):
        super().__init__(message)
        self.url = url
        self.status = status
