"""Errors raised by simulated enterprise services. Independent of the tool layer."""


class SimulatedServiceError(Exception):
    """Transient failure in a simulated backend. Tools map this to SERVICE_ERROR."""
