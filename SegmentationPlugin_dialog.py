import os
from qgis.PyQt import QtWidgets, QtCore
from qgis.PyQt.QtCore import QSettings
from qgis.gui import QgsMapLayerComboBox, QgsFileWidget
from qgis.core import QgsMapLayerProxyModel


class SegmentationPluginDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        """Constructor."""
        super(SegmentationPluginDialog, self).__init__(parent)
        
        # Настройки
        self.settings = QSettings('SegmentationPlugin', 'SegmentationPlugin')
        
        # Создание UI
        self.setupUi()
        
        # Инициализация UI
        self.init_ui()
        
        # Загрузка сохраненных настроек
        self.load_settings()
        
        # Подключение сигналов
        self.connect_signals()
    
    def setupUi(self):
        """Создание интерфейса программно"""
        self.setObjectName("SegmentationPluginDialog")
        self.resize(600, 500)
        self.setWindowTitle("Segmentation Plugin")
        
        # Главный layout
        self.verticalLayout = QtWidgets.QVBoxLayout(self)
        
        # Группа входных данных
        self.groupBox_input = QtWidgets.QGroupBox("Входные данные")
        self.gridLayout_input = QtWidgets.QGridLayout(self.groupBox_input)
        
        # Выбор растрового слоя
        self.label_raster = QtWidgets.QLabel("Растровый слой:")
        self.gridLayout_input.addWidget(self.label_raster, 0, 0)
        
        self.mMapLayerComboBox = QgsMapLayerComboBox()
        self.mMapLayerComboBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.gridLayout_input.addWidget(self.mMapLayerComboBox, 0, 1)
        
        # Чекбокс для использования текущего экстента
        self.checkBox_use_extent = QtWidgets.QCheckBox("Использовать текущий экстент")
        self.gridLayout_input.addWidget(self.checkBox_use_extent, 1, 0, 1, 2)
        
        self.verticalLayout.addWidget(self.groupBox_input)
        
        # Группа настроек модели
        self.groupBox_model = QtWidgets.QGroupBox("Настройки модели")
        self.gridLayout_model = QtWidgets.QGridLayout(self.groupBox_model)
        
        # Выбор модели
        self.label_model = QtWidgets.QLabel("Модель:")
        self.gridLayout_model.addWidget(self.label_model, 0, 0)
        
        self.comboBox_model = QtWidgets.QComboBox()
        self.gridLayout_model.addWidget(self.comboBox_model, 0, 1)
        
        # Путь к пользовательской модели
        self.label_custom_model = QtWidgets.QLabel("Путь к модели:")
        self.gridLayout_model.addWidget(self.label_custom_model, 1, 0)
        
        self.fileWidget_model = QgsFileWidget()
        self.fileWidget_model.setStorageMode(QgsFileWidget.GetFile)
        self.fileWidget_model.setFilter("Model Files (*.h5 *.keras *.tflite)")
        self.fileWidget_model.setEnabled(False)
        self.gridLayout_model.addWidget(self.fileWidget_model, 1, 1)
        
        self.verticalLayout.addWidget(self.groupBox_model)
        
        # Группа настроек инференса
        self.groupBox_inference = QtWidgets.QGroupBox("Настройки инференса")
        self.gridLayout_inference = QtWidgets.QGridLayout(self.groupBox_inference)
        
        # Радиокнопки для выбора типа инференса
        self.radioButton_local = QtWidgets.QRadioButton("Локальный инференс")
        self.radioButton_local.setChecked(True)
        self.gridLayout_inference.addWidget(self.radioButton_local, 0, 0)
        
        self.radioButton_api = QtWidgets.QRadioButton("API инференс")
        self.gridLayout_inference.addWidget(self.radioButton_api, 0, 1)
        
        # API URL
        self.label_api_url = QtWidgets.QLabel("API URL:")
        self.gridLayout_inference.addWidget(self.label_api_url, 1, 0)
        
        self.lineEdit_api_url = QtWidgets.QLineEdit()
        self.lineEdit_api_url.setText("http://localhost:8080")
        self.lineEdit_api_url.setEnabled(False)
        self.gridLayout_inference.addWidget(self.lineEdit_api_url, 1, 1)
        
        self.verticalLayout.addWidget(self.groupBox_inference)
        
        # Группа параметров обработки
        self.groupBox_params = QtWidgets.QGroupBox("Параметры обработки")
        self.gridLayout_params = QtWidgets.QGridLayout(self.groupBox_params)
        
        # Размер патча
        self.label_patch_size = QtWidgets.QLabel("Размер патча:")
        self.gridLayout_params.addWidget(self.label_patch_size, 0, 0)
        
        self.spinBox_patch_size = QtWidgets.QSpinBox()
        self.spinBox_patch_size.setMinimum(128)
        self.spinBox_patch_size.setMaximum(512)
        self.spinBox_patch_size.setSingleStep(64)
        self.spinBox_patch_size.setValue(256)
        self.gridLayout_params.addWidget(self.spinBox_patch_size, 0, 1)
        
        # Подразделения
        self.label_subdivisions = QtWidgets.QLabel("Подразделения:")
        self.gridLayout_params.addWidget(self.label_subdivisions, 1, 0)
        
        self.spinBox_subdivisions = QtWidgets.QSpinBox()
        self.spinBox_subdivisions.setMinimum(1)
        self.spinBox_subdivisions.setMaximum(4)
        self.spinBox_subdivisions.setValue(2)
        self.gridLayout_params.addWidget(self.spinBox_subdivisions, 1, 1)
        
        self.verticalLayout.addWidget(self.groupBox_params)
        
        # Прогресс-бар
        self.progressBar = QtWidgets.QProgressBar()
        self.progressBar.setValue(0)
        self.verticalLayout.addWidget(self.progressBar)
        
        # Кнопки
        self.button_box = QtWidgets.QDialogButtonBox()
        self.button_box.setOrientation(QtCore.Qt.Horizontal)
        self.button_box.setStandardButtons(
            QtWidgets.QDialogButtonBox.Cancel | QtWidgets.QDialogButtonBox.Ok
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.verticalLayout.addWidget(self.button_box)
    
    def init_ui(self):
        """Инициализация интерфейса"""
        # Заполнение списка моделей
        self.populate_models()
        
        # Отключение API URL по умолчанию
        self.lineEdit_api_url.setEnabled(False)
    
    def populate_models(self):
        """Заполнение списка доступных моделей"""
        self.comboBox_model.clear()
        self.comboBox_model.addItem("Выберите модель...")
        self.comboBox_model.addItem("best_model.h5 (по умолчанию)")
        
        # Добавление моделей из папки models
        models_dir = os.path.join(os.path.dirname(__file__), 'models')
        if os.path.exists(models_dir):
            for file in os.listdir(models_dir):
                if file.endswith(('.h5', '.keras', '.tflite')):
                    self.comboBox_model.addItem(file)
        
        self.comboBox_model.addItem("Загрузить свою модель...")
    
    def connect_signals(self):
        """Подключение сигналов"""
        self.radioButton_api.toggled.connect(self.on_inference_type_changed)
        self.radioButton_local.toggled.connect(self.on_inference_type_changed)
        self.comboBox_model.currentIndexChanged.connect(self.on_model_selection_changed)
    
    def on_inference_type_changed(self):
        """Обработка изменения типа инференса"""
        is_api = self.radioButton_api.isChecked()
        self.lineEdit_api_url.setEnabled(is_api)
        self.groupBox_model.setEnabled(not is_api)
    
    def on_model_selection_changed(self, index):
        """Обработка выбора модели"""
        if self.comboBox_model.currentText() == "Загрузить свою модель...":
            self.fileWidget_model.setEnabled(True)
        else:
            self.fileWidget_model.setEnabled(False)
            self.fileWidget_model.setFilePath("")
    
    def save_settings(self):
        """Сохранение настроек"""
        self.settings.setValue('api_url', self.lineEdit_api_url.text())
        self.settings.setValue('patch_size', self.spinBox_patch_size.value())
        self.settings.setValue('subdivisions', self.spinBox_subdivisions.value())
        self.settings.setValue('use_api', self.radioButton_api.isChecked())
    
    def load_settings(self):
        """Загрузка сохраненных настроек"""
        api_url = self.settings.value('api_url', 'http://localhost:8080')
        patch_size = int(self.settings.value('patch_size', 256))
        subdivisions = int(self.settings.value('subdivisions', 2))
        use_api = self.settings.value('use_api', False, type=bool)
        
        self.lineEdit_api_url.setText(api_url)
        self.spinBox_patch_size.setValue(patch_size)
        self.spinBox_subdivisions.setValue(subdivisions)
        
        if use_api:
            self.radioButton_api.setChecked(True)
        else:
            self.radioButton_local.setChecked(True)
