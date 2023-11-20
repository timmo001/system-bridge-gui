"""Player Window"""
import sys
from urllib.parse import urlencode

from PySide6.QtCore import QUrl
from PySide6.QtGui import QIcon, Qt
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QFrame, QVBoxLayout
from systembridgemodels.media_play import MediaPlay
from systembridgeshared.base import Base
from systembridgeshared.const import (
    QUERY_API_PORT,
    QUERY_TOKEN,
    SECRET_TOKEN,
    SETTING_PORT_API,
)
from systembridgeshared.settings import Settings


class PlayerWindow(Base, QFrame):
    """Player Window"""

    def __init__(
        self,
        settings: Settings,
        icon: QIcon,
        application: QApplication,
        media_type: str,
        media_play: MediaPlay,
    ) -> None:
        """Initialise the window"""
        Base.__init__(self)
        QFrame.__init__(
            self,
            WindowFlags=Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint,  # type: ignore
        )

        self._settings = settings

        self.layout = QVBoxLayout(self)  # type: ignore
        self.layout.setContentsMargins(0, 0, 0, 0)  # type: ignore

        self.browser = QWebEngineView()

        self.layout.addWidget(self.browser)  # type: ignore

        self.setWindowTitle("System Bridge - Player")
        self.setWindowIcon(icon)

        if media_type == "audio":
            self.resize(540, 140)
        elif media_type == "video":
            self.resize(480, 270)

        screen_geometry = application.primaryScreen().availableSize()

        self.move(
            screen_geometry.width() - self.width() - 8,
            screen_geometry.height() - self.height() - 8,
        )

        api_port = self._settings.get(SETTING_PORT_API)
        token = self._settings.get_secret(SECRET_TOKEN)
        url = QUrl(
            f"""http://localhost:{api_port}/app/player/{media_type}.html?{urlencode({
                    QUERY_TOKEN: token,
                    QUERY_API_PORT: api_port,
                    **media_play.dict(exclude_none=True),
                })}"""
        )
        self._logger.info("Open URL: %s", url)
        self.browser.load(url)

        self.browser.urlChanged.connect(self._url_changed)  # type: ignore

        self.showNormal()

    def _url_changed(self, url: QUrl):
        """Handle URL changes"""
        self._logger.info("URL Changed: %s", url)
        if url.host() == "close.window":
            self._logger.info("Close Window Requested. Closing Window.")
            self.close()
            sys.exit(0)
