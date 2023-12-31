"""System Bridge GUI."""
from __future__ import annotations

import asyncio
from asyncio import AbstractEventLoop
import concurrent.futures
import os
import sys
from typing import Any

from PySide6.QtCore import QUrl
from PySide6.QtGui import QIcon
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QApplication, QMessageBox

from systembridgeconnector.websocket_client import WebSocketClient
from systembridgemodels.media_play import MediaPlay
from systembridgemodels.modules import DataEnum, GetData, ModulesData
from systembridgemodels.notification import Notification as NotificationData
from systembridgeshared.base import Base
from systembridgeshared.exceptions import (
    AuthenticationException,
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeshared.logger import setup_logger
from systembridgeshared.settings import Settings

from ._version import __version__
from .system_tray import SystemTray
from .widgets.timed_message_box import TimedMessageBox
from .window.main import MainWindow
from .window.notification import NotificationWindow
from .window.player import PlayerWindow


class Application(Base):
    """Application."""

    def __init__(
        self,
        settings: Settings,
        command: str = "main",
        data: dict | None = None,
    ) -> None:
        """Initialise."""
        setup_logger(settings.data.log_level, "system-bridge-gui")
        super().__init__()
        self._logger.info("System Bridge GUI %s: Startup", __version__.public())

        self._settings = settings
        self._data = ModulesData()
        self._websocket_listen_task: asyncio.Task | None = None

        self._application = QApplication([])
        self._icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.png"))
        self._application.setStyleSheet(
            """
            QWidget {
                color: #FFFFFF;
                background-color: #212121;
            }

            QMenu {
                background-color: #292929;
            }

            QMenu::item {
                background-color: transparent;
            }

            QMenu::item:selected {
                background-color: #757575;
            }
            """
        )

        self._loop: AbstractEventLoop = asyncio.get_event_loop()

        if command == "main":
            self._logger.info("Main: Setup")

            # Setup the main window
            self._main_window = MainWindow(
                self._settings,
                self._icon,
            )

            # Setup the system tray
            self._system_tray = SystemTray(
                self._settings,
                self._icon,
                self._application,
                self._callback_exit_application,
                self._callback_show_window,
            )
            self._system_tray.show()

            # Setup the WebSocket
            self._websocket_client = WebSocketClient(
                "localhost",
                self._settings.data.api.port,
                self._settings.data.api.token,
            )
            self._loop.create_task(self._setup_websocket())
        elif command == "media-player-audio":
            self._logger.info("Media Player: Audio")
            if data is None:
                self._logger.error("No data provided!")
                self._startup_error("No data provided!")
                sys.exit(1)
            media_play = MediaPlay(**data)
            self._main_window = PlayerWindow(
                self._settings,
                self._icon,
                self._application,
                "audio",
                media_play,
            )
        elif command == "media-player-video":
            self._logger.info("Media Player: Video")
            if data is None:
                self._logger.error("No data provided!")
                self._startup_error("No data provided!")
                sys.exit(1)
            media_play = MediaPlay(**data)
            self._main_window = PlayerWindow(
                self._settings,
                self._icon,
                self._application,
                "video",
                media_play,
            )
        elif command == "notification":
            self._logger.info("Notification")
            if data is None:
                self._logger.error("No data provided!")
                self._startup_error("No data provided!")
                sys.exit(1)

            notification_data = NotificationData(**data)

            self._main_window = NotificationWindow(
                self._settings,
                self._icon,
                self._application,
                notification_data,
            )

            if notification_data.audio is not None:
                self._logger.info("Playing audio: %s", notification_data.audio)
                player = QMediaPlayer()
                player.setSource(QUrl(notification_data.audio.source))
                audio_output = QAudioOutput()
                audio_output.setVolume(
                    (
                        notification_data.audio.volume
                        if notification_data.audio.volume is not None
                        else 100
                    )
                    / 100
                )
                player.setAudioOutput(audio_output)
                player.play()

        sys.exit(self._application.exec())

    def _callback_exit_application(self) -> None:
        """Exit the application."""
        self._exit_application(0)

    def _callback_show_window(
        self,
        path: str,
        maximized: bool,
        width: int | None = 1280,
        height: int | None = 720,
    ) -> None:
        """Show the main window."""
        self._logger.info("Showing window: %s", path)

        if width is None:
            width = 1280
        if height is None:
            height = 720

        self._main_window.hide()
        self._main_window.setup(path)  # type: ignore
        self._main_window.resize(width, height)
        screen_geometry = self._application.primaryScreen().availableSize()
        self._main_window.move(
            int((screen_geometry.width() - self._main_window.width()) / 2),
            int((screen_geometry.height() - self._main_window.height()) / 2),
        )
        if maximized:
            self._main_window.showMaximized()
        else:
            self._main_window.showNormal()

    def _startup_error(
        self,
        message: str,
    ) -> None:
        """Handle a startup error."""
        error_message = TimedMessageBox(
            5,
            f"{message} Exiting in",
        )
        error_message.setIcon(QMessageBox.Critical)  # type: ignore
        error_message.setWindowTitle("Error")
        error_message.exec()
        # Exit cleanly
        self._exit_application(1)

    def _exit_application(
        self,
        code: int = 0,
    ) -> None:
        """Exit the backend."""
        self._logger.info("Exit..")

        if code == 0:
            if self._loop is not None:
                try:
                    if self._websocket_client is not None:
                        if not self._websocket_client.connected:
                            self._logger.info("Connect to backend..")
                            self._loop.run_until_complete(
                                self._setup_websocket(listen=False)
                            )
                        self._logger.info("Request backend exit..")
                        self._loop.run_until_complete(
                            self._websocket_client.exit_backend()
                        )
                        self._logger.info("Disconnect WebSocket..")
                        self._loop.run_until_complete(self._websocket_client.close())
                except (
                    AuthenticationException,
                    ConnectionErrorException,
                    ConnectionClosedException,
                    ConnectionResetError,
                ) as exception:
                    self._logger.warning(
                        "Could not connect to WebSocket: %s", exception
                    )

                try:
                    if self._websocket_listen_task:
                        self._logger.info("Cancel WebSocket listener..")
                        self._websocket_listen_task.cancel()
                        self._websocket_listen_task = None

                        self._logger.info("Stop event loop..")
                        self._loop.stop()
                        self._loop.close()
                except RuntimeError as exception:
                    self._logger.warning("Could not stop event loop: %s", exception)

        self._logger.info("Exit GUI..")
        self._system_tray.hide()
        self._application.exit(code)
        sys.exit(code)

    async def _handle_module(
        self,
        module_name: str,
        module: Any,
    ) -> None:
        """Handle data from the WebSocket client."""
        self._logger.debug("Set new data for: %s", module_name)
        setattr(self._data, module_name, module)
        self._system_tray.update_tray_data(self._data)

    async def _listen_for_data(self) -> None:
        """Listen for events from the WebSocket."""
        try:
            await self._websocket_client.listen(callback=self._handle_module)
        except asyncio.CancelledError:
            self._logger.info("WebSocket listener cancelled")
        except (
            ConnectionErrorException,
            ConnectionClosedException,
            ConnectionResetError,
        ) as exception:
            self._logger.warning("Connection closed to WebSocket: %s", exception)

        if self._websocket_listen_task:
            self._websocket_listen_task.cancel()
            self._websocket_listen_task = None

    def _setup_listener(self) -> None:
        """Set up the listener for the WebSocket."""
        self._logger.info("Setup WebSocket listener..")
        if self._websocket_listen_task:
            self._websocket_listen_task.cancel()
            self._websocket_listen_task = None

        if self._loop is None:
            self._logger.error("No event loop!")
            return

        # Listen for data
        self._websocket_listen_task = self._loop.create_task(
            self._listen_for_data(),
            name="System Bridge WebSocket Listener",
        )

    async def _setup_websocket(
        self,
        listen: bool = True,
    ) -> None:
        """Use WebSocket for updates."""
        if self._loop is None:
            self._logger.error("No event loop!")
            return

        try:
            async with asyncio.timeout(10):
                # Connect to the WebSocket
                await self._websocket_client.connect()

                # If we don't need to listen for data, return here
                if not listen:
                    return

                # Run the listener in a separate thread
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    self._loop.run_in_executor(executor, self._setup_listener)

                # Get initial data
                await self._websocket_client.get_data(
                    GetData(
                        modules=[DataEnum.SYSTEM.value],
                    )
                )

                # Wait for initial data
                while self._data.system is None:
                    self._logger.info("Waiting for system data..")
                    await asyncio.sleep(1)
        except (AuthenticationException, ConnectionErrorException) as exception:
            self._logger.warning("Could not connect to WebSocket: %s", exception)

            if self._websocket_listen_task:
                self._websocket_listen_task.cancel()
                self._websocket_listen_task = None
        except (ConnectionClosedException, ConnectionResetError) as exception:
            self._logger.warning("Connection closed to WebSocket: %s", exception)

            if self._websocket_listen_task:
                self._websocket_listen_task.cancel()
                self._websocket_listen_task = None
        except asyncio.TimeoutError as exception:
            self._logger.error("Connection timeout to WebSocket: %s", exception)

            if self._websocket_listen_task:
                self._websocket_listen_task.cancel()
                self._websocket_listen_task = None
