import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from skimage import measure
from matplotlib.colors import LinearSegmentedColormap

# Функция для генерации
def draw_fractal_3d(shape, min_length):
    # Создаем пустой массив
    fractal = np.zeros(shape)

    def draw_tree(x, y, z, ln, min_ln):
        if ln > min_ln:
            # Расчет новых координат
            new_x = int(x + ln * np.cos(np.pi / 4))
            new_y = int(y + ln * np.sin(np.pi / 4))
            new_z = int(z + ln * np.sin(np.pi / 4))

            # Проверяем, чтобы новые координаты были в пределах массива
            if 0 <= new_x < shape[0] and 0 <= new_y < shape[1] and 0 <= new_z < shape[2]:
                fractal[new_x, new_y, new_z] = 1

            # Рекурсивный вызов для дочерних ветвей
            draw_tree(new_x, new_y, new_z, ln * 0.5, min_ln)

    # Начальные параметры
    x0 = shape[0] // 2
    y0 = shape[1] // 2
    z0 = shape[2] // 2
    ln = min(shape) // 2
    draw_tree(x0, y0, z0, ln, min_length)

    return fractal

# Параметры
shape = (64, 64, 64)
min_length = 5

# Генерация
fractal = draw_fractal_3d(shape, min_length)

# Проверка значений
print(f"Ромб: минимальное значение = {fractal.min()}, максимальное значение = {fractal.max()}")

# Если значения в массиве не равны нулю, отображаем его
if fractal.max() > 0:
    # Нормализация массива
    fractal = (fractal - fractal.min()) / (fractal.max() - fractal.min())

    # Отображение
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    # Определение уровня изосурфейса
    iso_level = 0.5
    if fractal.min() <= iso_level <= fractal.max():
        # Проверка наличия поверхности
        try:
            verts, faces, _, _ = measure.marching_cubes(fractal, level=iso_level)
            # Настройка цветов
            cmap = LinearSegmentedColormap.from_list('fractal_cmap', ['green', 'black'], N=256)
            ax.plot_trisurf(verts[:, 0], verts[:, 1], faces, verts[:, 2], cmap=cmap, alpha=0.5)
            plt.show()
        except RuntimeError as e:
            print(f"Ошибка в marching cubes: {e}")
    else:
        print(f"Ошибка: уровень изосурфейса {iso_level} не находится в диапазоне значений фрактала.")
else:
    print("Ошибка: ромб не содержит значений, отличных от нуля.")
