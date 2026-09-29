"""Non-blocking GitHub release checks and verified Windows installer download."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

from PyQt5.QtCore import QCoreApplication, QObject, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PyQt5.QtWidgets import QMessageBox, QCheckBox, QProgressDialog

from .i18n import translate
from .version import __version__

REPOSITORY = 'https://github.com/auto-sun/labelImg2-custom'
LATEST_API = 'https://api.github.com/repos/auto-sun/labelImg2-custom/releases/latest'


def update_request(url):
    request = QNetworkRequest(QUrl(url))
    request.setRawHeader(b'User-Agent', b'LabelImg2Custom-Updater')
    request.setAttribute(QNetworkRequest.RedirectPolicyAttribute,
                         QNetworkRequest.NoLessSafeRedirectPolicy)
    return request


def check_connection():
    """Packaging diagnostic: verify HTTPS and JSON without user settings/UI."""
    app = QCoreApplication([])
    manager = QNetworkAccessManager()
    reply = manager.get(update_request(LATEST_API))
    def finished():
        try:
            data = json.loads(bytes(reply.readAll()).decode('utf-8'))
            ok = not reply.error() and version_tuple(data.get('tag_name', ''))
        except (ValueError, AttributeError):
            ok = False
        app.exit(0 if ok else 1)
    reply.finished.connect(finished)
    QTimer.singleShot(25000, lambda: app.exit(2))
    return app.exec_()


def version_tuple(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', str(value))
    return tuple(map(int, match.groups())) if match else None


def newer_release(data, current=__version__):
    version = version_tuple(data.get('tag_name', ''))
    if data.get('draft') or data.get('prerelease') or not version or version <= version_tuple(current):
        return None
    tag = data['tag_name']
    filename = 'LabelImg2Custom-%s-Setup.exe' % tag.lstrip('v')
    expected_url = REPOSITORY + '/releases/download/' + tag + '/' + filename
    for asset in data.get('assets', []):
        digest = str(asset.get('digest', ''))
        if (asset.get('name') == filename and asset.get('browser_download_url') == expected_url
                and re.fullmatch(r'sha256:[0-9a-fA-F]{64}', digest)
                and isinstance(asset.get('size'), int) and asset['size'] > 0):
            return dict(version=tag, url=expected_url, name=filename,
                        size=asset['size'], sha256=digest[7:].lower())
    return dict(version=tag)


class UpdateController(QObject):
    def __init__(self, window, settings):
        super().__init__(window)
        self.window, self.settings = window, settings
        self.network = QNetworkAccessManager(self)
        self.reply = None
        self.output = None
        self.progress = None
        self.cancelled = False
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self.abort)
        self.startup = QTimer(self)
        self.startup.setSingleShot(True)
        self.startup.timeout.connect(self.checkAtStartup)
        self.startup.start(3000)

    def tr(self, text):
        return translate(text, self.settings.get('language', 'zh'))

    def setAutomatic(self, enabled):
        self.settings['autoCheckUpdates'] = bool(enabled)
        self.settings.save()
        if not enabled:
            self.startup.stop()

    def checkAtStartup(self):
        if self.settings.get('autoCheckUpdates', True) and self.window.isVisible():
            self.check(automatic=True)

    def request(self, url):
        return self.network.get(update_request(url))

    def check(self, _checked=False, automatic=False):
        if self.reply is not None:
            return
        self.automatic = automatic
        self.reply = self.request(LATEST_API)
        self.timeout.start(20000)
        self.reply.finished.connect(self.checked)

    def checked(self):
        reply, self.reply = self.reply, None
        self.timeout.stop()
        if reply is None:
            return
        try:
            if reply.error():
                raise ValueError(reply.errorString())
            data = json.loads(bytes(reply.readAll()).decode('utf-8'))
            release = newer_release(data)
        except (ValueError, TypeError, KeyError) as error:
            if not self.automatic:
                QMessageBox.warning(self.window, self.tr('Check for Updates'),
                                    self.tr('Unable to check for updates. Try again later.') + '\n' + str(error))
            return
        finally:
            reply.deleteLater()
        if release is None:
            if not self.automatic:
                QMessageBox.information(self.window, self.tr('Check for Updates'),
                                        self.tr('You are using the latest version.') + ' (' + __version__ + ')')
            return
        self.release = release
        box = QMessageBox(self.window)
        box.setWindowTitle(self.tr('Check for Updates'))
        box.setText(self.tr('A new version is available:') + ' ' + release['version'])
        box.setInformativeText(self.tr('Download and install the update now? Your work will be saved before closing.'))
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        checkbox = QCheckBox(self.tr('Automatically check for updates'), box)
        checkbox.setChecked(self.settings.get('autoCheckUpdates', True))
        checkbox.toggled.connect(self.window.autoCheckUpdatesAction.setChecked)
        box.setCheckBox(checkbox)
        if box.exec_() != QMessageBox.Yes:
            return
        if not getattr(sys, 'frozen', False) or sys.platform != 'win32' or 'url' not in release:
            QDesktopServices.openUrl(QUrl(REPOSITORY + '/releases/tag/' + release['version']))
            return
        self.download()

    def download(self):
        try:
            folder = os.path.join(tempfile.gettempdir(), 'LabelImg2Custom-updates')
            os.makedirs(folder, exist_ok=True)
            self.path = os.path.join(folder, self.release['name'])
            self.output = open(self.path + '.part', 'wb')
        except OSError as error:
            QMessageBox.warning(self.window, self.tr('Check for Updates'), str(error))
            return
        self.digest = hashlib.sha256()
        self.received = 0
        self.cancelled = False
        self.progress = QProgressDialog(self.tr('Downloading update...'), self.tr('Cancel'), 0, 100, self.window)
        self.progress.setWindowTitle(self.tr('Check for Updates'))
        self.progress.setMinimumWidth(450)
        self.progress.setAutoClose(False)
        self.progress.setAutoReset(False)
        self.progress.canceled.connect(self.cancel)
        self.reply = self.request(self.release['url'])
        self.reply.readyRead.connect(self.readDownload)
        self.reply.finished.connect(self.downloaded)
        self.timeout.start(120000)
        self.progress.show()

    def readDownload(self):
        if self.reply is None or self.output is None:
            return
        chunk = bytes(self.reply.readAll())
        try:
            self.output.write(chunk)
        except OSError:
            self.abort()
            return
        self.digest.update(chunk)
        self.received += len(chunk)
        self.progress.setValue(min(99, int(self.received * 100 / self.release['size'])))
        self.timeout.start(120000)
        if self.received > self.release['size']:
            self.abort()

    def downloaded(self):
        self.readDownload()
        reply, self.reply = self.reply, None
        self.timeout.stop()
        self.output.close()
        self.output = None
        ok = (not self.cancelled and not reply.error() and self.received == self.release['size']
              and self.digest.hexdigest() == self.release['sha256'])
        self.progress.blockSignals(True)
        self.progress.close()
        reply.deleteLater()
        if not ok:
            if os.path.exists(self.path + '.part'):
                os.remove(self.path + '.part')
            if not self.cancelled:
                QMessageBox.warning(self.window, self.tr('Check for Updates'),
                                    self.tr('Download or verification failed. Please try again.'))
            return
        try:
            os.replace(self.path + '.part', self.path)
            # closeEvent owns unsaved-work handling and rejects closing while
            # model inference is active. Never force-kill an annotating app.
            if self.window.close():
                subprocess.Popen([self.path, '/SILENT', '/NORESTART',
                                  '/DIR=' + os.path.dirname(sys.executable)])
        except OSError as error:
            self.window.show()
            QMessageBox.warning(self.window, self.tr('Check for Updates'), str(error))

    def cancel(self):
        self.cancelled = True
        self.abort()

    def abort(self):
        if self.reply is not None:
            self.reply.abort()

    def stop(self):
        self.startup.stop()
        self.timeout.stop()
        self.cancelled = True
        self.automatic = True
        self.abort()
