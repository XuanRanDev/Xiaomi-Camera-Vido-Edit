import os
import subprocess
import random  # 用于随机选择视频
from datetime import datetime, timedelta

# 设置文件夹路径
base_folder = 'F:\\XuanRan\\Clip'
output_file = 'F:\\XuanRan\\Clip-Res\\final_video.mp4'


# 函数：根据时间戳对视频文件进行排序
def get_video_files_in_folder(folder):
    video_files = []
    for file in os.listdir(folder):
        if file.endswith('.mp4'):
            timestamp = int(file.split('_')[-1].split('.')[0])  # 提取时间戳
            video_files.append((file, timestamp))
    video_files.sort(key=lambda x: x[1])  # 按时间戳排序
    return video_files


# 函数：加速视频（16倍速）
def speed_up_video(input_video, output_video):
    command = [
        'ffmpeg', '-i', input_video, '-filter:v', 'setpts=0.0225*PTS', '-an', output_video
    ]
    subprocess.run(command)


# 函数：合并视频文件
def merge_videos(video_list, output_video):
    # 创建合并文件的临时文本文件
    with open('file_list.txt', 'w') as f:
        for video in video_list:
            f.write(f"file '{video}'\n")

    # 使用 ffmpeg 合并视频
    subprocess.run(['ffmpeg', '-f', 'concat', '-safe', '0', '-i', 'file_list.txt', '-c', 'copy', output_video])


# 函数：根据需求选取每一天的一个视频
def select_video_for_day(day_folders):
    selected_video = None

    for folder in day_folders:
        folder_name = os.path.basename(folder)
        start_time = datetime.strptime(folder_name, '%Y%m%d%H')

        # 获取视频文件（按时间戳排序）
        video_files = get_video_files_in_folder(folder)

        # 筛选 8-16 点之间的视频
        valid_videos = []
        for video, timestamp in video_files:
            video_time = datetime.fromtimestamp(timestamp)
            if 8 <= video_time.hour < 16:
                valid_videos.append(os.path.join(folder, video))

        # 如果找到符合条件的视频，则随机选择一个
        if valid_videos:
            selected_video = random.choice(valid_videos)
            break

    # 若没有找到8-16点的视频，则向后寻找其他时间段的视频（只选一天中的一个）
    if not selected_video and day_folders:
        folder = day_folders[0]
        video_files = get_video_files_in_folder(folder)
        selected_video = os.path.join(folder, video_files[0][0])

    return selected_video


# 主函数：遍历所有文件夹，按顺序合并视频
def process_videos():
    video_list = []
    day_folders = {}

    # 遍历文件夹
    for root, dirs, files in os.walk(base_folder):
        for folder_name in dirs:
            folder_path = os.path.join(root, folder_name)
            # 获取文件夹的日期部分
            folder_date = folder_name[:8]  # yyyyMMdd
            if folder_date not in day_folders:
                day_folders[folder_date] = []
            day_folders[folder_date].append(folder_path)

    # 遍历每天的文件夹，选取每一天的一个视频
    for day, folders in day_folders.items():
        selected_video = select_video_for_day(folders)

        if selected_video:
            # 加速视频
            temp_video = f"temp_{day}.mp4"
            speed_up_video(selected_video, temp_video)

            # 添加到视频列表
            video_list.append(temp_video)

    # 合并所有视频
    merge_videos(video_list, output_file)

    # 清理临时文件
    os.remove('file_list.txt')
    for video in video_list:
        os.remove(video)


# 执行脚本
process_videos()
