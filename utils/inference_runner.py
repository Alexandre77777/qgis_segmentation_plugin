"""
Единый модуль для выполнения инференса (локального и API)
"""
import sys
import json
import os
import numpy as np
from PIL import Image
import requests
import io


class InferenceRunner:
    def __init__(self, params):
        self.params = params
        self.plugin_dir = os.environ.get('PLUGIN_DIR', os.path.dirname(os.path.dirname(__file__)))
        
    def run(self):
        if self.params.get('use_api'):
            return self.run_api()
        else:
            return self.run_local()
    
    def run_api(self):
        """API инференс"""
        print("PROGRESS:20", flush=True)
        
        # Читаем изображение
        img = Image.open(self.params['input_path'])
        img_bytes_io = io.BytesIO()
        img.save(img_bytes_io, format='PNG')
        img_bytes = img_bytes_io.getvalue()
        
        print("PROGRESS:40", flush=True)
        
        # API запрос
        files = {"file": ("image.png", img_bytes, "image/png")}
        api_params = {
            "patch_size": self.params['patch_size'],
            "subdivisions": self.params['subdivisions']
        }
        
        response = requests.post(
            f"{self.params['api_url']}/predict/",
            files=files,
            params=api_params,
            timeout=300
        )
        response.raise_for_status()
        
        print("PROGRESS:70", flush=True)
        
        # Обработка результата
        result_image = Image.open(io.BytesIO(response.content))
        return self._save_results(result_image)
    
    def run_local(self):
        """Локальный инференс"""
        print("PROGRESS:20", flush=True)
        
        # Добавляем путь к плагину
        if self.plugin_dir not in sys.path:
            sys.path.insert(0, self.plugin_dir)
        
        # Импорты
        from config import DEFAULT_NUM_CLASSES, SEGMENTATION_COLORS
        from utils.model_loader import load_model
        from utils.prediction import predict_img_tiled
        
        # Загружаем модель
        model_path = self.params.get('model_path')
        if not model_path:
            model_path = os.path.join(self.plugin_dir, 'models', 'best_model.h5')
        
        _, predictor = load_model(model_path)
        
        print("PROGRESS:40", flush=True)
        
        # Читаем и подготавливаем изображение
        img = Image.open(self.params['input_path'])
        img_array = np.array(img)
        
        # Нормализация каналов
        if len(img_array.shape) == 2:
            img_array = np.stack([img_array] * 3, axis=2)
        elif img_array.shape[2] == 4:
            img_array = img_array[:, :, :3]
        elif img_array.shape[2] == 1:
            img_array = np.repeat(img_array, 3, axis=2)
        
        # Приведение к uint8
        if img_array.dtype != np.uint8:
            img_array = ((img_array - img_array.min()) / 
                        (img_array.max() - img_array.min() + 1e-8) * 255).astype(np.uint8)
        
        print("PROGRESS:60", flush=True)
        
        # Предсказание
        predictions = predict_img_tiled(
            img_array,
            window_size=self.params['patch_size'],
            subdivisions=self.params['subdivisions'],
            nb_classes=DEFAULT_NUM_CLASSES,
            pred_func=predictor
        )
        
        print("PROGRESS:80", flush=True)
        
        # Создаем RGB изображение
        mask = np.argmax(predictions, axis=2).astype(np.uint8)
        height, width = mask.shape
        rgb_result = np.zeros((height, width, 3), dtype=np.uint8)
        
        for class_idx, color in enumerate(SEGMENTATION_COLORS):
            rgb_result[mask == class_idx] = color
        
        result_image = Image.fromarray(rgb_result)
        return self._save_results(result_image, mask)
    
    def _save_results(self, rgb_image, mask=None):
        """Сохранение результатов с геореференцированием"""
        # Если маски нет, извлекаем из RGB
        if mask is None:
            sys.path.insert(0, self.plugin_dir)
            from config import SEGMENTATION_COLORS
            
            result_array = np.array(rgb_image)
            mask = np.zeros((result_array.shape[0], result_array.shape[1]), dtype=np.uint8)
            
            for i, color in enumerate(SEGMENTATION_COLORS):
                color_mask = np.all(result_array == color, axis=2)
                mask[color_mask] = i
        
        # Если есть геоданные, создаем геореференцированный файл
        if 'georeference_data' in self.params:
            geo_data = self.params['georeference_data']
            
            # Импортируем rasterio только здесь, в subprocess
            import rasterio
            from rasterio.transform import from_bounds
            
            height, width = mask.shape
            transform = from_bounds(
                geo_data['extent_xmin'],
                geo_data['extent_ymin'],
                geo_data['extent_xmax'],
                geo_data['extent_ymax'],
                width,
                height
            )
            
            # Сохраняем геореференцированный результат
            profile = {
                'driver': 'GTiff',
                'height': height,
                'width': width,
                'count': 1,
                'dtype': mask.dtype,
                'crs': geo_data.get('crs'),
                'transform': transform
            }
            
            with rasterio.open(self.params['output_path'], 'w', **profile) as dst:
                dst.write(mask, 1)
        else:
            # Без геореференцирования сохраняем как простые файлы
            mask_path = self.params['output_path'].replace('.tif', '_mask.png')
            Image.fromarray(mask).save(mask_path)
            
            rgb_path = self.params['output_path'].replace('.tif', '_rgb.png')
            rgb_image.save(rgb_path)
        
        # Метаданные
        metadata_path = self.params['output_path'].replace('.tif', '_metadata.json')
        metadata = {
            'output_path': self.params['output_path'],
            'classes': SEGMENTATION_COLORS if 'SEGMENTATION_COLORS' in locals() else [],
            'num_classes': len(SEGMENTATION_COLORS) if 'SEGMENTATION_COLORS' in locals() else 6,
            'has_georef': 'georeference_data' in self.params
        }
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)
        
        print("PROGRESS:100", flush=True)
        print(f"RESULT:{metadata_path}", flush=True)
        
        return metadata_path


def main():
    params_file = sys.argv[1]
    with open(params_file, 'r') as f:
        params = json.load(f)
    
    runner = InferenceRunner(params)
    runner.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr, flush=True)
        sys.exit(1)
