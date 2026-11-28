# -*- coding: utf-8 -*-
"""Small, dependency-free UI translation layer for the desktop application."""
from PyQt5.QtCore import QObject, Qt
from PyQt5.QtWidgets import (QApplication, QAction, QComboBox, QLineEdit,
                             QDoubleSpinBox, QTableView, QTreeView, QWidget)


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
    "Mark %d selected image(s) for review": ("标记选中的 %d 张图（待确认）", "選択した %d 枚を要確認にする", "Marcar %d imágenes para revisión", "وضع علامة مراجعة على %d صور", "Marquer %d images à vérifier", "선택한 이미지 %d장을 검토용으로 표시"),
    "Unmark %d selected image(s)": ("取消选中的 %d 张图的待确认标记", "選択した %d 枚のマークを解除", "Quitar la marca a %d imágenes", "إزالة العلامة عن %d صور", "Retirer la marque de %d images", "선택한 이미지 %d장의 표시 해제"),
    'Mark or Unmark Current Image': ('标记或取消标记当前图片', '現在の画像の確認マークを切り替え', 'Marcar o desmarcar la imagen actual', 'تمييز الصورة الحالية أو إلغاء تمييزها', 'Marquer ou démarquer l’image actuelle', '현재 이미지 표시 또는 해제'),
    "Recycle %d selected image(s) and labels…": ("删除选中的 %d 张图片及其标签…", "選択した %d 枚とラベルをごみ箱へ…", "Enviar %d imágenes y sus etiquetas a la papelera…", "نقل %d صور وتسمياتها إلى سلة المحذوفات…", "Mettre %d images et leurs annotations à la corbeille…", "선택한 이미지 %d장과 레이블을 휴지통으로…"),
    "Shared labels were kept.": ("共用或受保护的标签已保留。", "共有または保護されたラベルは保持されました。", "Se conservaron las etiquetas compartidas o protegidas.", "تم الاحتفاظ بالتسميات المشتركة أو المحمية.", "Les annotations partagées ou protégées ont été conservées.", "공유 또는 보호된 레이블은 유지했습니다."),
    "Stop annotation before recycling images.": ("请先停止自动标注，再删除图片。", "画像を削除する前に自動注釈を停止してください。", "Detén la anotación antes de eliminar imágenes.", "أوقف وضع التسميات قبل حذف الصور.", "Arrêtez l’annotation avant de recycler des images.", "이미지를 삭제하기 전에 자동 주석을 중지하세요."),
    "Move %d image(s) and %d matching label file(s) to the Recycle Bin?": ("将 %d 张图片和 %d 个对应标签文件移入回收站吗？", "画像 %d 枚と対応するラベル %d 個をごみ箱に移動しますか？", "¿Enviar %d imágenes y %d archivos de etiquetas a la papelera?", "هل تريد نقل %d صور و%d ملفات تسميات إلى سلة المحذوفات؟", "Mettre %d images et %d fichiers d’annotations à la corbeille ?", "이미지 %d장과 일치하는 레이블 파일 %d개를 휴지통으로 옮길까요?"),
    "Shared or protected label files will be kept.": ("共用或受保护的标签文件会保留。", "共有または保護されたラベルは保持されます。", "Se conservarán las etiquetas compartidas o protegidas.", "سيتم الاحتفاظ بالتسميات المشتركة أو المحمية.", "Les annotations partagées ou protégées seront conservées.", "공유 또는 보호된 레이블 파일은 유지합니다."),
    "Recycle selected images": ("将选中的图片移入回收站", "選択した画像をごみ箱へ", "Enviar las imágenes seleccionadas a la papelera", "نقل الصور المحددة إلى سلة المحذوفات", "Mettre les images sélectionnées à la corbeille", "선택한 이미지를 휴지통으로"),
    "File is no longer available.": ("文件已不存在或无法访问。", "ファイルにアクセスできません。", "El archivo ya no está disponible.", "الملف لم يعد متاحًا.", "Le fichier n’est plus disponible.", "파일을 더 이상 사용할 수 없습니다."),
    "Recycled %d image(s) and %d label file(s).": ("已移入回收站：%d 张图片、%d 个标签文件。", "画像 %d 枚とラベル %d 個をごみ箱に移動しました。", "Se enviaron %d imágenes y %d etiquetas a la papelera.", "تم نقل %d صور و%d ملفات تسميات إلى سلة المحذوفات.", "%d images et %d fichiers d’annotations mis à la corbeille.", "이미지 %d장과 레이블 파일 %d개를 휴지통으로 옮겼습니다."),
    "%d file(s) could not be recycled.": ("有 %d 个文件未能移入回收站。", "%d 個のファイルをごみ箱に移動できませんでした。", "No se pudieron enviar %d archivos a la papelera.", "تعذر نقل %d ملفات إلى سلة المحذوفات.", "%d fichiers n’ont pas pu être mis à la corbeille.", "파일 %d개를 휴지통으로 옮기지 못했습니다."),
    "New Features Guide": ("新功能导览", "新機能ガイド", "Guía de novedades", "دليل الميزات الجديدة", "Guide des nouveautés", "새 기능 안내"),
    "Show Guide After Updates": ("更新后自动显示新功能导览", "更新後にガイドを表示", "Mostrar la guía tras actualizar", "عرض الدليل بعد التحديثات", "Afficher le guide après les mises à jour", "업데이트 후 안내 표시"),
    "Interface Animations": ("界面动画", "画面アニメーション", "Animaciones de interfaz", "رسوم الواجهة المتحركة", "Animations de l’interface", "인터페이스 애니메이션"),
    "Previous": ("上一步", "戻る", "Anterior", "السابق", "Précédent", "이전"),
    "Next": ("下一步", "次へ", "Siguiente", "التالي", "Suivant", "다음"),
    "Skip Guide": ("跳过导览", "ガイドをスキップ", "Saltar guía", "تخطي الدليل", "Passer le guide", "안내 건너뛰기"),
    "Finish Guide": ("完成导览", "ガイドを終了", "Terminar guía", "إنهاء الدليل", "Terminer le guide", "안내 완료"),
    "Batch image actions": ("批量处理图片", "画像の一括操作", "Acciones por lotes", "إجراءات الصور المجمعة", "Actions par lot", "이미지 일괄 작업"),
    "Drag across rows in File List, then right-click. Mark or unmark the selection, or recycle the images and matching labels after confirming.": ("在文件列表拖动框选，再右键。可批量标记或取消待确认，也可确认后将图片和对应标签移入回收站。", "ファイル一覧でドラッグして選択し、右クリックします。一括で要確認マークを設定・解除したり、確認後に画像とラベルをごみ箱へ移動できます。", "Arrastra por la lista y haz clic con el botón derecho. Marca o desmarca la selección, o envía las imágenes y sus etiquetas a la papelera tras confirmar.", "اسحب فوق قائمة الملفات، ثم انقر بزر الفأرة الأيمن. يمكنك تعليم المجموعة أو إزالة علاماتها أو نقل الصور وتسمياتها إلى السلة بعد التأكيد.", "Faites glisser dans la liste, puis faites un clic droit. Marquez ou démarquez la sélection, ou mettez les images et leurs annotations à la corbeille après confirmation.", "파일 목록을 드래그해 선택한 뒤 마우스 오른쪽 버튼을 누르세요. 일괄 표시, 표시 해제, 확인 후 이미지와 레이블을 휴지통으로 이동할 수 있습니다."),
    "Windows collapse back to their entry": ("窗口收回打开入口", "ウィンドウを開いた場所に戻す", "Las ventanas vuelven a su acceso", "تعود النوافذ إلى زر فتحها", "Les fenêtres se replient vers leur raccourci", "열었던 위치로 창 접기"),
    "Collapse the Agent Task Window to its status-bar button. Annotation keeps running. Click the button to bring it back.": ("收起智能体任务窗口，它会缩回状态栏按钮。标注会继续运行，点击按钮即可展开。", "エージェントのタスクウィンドウをステータスバーのボタンへ折りたたみます。作業は続行され、ボタンから再表示できます。", "Contrae la ventana del agente a su botón en la barra de estado. La anotación continúa. Pulsa el botón para volver a abrirla.", "اطوِ نافذة مهام الوكيل إلى زرها في شريط الحالة. يستمر وضع التسميات، ويمكنك إظهار النافذة بالضغط على الزر.", "Réduisez la fenêtre de l’agent vers son bouton dans la barre d’état. L’annotation continue. Cliquez sur le bouton pour la rouvrir.", "에이전트 작업 창을 상태 표시줄의 버튼으로 접을 수 있습니다. 주석 작업은 계속되며 버튼을 눌러 다시 엽니다."),
    "Replay the guide or reduce motion": ("重看导览或减少动画", "ガイドの再表示とアニメーション設定", "Volver a ver la guía o reducir el movimiento", "إعادة الدليل أو تقليل الحركة", "Revoir le guide ou réduire les animations", "안내 다시 보기 또는 모션 줄이기"),
    "Reopen this guide from Help. Under Settings, you can turn off interface animations or the automatic guide after updates.": ("从「帮助」可以重看导览。在「设置」里可关闭界面动画，或取消更新后自动显示导览。", "ヘルプからガイドを再表示できます。設定でアニメーションや更新後の自動表示を無効にできます。", "Vuelve a abrir la guía desde Ayuda. En Ajustes puedes desactivar las animaciones o la guía automática tras actualizar.", "أعد فتح الدليل من المساعدة. يمكنك تعطيل الرسوم المتحركة أو الدليل التلقائي بعد التحديث من الإعدادات.", "Rouvrez le guide depuis Aide. Les paramètres permettent de désactiver les animations ou l’affichage automatique du guide après une mise à jour.", "도움말에서 안내를 다시 열 수 있습니다. 설정에서 화면 애니메이션이나 업데이트 후 자동 안내를 끌 수 있습니다."),
    "Mark selected images": ("标记选中的图片", "選択画像にマークを付ける", "Marcar imágenes seleccionadas", "تعليم الصور المحددة", "Marquer les images sélectionnées", "선택한 이미지 표시"),
    "Unmark selected images": ("取消选中的图片标记", "選択画像のマークを解除", "Desmarcar imágenes seleccionadas", "إزالة تعليم الصور المحددة", "Démarquer les images sélectionnées", "선택한 이미지 표시 해제"),
    'Stop the agent task before converting annotations.': ('请先停止智能体任务，再转换标签格式。','ラベル変換前にエージェントのタスクを停止してください。','Detén la tarea del agente antes de convertir anotaciones.','أوقف مهمة الوكيل قبل تحويل التسميات.','Arrêtez la tâche de l’agent avant de convertir les annotations.','레이블 변환 전에 에이전트 작업을 중지하세요.'),
    'Agent Task Window': ('智能体任务窗口','エージェントのタスク','Tarea del agente','نافذة مهام الوكيل','Tâche de l’agent','에이전트 작업 창'),
    'Add %d image(s) to Agent Task': ('将选中的 %d 张图片加入智能体任务','選択した %d 枚をタスクに追加','Añadir %d imágenes a la tarea','إضافة %d صور إلى المهمة','Ajouter %d images à la tâche','선택한 이미지 %d장을 작업에 추가'),
    'Collapse': ('收起','折りたたむ','Contraer','طي','Réduire','접기'),
    'Stop Agent Task': ('停止任务','タスクを停止','Detener tarea','إيقاف المهمة','Arrêter la tâche','작업 중지'),
    'Reserved for agent task': ('智能体任务占用中','エージェントのタスク用に確保済み','Reservada para el agente','محجوزة لمهمة الوكيل','Réservée à l’agent','에이전트 작업에 예약됨'),
    'Waiting for a task': ('暂无任务','タスク待ち','Esperando tarea','بانتظار مهمة','En attente d’une tâche','작업 대기 중'),
    'Waiting for the agent': ('已加入，等待智能体领取','エージェントの開始待ち','Esperando al agente','بانتظار الوكيل','En attente de l’agent','에이전트 시작 대기 중'),
    'Agent annotation in progress': ('智能体正在标注','エージェントが作業中','El agente está anotando','الوكيل يعلّق الآن','L’agent annote','에이전트 주석 작업 중'),
    'Total elapsed: {time}': ('总耗时：{time}', '合計時間：{time}', 'Tiempo total: {time}', 'الوقت الإجمالي: {time}', 'Durée totale : {time}', '총 소요 시간: {time}'),
    'Average per image: {time}': ('平均每张耗时：{time}', '1枚あたりの平均：{time}', 'Media por imagen: {time}', 'المتوسط لكل صورة: {time}', 'Moyenne par image : {time}', '이미지당 평균: {time}'),
    'Agent task completed': ('任务完成，图片已解锁','タスク完了、画像の確保を解除','Tarea completada; imágenes liberadas','اكتملت المهمة وأُفرج عن الصور','Tâche terminée, images libérées','작업 완료, 이미지 잠금 해제'),
    'Task stopped; images released': ('任务已停止，图片已解锁','タスク停止、画像の確保を解除','Tarea detenida; imágenes liberadas','توقفت المهمة وأُفرج عن الصور','Tâche arrêtée, images libérées','작업 중지, 이미지 잠금 해제'),
    'Saved': ('已保存','保存済み','Guardada','محفوظة','Enregistrée','저장됨'),
    'Empty annotation': ('空标签','空のラベル','Anotación vacía','تسمية فارغة','Annotation vide','빈 레이블'),
    'Needs review': ('待复核','要確認','Por revisar','تحتاج للمراجعة','À vérifier','검토 필요'),
    'Skipped': ('已跳过','スキップ済み','Omitida','تم التخطي','Ignorée','건너뜀'),
    'Finish the running task before adding another batch.': ('请先完成或停止当前任务，再加入下一批。','現在のタスクを終了してから次を追加してください。','Termina la tarea actual antes de añadir otro lote.','أنه المهمة الحالية قبل إضافة دفعة أخرى.','Terminez la tâche en cours avant d’ajouter un lot.','다음 묶음을 추가하기 전에 현재 작업을 마치세요.'),
    'No unlabeled images to add.': ('没有可加入的未标注图片。','追加できる未ラベル画像がありません。','No hay imágenes sin etiquetar para añadir.','لا توجد صور غير معنونة لإضافتها.','Aucune image non annotée à ajouter.','추가할 미주석 이미지가 없습니다.'),
    'Stop the agent task before running the local model.': ('请先停止智能体任务，再运行本地模型。','ローカルモデルの実行前にエージェントのタスクを停止してください。','Detén la tarea del agente antes de ejecutar el modelo local.','أوقف مهمة الوكيل قبل تشغيل النموذج المحلي.','Arrêtez la tâche de l’agent avant d’exécuter le modèle local.','로컬 모델 실행 전에 에이전트 작업을 중지하세요.'),
    'Agent access (MCP)': ('允许智能体标注当前项目（MCP）','現在のプロジェクトへの MCP アクセス','Acceso del agente (MCP)','وصول الوكيل (MCP)','Accès de l’agent (MCP)','현재 프로젝트 에이전트 접근 (MCP)'),
    'Copy MCP configuration': ('复制 MCP 配置','MCP 設定をコピー','Copiar configuración MCP','نسخ إعدادات MCP','Copier la configuration MCP','MCP 설정 복사'),
    'MCP configuration copied': ('MCP 配置已复制','MCP 設定をコピーしました','Configuración MCP copiada','تم نسخ إعدادات MCP','Configuration MCP copiée','MCP 설정을 복사했습니다'),
    'Stop MCP': ('停止智能体','MCP を停止','Detener MCP','إيقاف MCP','Arrêter MCP','MCP 중지'),
    'Allow the connected agent to read images and save new labels in this project? Images may be sent to its model provider.': ('允许智能体读取此项目图片并自动保存新标签吗？图片可能被发送给智能体的模型服务商。','画像の読み取りと新規ラベルの保存を許可しますか？画像はモデル提供元に送信される場合があります。','¿Permitir leer imágenes y guardar etiquetas nuevas? Las imágenes pueden enviarse al proveedor del modelo.','هل تسمح بقراءة الصور وحفظ تسميات جديدة؟ قد تُرسل الصور إلى مزود النموذج.','Autoriser la lecture des images et la création d’annotations ? Les images peuvent être transmises au fournisseur du modèle.','이미지 읽기 및 새 레이블 저장을 허용할까요? 이미지가 모델 제공업체에 전송될 수 있습니다.'),
    'Select all boxes in group': ('全选本组框', 'グループの枠をすべて選択', 'Seleccionar todos los cuadros del grupo', 'تحديد كل إطارات المجموعة', 'Sélectionner tous les cadres du groupe', '그룹의 모든 상자 선택'),
    'Change group class…': ('批量修改类别…', 'グループのクラスを変更…', 'Cambiar la clase del grupo…', 'تغيير فئة المجموعة…', 'Changer la classe du groupe…', '그룹 클래스 변경…'),
    'Change box class': ('修改框类别', '枠のクラスを変更', 'Cambiar la clase del cuadro', 'تغيير فئة الإطار', 'Changer la classe du cadre', '상자 클래스 변경'),
    'Change class for %d boxes': ('修改 %d 个框的类别', '%d 個の枠のクラスを変更', 'Cambiar la clase de %d cuadros', 'تغيير فئة %d إطارات', 'Changer la classe de %d cadres', '상자 %d개의 클래스 변경'),
    'Type a class initial or use a class shortcut.': ('输入类别首字母、拼音或已设置的类别快捷键。', 'クラスの頭文字、拼音、またはショートカットを入力します。', 'Escribe la inicial, el pinyin o el atajo de la clase.', 'اكتب الحرف الأول أو البينيين أو استخدم اختصار الفئة.', 'Saisissez l’initiale, le pinyin ou le raccourci de la classe.', '클래스의 첫 글자, 병음 또는 단축키를 입력하세요.'),
    'Start': ('开始', '開始', 'Inicio', 'البدء', 'Démarrer', '시작'),
    'Open Image': ('打开图片', '画像を開く', 'Abrir imagen', 'فتح صورة', 'Ouvrir une image', '이미지 열기'),
    'Recent Work': ('最近工作', '最近の作業', 'Trabajo reciente', 'العمل الأخير', 'Travail récent', '최근 작업'),
    'Open a dataset to start annotating.': ('打开数据集开始标注。', 'データセットを開いてアノテーションを開始します。', 'Abre un conjunto de datos para empezar a anotar.', 'افتح مجموعة بيانات لبدء التعليق التوضيحي.', 'Ouvrez un jeu de données pour commencer à annoter.', '데이터셋을 열어 주석 작업을 시작하세요.'),
    'Recently opened folders and images will appear here.': ('最近打开的文件夹和图片会显示在这里。', '最近開いたフォルダーと画像がここに表示されます。', 'Aquí aparecerán las carpetas e imágenes abiertas recientemente.', 'ستظهر هنا المجلدات والصور المفتوحة مؤخرًا.', 'Les dossiers et images ouverts récemment apparaîtront ici.', '최근에 연 폴더와 이미지가 여기에 표시됩니다.'),
    'Choose a detected label folder or browse for another folder.': ('选择检测到的标签文件夹，或打开其他文件夹。', '見つかったラベルフォルダーを選ぶか、別のフォルダーを参照してください。', 'Elige una carpeta de etiquetas detectada o busca otra carpeta.', 'اختر مجلد تسميات تم العثور عليه أو تصفح لاختيار مجلد آخر.', 'Choisissez un dossier d’annotations détecté ou parcourez un autre dossier.', '찾은 라벨 폴더를 선택하거나 다른 폴더를 찾아보세요.'),
    'Choose Another Folder…': ('选择其他文件夹…', '別のフォルダーを選択…', 'Elegir otra carpeta…', 'اختيار مجلد آخر…', 'Choisir un autre dossier…', '다른 폴더 선택…'),
    'No supported images were found in this folder.': ('此文件夹内没有受支持的图片。', 'このフォルダーに対応する画像がありません。', 'No se encontraron imágenes compatibles en esta carpeta.', 'لم يتم العثور على صور مدعومة في هذا المجلد.', 'Ce dossier ne contient aucune image prise en charge.', '이 폴더에 지원되는 이미지가 없습니다.'),
    'Restart Software': ('重启软件', 'ソフトウェアを再起動', 'Reiniciar software', 'إعادة تشغيل البرنامج', 'Redémarrer le logiciel', '소프트웨어 다시 시작'),
    'Restart the application': ('重启当前软件，保留已保存的项目设置', '保存した設定でアプリを再起動', 'Reiniciar con los ajustes guardados', 'إعادة التشغيل بالإعدادات المحفوظة', 'Redémarrer avec les paramètres enregistrés', '저장된 설정으로 앱 다시 시작'),
    'Save changes before restarting?': ('重启前保存当前标注吗？', '再起動前に変更を保存しますか？', '¿Guardar antes de reiniciar?', 'هل تريد حفظ التغييرات قبل إعادة التشغيل؟', 'Enregistrer avant de redémarrer ?', '다시 시작하기 전에 저장할까요?'),
    'Stop model annotation before restarting.': ('请先中止模型标注，再重启软件。', '再起動前に自動アノテーションを停止してください。', 'Detenga la anotación automática antes de reiniciar.', 'أوقف التعليق التلقائي قبل إعادة التشغيل.', 'Arrêtez l’annotation automatique avant de redémarrer.', '다시 시작하기 전에 자동 주석을 중지하세요.'),
    'Unable to restart. Please reopen the application.': ('重启失败，请手动重新打开软件。', '再起動できません。手動で開き直してください。', 'No se pudo reiniciar. Abra la aplicación de nuevo.', 'تعذرت إعادة التشغيل. أعد فتح التطبيق يدويًا.', 'Échec du redémarrage. Rouvrez l’application.', '다시 시작하지 못했습니다. 앱을 다시 열어 주세요.'),
    'Check for Updates': ('检查更新', '更新を確認', 'Buscar actualizaciones', 'التحقق من التحديثات', 'Rechercher des mises à jour', '업데이트 확인'),
    'Update highlights': ('本次更新的主要内容', '主な変更点', 'Novedades principales', 'أبرز التغييرات', 'Principales nouveautés', '주요 변경 사항'),
    'No update highlights were provided.': ('此版本未提供更新摘要。', 'このバージョンの変更概要はありません。', 'No se ha publicado un resumen de los cambios.', 'لم يُنشر ملخص للتغييرات.', 'Aucun résumé des changements n’a été fourni.', '이 버전의 변경 요약이 없습니다.'),
    'Automatically check for updates': ('启动时自动检查更新', '起動時に更新を自動確認', 'Buscar actualizaciones al iniciar', 'التحقق تلقائيًا عند بدء التشغيل', 'Vérifier automatiquement au démarrage', '시작할 때 자동으로 업데이트 확인'),
    'Unable to check for updates. Try again later.': ('无法检查更新，请稍后重试。', '更新を確認できません。後で再試行してください。', 'No se pudo comprobar. Inténtelo más tarde.', 'تعذر التحقق. حاول لاحقًا.', 'Vérification impossible. Réessayez plus tard.', '업데이트를 확인할 수 없습니다. 나중에 다시 시도하세요.'),
    'You are using the latest version.': ('当前已是最新版本。', '最新バージョンです。', 'Tiene la última versión.', 'لديك أحدث إصدار.', 'Vous utilisez la dernière version.', '최신 버전입니다.'),
    'A new version is available:': ('发现新版本：', '新しいバージョン：', 'Nueva versión disponible:', 'يتوفر إصدار جديد:', 'Nouvelle version disponible :', '새 버전이 있습니다:'),
    'Download and install the update now? Your work will be saved before closing.': ('现在下载并安装更新吗？关闭前会按当前保存设置处理未保存的标注。', '今すぐ更新しますか？終了前に保存設定に従って変更を処理します。', '¿Descargar e instalar ahora? Se gestionarán los cambios sin guardar antes de cerrar.', 'هل تريد التنزيل والتثبيت الآن؟ ستتم معالجة التغييرات غير المحفوظة قبل الإغلاق.', 'Télécharger et installer maintenant ? Les modifications seront traitées avant la fermeture.', '지금 다운로드하고 설치할까요? 종료 전에 저장되지 않은 변경 사항을 처리합니다.'),
    'Downloading update...': ('正在下载更新…', '更新をダウンロード中…', 'Descargando actualización…', 'جارٍ تنزيل التحديث…', 'Téléchargement de la mise à jour…', '업데이트 다운로드 중…'),
    'Download or verification failed. Please try again.': ('下载或完整性校验失败，请重试。', 'ダウンロードまたは検証に失敗しました。', 'Error de descarga o verificación. Inténtelo de nuevo.', 'فشل التنزيل أو التحقق. حاول مجددًا.', 'Échec du téléchargement ou de la vérification. Réessayez.', '다운로드 또는 검증에 실패했습니다. 다시 시도하세요.'),
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
    'Label Shortcut Settings': ('标签快捷键设置', 'ラベルショートカット設定', 'Configuración de atajos de etiquetas', 'إعداد اختصارات الفئات', 'Paramètres des raccourcis d’étiquettes', '레이블 바로 가기 설정'),
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
    '使用本地 YOLO / YOLO OBB 模型批量标注未标注图片': ('Batch-label images without annotations using a local YOLO / YOLO OBB model', 'ローカルの YOLO / YOLO OBB モデルで未注釈の画像を一括ラベリング', 'Anotar por lotes las imágenes sin etiquetas con un modelo YOLO / YOLO OBB local', 'وضع تسميات على الصور غير الموسومة دفعة واحدة باستخدام نموذج YOLO / YOLO OBB محلي', 'Annoter par lots les images sans annotations avec un modèle YOLO / YOLO OBB local', '로컬 YOLO / YOLO OBB 모델로 주석이 없는 이미지를 일괄 라벨링'),
    '使用本地 YOLO / YOLO OBB 模型标注当前图片': ('Annotate the current image using a local YOLO / YOLO OBB model', 'ローカルの YOLO / YOLO OBB モデルで現在の画像にラベルを付ける', 'Anotar la imagen actual con un modelo YOLO / YOLO OBB local', 'وضع تسميات على الصورة الحالية باستخدام نموذج YOLO / YOLO OBB محلي', 'Annoter l’image actuelle avec un modèle YOLO / YOLO OBB local', '로컬 YOLO / YOLO OBB 모델로 현재 이미지 주석 달기'),
    '将 File List 中选中的图片及同名 XML/TXT 标签移入回收站': ('Move the selected image and matching XML/TXT labels from File List to the Recycle Bin', 'File List で選択した画像と同名の XML/TXT ラベルをごみ箱に移動', 'Mover la imagen seleccionada y sus etiquetas XML/TXT a la Papelera', 'نقل الصورة المحددة وتسميات XML/TXT المطابقة من File List إلى سلة المحذوفات', 'Déplacer l’image sélectionnée et ses annotations XML/TXT dans la corbeille', 'File List에서 선택한 이미지와 같은 이름의 XML/TXT 레이블을 휴지통으로 이동'),
    '按当前 Annotation Format 为当前图片生成空标签': ('Create an empty annotation for the current image in the selected Annotation Format', '現在の Annotation Format で空のラベルを作成', 'Crear una anotación vacía para la imagen actual en el formato seleccionado', 'إنشاء تسمية فارغة للصورة الحالية بالتنسيق المحدد', 'Créer une annotation vide pour l’image actuelle au format sélectionné', '현재 이미지에 선택한 Annotation Format으로 빈 레이블 만들기'),
    '选择本地 YOLO / YOLO OBB .pt 模型': ('Choose a local YOLO / YOLO OBB .pt model', 'ローカルの YOLO / YOLO OBB .pt モデルを選択', 'Elegir un modelo YOLO / YOLO OBB .pt local', 'اختيار نموذج YOLO / YOLO OBB .pt محلي', 'Choisir un modèle YOLO / YOLO OBB .pt local', '로컬 YOLO / YOLO OBB .pt 모델 선택'),
    '模型置信度阈值（0.01–1.00）；数值越高，保留的预测框通常越少。': ('Model confidence threshold (0.01–1.00). Higher values usually keep fewer predicted boxes.', 'モデルの信頼度しきい値（0.01–1.00）。値を上げると、通常、残る予測ボックスは少なくなります。', 'Umbral de confianza del modelo (0.01–1.00). Un valor más alto suele conservar menos cuadros detectados.', 'حدّ ثقة النموذج (0.01–1.00). عادةً ما تؤدي القيمة الأعلى إلى الاحتفاظ بعدد أقل من الصناديق المتوقعة.', 'Seuil de confiance du modèle (0.01–1.00). Une valeur plus élevée conserve généralement moins de boîtes prédites.', '모델 신뢰도 임계값(0.01–1.00). 값이 높을수록 일반적으로 유지되는 예측 상자가 줄어듭니다.'),
    '置信度 ': ('Confidence ', '信頼度 ', 'Confianza ', 'الثقة ', 'Confiance ', '신뢰도 '),
    '置信度：': ('Confidence: ', '信頼度：', 'Confianza: ', 'الثقة: ', 'Confiance : ', '신뢰도: '),
    '自动标注置信度已设为 %.2f。': ('Auto-annotation confidence set to %.2f.', '自動ラベリングの信頼度を %.2f に設定しました。', 'La confianza del etiquetado automático se estableció en %.2f.', 'تم ضبط ثقة الوسم الآلي على %.2f.', 'La confiance du pré-étiquetage automatique est réglée sur %.2f.', '자동 주석 신뢰도를 %.2f로 설정했습니다.'),
    '加载模型…（当前图片，置信度 %.2f）': ('Loading model… (current image, confidence %.2f)', 'モデルを読み込み中…（現在の画像、信頼度 %.2f）', 'Cargando modelo… (imagen actual, confianza %.2f)', 'جارٍ تحميل النموذج… (الصورة الحالية، الثقة %.2f)', 'Chargement du modèle… (image actuelle, confiance %.2f)', '모델 로드 중… (현재 이미지, 신뢰도 %.2f)'),
    '加载模型…（待标注 %d 张，置信度 %.2f）': ('Loading model… (%d images to annotate, confidence %.2f)', 'モデルを読み込み中…（注釈対象 %d 枚、信頼度 %.2f）', 'Cargando modelo… (%d imágenes por anotar, confianza %.2f)', 'جارٍ تحميل النموذج… (%d صور متبقية للتوسيم، الثقة %.2f)', 'Chargement du modèle… (%d images à annoter, confiance %.2f)', '모델 로드 중… (주석 대상 이미지 %d장, 신뢰도 %.2f)'),
    '模型已加载：%s（置信度 %.2f）': ('Model loaded: %s (confidence %.2f)', 'モデルを読み込みました：%s（信頼度 %.2f）', 'Modelo cargado: %s (confianza %.2f)', 'تم تحميل النموذج: %s (الثقة %.2f)', 'Modèle chargé : %s (confiance %.2f)', '모델 로드됨: %s (신뢰도 %.2f)'),
    '%s\n置信度：%.2f': ('%s\nConfidence: %.2f', '%s\n信頼度：%.2f', '%s\nConfianza: %.2f', '%s\nالثقة: %.2f', '%s\nConfiance : %.2f', '%s\n신뢰도: %.2f'),
    '置信度：%.2f\n%s': ('Confidence: %.2f\n%s', '信頼度：%.2f\n%s', 'Confianza: %.2f\n%s', 'الثقة: %.2f\n%s', 'Confiance : %.2f\n%s', '신뢰도: %.2f\n%s'),
    '置信度：%.2f': ('Confidence: %.2f', '信頼度：%.2f', 'Confianza: %.2f', 'الثقة: %.2f', 'Confiance : %.2f', '신뢰도: %.2f'),
    '选择按 E 绘制的框类型；旁边的画框按钮仍可直接使用。': ('Choose the box type drawn by pressing E. The adjacent draw buttons remain available.', 'E キーで描画する枠の種類を選択します。隣の描画ボタンも引き続き使用できます。', 'Elige el tipo de cuadro que se dibuja al pulsar E. Los botones de dibujo contiguos siguen disponibles.', 'اختر نوع الإطار الذي يرسمه المفتاح E. تظل أزرار الرسم المجاورة متاحة.', 'Choisissez le type de boîte dessiné avec E. Les boutons de dessin voisins restent disponibles.', 'E 키로 그릴 상자 유형을 선택합니다. 옆의 그리기 버튼도 계속 사용할 수 있습니다.'),
}
for _source, _items in _EXTRA_ZH.items():
    _LOOKUP[_source] = dict(zip(
        ('en', 'ja', 'es', 'ar', 'fr', 'ko'), _items))
    _LOOKUP[_source]['zh'] = _source

_EXTRA_EN = {
    'Background': ('背景', '背景', 'Fondo', 'الخلفية', 'Arrière-plan', '배경'),
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
    'Configure shortcut keys for preset labels': ('设置预设类别快捷键', 'プリセットラベルのショートカットを設定', 'Configurar atajos para clases predefinidas', 'إعداد اختصارات الفئات المحددة مسبقًا', 'Configurer les raccourcis des classes prédéfinies', '프리셋 클래스 바로 가기 설정'),
    'Copy selected Box': ('复制选中的框', '選択した枠をコピー', 'Copiar el cuadro seleccionado', 'نسخ الإطار المحدد', 'Copier la boîte sélectionnée', '선택한 상자 복사'),
    'Cut selected Box': ('剪切选中的框', '選択した枠を切り取り', 'Cortar el cuadro seleccionado', 'قص الإطار المحدد', 'Couper la boîte sélectionnée', '선택한 상자 잘라내기'),
    'Decrease zoom level': ('缩小图像', '画像を縮小', 'Reducir el zoom', 'تصغير الصورة', 'Diminuer le zoom', '확대율 낮추기'),
    'Draw a new Box': ('绘制新框', '新しい枠を描画', 'Dibujar un cuadro nuevo', 'رسم إطار جديد', 'Dessiner une nouvelle boîte', '새 상자 그리기'),
    'Draw a new RotatedRBox': ('绘制新的旋转框（OBB）', '新しい回転枠（OBB）を描画', 'Dibujar un nuevo cuadro girado (OBB)', 'رسم إطار مائل جديد (OBB)', 'Dessiner une nouvelle boîte orientée (OBB)', '새 회전 상자(OBB) 그리기'),
    'Increase zoom level': ('放大图像', '画像を拡大', 'Aumentar el zoom', 'تكبير الصورة', 'Augmenter le zoom', '확대율 높이기'),
    'Modify the label of the selected Box': ('修改所选框的类别', '選択した枠のラベルを変更', 'Cambiar la etiqueta del cuadro seleccionado', 'تعديل تسمية الإطار المحدد', 'Modifier l’étiquette de la boîte sélectionnée', '선택한 상자의 레이블 수정'),
    'Paste copied Box': ('粘贴已复制的框', 'コピーした枠を貼り付け', 'Pegar el cuadro copiado', 'لصق الإطار المنسوخ', 'Coller la boîte copiée', '복사한 상자 붙여넣기'),
    'Reset all': ('重置所有设置', 'すべてリセット', 'Restablecer todo', 'إعادة تعيين الكل', 'Tout réinitialiser', '모두 초기화'),
    'Undo the last box operation': ('撤销上一步框操作', '直前の枠操作を元に戻す', 'Deshacer la última operación del cuadro', 'التراجع عن عملية الإطار الأخيرة', 'Annuler la dernière opération sur la boîte', '마지막 상자 작업 실행 취소'),
    'Zoom follows window size': ('缩放以适应窗口', 'ウィンドウサイズに合わせて拡大縮小', 'Ajustar el zoom al tamaño de la ventana', 'تكييف التكبير مع حجم النافذة', 'Adapter le zoom à la taille de la fenêtre', '창 크기에 맞게 확대/축소'),
    'Zoom follows window width': ('缩放以适应窗口宽度', 'ウィンドウ幅に合わせて拡大縮小', 'Ajustar el zoom al ancho de la ventana', 'تكييف التكبير مع عرض النافذة', 'Adapter le zoom à la largeur de la fenêtre', '창 너비에 맞게 확대/축소'),
    'Zoom to original size': ('恢复原始大小', '元のサイズに戻す', 'Restablecer el tamaño original', 'العودة إلى الحجم الأصلي', 'Rétablir la taille d’origine', '원래 크기로 확대/축소'),
    'auto next': ('自动切换到下一张', '次の画像へ自動で切り替え', 'Avanzar automáticamente a la siguiente imagen', 'الانتقال تلقائيًا إلى الصورة التالية', 'Passer automatiquement à l’image suivante', '자동으로 다음 이미지로 이동'),
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
            if isinstance(widget, QDoubleSpinBox):
                self._update(widget, widget.prefix, widget.setPrefix,
                             'prefix')
                if widget.objectName() == 'autoAnnotationConfidenceSpinBox':
                    widget.setMinimumWidth(widget.sizeHint().width() + 8)
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
            if isinstance(widget, QTableView) or (isinstance(widget, QTreeView) and widget.objectName() == 'boxLabelTree'):
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
