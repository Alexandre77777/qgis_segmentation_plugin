# -*- coding: utf-8 -*-
"""
Worker для выполнения сегментации в отдельном потоке
"""
from qgis.PyQt.QtCore import QThread, pyqtSignal
import os
import sys
import subprocess
import json
import tempfile
import locale


class SegmentationWorker(QThread):
    """Worker для выполнения сегментации"""
    finished = pyqtSignal()
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    result_ready = pyqtSignal(str)
    
    def __init__(self, params, plugin_dir):
        super().__init__()
        self.params = params
        self.plugin_dir = plugin_dir
        self.process = None
    
    def run(self):
        try:
            self.run_inference()
        except Exception as e:
            self.error.emit(str(e))
    
    def run_inference(self):
        """Запускает единый скрипт инференса"""
        self.progress.emit(10)
        
        # Путь к единому скрипту
        inference_script = os.path.join(self.plugin_dir, 'utils', 'inference_runner.py')
        
        # Python из venv или portable
        python_exe = self._find_python()
        
        # Сохраняем параметры
        params_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False, encoding='utf-8'
        )
        json.dump(self.params, params_file, ensure_ascii=False)
        params_file.close()
        
        try:
            # Чистое окружение
            env = self._create_clean_env()
            
            # Запускаем процесс
            cmd = [python_exe, '-u', inference_script, params_file.name]
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                universal_newlines=True,
                encoding='utf-8'
            )
            
            # Читаем вывод
            for line in iter(self.process.stdout.readline, ''):
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('PROGRESS:'):
                    try:
                        progress = int(line.split(':')[1])
                        self.progress.emit(progress)
                    except:
                        pass
                elif line.startswith('RESULT:'):
                    result_path = line.split(':', 1)[1].strip()
                    self.result_ready.emit(result_path)
            
            self.process.wait()
            
            if self.process.returncode != 0:
                stderr = self.process.stderr.read()
                raise Exception(f"Ошибка инференса: {stderr}")
            
            self.finished.emit()
            
        finally:
            if self.process:
                self.process.stdout.close()
                self.process.stderr.close()
                self.process = None
            
            try:
                os.unlink(params_file.name)
            except:
                pass
    
    def _find_python(self):
        """Поиск Python интерпретатора"""
        # Сначала ищем в venv
        venv_path = os.path.join(self.plugin_dir, '.venv')
        if os.name == 'nt':
            python_exe = os.path.join(venv_path, 'Scripts', 'python.exe')
        else:
            python_exe = os.path.join(venv_path, 'bin', 'python')
        
        if os.path.exists(python_exe):
            return python_exe
        
        # Потом в portable_python
        portable_path = os.path.join(self.plugin_dir, 'portable_python', 'python.exe')
        if os.path.exists(portable_path):
            return portable_path
        
        raise Exception("Python интерпретатор не найден")
    
    def _create_clean_env(self):
        """Создает чистое окружение для subprocess"""
        env = {}
        
        # Минимальные системные переменные
        for var in ['SYSTEMROOT', 'SYSTEMDRIVE', 'TEMP', 'TMP', 'USERPROFILE', 'HOME']:
            if var in os.environ:
                env[var] = os.environ[var]
        
        # Определяем пути в зависимости от типа Python
        python_exe = self._find_python()
        if '.venv' in python_exe:
            # Для venv
            venv_path = os.path.join(self.plugin_dir, '.venv')
            if os.name == 'nt':
                paths = [
                    os.path.join(venv_path, 'Scripts'),
                    os.path.join(os.environ.get('SYSTEMROOT', 'C:\\Windows'), 'System32')
                ]
            else:
                paths = [
                    os.path.join(venv_path, 'bin'),
                    '/usr/bin',
                    '/bin'
                ]
            env['PYTHONHOME'] = venv_path
        else:
            # Для portable Python
            portable_dir = os.path.join(self.plugin_dir, 'portable_python')
            paths = [
                portable_dir,
                os.path.join(portable_dir, 'Scripts'),
                os.path.join(os.environ.get('SYSTEMROOT', 'C:\\Windows'), 'System32')
            ]
        
        env['PATH'] = os.pathsep.join(paths)
        env['PLUGIN_DIR'] = self.plugin_dir
        env['PYTHONIOENCODING'] = 'utf-8'
        
        return env
