"""Headless Dashboard contracts; importing this package never imports Tk."""

from .controller import DashboardController, DashboardWorkerPort
from .presenter import DashboardPresenter, initial_dashboard_state
from .state import (
    DASHBOARD_HARDWARE_CLAIM,
    DASHBOARD_STATE_SCHEMA_VERSION,
    MAX_DASHBOARD_ARTIFACTS,
    MAX_DASHBOARD_EVENT_HISTORY,
    MAX_DASHBOARD_PLOT_POINTS,
    MAX_DASHBOARD_TEXT_CHARS,
    DashboardAction,
    DashboardActionType,
    DashboardArtifactsPanel,
    DashboardArtifactView,
    DashboardConfigurationPanel,
    DashboardPlotPanel,
    DashboardPlotPoint,
    DashboardProgressPanel,
    DashboardResultPanel,
    DashboardSourcePanel,
    DashboardState,
)

__all__ = [
    "DASHBOARD_HARDWARE_CLAIM",
    "DASHBOARD_STATE_SCHEMA_VERSION",
    "MAX_DASHBOARD_ARTIFACTS",
    "MAX_DASHBOARD_EVENT_HISTORY",
    "MAX_DASHBOARD_PLOT_POINTS",
    "MAX_DASHBOARD_TEXT_CHARS",
    "DashboardAction",
    "DashboardActionType",
    "DashboardArtifactView",
    "DashboardArtifactsPanel",
    "DashboardConfigurationPanel",
    "DashboardController",
    "DashboardPlotPanel",
    "DashboardPlotPoint",
    "DashboardPresenter",
    "DashboardProgressPanel",
    "DashboardResultPanel",
    "DashboardSourcePanel",
    "DashboardState",
    "DashboardWorkerPort",
    "initial_dashboard_state",
]
