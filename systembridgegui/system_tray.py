"""System Tray."""
from __future__ import annotations

from collections.abc import Callable
import os
from webbrowser import open_new_tab

from pyperclip import copy
from PySide6.QtGui import QAction, QCursor, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from systembridgemodels.modules import ModulesData
from systembridgeshared.base import Base
from systembridgeshared.common import get_user_data_directory
from systembridgeshared.settings import Settings

PATH_BRIDGES_OPEN_ON = "/app/bridges/openon.html"
PATH_BRIDGES_SETUP = "/app/bridges/setup.html"
PATH_DATA = "/app/data.html"
PATH_SETTINGS = "/app/settings.html"

URL_DISCUSSIONS = "https://github.com/timmo001/system-bridge/discussions"
URL_DOCS = "https://system-bridge.timmo.dev"
URL_ISSUES = "https://github.com/timmo001/system-bridge/issues/new/choose"
URL_LATEST_RELEASE = "https://github.com/timmo001/system-bridge/releases/latest"


class SystemTray(Base, QSystemTrayIcon):
    """System Tray."""

    # pylint: disable=unsubscriptable-object
    def __init__(
        self,
        settings: Settings,
        icon: QIcon,
        parent: QApplication,
        callback_exit_application: Callable,
        callback_show_window: Callable[[str, bool, int | None, int | None], None],
    ) -> None:
        """Initialise the system tray."""
        Base.__init__(self)
        QSystemTrayIcon.__init__(self, icon, parent)

        self._settings = settings

        self._logger.info("Setup system tray")

        self.callback_show_window = callback_show_window

        self.activated.connect(self._on_activated)  # type: ignore

        menu = QMenu()

        action_settings: QAction = menu.addAction("Open Settings")
        action_settings.triggered.connect(self._show_settings)  # type: ignore

        action_data: QAction = menu.addAction("View Data")
        action_data.triggered.connect(self._show_data)  # type: ignore

        menu.addSeparator()

        action_latest_release: QAction = menu.addAction("Check for Updates")
        action_latest_release.triggered.connect(self._open_latest_releases)  # type: ignore

        menu_help = menu.addMenu("Help")

        action_docs: QAction = menu_help.addAction("Documentation / Website")
        action_docs.triggered.connect(self._open_docs)  # type: ignore

        action_feature: QAction = menu_help.addAction("Suggest a Feature")
        action_feature.triggered.connect(self._open_feature_request)  # type: ignore

        action_issue: QAction = menu_help.addAction("Report an issue")
        action_issue.triggered.connect(self._open_issues)  # type: ignore

        action_discussions: QAction = menu_help.addAction("Discussions")
        action_discussions.triggered.connect(self._open_discussions)  # type: ignore

        menu_help.addSeparator()

        action_token: QAction = menu_help.addAction("Copy Token to clipboard")
        action_token.triggered.connect(self._copy_token)  # type: ignore

        menu_help.addSeparator()

        action_log: QAction = menu_help.addAction("Open Backend Logs")
        action_log.triggered.connect(self._open_backend_logs)  # type: ignore

        action_log_gui: QAction = menu_help.addAction("Open GUI Logs")
        action_log_gui.triggered.connect(self._open_gui_logs)  # type: ignore

        menu.addSeparator()

        action_exit: QAction = menu.addAction("Exit")
        action_exit.triggered.connect(callback_exit_application)  # type: ignore

        self.setContextMenu(menu)

    def _on_activated(
        self,
        reason: int,
    ) -> None:
        """Handle the activated signal."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.contextMenu().popup(QCursor.pos())

    def _copy_token(self) -> None:
        """Copy Token to clipboard."""
        self._logger.info("Copy Token to clipboard")
        copy(self._settings.data.api.token)

    def _open_latest_releases(self) -> None:
        """Open latest release."""
        self._logger.info("Open: %s", URL_LATEST_RELEASE)
        open_new_tab(URL_LATEST_RELEASE)

    def _open_docs(self) -> None:
        """Open documentation."""
        self._logger.info("Open: %s", URL_DOCS)
        open_new_tab(URL_DOCS)

    def _open_feature_request(self) -> None:
        """Open feature request."""
        self._logger.info("Open: %s", URL_ISSUES)
        open_new_tab(URL_ISSUES)

    def _open_issues(self) -> None:
        """Open issues."""
        self._logger.info("Open: %s", URL_ISSUES)
        open_new_tab(URL_ISSUES)

    def _open_discussions(self) -> None:
        """Open discussions."""
        self._logger.info("Open: %s", URL_DISCUSSIONS)
        open_new_tab(URL_DISCUSSIONS)

    def _open_backend_logs(self) -> None:
        """Open backend logs."""
        log_path = os.path.join(get_user_data_directory(), "system-bridge-backend.log")
        self._logger.info("Open: %s", log_path)
        open_new_tab(log_path)

    def _open_gui_logs(self) -> None:
        """Open GUI logs."""
        log_path = os.path.join(get_user_data_directory(), "system-bridge-gui.log")
        self._logger.info("Open: %s", log_path)
        open_new_tab(log_path)

    def _show_data(self) -> None:
        """Show api data."""
        self.callback_show_window(PATH_DATA, False)  # type: ignore

    def _show_settings(self) -> None:
        """Show settings."""
        self.callback_show_window(PATH_SETTINGS, False)  # type: ignore

    def update_tray_data(
        self,
        data: ModulesData,
    ) -> None:
        """Update the tray."""
        self._logger.info("Update tray data")

        latest_version_text = "Check for Updates"

        version_current = getattr(data.system, "version") if data.system else None
        version_latest = getattr(data.system, "version_latest") if data.system else None
        version_newer_available = (
            getattr(data.system, "version_newer_available") if data.system else None
        )

        if version_newer_available is not None:
            latest_version_text = f"New version avaliable ({version_latest})"
        elif version_current is not None:
            latest_version_text = f"Up to date ({version_current})"

        self.contextMenu().actions()[3].setText(latest_version_text)
