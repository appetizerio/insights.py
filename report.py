# -*- coding: utf-8 -*-
import os
import sys
import json
import subprocess
import gzip

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import gridspec
from matplotlib.ticker import MultipleLocator
from bisect import bisect_left
from scipy import stats

SCALE_TO_MB = 1.0 / 1024 / 1024
SCALE_TO_KB = 1.0 / 1024


def photo_to_mp4(image_list, mp4_path):
    if not image_list: return
    photos_txt_filepath = mp4_path.replace('mp4', 'txt')
    output = open(photos_txt_filepath, 'w')
    for item in image_list:
        output.write('file ' + item + '\n')
        output.write('duration 0.5\n')
    output.write('file ' + image_list[-1])
    output.close()
    ffmpeg_command = 'ffmpeg -f concat -safe 0 -i ' + photos_txt_filepath + \
                     ' -vsync vfr -pix_fmt yuv420p ' + mp4_path
    return subprocess.check_output(ffmpeg_command, shell=True)


def is_same_photo(photo_path_list):
    import cv2
    if not photo_path_list: return None
    temp = photo_path_list[len(photo_path_list) // 2]
    for index in range(0, len(photo_path_list)):
        image1 = cv2.imread(temp)
        image2 = cv2.imread(photo_path_list[index])
        difference = cv2.subtract(image1, image2)
        if np.any(difference):
            return False
    return True


# 向前向后各多捕获三秒的截图
def get_low_fps_time_photo_path_list(low_fps_time_list, file_path):
    low_fps_point_time = []
    more_time_count = 3  # 取fps时间段前后再加3秒的图片路径
    for i in range(1, more_time_count + 1)[::-1]:  # 分片 从后往前取值
        low_fps_point_time.append(int(low_fps_time_list[0]) // 1000 - i)
    for item in low_fps_time_list:
        low_fps_point_time.append(int(item) // 1000)
    for i in range(1, more_time_count + 1):
        low_fps_point_time.append(int(low_fps_time_list[-1]) // 1000 + i)

    screenshot_path = file_path + 'screenshots/'
    if not os.path.exists(screenshot_path):
        # print('未采集到app运行时的截图!')
        return
    screenshot_files = os.listdir(screenshot_path)
    screenshot_files.sort()
    screenshot_list = []
    for item in screenshot_files[bisect_left(screenshot_files, "max_" + str(low_fps_point_time[0])): \
            bisect_left(screenshot_files, "max_" + str(low_fps_point_time[-1]))]:
        full_name = os.path.join(screenshot_path, item)
        screenshot_list.append(full_name)
    return sorted(screenshot_list)


def get_low_fps_point_color(low_fps_time_photo_path_list):
    return 'green' if is_same_photo(low_fps_time_photo_path_list) else 'red'


def generate_density_data(count_data, t_min, t_max, x_interval, category=''):
    sub_count, x_data, y_data = {}, [], []
    count, size, index = 0, 0, 0
    bins = x_interval // 6  # 每个滑动窗口,分6小格
    while bins * index <= (t_max - t_min) // 1000:
        temp = bins * index
        for item in count_data:
            tt = (int(item[0]) - t_min) // 1000
            if temp <= tt <= temp + x_interval:
                count += 1
                size += float(item[1])
            if tt > temp + x_interval:
                break
        if "FPS density" in category:
            sub_count[temp] = count
        elif "GC density" in category:
            sub_count[temp] = count // 2
        else:
            sub_count[temp] = size

        index += 1
        count = 0
        size = 0
    for key in sorted(sub_count):
        x_data.append(key)
        y_data.append(sub_count[key])
    return x_data, y_data


def pick_common_interval(tspan, suggested_ticks):
    unaligned, picked, current_min = tspan // suggested_ticks, None, None
    for interval in [30, 60, 90, 120]:  # 常规的时间刻度（seconds）
        if current_min is None or abs(unaligned - interval) < current_min:
            current_min = abs(unaligned - interval)
            picked = interval
    return picked


def get_confidence_interval(data, alpha=0.95):  # 95%置信区间
    values = np.array(data)
    mean, std = values.mean(), values.std()
    return stats.t.interval(alpha, len(values) - 1, mean, std)


class Appetizer(object):
    HIGHLIGHT_FPS_BY_THRESHOLD = True  # True用FPS_THRESHOLD，False用FPS_LOW_COUNT
    FPS_THRESHOLD = 40  # 在FPS图中高亮低于本阀值的数据点
    FPS_LOW_COUNT = 20  # 在FPS图中高亮最低N个数据点
    X_MAJOR_COUNT = 30  # 图中X轴显示多少个刻度段

    def __init__(self, report_json):
        cpu = {}  # epoch => CPU_usage
        fps = {}  # epoch => FPS
        uithread_time = {}  # epoch => UI thread response time
        http_time = {}  # epoch => http response time
        http_size = {}  # epoch => http response size
        bitmap_size = {}  # epoch => UI thread response bitmap size
        native_heap_free = {}  # epoch => native_heap_free
        native_heap_allocated = {}  # epoch => native_heap_allocated

        tmax, tmin = None, None
        for item in report_json['allItems']:
            if item["category"] == "perf":
                if "start" in item:
                    start_time = item["start"]
                    if tmax is None or tmax < float(start_time): tmax = float(start_time)
                    if tmin is None or tmin > float(start_time): tmin = float(start_time)

                    if item["elapsed_time"] == 0: continue
                    elapsed_time = item["elapsed_time"]
                    uithread_time[start_time] = elapsed_time

                    if "method" in item and "bytes" in item:
                        bitmap_size[start_time] = int(item["bytes"])

            if item["category"] == "http":
                if "start_time" in item:
                    start_time = item["start_time"]
                    if tmax is None or tmax < float(start_time): tmax = float(start_time)
                    if tmin is None or tmin > float(start_time): tmin = float(start_time)
                    if item["elapsed_time"] == 0: continue
                    elapsed_time = item["elapsed_time"]
                    http_time[start_time] = elapsed_time
                    response = item["response"]
                    http_size[start_time] = response["content_length"] + response["header_size"]

        for session in report_json['session']:
            for item in session["ticker"]:
                start_time = item["time"]
                if tmax is None or tmax < float(start_time): tmax = float(start_time)
                if tmin is None or tmin > float(start_time): tmin = float(start_time)
                if "CPU_usage" in item:
                    cpu[start_time] = float(item["CPU_usage"])
                if "fps" in item:
                    fps[start_time] = float(item["fps"])
                if "native_heap_allocated" in item and "native_heap_free" in item:
                    native_heap_allocated[start_time] = float(item["native_heap_allocated"])
                    native_heap_free[start_time] = float(item["native_heap_free"])

        self.uithread_time = sorted(uithread_time.items(), key=lambda s: s[0])
        self.http_time = sorted(http_time.items(), key=lambda s: s[0])
        self.cpu = sorted(cpu.items(), key=lambda s: s[0])
        self.fps = sorted(fps.items(), key=lambda s: s[0])
        self.native_heap_allocated = sorted(native_heap_allocated.items(), key=lambda s: s[0])
        self.native_heap_free = sorted(native_heap_free.items(), key=lambda s: s[0])
        self.http_response_size = sorted(http_size.items(), key=lambda s: s[0])
        self.bitmap_size = sorted(bitmap_size.items(), key=lambda s: s[0])

        self.t_min, self.t_max, self.total_seconds = tmin, tmax, (tmax - tmin) / 1000
        self.x_interval = pick_common_interval(self.total_seconds, Appetizer.X_MAJOR_COUNT)
        self.sharex = None

    def generate_plots(self, screenshot_folder):
        plt.figure('Appetizer Data Visualization', figsize=(20, 20))
        plt.subplots_adjust(top=0.98, bottom=0.03, left=0.05, right=0.95, hspace=0.2, wspace=0.2)
        gs = gridspec.GridSpec(7, 1, height_ratios=[1, 1, 1, 1, 1.5, 1, 1])

        ax = self.draw_scatter(self.http_time, "HTTP response time (Appetizer)", "ms", self.t_min, None, gs[0])
        ax.xaxis.set_major_locator(MultipleLocator(self.x_interval))  # 设置x轴主刻度
        ax.set_xlim([0, self.total_seconds])

        self.sharex = ax

        ax1 = self.draw_scatter(self.http_response_size, "HTTP response size (Appetizer)", "KB", self.t_min,
                                self.sharex, gs[1], SCALE_TO_KB)
        ax1.set_yscale('log')

        ax2 = self.draw_scatter(self.uithread_time, "UI thread response time (Appetizer)", "ms", self.t_min, self.sharex,
                                gs[2])

        ax3 = self.draw_scatter(self.bitmap_size, "Bitmap size (Appetizer)", "KB", self.t_min, self.sharex, gs[3],
                                SCALE_TO_KB)
        ax3.set_yscale('log')

        ax4 = self.draw_line(self.fps, "FPS (Appetizer)", "frame/S", self.t_min, self.sharex, gs[4])
        self.highlight_low_fps(self.fps, self.t_min, screenshot_folder)
        if ax4 and len(self.fps) > 0:
            lower_conf_interval, upper_conf_interval = get_confidence_interval([float(item[1]) for item in self.fps])
            ax4.hlines(round(lower_conf_interval), 0, self.total_seconds, colors="r", linestyles="solid")

        ax5 = self.draw_line(self.cpu, "CPU utilization (Appetizer)", "%", self.t_min, self.sharex, gs[5], 100)

        ax6 = self.draw_area(self.native_heap_allocated, self.native_heap_free, 'native_heap_allocated (Appetizer)',
                             'native_heap_free (Appetizer)', "MB", self.t_min, self.sharex, gs[6])

    def save_figure(self, output_file):
        plt.savefig(output_file, bbox_inches='tight')

    def draw_scatter(self, data, legend, unit, t_min, sharex, pos, scaler=1.0, shapecolor='b.'):
        return self.draw_line(data, legend=legend, unit=unit, t_min=t_min, sharex=sharex, pos=pos, scaler=scaler, shapecolor=shapecolor, linewidth=0.0)

    def draw_line(self, data, legend, unit, t_min, sharex, pos, scaler=1.0, shapecolor='b', linewidth=1.0):
        ax = plt.subplot(pos, sharex=sharex)
        x_data, y_data = self.generate_plot_data(data, t_min, scaler=scaler)
        plt.plot(x_data, y_data, shapecolor, linewidth=linewidth, label=legend)
        plt.legend(loc='upper right')
        plt.ylabel(unit)
        return ax

    def draw_area(self, data1, data2, legend1, legend2, unit, t_min, sharex, pos, ):
        ax = plt.subplot(pos, sharex=sharex)
        x_data, y_data1 = self.generate_plot_data(data1, t_min, scaler=SCALE_TO_MB)
        x_data, y_data2 = self.generate_plot_data(data2, t_min, scaler=SCALE_TO_MB)
        l2, l4 = plt.stackplot(x_data, y_data1, y_data2)
        plt.legend((l2, l4), (legend1, legend2), loc='upper right')
        plt.ylabel(unit)
        return ax

    def generate_plot_data(self, data, t_min, scaler=1.0):
        xdata, ydata = [], []
        for item in data:
            xdata.append((float(item[0]) - t_min) / 1000)
            ydata.append(float(item[1]) * scaler)
        return xdata, ydata

    def highlight_low_fps(self, data, t_min, file_path):
        if Appetizer.HIGHLIGHT_FPS_BY_THRESHOLD:
            highlight_items = [item for item in data if item[1] < Appetizer.FPS_THRESHOLD]
        else: # highlight FPS by lowest N
            data_sorted_by_fps = sorted(data, key=lambda d: d[1])
            highlight_items = data_sorted_by_fps[:Appetizer.FPS_LOW_COUNT]
        highlight_items.append(('temp', 0))

        count_mp4 = 0
        temp_fps_data = highlight_items[0]
        low_fps_time_list = []
        points_to_decorate = {}
        for item in highlight_items:
            if item[1] == temp_fps_data[1]:
                low_fps_time_list.append(item[0])
            else:
                count_mp4 += 1
                low_fps_time_photo_path_list = get_low_fps_time_photo_path_list(low_fps_time_list, file_path)
                if low_fps_time_photo_path_list:
                    mp4_path = "{file_path}{mp4_name}.mp4".format \
                        (file_path=file_path, mp4_name=str((int(low_fps_time_list[-1]) - t_min) // 1000))
                    photo_to_mp4(low_fps_time_photo_path_list, mp4_path)
                    fps_color_photo = get_low_fps_point_color(low_fps_time_photo_path_list)
                    for low_fps_time in low_fps_time_list:
                        points_to_decorate[low_fps_time] = fps_color_photo
                low_fps_time_list = []
                temp_fps_data = item
                low_fps_time_list.append(item[0])
        x_data, y_data = self.generate_plot_data(data, t_min)
        for key in points_to_decorate:
            x = (float(key) - t_min) / 1000
            plt.scatter(x, y_data[x_data.index(x)], s=25, c=points_to_decorate[key], marker='.')


if __name__ == "__main__":
    if len(sys.argv) <= 1:
        print("Usage: python analyzeReportJson.py ./xx/xx.report.json")
        print("output to dirname(abspath(input))")
        sys.exit(1)
    input_report = sys.argv[1]
    if os.path.splitext(input_report)[1] == '.gz':
        with gzip.open(input_report, 'r') as report:
            report_json = json.loads(report.read().decode('utf-8'))
    else:
        with open(input_report) as report:
            report_json = json.load(report)

    output_dir = os.path.dirname(os.path.abspath(input_report)) + '/'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    appetizer = Appetizer(report_json)
    appetizer.generate_plots(output_dir)
    appetizer.save_figure(output_dir + "viz.png")
    plt.show()
