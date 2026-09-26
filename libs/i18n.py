# -*- coding: utf-8 -*-
"""Small, dependency-free UI translation layer for the desktop application."""
from PyQt5.QtCore import QObject, Qt
from PyQt5.QtWidgets import (QApplication, QAction, QComboBox, QLineEdit,
                             QTableView, QWidget)


LANGUAGES = {
    'en': ('English', Qt.LeftToRight),
    'zh': ('简体中文', Qt.LeftToRight),
    'ja': ('日本語', Qt.LeftToRight),
    'es': ('Español', Qt.LeftToRight),
    'ar': ('العربية', Qt.RightToLeft),
    'fr': ('Français', Qt.LeftToRight),
    'ko': ('한국어', Qt.LeftToRight),
}

# These are application chrome strings, not annotation data. Class names,
# image names, paths, and user-entered text are intentionally never translated.
_ROWS = {
    'File': ('文件', 'ファイル', 'Archivo', 'ملف', 'Fichier', '파일'),
    'Edit': ('编辑', '編集', 'Editar', 'تحرير', 'Édition', '편집'),
    'View': ('视图', '表示', 'Ver', 'عرض', 'Affichage', '보기'),
    'Help': ('帮助', 'ヘルプ', 'Ayuda', 'مساعدة', 'Aide', '도움말'),
    'Settings': ('设置', '設定', 'Ajustes', 'الإعدادات', 'Paramètres', '설정'),
    'User Guide': ('使用指南', 'ユーザーガイド', 'Guía de usuario', 'دليل المستخدم', 'Guide utilisateur', '사용자 안내서'),
    'About': ('关于', 'バージョン情報', 'Acerca de', 'حول', 'À propos', '정보'),
    'Open': ('打开', '開く', 'Abrir', 'فتح', 'Ouvrir', '열기'),
    'Open Dir': ('打开图片目录', '画像フォルダーを開く', 'Abrir carpeta de imágenes', 'فتح مجلد الصور', 'Ouvrir le dossier d’images', '이미지 폴더 열기'),
    'Open Annotation Dir': ('打开标签目录', 'アノテーションフォルダーを開く', 'Abrir carpeta de anotaciones', 'فتح مجلد التسميات', 'Ouvrir le dossier d’annotations', '주석 폴더 열기'),
    'Annotation Format': ('标签格式', 'アノテーション形式', 'Formato de anotación', 'تنسيق التوسيم', 'Format d’annotation', '주석 형식'),
    'Label Shortcut Settings...': ('标签快捷键设置...', 'ラベルショートカット設定...', 'Atajos de etiquetas...', 'اختصارات الفئات...', 'Raccourcis des étiquettes...', '레이블 바로 가기 설정...'),
    'Auto Saving': ('自动保存', '自動保存', 'Guardado automático', 'الحفظ التلقائي', 'Enregistrement auto', '자동 저장'),
    'Paint Labels': ('显示框标签', 'ラベル名を表示', 'Mostrar etiquetas', 'إظهار أسماء الفئات', 'Afficher les étiquettes', '레이블 표시'),
    'Always Draw Corner': ('始终显示框角', '常に角を表示', 'Mostrar siempre las esquinas', 'إظهار الزوايا دائمًا', 'Toujours afficher les sommets', '항상 모서리 표시'),
    'Language': ('语言', '言語', 'Idioma', 'اللغة', 'Langue', '언어'),
    'Pascal VOC XML': ('Pascal VOC XML', 'Pascal VOC XML', 'Pascal VOC XML', 'Pascal VOC XML', 'Pascal VOC XML', 'Pascal VOC XML'),
    'Ultralytics YOLO': ('Ultralytics YOLO', 'Ultralytics YOLO', 'Ultralytics YOLO', 'Ultralytics YOLO', 'Ultralytics YOLO', 'Ultralytics YOLO'),
    'Ultralytics YOLO OBB': ('Ultralytics YOLO OBB', 'Ultralytics YOLO OBB', 'Ultralytics YOLO OBB', 'Ultralytics YOLO OBB', 'Ultralytics YOLO OBB', 'Ultralytics YOLO OBB'),
    'Zoom In': ('放大', '拡大', 'Acercar', 'تكبير', 'Zoom avant', '확대'),
    'Zoom Out': ('缩小', '縮小', 'Alejar', 'تصغير', 'Zoom arrière', '축소'),
    'Fit Window': ('适合窗口', 'ウィンドウに合わせる', 'Ajustar a ventana', 'ملاءمة النافذة', 'Ajuster à la fenêtre', '창에 맞춤'),
    'Fit Width': ('适合宽度', '幅に合わせる', 'Ajustar al ancho', 'ملاءمة العرض', 'Ajuster à la largeur', '너비에 맞춤'),
    'Quit': ('退出', '終了', 'Salir', 'خروج', 'Quitter', '종료'),
    'Open Recent': ('最近打开', '最近使った項目', 'Recientes', 'الملفات الأخيرة', 'Récents', '최근 항목'),
    'Open image or label file': ('打开图片或标签文件', '画像またはラベルファイルを開く', 'Abrir imagen o archivo de etiquetas', 'فتح صورة أو ملف تسميات', 'Ouvrir une image ou un fichier d’annotations', '이미지 또는 레이블 파일 열기'),
    'Save': ('保存', '保存', 'Guardar', 'حفظ', 'Enregistrer', '저장'),
    'Delete': ('删除', '削除', 'Eliminar', 'حذف', 'Supprimer', '삭제'),
    'Create': ('绘制框', 'ボックスを描画', 'Dibujar cuadro', 'رسم إطار', 'Dessiner une boîte', '상자 그리기'),
    'Open the directory used to load and save annotations': ('打开用于读取和保存标签的目录', 'ラベルの読み込みと保存に使うフォルダーを開く', 'Abrir la carpeta de anotaciones', 'فتح مجلد قراءة التسميات وحفظها', 'Ouvrir le dossier des annotations', '레이블을 읽고 저장할 폴더 열기'),
    'Box Labels': ('框标签', 'ボックスラベル', 'Etiquetas de cuadros', 'تسميات الإطارات', 'Étiquettes des boîtes', '상자 레이블'),
    'File List': ('文件列表', 'ファイル一覧', 'Lista de archivos', 'قائمة الملفات', 'Liste des fichiers', '파일 목록'),
    'Manage Labels': ('管理标签', 'ラベルを管理', 'Administrar etiquetas', 'إدارة الفئات', 'Gérer les étiquettes', '레이블 관리'),
    'difficult': ('困难样本', '難例', 'Difícil', 'صعب', 'Difficile', '난이도 높음'),
    'Rect': ('普通框', '通常の枠', 'Rectángulo', 'مستطيل', 'Rectangle', '사각형'),
    'OBB': ('旋转框', '回転枠', 'OBB', 'OBB', 'OBB', 'OBB'),
    'Select box type': ('选择框类型', '枠の種類を選択', 'Seleccionar tipo de cuadro', 'اختيار نوع الإطار', 'Choisir le type de boîte', '상자 유형 선택'),
    'Save As': ('另存为', '名前を付けて保存', 'Guardar como', 'حفظ باسم', 'Enregistrer sous', '다른 이름으로 저장'),
    'Close': ('关闭', '閉じる', 'Cerrar', 'إغلاق', 'Fermer', '닫기'),
    'ResetAll': ('重置', 'すべてリセット', 'Restablecer', 'إعادة تعيين', 'Tout réinitialiser', '모두 초기화'),
    'Shortcuts, basic operation, and advanced workflows': ('快捷键、基础操作与进阶流程', 'ショートカット、基本操作、応用ワークフロー', 'Atajos, uso básico y flujos avanzados', 'الاختصارات والاستخدام الأساسي وسير العمل المتقدم', 'Raccourcis, utilisation de base et flux avancés', '단축키, 기본 사용법 및 고급 작업'),
    'Tool Box': ('工具箱', 'ツール', 'Herramientas', 'الأدوات', 'Outils', '도구'),
    'Tools': ('工具', 'ツール', 'Herramientas', 'الأدوات', 'Outils', '도구'),
    'Drawing': ('绘制', '描画', 'Dibujo', 'الرسم', 'Dessin', '그리기'),
}

_LANG_INDEX = {'zh': 0, 'ja': 1, 'es': 2, 'ar': 3, 'fr': 4, 'ko': 5}
_LOOKUP = {}
for _english, _translations in _ROWS.items():
    _LOOKUP[_english] = dict(zip(_LANG_INDEX, _translations))
    # Map the Simplified Chinese UI strings back to the same canonical entry.
    _LOOKUP[_translations[0]] = {
        'en': _english,
        **dict(zip(('ja', 'es', 'ar', 'fr', 'ko'), _translations[1:])),
    }

_EXTRA_ZH = {
    '选择类别文件...': ('Choose Class File…', 'クラスファイルを選択…', 'Elegir archivo de clases…', 'اختيار ملف الفئات…', 'Choisir le fichier de classes…', '클래스 파일 선택…'),
    '选择自动标注模型...': ('Choose Auto-Label Model…', '自動ラベリングモデルを選択…', 'Elegir modelo de autoetiquetado…', 'اختيار نموذج الوسم الآلي…', 'Choisir le modèle de pré-étiquetage…', '자동 주석 모델 선택…'),
    '自动标注': ('Auto-Label', '自動ラベリング', 'Etiquetado automático', 'وسم آلي', 'Pré-étiquetage automatique', '자동 주석'),
    '标注当前图': ('Label Current Image', '現在の画像にラベル付け', 'Etiquetar imagen actual', 'وسم الصورة الحالية', 'Annoter l’image actuelle', '현재 이미지 주석'),
    '生成空标签': ('Create Empty Label', '空のラベルを作成', 'Crear etiqueta vacía', 'إنشاء تسمية فارغة', 'Créer une annotation vide', '빈 레이블 생성'),
    '按所选类型画框': ('Draw Selected Box Type', '選択した種類の枠を描画', 'Dibujar tipo de cuadro seleccionado', 'رسم نوع الإطار المحدد', 'Dessiner le type de boîte sélectionné', '선택한 상자 유형 그리기'),
    '按 E 绘制工具栏选中的普通框或 OBB；再按 E 退出': ('Press E to draw the selected rectangle or OBB; press E again to exit', 'E キーで選択した矩形または OBB を描画し、再度押すと終了', 'Pulsa E para dibujar el rectángulo u OBB seleccionado; vuelve a pulsar para salir', 'اضغط E لرسم المستطيل أو OBB المحدد، واضغط مجددًا للخروج', 'Appuyez sur E pour dessiner le rectangle ou OBB choisi ; appuyez de nouveau pour quitter', 'E 키로 선택한 사각형 또는 OBB를 그리고 다시 눌러 종료'),
    '刷新图片和标签': ('Refresh Images and Labels', '画像とラベルを更新', 'Actualizar imágenes y etiquetas', 'تحديث الصور والتسميات', 'Actualiser les images et annotations', '이미지 및 레이블 새로 고침'),
    '重新扫描当前图片文件夹和标签文件夹（F5）': ('Rescan the current image and annotation folders (F5)', '現在の画像・ラベルフォルダーを再スキャン (F5)', 'Volver a escanear las carpetas actuales (F5)', 'إعادة فحص مجلدي الصور والتسميات الحاليين (F5)', 'Analyser à nouveau les dossiers actuels (F5)', '현재 이미지 및 레이블 폴더 다시 검색 (F5)'),
    '删除图片及对应标签...': ('Delete Image and Matching Labels…', '画像と対応するラベルを削除…', 'Eliminar imagen y etiquetas asociadas…', 'حذف الصورة والتسميات المطابقة…', 'Supprimer l’image et ses annotations…', '이미지 및 연결된 레이블 삭제…'),
    '标记该图（待确认）': ('Flag Image for Review', '画像を要確認としてマーク', 'Marcar imagen para revisar', 'تمييز الصورة للمراجعة', 'Marquer l’image à vérifier', '이미지 검토 표시'),
    '将当前图片标为待确认，或取消待确认标记': ('Mark or unmark the current image for review', '現在の画像を要確認としてマーク/解除', 'Marcar o desmarcar la imagen actual para revisión', 'تمييز الصورة الحالية للمراجعة أو إلغاء التمييز', 'Marquer ou démarquer l’image actuelle pour vérification', '현재 이미지를 검토 대상으로 표시하거나 해제'),
    '类别文件：': ('Class file:', 'クラスファイル：', 'Archivo de clases:', 'ملف الفئات:', 'Fichier de classes :', '클래스 파일:'),
    '未选择': ('Not selected', '未選択', 'No seleccionado', 'غير محدد', 'Non sélectionné', '선택 안 됨'),
    '项目总标签数：': ('Total project labels:', 'プロジェクトのラベル総数：', 'Total de etiquetas del proyecto:', 'إجمالي تسميات المشروع:', 'Total des étiquettes du projet :', '프로젝트 전체 레이블 수:'),
    '当前图片标签数：': ('Labels in current image:', '現在の画像のラベル数：', 'Etiquetas de la imagen actual:', 'تسميات الصورة الحالية:', 'Étiquettes de l’image actuelle :', '현재 이미지 레이블 수:'),
    '本次工作已打标签数：': ('Labels added this session:', '今回の作業で追加したラベル数：', 'Etiquetas añadidas en esta sesión:', 'التسميات المضافة في هذه الجلسة:', 'Étiquettes ajoutées durant cette session :', '이번 작업에서 추가한 레이블 수:'),
    '标签统计': ('Label Statistics', 'ラベル統計', 'Estadísticas de etiquetas', 'إحصاءات التسميات', 'Statistiques des étiquettes', '레이블 통계'),
    '中止': ('Stop', '中止', 'Detener', 'إيقاف', 'Arrêter', '중지'),
    '中止中…': ('Stopping…', '中止しています…', 'Deteniendo…', 'جارٍ الإيقاف…', 'Arrêt en cours…', '중지 중…'),
    '将在当前图片推理结束后中止…': ('Will stop after the current image finishes…', '現在の画像の推論後に中止します…', 'Se detendrá al terminar la imagen actual…', 'سيتوقف بعد انتهاء معالجة الصورة الحالية…', 'Arrêt après le traitement de l’image actuelle…', '현재 이미지 처리가 끝나면 중지합니다…'),
    '选择类别文件': ('Choose Class File', 'クラスファイルを選択', 'Elegir archivo de clases', 'اختيار ملف الفئات', 'Choisir le fichier de classes', '클래스 파일 선택'),
    '历史类别文件：': ('Class file history:', 'クラスファイルの履歴：', 'Historial de archivos de clases:', 'سجل ملفات الفئات:', 'Historique des fichiers de classes :', '클래스 파일 기록:'),
    '浏览...': ('Browse…', '参照…', 'Examinar…', 'استعراض…', 'Parcourir…', '찾아보기…'),
    '移出历史': ('Remove from history', '履歴から削除', 'Quitar del historial', 'إزالة من السجل', 'Retirer de l’historique', '기록에서 제거'),
    '使用此类别文件': ('Use this class file', 'このクラスファイルを使用', 'Usar este archivo de clases', 'استخدام ملف الفئات هذا', 'Utiliser ce fichier de classes', '이 클래스 파일 사용'),
    '取消': ('Cancel', 'キャンセル', 'Cancelar', 'إلغاء', 'Annuler', '취소'),
    '保存': ('Save', '保存', 'Guardar', 'حفظ', 'Enregistrer', '저장'),
    '添加快捷键': ('Add Shortcut', 'ショートカットを追加', 'Añadir atajo', 'إضافة اختصار', 'Ajouter un raccourci', '바로 가기 추가'),
    '删除': ('Delete', '削除', 'Eliminar', 'حذف', 'Supprimer', '삭제'),
    '快捷键': ('Shortcut', 'ショートカット', 'Atajo', 'اختصار', 'Raccourci', '바로 가기'),
    '预设类别': ('Preset Class', 'プリセットクラス', 'Clase predefinida', 'فئة محددة مسبقًا', 'Classe prédéfinie', '프리셋 클래스'),
    '操作': ('Action', '操作', 'Acción', 'إجراء', 'Action', '작업'),
    '类别名称': ('Class Name', 'クラス名', 'Nombre de clase', 'اسم الفئة', 'Nom de classe', '클래스 이름'),
    '框型：普通框': ('Box: Rectangle', '枠：矩形', 'Cuadro: rectángulo', 'الإطار: مستطيل', 'Boîte : rectangle', '상자: 사각형'),
    '框型：OBB': ('Box: OBB', '枠：OBB', 'Cuadro: OBB', 'الإطار: OBB', 'Boîte : OBB', '상자: OBB'),
    '设置“按键 → 预设类别”。按下快捷键后会直接进入该类别的 OBB 画框状态。快捷键不能与现有功能或其他映射冲突。': ('Bind a key to a preset class. Pressing the key starts drawing an OBB with that class. Shortcuts cannot conflict with existing commands or other mappings.', 'キーをプリセットクラスに割り当てます。押すと、そのクラスの OBB 描画を開始します。既存機能や他の割り当てと重複できません。', 'Asigna una tecla a una clase. Al pulsarla, comienza a dibujar un OBB con esa clase. No puede haber conflictos con otros atajos.', 'اربط مفتاحًا بفئة محددة. يؤدي الضغط عليه إلى بدء رسم OBB بهذه الفئة. يجب ألا يتعارض الاختصار مع وظيفة أخرى.', 'Associez une touche à une classe. Elle lance le dessin d’une OBB pour cette classe. Le raccourci ne peut pas entrer en conflit avec une autre fonction.', '키를 프리셋 클래스에 지정합니다. 누르면 해당 클래스의 OBB 그리기가 시작됩니다. 기존 기능이나 다른 바로 가기와 충돌할 수 없습니다.'),
    '选择一个 class.txt 作为当前项目的标注类别。类别 ID 按文件中的行序从 0 开始；空行会忽略，类别名称中的内部空格会保留。': ('Choose a class.txt file for this project. Class IDs start at 0 in file order. Blank lines are ignored, and spaces inside class names are preserved.', 'プロジェクトの class.txt を選択します。クラス ID はファイル順に 0 から始まります。空行は無視され、クラス名内の空白は保持されます。', 'Elige el class.txt del proyecto. Los ID empiezan en 0 según el orden del archivo. Se ignoran líneas vacías y se conservan los espacios internos.', 'اختر ملف class.txt للمشروع. تبدأ معرفات الفئات من 0 حسب ترتيب الملف. تُتجاهل الأسطر الفارغة وتُحفظ المسافات داخل الأسماء.', 'Choisissez le class.txt du projet. Les ID commencent à 0 dans l’ordre du fichier. Les lignes vides sont ignorées et les espaces internes sont conservés.', '프로젝트의 class.txt를 선택합니다. 클래스 ID는 파일 순서대로 0부터 시작하며 빈 줄은 무시되고 이름 내부 공백은 유지됩니다.'),
    '当前图片已有标签': ('The current image already has labels', '現在の画像には既にラベルがあります', 'La imagen actual ya tiene etiquetas', 'تحتوي الصورة الحالية على تسميات بالفعل', 'L’image actuelle contient déjà des annotations', '현재 이미지에 이미 레이블이 있습니다'),
    '当前图片已有 %d 个框%s，请选择处理方式。': ('The current image has %d boxes%s. Choose how to proceed.', '現在の画像には %d 個の枠%sがあります。処理方法を選択してください。', 'La imagen actual tiene %d cuadros%s. Elige cómo continuar.', 'تحتوي الصورة الحالية على %d إطارًا%s. اختر طريقة المتابعة.', 'L’image actuelle contient %d boîtes%s. Choisissez la suite.', '현재 이미지에 상자 %d개%s가 있습니다. 처리 방법을 선택하세요.'),
    '修改 Annotation Format': ('Changing annotation format', 'アノテーション形式を変更中', 'Cambiando formato de anotación', 'جارٍ تغيير تنسيق التوسيم', 'Modification du format d’annotation', '주석 형식 변경 중'),
    'Label': ('标签', 'ラベル', 'Etiqueta', 'الفئة', 'Étiquette', '레이블'),
    'Extra Info': ('附加信息', '追加情報', 'Información extra', 'معلومات إضافية', 'Info supplémentaire', '추가 정보'),
    'Open Recent': ('最近打开', '最近使った項目', 'Recientes', 'الملفات الأخيرة', 'Récents', '최근 항목'),
    '类别文件：': ('Class file:', 'クラスファイル：', 'Archivo de clases:', 'ملف الفئات:', 'Fichier de classes :', '클래스 파일:'),
    '未选择': ('Not selected', '未選択', 'No seleccionado', 'غير محدد', 'Non sélectionné', '선택 안 됨'),
    '标签快捷键设置': ('Label Shortcut Settings', 'ラベルショートカット設定', 'Configuración de atajos de etiquetas', 'إعداد اختصارات الفئات', 'Paramètres des raccourcis d’étiquettes', '레이블 바로 가기 설정'),
    '标签快捷键设置...': ('Label Shortcut Settings…', 'ラベルショートカット設定…', 'Configuración de atajos de etiquetas…', 'إعداد اختصارات الفئات…', 'Paramètres des raccourcis d’étiquettes…', '레이블 바로 가기 설정…'),
    '标签统计': ('Label Statistics', 'ラベル統計', 'Estadísticas de etiquetas', 'إحصاءات التسميات', 'Statistiques des étiquettes', '레이블 통계'),
    '当前图片已有标签': ('The current image already has labels', '現在の画像には既にラベルがあります', 'La imagen actual ya tiene etiquetas', 'تحتوي الصورة الحالية على تسميات بالفعل', 'L’image actuelle contient déjà des annotations', '현재 이미지에 이미 레이블이 있습니다'),
    '请选择类别文件...': ('Please choose a class file…', 'クラスファイルを選択してください…', 'Elige un archivo de clases…', 'يرجى اختيار ملف فئات…', 'Veuillez choisir un fichier de classes…', '클래스 파일을 선택하세요…'),
    '预览、选择或切换 class.txt 类别文件': ('Preview, select, or switch the class.txt file', 'class.txt をプレビュー、選択、切り替え', 'Previsualizar, seleccionar o cambiar el archivo class.txt', 'معاينة ملف class.txt أو اختياره أو تبديله', 'Prévisualiser, sélectionner ou changer le fichier class.txt', 'class.txt 미리 보기, 선택 또는 전환'),
    '请选择本地 YOLO / YOLO OBB .pt 模型': ('Choose a local YOLO / YOLO OBB .pt model', 'ローカルの YOLO / YOLO OBB .pt モデルを選択', 'Elige un modelo YOLO / YOLO OBB .pt local', 'اختر نموذج YOLO / YOLO OBB .pt محليًا', 'Choisir un modèle YOLO / YOLO OBB .pt local', '로컬 YOLO / YOLO OBB .pt 모델 선택'),
    '选择类别文件': ('Choose Class File', 'クラスファイルを選択', 'Elegir archivo de clases', 'اختيار ملف الفئات', 'Choisir le fichier de classes', '클래스 파일 선택'),
    '选择类别文件...': ('Choose Class File…', 'クラスファイルを選択…', 'Elegir archivo de clases…', 'اختيار ملف الفئات…', 'Choisir le fichier de classes…', '클래스 파일 선택…'),
    '选择类别文件': ('Choose Class File', 'クラスファイルを選択', 'Elegir archivo de clases', 'اختيار ملف الفئات', 'Choisir le fichier de classes', '클래스 파일 선택'),
    '历史类别文件：': ('Class file history:', 'クラスファイルの履歴：', 'Historial de archivos de clases:', 'سجل ملفات الفئات:', 'Historique des fichiers de classes :', '클래스 파일 기록:'),
    '浏览...': ('Browse…', '参照…', 'Examinar…', 'استعراض…', 'Parcourir…', '찾아보기…'),
    '移出历史': ('Remove from history', '履歴から削除', 'Quitar del historial', 'إزالة من السجل', 'Retirer de l’historique', '기록에서 제거'),
    '使用此类别文件': ('Use this class file', 'このクラスファイルを使用', 'Usar este archivo de clases', 'استخدام ملف الفئات هذا', 'Utiliser ce fichier de classes', '이 클래스 파일 사용'),
    '取消': ('Cancel', 'キャンセル', 'Cancelar', 'إلغاء', 'Annuler', '취소'),
    '保存': ('Save', '保存', 'Guardar', 'حفظ', 'Enregistrer', '저장'),
    '添加快捷键': ('Add Shortcut', 'ショートカットを追加', 'Añadir atajo', 'إضافة اختصار', 'Ajouter un raccourci', '바로 가기 추가'),
    '删除': ('Delete', '削除', 'Eliminar', 'حذف', 'Supprimer', '삭제'),
}
for _source, _items in _EXTRA_ZH.items():
    _LOOKUP[_source] = dict(zip(
        ('en', 'ja', 'es', 'ar', 'fr', 'ko'), _items))
    _LOOKUP[_source]['zh'] = _source

_EXTRA_EN = {
    'Verify Image': ('校验图片', '画像を確認', 'Verificar imagen', 'التحقق من الصورة', 'Vérifier l’image', '이미지 확인'),
    'Create\nRectBox': ('绘制普通框', '通常枠を描画', 'Dibujar rectángulo', 'رسم مستطيل', 'Dessiner un rectangle', '사각형 그리기'),
    'Create\nSolidRectBox': ('绘制矩形', '矩形を描画', 'Dibujar rectángulo sólido', 'رسم مستطيل', 'Dessiner un rectangle plein', '솔리드 사각형 그리기'),
    'Create\nRotatedRBox': ('绘制旋转框', '回転枠を描画', 'Dibujar OBB', 'رسم OBB', 'Dessiner une OBB', 'OBB 그리기'),
    'Delete\nRectBox': ('删除框', '枠を削除', 'Eliminar cuadro', 'حذف الإطار', 'Supprimer la boîte', '상자 삭제'),
    'Duplicate\nRectBox': ('复制框', '枠を複製', 'Duplicar cuadro', 'تكرار الإطار', 'Dupliquer la boîte', '상자 복제'),
    'Label as background': ('标记为背景样本', '背景サンプルとしてマーク', 'Marcar como fondo', 'وضع علامة كخلفية', 'Marquer comme arrière-plan', '배경 샘플로 표시'),
    'No Label': ('删除当前图片全部标签', '現在の画像のラベルをすべて削除', 'Eliminar todas las etiquetas', 'حذف جميع التسميات', 'Supprimer toutes les annotations', '모든 레이블 삭제'),
    'Copy Box': ('复制框', '枠をコピー', 'Copiar cuadro', 'نسخ الإطار', 'Copier la boîte', '상자 복사'),
    'Cut Box': ('剪切框', '枠を切り取り', 'Cortar cuadro', 'قص الإطار', 'Couper la boîte', '상자 잘라내기'),
    'Paste Box': ('粘贴框', '枠を貼り付け', 'Pegar cuadro', 'لصق الإطار', 'Coller la boîte', '상자 붙여넣기'),
    'Undo Last Operation': ('撤销上一步操作', '直前の操作を元に戻す', 'Deshacer última operación', 'التراجع عن العملية الأخيرة', 'Annuler la dernière opération', '마지막 작업 실행 취소'),
    'Original size': ('原始大小', '元のサイズ', 'Tamaño original', 'الحجم الأصلي', 'Taille d’origine', '원래 크기'),
    'Prev Image': ('上一张图片', '前の画像', 'Imagen anterior', 'الصورة السابقة', 'Image précédente', '이전 이미지'),
    'Next Image': ('下一张图片', '次の画像', 'Imagen siguiente', 'الصورة التالية', 'Image suivante', '다음 이미지'),
    'Play': ('自动播放', '自動再生', 'Reproducir', 'تشغيل', 'Lire', '재생'),
    'Manage Labels': ('管理标签', 'ラベルを管理', 'Administrar etiquetas', 'إدارة الفئات', 'Gérer les étiquettes', '레이블 관리'),
    'set as default': ('设为默认类别', '既定に設定', 'Establecer como predeterminado', 'تعيين كافتراضي', 'Définir par défaut', '기본값으로 설정'),
    'add': ('添加', '追加', 'Añadir', 'إضافة', 'Ajouter', '추가'),
    '置信度': ('Confidence', '信頼度', 'Confianza', 'الثقة', 'Confiance', '신뢰도'),
    '框型：': ('Box type:', '枠の種類：', 'Tipo de cuadro:', 'نوع الإطار:', 'Type de boîte :', '상자 유형:'),
}
for _source, _items in _EXTRA_EN.items():
    _LOOKUP[_source] = {'en': _source}
    _LOOKUP[_source].update(dict(zip(
        ('zh', 'ja', 'es', 'ar', 'fr', 'ko'), _items)))

_EN_EXTRA = {
    'Cancel': ('取消', 'キャンセル', 'Cancelar', 'إلغاء', 'Annuler', '취소'),
    'Close': ('关闭', '閉じる', 'Cerrar', 'إغلاق', 'Fermer', '닫기'),
    'Save': ('保存', '保存', 'Guardar', 'حفظ', 'Enregistrer', '저장'),
    'Yes': ('是', 'はい', 'Sí', 'نعم', 'Oui', '예'),
    'No': ('否', 'いいえ', 'No', 'لا', 'Non', '아니요'),
    'OK': ('确定', 'OK', 'Aceptar', 'موافق', 'OK', '확인'),
}
for _source, _items in _EN_EXTRA.items():
    _LOOKUP[_source] = {'en': _source}
    _LOOKUP[_source].update(dict(zip(
        ('zh', 'ja', 'es', 'ar', 'fr', 'ko'), _items)))


def translate(text, language):
    mnemonic = str(text).startswith('&')
    key = str(text).replace('&', '')
    if language == 'en':
        result = _LOOKUP.get(key, {}).get('en')
    else:
        result = _LOOKUP.get(key, {}).get(language)
    if result is None:
        for prefix in sorted(_LOOKUP, key=len, reverse=True):
            if prefix and key.startswith(prefix):
                translated_prefix = _LOOKUP[prefix].get(language, prefix)
                result = translated_prefix + key[len(prefix):]
                break
    if result is None:
        result = key
    return ('&' if mnemonic else '') + result


class LanguageManager(QObject):
    """Translate widget chrome while preserving original source strings."""

    def __init__(self, root, language='en'):
        super(LanguageManager, self).__init__(root)
        self.root = root
        self.language = language if language in LANGUAGES else 'en'

    def _update(self, widget, getter, setter, property_name):
        source_property = 'i18nSource_' + property_name
        rendered_property = 'i18nRendered_' + property_name
        current = getter()
        source = widget.property(source_property)
        previous = widget.property(rendered_property)
        if source is None or (current != previous and current != source):
            source = current
            widget.setProperty(source_property, source)
        translated = translate(str(source), self.language)
        if str(current) != translated:
            setter(translated)
        widget.setProperty(rendered_property, translated)

    def applyWidget(self, widget):
        if not isinstance(widget, QWidget):
            return
        widgets = [widget] + widget.findChildren(QWidget)
        for widget in widgets:
            for prop, getter, setter in (
                    ('text', lambda w=widget: w.text()
                     if hasattr(w, 'text') else None,
                     lambda value, w=widget: w.setText(value)
                     if hasattr(w, 'setText') else None),
                    ('title', lambda w=widget: w.windowTitle(),
                     lambda value, w=widget: w.setWindowTitle(value)),
                    ('tooltip', lambda w=widget: w.toolTip(),
                     lambda value, w=widget: w.setToolTip(value),),
                    ('statustip', lambda w=widget: w.statusTip(),
                     lambda value, w=widget: w.setStatusTip(value)),
                    ('whatsthis', lambda w=widget: w.whatsThis(),
                     lambda value, w=widget: w.setWhatsThis(value))):
                try:
                    current = getter()
                    if current is not None and current != '':
                        self._update(widget, getter, setter, prop)
                except (AttributeError, RuntimeError, TypeError):
                    pass
            if isinstance(widget, QLineEdit):
                self._update(widget, widget.placeholderText,
                             widget.setPlaceholderText, 'placeholder')
            if isinstance(widget, QComboBox) and widget.objectName() == 'boxTypeComboBox':
                for index in range(widget.count()):
                    source_property = 'i18nItemSource_%d' % index
                    rendered_property = 'i18nItemRendered_%d' % index
                    current = widget.itemText(index)
                    source = widget.property(source_property)
                    previous = widget.property(rendered_property)
                    if source is None or (current != previous and
                                          current != source):
                        source = current
                        widget.setProperty(source_property, source)
                    translated = translate(str(source), self.language)
                    if current != translated:
                        widget.setItemText(index, translated)
                    widget.setProperty(rendered_property, translated)
            if isinstance(widget, QTableView):
                model = widget.model()
                for section in range(model.columnCount()):
                    source_property = 'i18nHeaderSource_%d' % section
                    rendered_property = 'i18nHeaderRendered_%d' % section
                    current = model.headerData(section, Qt.Horizontal,
                                               Qt.DisplayRole)
                    source = model.property(source_property)
                    previous = model.property(rendered_property)
                    if source is None or (current != previous and
                                          current != source):
                        source = current
                        model.setProperty(source_property, source)
                    translated = translate(str(source), self.language)
                    if current != translated:
                        model.setHeaderData(section, Qt.Horizontal,
                                            translated, Qt.DisplayRole)
                    model.setProperty(rendered_property, translated)
            actions = getattr(widget, 'actions', None)
            if callable(actions):
                for action in actions():
                    self._update(action, action.text, action.setText, 'text')
                    self._update(action, action.toolTip, action.setToolTip,
                                 'tooltip')
    def apply(self, language=None):
        if language is not None:
            self.language = language if language in LANGUAGES else 'en'
        self.applyWidget(self.root)
        self.root.setLayoutDirection(LANGUAGES[self.language][1])
        app = QApplication.instance()
        if app is not None:
            app.setLayoutDirection(LANGUAGES[self.language][1])
