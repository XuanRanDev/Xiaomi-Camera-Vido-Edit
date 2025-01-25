import os
import subprocess
import random
from datetime import datetime

# 设置文件夹路径和日志文件
base_folder = 'F:\\XuanRan\\Clip'
output_file = 'video\\final_video.mp4'
log_file = 'log\\process_log.txt'


# 日志函数
def log_message(message):
    with open(log_file, 'a') as log:
        log.write(f"{datetime.now()} - {message}\n")
    print(message)


# 函数：获取文件夹中的视频文件（按时间戳排序）
def get_video_files_in_folder(folder):
    video_files = []
    for file in os.listdir(folder):
        if file.endswith('.mp4'):
            try:
                timestamp = int(file.split('_')[-1].split('.')[0])  # 提取时间戳
                video_files.append((file, timestamp))
            except ValueError:
                continue
    video_files.sort(key=lambda x: x[1])  # 按时间戳排序
    return video_files


# 函数：加速视频（16倍速，并确保帧率一致）
def speed_up_video(input_video, output_video, speed_factor=39):
    log_message(f"开始加速视频: {input_video}")
    command = [
        'ffmpeg', '-i', input_video, '-filter:v', f'setpts={1 / speed_factor}*PTS',
        '-r', '30', '-an', '-fflags', '+genpts', output_video  # 重新生成时间戳
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        log_message(f"加速完成: {output_video}")
    else:
        log_message(f"加速失败: {input_video}，错误信息:\n{result.stderr.decode()}")


# 函数：合并视频文件（重新编码）
def merge_videos(video_list, output_video):
    log_message(f"{datetime.now()} 开始合并视频，总计 {len(video_list)} 个文件")
    with open('file_list.txt', 'w') as f:
        for video in video_list:
            f.write(f"file '{video}'\n")

    command = [
        'ffmpeg', '-f', 'concat', '-safe', '0', '-i', 'file_list.txt',
        '-c:v', 'libx264', '-crf', '23', '-preset', 'fast', output_video
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        log_message(f"合并完成: {output_file}")
    else:
        log_message(f"合并失败，错误信息:\n{result.stderr.decode()}")


# 函数：随机选择 8-20 点之间的视频
def select_video_for_day(day_folders):
    for folder in day_folders:
        video_files = get_video_files_in_folder(folder)
        valid_videos = []

        for video, timestamp in video_files:
            video_time = datetime.fromtimestamp(timestamp)
            if 8 <= video_time.hour < 20:
                valid_videos.append(os.path.join(folder, video))

        if valid_videos:
            selected_video = random.choice(valid_videos)
            log_message(f"随机选择视频: {selected_video}")
            return selected_video

    if day_folders:
        folder = day_folders[0]
        video_files = get_video_files_in_folder(folder)
        if video_files:
            fallback_video = os.path.join(folder, video_files[0][0])
            log_message(f"未找到符合条件的视频，使用备选视频: {fallback_video}")
            return fallback_video
    return None


# 主函数：遍历所有文件夹，按顺序加速并合并视频
def process_videos():
    if os.path.exists(log_file):
        os.remove(log_file)  # 清空旧日志文件

    log_message("开始处理视频")
    video_list = []
    day_folders = {}

    # 遍历文件夹
    for root, dirs, files in os.walk(base_folder):
        for folder_name in dirs:
            folder_path = os.path.join(root, folder_name)
            folder_date = folder_name[:8]  # yyyyMMdd
            if folder_date not in day_folders:
                day_folders[folder_date] = []
            day_folders[folder_date].append(folder_path)

    # 遍历每天的文件夹，选取每一天的一个视频
    for day, folders in sorted(day_folders.items()):
        log_message(f"处理日期: {day}")
        selected_video = select_video_for_day(folders)

        if selected_video:
            temp_video = f"temp\\temp_{day}.mp4"
            speed_up_video(selected_video, temp_video)
            video_list.append(temp_video)

    # 合并所有视频
    if video_list:
        merge_videos(video_list, output_file)

    # 清理临时文件
    if os.path.exists('file_list.txt'):
        os.remove('file_list.txt')
    for video in video_list:
        if os.path.exists(video):
            os.remove(video)

    log_message("视频处理完成")


# 执行脚本
if __name__ == '__main__':
    process_videos()
