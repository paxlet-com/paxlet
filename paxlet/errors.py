class PaxletError(Exception):
    """Base error for the reference runtime."""


class ManifestError(PaxletError):
    """Manifest is missing or invalid."""


class ResolutionError(PaxletError):
    """An identity cannot be resolved to a usable location."""


class RuntimeError(PaxletError):
    """An action could not be executed."""
