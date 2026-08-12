"""Workflow platform errors."""

from __future__ import annotations


class WorkflowError(Exception):
    """Base error for the workflow platform spine."""


class UnknownWorkflowError(WorkflowError):
    """Raised when a workflow_type is not registered."""


class WorkflowRegistrationError(WorkflowError):
    """Raised when workflow registration is invalid."""


class WorkflowResumeError(WorkflowError):
    """Raised when a paused workflow cannot be resumed."""
