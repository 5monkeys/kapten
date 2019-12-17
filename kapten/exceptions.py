class KaptenError(Exception):
    pass


class KaptenClientError(KaptenError):
    pass


class KaptenAPIError(KaptenError):
    pass


class KaptenConnectionError(KaptenAPIError):
    pass
