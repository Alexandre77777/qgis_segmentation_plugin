# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import QgsProject, QgsRasterLayer, QgsPalettedRasterRenderer
from qgis.PyQt.QtGui import QColor

from .resources import *
from .SegmentationPlugin_dialog import SegmentationPluginDialog
from .utils.worker import SegmentationWorker
from .utils.image_utils import ImageProcessor

import os
import json
import tempfile


class SegmentationPlugin:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor."""
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'SegmentationPlugin_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        self.actions = []
        self.menu = self.tr(u'&Segmentation Plugin')
        self.first_start = None
        self.worker = None

    def tr(self, message):
        return QCoreApplication.translate('SegmentationPlugin', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        icon_path = ':/plugins/SegmentationPlugin/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Segmentation Plugin'),
            callback=self.run,
            parent=self.iface.mainWindow())

        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Segmentation Plugin'),
                action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        """Run method that performs all the real work"""
        if self.first_start == True:
            self.first_start = False
            self.dlg = SegmentationPluginDialog()

        self.dlg.show()
        result = self.dlg.exec_()
        
        if result:
            try:
                # Сохранение настроек
                self.dlg.save_settings()
                
                # Получение параметров
                layer = self.dlg.mMapLayerComboBox.currentLayer()
                if not layer:
                    QMessageBox.warning(self.dlg, "Предупреждение", "Выберите растровый слой")
                    return
                
                # Подготовка параметров
                params = self.prepare_parameters()
                if params is None:
                    return  # Ошибка уже показана в prepare_parameters
                
                # Запуск обработки в отдельном потоке
                self.worker = SegmentationWorker(params, self.plugin_dir)
                self.worker.progress.connect(self.update_progress)
                self.worker.result_ready.connect(self.add_result_layer)
                self.worker.error.connect(self.handle_error)
                self.worker.finished.connect(self.processing_finished)
                
                self.worker.start()
                
            except Exception as e:
                QMessageBox.critical(
                    self.dlg,
                    "Ошибка",
                    f"Ошибка при запуске обработки: {str(e)}"
                )
    
    def prepare_parameters(self):
        """Подготовка параметров для обработки"""
        try:
            layer = self.dlg.mMapLayerComboBox.currentLayer()
            use_extent = self.dlg.checkBox_use_extent.isChecked()
            
            # Создаем процессор изображений
            from .config import SEGMENTATION_COLORS
            image_processor = ImageProcessor(SEGMENTATION_COLORS)
            
            # Сохраняем слой во временный файл
            temp_input = tempfile.NamedTemporaryFile(suffix='.tif', delete=False)
            temp_input.close()
            
            # Экспортируем слой
            success = False
            if use_extent:
                extent = self.iface.mapCanvas().extent()
                # Пробуем сначала альтернативный метод через GDAL
                if hasattr(image_processor, 'export_qgis_layer_simple'):
                    success = image_processor.export_qgis_layer_simple(layer, temp_input.name, extent)
                
                # Если не получилось, используем основной метод
                if not success:
                    success = image_processor.export_qgis_layer(layer, temp_input.name, extent)
            else:
                extent = layer.extent()
                # Пробуем сначала альтернативный метод через GDAL
                if hasattr(image_processor, 'export_qgis_layer_simple'):
                    success = image_processor.export_qgis_layer_simple(layer, temp_input.name)
                
                # Если не получилось, используем основной метод
                if not success:
                    success = image_processor.export_qgis_layer(layer, temp_input.name)
            
            if not success or not os.path.exists(temp_input.name):
                # Удаляем временный файл если он создан
                try:
                    os.unlink(temp_input.name)
                except:
                    pass
                
                QMessageBox.critical(
                    self.dlg, 
                    "Ошибка", 
                    "Не удалось экспортировать растровый слой. Убедитесь, что слой корректный и доступен для чтения."
                )
                return None
            
            # Определение пути к модели
            model_path = None
            if self.dlg.comboBox_model.currentText() == "Загрузить свою модель...":
                model_path = self.dlg.fileWidget_model.filePath()
                if not model_path or not os.path.exists(model_path):
                    QMessageBox.critical(
                        self.dlg,
                        "Ошибка",
                        "Выберите файл модели"
                    )
                    return None
            elif self.dlg.comboBox_model.currentIndex() > 1:
                model_name = self.dlg.comboBox_model.currentText()
                model_path = os.path.join(self.plugin_dir, 'models', model_name)
            else:
                # Используем модель по умолчанию
                model_path = os.path.join(self.plugin_dir, 'models', 'best_model.h5')
            
            # Проверяем существование модели
            if model_path and not os.path.exists(model_path):
                QMessageBox.critical(
                    self.dlg,
                    "Ошибка",
                    f"Файл модели не найден: {model_path}"
                )
                return None
            
            # Создание временного файла для результата
            temp_output = tempfile.NamedTemporaryFile(suffix='_segmentation.tif', delete=False)
            temp_output.close()
            
            # Создаем словарь с JSON-сериализуемыми параметрами
            params = {
                'input_path': temp_input.name,
                'output_path': temp_output.name,
                'use_api': self.dlg.radioButton_api.isChecked(),
                'api_url': self.dlg.lineEdit_api_url.text(),
                'model_path': model_path,
                'patch_size': self.dlg.spinBox_patch_size.value(),
                'subdivisions': self.dlg.spinBox_subdivisions.value(),
                'crs': layer.crs().toWkt(),
                # Передаем геоданные для использования в subprocess
                'georeference_data': {
                    'extent_xmin': extent.xMinimum(),
                    'extent_xmax': extent.xMaximum(),
                    'extent_ymin': extent.yMinimum(),
                    'extent_ymax': extent.yMaximum(),
                    'crs': layer.crs().toWkt()
                }
            }
            
            # Сохраняем ссылки для использования после инференса
            self.reference_layer = layer
            self.reference_extent = extent
            
            return params
            
        except Exception as e:
            QMessageBox.critical(
                self.dlg,
                "Ошибка",
                f"Ошибка при подготовке параметров: {str(e)}"
            )
            return None
    
    def update_progress(self, value):
        """Обновление прогресс-бара"""
        self.dlg.progressBar.setValue(value)
    
    def add_result_layer(self, metadata_path):
        """Добавление результата как нового слоя"""
        try:
            # Читаем метаданные
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            # Путь к результату
            output_path = metadata['output_path']
            
            if not os.path.exists(output_path):
                raise Exception(f"Файл результата не найден: {output_path}")
            
            # Загружаем результат как слой
            layer_name = "Segmentation Result"
            result_layer = QgsRasterLayer(output_path, layer_name)
            
            if result_layer.isValid():
                QgsProject.instance().addMapLayer(result_layer)
                
                # Применяем палитровый рендерер для одноканального изображения
                if result_layer.bandCount() == 1:
                    # Создаем палитру классов
                    classes = []
                    colors = metadata.get('classes', [])
                    
                    # Если нет цветов в метаданных, используем из конфига
                    if not colors:
                        from .config import SEGMENTATION_COLORS, CLASS_NAMES
                        colors = SEGMENTATION_COLORS
                    else:
                        from .config import CLASS_NAMES
                    
                    for i, color in enumerate(colors):
                        class_name = CLASS_NAMES[i] if i < len(CLASS_NAMES) else f"Class {i}"
                        paletteClass = QgsPalettedRasterRenderer.Class(
                            i,
                            QColor(color[0], color[1], color[2]),
                            class_name
                        )
                        classes.append(paletteClass)
                    
                    # Применяем рендерер
                    renderer = QgsPalettedRasterRenderer(
                        result_layer.dataProvider(),
                        1,
                        classes
                    )
                    result_layer.setRenderer(renderer)
                
                result_layer.triggerRepaint()
                
                self.iface.messageBar().pushSuccess(
                    "Segmentation Plugin",
                    "Сегментация выполнена успешно!"
                )
                
                # Очистка временных файлов
                self.cleanup_temp_files(metadata_path)
                
            else:
                raise Exception("Не удалось загрузить результирующий слой")
                
        except Exception as e:
            QMessageBox.critical(
                self.dlg,
                "Ошибка",
                f"Не удалось загрузить результат: {str(e)}"
            )
    
    def handle_error(self, error_message):
        """Обработка ошибок"""
        QMessageBox.critical(
            self.dlg,
            "Ошибка сегментации",
            f"Произошла ошибка: {error_message}"
        )
        self.dlg.progressBar.setValue(0)
    
    def processing_finished(self):
        """Завершение обработки"""
        self.dlg.progressBar.setValue(0)
        self.worker = None
    
    def cleanup_temp_files(self, metadata_path):
        """Очистка временных файлов"""
        try:
            # Удаляем файл метаданных
            if os.path.exists(metadata_path):
                os.unlink(metadata_path)
            
            # Удаляем входной временный файл если есть параметры
            if hasattr(self, 'worker') and self.worker and hasattr(self.worker, 'params'):
                input_path = self.worker.params.get('input_path')
                if input_path and os.path.exists(input_path):
                    try:
                        os.unlink(input_path)
                    except:
                        pass
        except Exception as e:
            # Не критичная ошибка, просто логируем
            print(f"Ошибка при очистке временных файлов: {str(e)}")
