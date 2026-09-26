# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (QDialog, QDialogButtonBox, QTextBrowser,
                             QVBoxLayout)


_GUIDES = {
    'en': ('User Guide', 'Keyboard shortcuts',
           '<li><b>E</b>: draw the selected box type (rectangle or OBB); press again to exit.</li>'
           '<li><b>R</b>: hide/show the selected box, or all boxes when none is selected.</li>'
           '<li><b>Ctrl+Shift+L</b>: hide/show labels for the selected box, or all labels when none is selected.</li>'
           '<li><b>Ctrl+S</b>: save. <b>Up/Down</b>: move between images when no box is selected.</li>'
           '<li><b>Ctrl+C / Ctrl+X / Ctrl+V / Ctrl+Z</b>: copy / cut / paste / undo.</li>'
           '<li><b>T</b>: show/hide rotated boxes. <b>N</b>: show/hide normal boxes.</li>'
           '<li><b>Alt + left-drag</b>: pan the canvas. Mouse wheel zooms the image, or resizes selected boxes.</li>',
           'Basic use',
           '<ol><li>Open an image folder, then choose an annotation folder with <i>Open Annotation Dir</i>.</li>'
           '<li>Choose a class file and annotation format in <i>Settings</i>.</li>'
           '<li>Select the rectangle or OBB tool, draw a box, and choose its class.</li>'
           '<li>Save your work; enable Auto Saving in Settings if desired.</li></ol>',
           'Advanced use',
           '<ul><li>Drag from outside the image to create a box; its edges snap inside the image.</li>'
           '<li>Drag from empty canvas space—even outside the image—to select multiple boxes; then move, copy, or delete them together.</li>'
           '<li>Use Label Shortcut Settings to bind keys to classes from the active class file.</li>'
           '<li>Use the model controls for batch or single-image pre-annotation, then review all predictions manually.</li></ul>'),
    'zh': ('使用指南', '快捷键',
           '<li><b>E</b>：按工具栏选定的框型（普通框或 OBB）绘框；再次按下退出。</li>'
           '<li><b>R</b>：隐藏/显示选中的框；未选中时隐藏/显示全部框。</li>'
           '<li><b>Ctrl+Shift+L</b>：隐藏/显示选中框的标签；未选中时隐藏/显示全部标签。</li>'
           '<li><b>Ctrl+S</b>：保存。未选中框时按<b>上/下方向键</b>切换图片。</li>'
           '<li><b>Ctrl+C / Ctrl+X / Ctrl+V / Ctrl+Z</b>：复制 / 剪切 / 粘贴 / 撤销。</li>'
           '<li><b>T</b>：显示/隐藏旋转框；<b>N</b>：显示/隐藏普通框。</li>'
           '<li><b>Alt + 鼠标左键拖动</b>：平移画布。滚轮缩放图片；选中框时滚轮调整框大小。</li>',
           '基础使用',
           '<ol><li>打开图片目录，再用“Open Annotation Dir”选择标签目录。</li>'
           '<li>在“Settings”中选择类别文件和标签格式。</li>'
           '<li>选择普通框或 OBB 工具，绘框并选择类别。</li>'
           '<li>保存标注；也可在 Settings 中开启自动保存。</li></ol>',
           '进阶使用',
           '<ul><li>可从图片外开始绘框，生成后会吸附到图片边界内。</li>'
           '<li>从画布空白处（包括图片外）拖动可多选框，然后集体移动、复制或删除。</li>'
           '<li>在“标签快捷键设置”中将按键绑定到当前类别文件中的类别。</li>'
           '<li>可批量或单张使用模型预标注；请始终人工复核模型结果。</li></ul>'),
    'ja': ('ユーザーガイド', 'ショートカット',
           '<li><b>E</b>：ツールバーで選択した矩形または OBB を描画。もう一度押すと終了。</li>'
           '<li><b>R</b>：選択した枠を表示/非表示。未選択の場合はすべての枠を切り替え。</li>'
           '<li><b>Ctrl+Shift+L</b>：選択枠のラベルを表示/非表示。未選択時はすべてのラベル。</li>'
           '<li><b>Ctrl+S</b>：保存。枠が未選択なら<b>上/下</b>で画像を切り替え。</li>'
           '<li><b>Ctrl+C / Ctrl+X / Ctrl+V / Ctrl+Z</b>：コピー / 切り取り / 貼り付け / 元に戻す。</li>'
           '<li><b>T</b>：回転枠の表示切替。<b>N</b>：通常枠の表示切替。</li>'
           '<li><b>Alt + 左ドラッグ</b>：キャンバスを移動。ホイールで画像を拡大縮小、枠選択時は枠を拡大縮小。</li>',
           '基本操作',
           '<ol><li>画像フォルダーを開き、「Open Annotation Dir」でラベルフォルダーを選択します。</li>'
           '<li>「Settings」でクラスファイルと形式を選択します。</li>'
           '<li>矩形または OBB を選び、枠を描いてクラスを指定します。</li><li>保存します。自動保存も設定できます。</li></ol>',
           '応用操作',
           '<ul><li>画像外から枠を描き始めても、完成時に画像境界内へ収まります。</li>'
           '<li>画像外を含む空白部分からドラッグして複数枠を選択し、一括操作できます。</li>'
           '<li>ラベルショートカット設定で、現在のクラスファイルのカテゴリにキーを割り当てます。</li>'
           '<li>モデルによる一括・単一画像の事前アノテーション後は、結果を必ず確認してください。</li></ul>'),
    'es': ('Guía de usuario', 'Atajos de teclado',
           '<li><b>E</b>: dibuja el tipo seleccionado (rectángulo u OBB); vuelve a pulsar para salir.</li>'
           '<li><b>R</b>: oculta/muestra el cuadro seleccionado o todos si no hay selección.</li>'
           '<li><b>Ctrl+Shift+L</b>: oculta/muestra las etiquetas seleccionadas o todas si no hay selección.</li>'
           '<li><b>Ctrl+S</b>: guardar. Sin cuadro seleccionado, <b>Arriba/Abajo</b> cambia de imagen.</li>'
           '<li><b>Ctrl+C / Ctrl+X / Ctrl+V / Ctrl+Z</b>: copiar / cortar / pegar / deshacer.</li>'
           '<li><b>T</b>: mostrar/ocultar OBB. <b>N</b>: mostrar/ocultar rectángulos.</li>'
           '<li><b>Alt + arrastrar con botón izquierdo</b>: mover el lienzo. La rueda amplía la imagen o, con cuadros seleccionados, los cuadros.</li>',
           'Uso básico',
           '<ol><li>Abre una carpeta de imágenes y selecciona la carpeta de etiquetas con “Open Annotation Dir”.</li>'
           '<li>Elige el archivo de clases y el formato en “Settings”.</li>'
           '<li>Selecciona rectángulo u OBB, dibuja un cuadro y asigna una clase.</li><li>Guarda; puedes activar el guardado automático.</li></ol>',
           'Uso avanzado',
           '<ul><li>Puedes empezar el cuadro fuera de la imagen; al terminar se ajusta a sus bordes.</li>'
           '<li>Arrastra desde un espacio vacío, incluso fuera de la imagen, para seleccionar varios cuadros.</li>'
           '<li>Asigna teclas a clases del archivo actual en la configuración de atajos.</li>'
           '<li>Revisa manualmente todas las predicciones del etiquetado automático.</li></ul>'),
    'ar': ('دليل المستخدم', 'اختصارات لوحة المفاتيح',
           '<li><b>E</b>: ارسم نوع الإطار المحدد (مستطيل أو OBB)، واضغط مجددًا للخروج.</li>'
           '<li><b>R</b>: إخفاء/إظهار الإطار المحدد، أو جميع الإطارات عند عدم التحديد.</li>'
           '<li><b>Ctrl+Shift+L</b>: إخفاء/إظهار تسميات الإطار المحدد، أو جميع التسميات عند عدم التحديد.</li>'
           '<li><b>Ctrl+S</b>: حفظ. عند عدم تحديد إطار، يبدّل <b>أعلى/أسفل</b> الصورة.</li>'
           '<li><b>Ctrl+C / Ctrl+X / Ctrl+V / Ctrl+Z</b>: نسخ / قص / لصق / تراجع.</li>'
           '<li><b>T</b>: إظهار/إخفاء OBB. <b>N</b>: إظهار/إخفاء المستطيلات.</li>'
           '<li><b>Alt + سحب بالزر الأيسر</b>: تحريك اللوحة. تستخدم العجلة للتكبير، أو لتغيير حجم الإطارات المحددة.</li>',
           'الاستخدام الأساسي',
           '<ol><li>افتح مجلد الصور، ثم اختر مجلد التسميات عبر “Open Annotation Dir”.</li>'
           '<li>اختر ملف الفئات وتنسيق التسميات في “Settings”.</li>'
           '<li>اختر المستطيل أو OBB، وارسم إطارًا ثم حدد الفئة.</li><li>احفظ العمل ويمكنك تفعيل الحفظ التلقائي.</li></ol>',
           'الاستخدام المتقدم',
           '<ul><li>يمكن بدء رسم الإطار خارج الصورة؛ وعند الانتهاء يلتصق بحدودها.</li>'
           '<li>اسحب من مساحة فارغة، حتى خارج الصورة، لتحديد عدة إطارات وتحريكها أو نسخها أو حذفها معًا.</li>'
           '<li>اربط مفاتيح بالفئات من ملف الفئات الحالي عبر إعدادات الاختصارات.</li>'
           '<li>راجع يدويًا جميع تنبؤات الوسم الآلي.</li></ul>'),
    'fr': ('Guide utilisateur', 'Raccourcis clavier',
           '<li><b>E</b> : dessiner le type choisi (rectangle ou OBB) ; appuyez de nouveau pour quitter.</li>'
           '<li><b>R</b> : masquer/afficher la boîte sélectionnée, ou toutes les boîtes sans sélection.</li>'
           '<li><b>Ctrl+Shift+L</b> : masquer/afficher les étiquettes sélectionnées, ou toutes sans sélection.</li>'
           '<li><b>Ctrl+S</b> : enregistrer. Sans boîte sélectionnée, <b>Haut/Bas</b> change d’image.</li>'
           '<li><b>Ctrl+C / Ctrl+X / Ctrl+V / Ctrl+Z</b> : copier / couper / coller / annuler.</li>'
           '<li><b>T</b> : afficher/masquer les OBB. <b>N</b> : afficher/masquer les rectangles.</li>'
           '<li><b>Alt + glisser gauche</b> : déplacer le canevas. La molette zoome l’image ou redimensionne les boîtes sélectionnées.</li>',
           'Utilisation de base',
           '<ol><li>Ouvrez un dossier d’images, puis choisissez le dossier d’annotations avec « Open Annotation Dir ».</li>'
           '<li>Choisissez le fichier de classes et le format dans « Settings ».</li>'
           '<li>Sélectionnez rectangle ou OBB, dessinez une boîte et choisissez sa classe.</li><li>Enregistrez ; l’enregistrement automatique est disponible.</li></ol>',
           'Utilisation avancée',
           '<ul><li>Commencez une boîte hors image ; elle sera ajustée aux limites à la fin.</li>'
           '<li>Faites glisser depuis une zone vide, même hors image, pour sélectionner plusieurs boîtes.</li>'
           '<li>Associez des touches aux classes du fichier courant dans les paramètres de raccourcis.</li>'
           '<li>Vérifiez manuellement toutes les prédictions du pré-étiquetage automatique.</li></ul>'),
    'ko': ('사용자 안내서', '키보드 단축키',
           '<li><b>E</b>: 선택된 상자 유형(사각형 또는 OBB)을 그립니다. 다시 누르면 종료합니다.</li>'
           '<li><b>R</b>: 선택한 상자를 숨기거나 표시합니다. 선택이 없으면 모든 상자를 전환합니다.</li>'
           '<li><b>Ctrl+Shift+L</b>: 선택한 상자의 레이블을 전환합니다. 선택이 없으면 모든 레이블을 전환합니다.</li>'
           '<li><b>Ctrl+S</b>: 저장. 상자 선택이 없으면 <b>위/아래</b>로 이미지를 전환합니다.</li>'
           '<li><b>Ctrl+C / Ctrl+X / Ctrl+V / Ctrl+Z</b>: 복사 / 잘라내기 / 붙여넣기 / 실행 취소.</li>'
           '<li><b>T</b>: OBB 표시/숨기기. <b>N</b>: 사각형 표시/숨기기.</li>'
           '<li><b>Alt + 마우스 왼쪽 드래그</b>: 캔버스 이동. 휠은 이미지 확대/축소 또는 선택 상자 크기 조절에 사용됩니다.</li>',
           '기본 사용법',
           '<ol><li>이미지 폴더를 열고 “Open Annotation Dir”에서 레이블 폴더를 선택합니다.</li>'
           '<li>“Settings”에서 클래스 파일과 레이블 형식을 선택합니다.</li>'
           '<li>사각형 또는 OBB를 선택해 상자를 그리고 클래스를 지정합니다.</li><li>저장하거나 자동 저장을 활성화합니다.</li></ol>',
           '고급 사용법',
           '<ul><li>이미지 바깥에서 상자를 시작해도 완료 시 경계 안으로 맞춰집니다.</li>'
           '<li>이미지 바깥을 포함한 빈 캔버스에서 드래그해 여러 상자를 선택하고 함께 편집할 수 있습니다.</li>'
           '<li>바로 가기 설정에서 현재 클래스 파일의 클래스에 키를 지정합니다.</li>'
           '<li>모델 자동 주석 결과는 모두 직접 검토하세요.</li></ul>'),
}


class UserGuideDialog(QDialog):
    def __init__(self, language='en', parent=None):
        super(UserGuideDialog, self).__init__(parent)
        self.setMinimumSize(520, 420)
        self.setWindowTitle(_GUIDES.get(language, _GUIDES['en'])[0])
        (title, shortcuts, shortcut_body, basic, basic_body,
         advanced, advanced_body) = _GUIDES.get(language, _GUIDES['en'])
        browser = QTextBrowser(self)
        browser.setOpenExternalLinks(False)
        browser.setHtml(
            '<h2>{0}</h2><h3>{1}</h3><ul>{2}</ul>'
            '<h3>{3}</h3>{4}<h3>{5}</h3>{6}'.format(
                title, shortcuts, shortcut_body, basic, basic_body,
                advanced, advanced_body))
        buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(browser)
        layout.addWidget(buttons)
