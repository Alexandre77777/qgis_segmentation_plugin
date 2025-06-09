"""
Утилиты для работы с изображениями и QGIS слоями
"""
import numpy as np
from PIL import Image
from qgis.core import (
    QgsRasterLayer, QgsRasterFileWriter, QgsRasterPipe,
    QgsRectangle, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsProject
)
import os


class ImageProcessor:
    """Класс для всех операций с изображениями"""
    
    def __init__(self, segmentation_colors):
        self.colors = np.array(segmentation_colors, dtype=np.uint8)
    
    def label_to_rgb(self, mask):
        """Преобразует маску классов в RGB"""
        return self.colors[mask]
    
    def rgb_to_label(self, rgb_image):
        """Преобразует RGB в маску классов"""
        rgb_array = np.array(rgb_image)
        mask = np.zeros(rgb_array.shape[:2], dtype=np.uint8)
        
        for i, color in enumerate(self.colors):
            color_mask = np.all(rgb_array == color, axis=2)
            mask[color_mask] = i
        
        return mask
    
    @staticmethod
    def export_qgis_layer(layer, output_path, extent=None):
        """Экспортирует QGIS слой в файл"""
        if not isinstance(layer, QgsRasterLayer):
            raise ValueError("Layer must be a QgsRasterLayer")
        
        provider = layer.dataProvider()
        
        # Создаем pipe
        pipe = QgsRasterPipe()
        if not pipe.set(provider.clone()):
            return False
        
        # Настройки файла
        file_writer = QgsRasterFileWriter(output_path)
        file_writer.setOutputFormat("GTiff")
        
        # Определяем размеры и экстент
        if extent is None:
            extent = provider.extent()
            x_size = provider.xSize()
            y_size = provider.ySize()
        else:
            # Вычисляем размеры для заданного экстента
            pixel_size_x = layer.rasterUnitsPerPixelX()
            pixel_size_y = layer.rasterUnitsPerPixelY()
            x_size = int((extent.xMaximum() - extent.xMinimum()) / pixel_size_x)
            y_size = int((extent.yMaximum() - extent.yMinimum()) / pixel_size_y)
        
        # Используем writeRaster без feedback параметра
        error = file_writer.writeRaster(
            pipe,
            x_size,
            y_size,
            extent,
            layer.crs()
        )
        
        return error == QgsRasterFileWriter.NoError
    
    @staticmethod
    def export_qgis_layer_simple(layer, output_path, extent=None):
        """Альтернативный метод экспорта через GDAL"""
        try:
            from osgeo import gdal, osr
            
            # Открываем исходный растр
            source_ds = gdal.Open(layer.source())
            if source_ds is None:
                return False
            
            # Получаем геотрансформацию
            geotransform = source_ds.GetGeoTransform()
            projection = source_ds.GetProjection()
            
            # Если задан extent, вычисляем окно
            if extent is not None:
                # Вычисляем пиксельные координаты extent
                inv_geotransform = gdal.InvGeoTransform(geotransform)
                x1, y1 = gdal.ApplyGeoTransform(inv_geotransform, extent.xMinimum(), extent.yMaximum())
                x2, y2 = gdal.ApplyGeoTransform(inv_geotransform, extent.xMaximum(), extent.yMinimum())
                
                # Округляем и ограничиваем координатами изображения
                x_off = int(max(0, x1))
                y_off = int(max(0, y1))
                x_size = int(min(source_ds.RasterXSize - x_off, x2 - x1))
                y_size = int(min(source_ds.RasterYSize - y_off, y2 - y1))
                
                # Создаем новую геотрансформацию для вырезанной области
                new_geotransform = list(geotransform)
                new_geotransform[0] = geotransform[0] + x_off * geotransform[1] + y_off * geotransform[2]
                new_geotransform[3] = geotransform[3] + x_off * geotransform[4] + y_off * geotransform[5]
            else:
                x_off = 0
                y_off = 0
                x_size = source_ds.RasterXSize
                y_size = source_ds.RasterYSize
                new_geotransform = geotransform
            
            # Создаем выходной файл
            driver = gdal.GetDriverByName('GTiff')
            out_ds = driver.Create(output_path, x_size, y_size, source_ds.RasterCount, source_ds.GetRasterBand(1).DataType)
            
            # Устанавливаем геотрансформацию и проекцию
            out_ds.SetGeoTransform(new_geotransform)
            out_ds.SetProjection(projection)
            
            # Копируем данные по бандам
            for i in range(1, source_ds.RasterCount + 1):
                in_band = source_ds.GetRasterBand(i)
                out_band = out_ds.GetRasterBand(i)
                
                # Читаем и записываем данные
                data = in_band.ReadAsArray(x_off, y_off, x_size, y_size)
                out_band.WriteArray(data)
                
                # Копируем статистику и цветовую таблицу если есть
                if in_band.GetColorTable():
                    out_band.SetColorTable(in_band.GetColorTable())
                
                out_band.FlushCache()
            
            # Закрываем датасеты
            out_ds = None
            source_ds = None
            
            return True
            
        except Exception as e:
            print(f"Error in export_qgis_layer_simple: {str(e)}")
            # Если GDAL недоступен, используем основной метод
            return False
    
    @staticmethod
    def create_georeferenced_tiff_simple(mask_path, output_path, reference_layer, extent):
        """Создает георефенцированный TIFF используя World File"""
        # Читаем маску
        mask_img = Image.open(mask_path)
        mask_array = np.array(mask_img)
        
        height, width = mask_array.shape[:2] if len(mask_array.shape) >= 2 else (mask_array.shape[0], 1)
        
        # Сохраняем как TIFF
        mask_img.save(output_path, 'TIFF')
        
        # Создаем World File для геопривязки
        tfw_path = output_path.replace('.tif', '.tfw')
        pixel_width = (extent.xMaximum() - extent.xMinimum()) / width
        pixel_height = (extent.yMaximum() - extent.yMinimum()) / height
        
        with open(tfw_path, 'w') as f:
            f.write(f"{pixel_width}\n")
            f.write("0.0\n")
            f.write("0.0\n")
            f.write(f"{-pixel_height}\n")
            f.write(f"{extent.xMinimum() + pixel_width/2}\n")
            f.write(f"{extent.yMaximum() - pixel_height/2}\n")
        
        # Создаем PRJ файл с проекцией
        prj_path = output_path.replace('.tif', '.prj')
        with open(prj_path, 'w') as f:
            f.write(reference_layer.crs().toWkt())
        
        return True
    
    @staticmethod
    def extract_selected_extent(layer, canvas):
        """Извлекает выбранную область растра"""
        canvas_extent = canvas.extent()
        canvas_crs = canvas.mapSettings().destinationCrs()
        
        if canvas_crs != layer.crs():
            transform = QgsCoordinateTransform(
                canvas_crs,
                layer.crs(),
                QgsProject.instance()
            )
            layer_extent = transform.transformBoundingBox(canvas_extent)
        else:
            layer_extent = canvas_extent
        
        layer_full_extent = layer.extent()
        intersection = layer_extent.intersect(layer_full_extent)
        
        return intersection
