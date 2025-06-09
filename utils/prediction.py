# -*- coding: utf-8 -*-
"""
Упрощенный модуль предсказания с единой функцией
"""
import numpy as np


def predict_img_tiled(input_img, window_size, subdivisions, nb_classes, pred_func):
    """
    Универсальная функция предсказания с тайлами
    
    Args:
        input_img: входное изображение (H, W, C)
        window_size: размер окна/патча
        subdivisions: количество подразделений (1 = без перекрытия, 2+ = с перекрытием)
        nb_classes: количество классов
        pred_func: функция предсказания
    
    Returns:
        numpy array с предсказаниями (H, W, nb_classes)
    """
    h, w = input_img.shape[:2]
    
    # Если изображение меньше окна
    if h <= window_size and w <= window_size:
        padded = np.zeros((window_size, window_size, input_img.shape[2]), dtype=input_img.dtype)
        padded[:h, :w] = input_img
        prediction = pred_func(padded[np.newaxis, ...])[0]
        return prediction[:h, :w]
    
    # Расчет шага и перекрытия
    if subdivisions == 1:
        overlap = 0
        step = window_size
    else:
        overlap = window_size // subdivisions
        step = window_size - overlap
    
    # Подготовка массивов
    prediction = np.zeros((h, w, nb_classes), dtype=np.float32)
    weights = np.zeros((h, w, 1), dtype=np.float32)
    
    # Создаем весовую матрицу для смешивания
    weight_matrix = create_weight_matrix(window_size, overlap)
    
    # Собираем патчи
    patches = []
    coords = []
    
    for y in range(0, h - window_size + 1, step):
        for x in range(0, w - window_size + 1, step):
            patch = input_img[y:y+window_size, x:x+window_size]
            patches.append(patch)
            coords.append((y, x))
    
    # Обрабатываем края, если нужно
    if h % step != 0:
        for x in range(0, w - window_size + 1, step):
            y = h - window_size
            patch = input_img[y:y+window_size, x:x+window_size]
            patches.append(patch)
            coords.append((y, x))
    
    if w % step != 0:
        for y in range(0, h - window_size + 1, step):
            x = w - window_size
            patch = input_img[y:y+window_size, x:x+window_size]
            patches.append(patch)
            coords.append((y, x))
    
    # Угловой патч
    if h % step != 0 and w % step != 0:
        patch = input_img[h-window_size:h, w-window_size:w]
        patches.append(patch)
        coords.append((h-window_size, w-window_size))
    
    # Пакетное предсказание
    if patches:
        patches_array = np.array(patches)
        predictions = pred_func(patches_array)
        
        # Встраиваем предсказания
        for idx, (y, x) in enumerate(coords):
            prediction[y:y+window_size, x:x+window_size] += predictions[idx] * weight_matrix
            weights[y:y+window_size, x:x+window_size] += weight_matrix
    
    # Нормализация
    prediction = np.divide(prediction, weights + 1e-8, out=prediction, where=weights > 0)
    
    return prediction


def create_weight_matrix(window_size, overlap):
    """Создает матрицу весов для плавного смешивания"""
    weight = np.ones((window_size, window_size, 1), dtype=np.float32)
    
    if overlap > 0:
        # Создаем градиент для краев
        fade = np.linspace(0.1, 1.0, overlap)
        
        # Применяем градиент к краям
        weight[:overlap, :, 0] *= fade[:, np.newaxis]
        weight[-overlap:, :, 0] *= fade[::-1, np.newaxis]
        weight[:, :overlap, 0] *= fade[np.newaxis, :]
        weight[:, -overlap:, 0] *= fade[np.newaxis, ::-1]
    
    return weight
