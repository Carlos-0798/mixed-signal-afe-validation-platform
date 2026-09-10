"""Lossless, resource-free conversion of offline presets into editable forms."""

from __future__ import annotations

from dataclasses import fields
from typing import Any

from ..errors import ProductRequestError
from ..models import ProductSourceMode
from ..product_workflows import ProductWorkflowConfiguration
from .wizard import DashboardWizardDraft


def draft_from_configuration(
    configuration: ProductWorkflowConfiguration,
) -> DashboardWizardDraft:
    """Copy an offline configuration without reviewing or opening its source."""

    if not isinstance(configuration, ProductWorkflowConfiguration):
        raise ProductRequestError(
            "preset configuration must be a ProductWorkflowConfiguration"
        )
    if configuration.source_mode not in {
        ProductSourceMode.SIMULATOR,
        ProductSourceMode.CSV_REPLAY,
    }:
        raise ProductRequestError(
            "Only Simulator and CSV Replay presets can load into Setup."
        )
    draft_fields = {item.name for item in fields(DashboardWizardDraft)}
    values: dict[str, Any] = {}
    for item in fields(configuration):
        if item.name not in draft_fields:
            continue
        value = getattr(configuration, item.name)
        if item.name == "replay_path":
            value = "" if value is None else str(value)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            value = str(value)
        values[item.name] = value
    draft = DashboardWizardDraft(**values)
    if draft.to_product_configuration() != configuration:
        raise ProductRequestError("This preset cannot be represented exactly in Setup.")
    return draft
