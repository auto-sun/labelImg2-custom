import hashlib
import json
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtCore import QByteArray, Qt
from PyQt5.QtWidgets import QAction, QApplication, QMessageBox, QWidget
from libs.annotation_paths import annotation_base
from libs.updater import newer_release, release_highlights, UpdateController, REPOSITORY
import test_delete_image as deletion
MemorySettings = deletion.MemorySettings


class ProjectPathTests(unittest.TestCase):
    def test_legacy_flat_file_is_reused_only_for_unique_name(self):
        with tempfile.TemporaryDirectory() as root:
            labels = os.path.join(root, 'labels')
            images = os.path.join(root, 'img')
            os.makedirs(labels)
            image = os.path.join(images, 'c', 'apple.jpg')
            flat = os.path.join(labels, 'apple')
            with open(flat + '.txt', 'w') as stream:
                stream.write('')
            self.assertEqual(flat, annotation_base(image, images, labels, {}, {'apple'}))
            self.assertEqual(os.path.join(labels, 'c', 'apple'),
                             annotation_base(image, images, labels, {}, set()))

    def test_remembered_child_mapping_survives_parent_open_and_new_labels(self):
        with tempfile.TemporaryDirectory() as root:
            labels = os.path.join(root, 'labels')
            child = os.path.join(root, 'img', 'c')
            image = os.path.join(child, 'nested', 'apple.jpg')
            self.assertEqual(os.path.join(labels, 'nested', 'apple'),
                             annotation_base(image, os.path.dirname(child), labels, {child: labels}))

    def test_existing_hierarchy_precedes_legacy_flat(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, 'labels', 'c'))
            for name in ('apple.xml', os.path.join('c', 'apple.xml')):
                with open(os.path.join(root, 'labels', name), 'w') as stream:
                    stream.write('')
            self.assertEqual(os.path.join(root, 'labels', 'c', 'apple'),
                             annotation_base(os.path.join(root, 'img', 'c', 'apple.jpg'),
                                             os.path.join(root, 'img'), os.path.join(root, 'labels'), {}, {'apple'}))


class ProjectIntegrationTests(unittest.TestCase):
    setUpClass = classmethod(deletion.DeleteImageTests.setUpClass.__func__)
    setUp = deletion.DeleteImageTests.setUp
    tearDown = deletion.DeleteImageTests.tearDown
    createImage = deletion.DeleteImageTests.createImage
    def test_reopen_parent_reads_same_flat_labels_and_counts(self):
        labels = self.annotationDir
        with open(os.path.join(labels, 'one.xml'), 'w', encoding='utf-8') as stream:
            stream.write('<annotation><filename>one.jpg</filename><size><width>100</width><height>80</height><depth>3</depth></size>'
                         '<object><name>person</name><bndbox><xmin>10</xmin><ymin>10</ymin>'
                         '<xmax>50</xmax><ymax>50</ymax></bndbox></object></annotation>')
        self.window.openAnnotationDirDialog(dirpath=labels)
        self.window.importDirImages(self.temporary.name)
        self.assertEqual(os.path.join(labels, 'one'), self.window.annotationBasePathForImage(self.firstImage))
        self.assertEqual(os.path.join(labels, 'one'), self.window.annotationScanner.annotationBasePath(self.firstImage))
        self.assertIn(os.path.abspath(self.imageDir), self.window.settings.get('annotationDirectoryBindings'))
        self.assertEqual(1, self.window.fileModel.parseOne(self.firstImage)[1])
        self.assertEqual(['person'], [shape.label for shape in self.window.canvas.shapes])


class UpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def release(self):
        return {'tag_name': 'v2.7.0', 'assets': [{'name': 'LabelImg2Custom-2.7.0-Setup.exe',
                'browser_download_url': REPOSITORY + '/releases/download/v2.7.0/LabelImg2Custom-2.7.0-Setup.exe',
                'size': 10, 'digest': 'sha256:' + 'a' * 64}]}

    def test_numeric_version_comparison_and_stable_only(self):
        data = self.release()
        self.assertIsNotNone(newer_release(data, '2.6.9'))
        self.assertIsNone(newer_release(data, '2.10.0'))
        self.assertIsNone(newer_release(data, '2.7.0'))
        data['prerelease'] = True
        self.assertIsNone(newer_release(data, '2.6.0'))

    def test_untrusted_asset_and_missing_digest_never_auto_install(self):
        data = self.release()
        data['assets'][0]['browser_download_url'] = 'https://example.com/evil.exe'
        self.assertNotIn('url', newer_release(data, '2.6.0'))
        data = self.release()
        data['assets'][0].pop('digest')
        self.assertNotIn('url', newer_release(data, '2.6.0'))

    def test_highlights_support_bullets_and_prose_without_download_noise(self):
        notes = '# v3\n**[下载安装包](https://example.org)**，SHA-256：123\n- **修复：** 列表刷新\n- 支持 [MCP](https://example.org)\n## 下载与安装\n- 安装步骤'
        self.assertEqual(release_highlights(notes), '• 修复： 列表刷新\n• 支持 MCP')
        self.assertEqual(release_highlights('# v3\n支持实时标注。\n\n增加欢迎页。\n[下载](url)'),
                         '• 支持实时标注。\n• 增加欢迎页。')
        self.assertEqual(release_highlights('## 下载\n- 安装包'), '')
        long_notes = '\n'.join('- ' + str(i) + '长' * 200 for i in range(8))
        preview = release_highlights(long_notes)
        self.assertEqual(preview.count('•'), 5)
        self.assertLess(len(preview), 630)

    def test_popup_shows_highlights_before_accepting_in_both_modes(self):
        for automatic in (False, True):
            for notes in ('- 修复列表刷新\n- 新增实时预览', None):
                with self.subTest(automatic=automatic, notes=notes):
                    window = QWidget()
                    window.autoCheckUpdatesAction = QAction(window)
                    controller = UpdateController(window, MemorySettings())
                    controller.startup.stop()
                    controller.automatic = automatic
                    reply = controller.reply = mock.Mock()
                    reply.error.return_value = 0
                    reply.readAll.return_value = json.dumps({'tag_name': 'v99.0.0', 'body': notes}).encode()
                    def inspect(box):
                        self.assertEqual(box.textFormat(), Qt.PlainText)
                        self.assertIn('本次更新的主要内容', box.text())
                        self.assertIn('• 修复列表刷新\n• 新增实时预览' if notes else '此版本未提供更新摘要。', box.text())
                        self.assertEqual(box.detailedText(), notes or '')
                        return QMessageBox.No
                    with mock.patch.object(QMessageBox, 'exec_', new=inspect):
                        controller.checked()
                    reply.deleteLater.assert_called_once()
                    controller.stop()

    def test_opt_out_persists_and_prevents_startup_check(self):
        from PyQt5.QtWidgets import QWidget
        window = QWidget()
        settings = MemorySettings()
        controller = UpdateController(window, settings)
        controller.setAutomatic(False)
        with mock.patch.object(controller, 'check') as check:
            controller.checkAtStartup()
        check.assert_not_called()
        self.assertFalse(settings.get('autoCheckUpdates'))
        controller.stop()

    def test_download_validates_digest_and_respects_close_cancel(self):
        from PyQt5.QtWidgets import QWidget
        with tempfile.TemporaryDirectory() as folder:
            window = QWidget()
            controller = UpdateController(window, MemorySettings())
            controller.startup.stop()
            controller.path = os.path.join(folder, 'installer.exe')
            controller.output = open(controller.path + '.part', 'wb')
            controller.reply = mock.Mock()
            controller.reply.readAll.return_value = QByteArray(b'installer')
            controller.reply.error.return_value = 0
            controller.progress = mock.Mock()
            controller.digest = hashlib.sha256()
            controller.received = 0
            controller.release = {'size': 9, 'sha256': hashlib.sha256(b'installer').hexdigest()}
            with mock.patch.object(window, 'close', return_value=False), mock.patch('libs.updater.subprocess.Popen') as launch:
                controller.downloaded()
                launch.assert_not_called()
            self.assertTrue(os.path.isfile(controller.path))
            controller.stop()

    def test_verified_update_launches_in_current_install_directory(self):
        from PyQt5.QtWidgets import QWidget
        import sys
        with tempfile.TemporaryDirectory() as folder:
            window = QWidget()
            controller = UpdateController(window, MemorySettings())
            controller.startup.stop()
            controller.path = os.path.join(folder, 'installer.exe')
            controller.output = open(controller.path + '.part', 'wb')
            controller.reply = mock.Mock()
            controller.reply.readAll.return_value = QByteArray(b'installer')
            controller.reply.error.return_value = 0
            controller.progress = mock.Mock()
            controller.digest = hashlib.sha256()
            controller.received = 0
            controller.release = {'size': 9, 'sha256': hashlib.sha256(b'installer').hexdigest()}
            with mock.patch.object(window, 'close', return_value=True), mock.patch('libs.updater.subprocess.Popen') as launch:
                controller.downloaded()
                launch.assert_called_once_with([controller.path, '/SILENT', '/NORESTART',
                                                '/DIR=' + os.path.dirname(sys.executable)])
            controller.stop()

    def test_bad_digest_never_launches_installer_and_removes_partial(self):
        from PyQt5.QtWidgets import QWidget
        with tempfile.TemporaryDirectory() as folder:
            window = QWidget()
            controller = UpdateController(window, MemorySettings())
            controller.startup.stop()
            controller.path = os.path.join(folder, 'installer.exe')
            controller.output = open(controller.path + '.part', 'wb')
            controller.reply = mock.Mock()
            controller.reply.readAll.return_value = QByteArray(b'bad')
            controller.reply.error.return_value = 0
            controller.progress = mock.Mock()
            controller.digest = hashlib.sha256()
            controller.received = 0
            controller.release = {'size': 3, 'sha256': 'a' * 64}
            with mock.patch.object(QMessageBox, 'warning') as warning, mock.patch('libs.updater.subprocess.Popen') as launch:
                controller.downloaded()
                launch.assert_not_called()
                warning.assert_called_once()
            self.assertFalse(os.path.exists(controller.path + '.part'))
            self.assertFalse(os.path.exists(controller.path))
            controller.stop()


if __name__ == '__main__':
    unittest.main()
