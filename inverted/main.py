import os
import subprocess
from natsort import natsorted


def process_and_reverse_video(input_file, output_file, speed_factor):
    """
    修改视频速度并倒放
    :param input_file: 输入视频文件路径
    :param output_file: 输出视频文件路径
    :param speed_factor: 倍速因子 (大于1为加速，小于1为减速)
    """
    try:
        # 调整速度并倒放视频
        subprocess.run(
            [
                "ffmpeg",
                "-i", input_file,
                "-vf", f"reverse,setpts={1 / speed_factor}*PTS",
                "-af", "areverse",  # 音频倒放
                output_file
            ],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Error processing file {input_file}: {e}")


def merge_videos(video_list, output_file):
    """
    合并视频
    :param video_list: 处理后视频文件路径列表
    :param output_file: 最终合并后的视频文件路径
    """
    try:
        # 创建临时文件列表
        with open("file_list.txt", "w") as file_list:
            for video in video_list:
                file_list.write(f"file '{video}'\n")

        # 使用ffmpeg合并
        subprocess.run(
            [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", "file_list.txt",
                "-c", "copy",  # 不重新编码
                output_file
            ],
            check=True
        )
        os.remove("file_list.txt")
    except subprocess.CalledProcessError as e:
        print(f"Error merging videos: {e}")


def process_videos(input_dir, output_dir, speed_factor, merged_output):
    """
    主处理函数
    :param input_dir: 输入视频目录
    :param output_dir: 输出视频目录
    :param speed_factor: 倍速因子
    :param merged_output: 合并后视频的文件路径
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 获取所有视频文件（按自然顺序排序）
    video_files = [f for f in os.listdir(input_dir) if f.endswith(('.mp4', '.avi', '.mkv'))]
    video_files = natsorted(video_files)

    processed_files = []

    for video in video_files:
        input_path = os.path.join(input_dir, video)
        output_path = os.path.join(output_dir, f"processed_{video}")

        print(f"Processing and reversing {video}...")
        process_and_reverse_video(input_path, output_path, speed_factor)
        processed_files.append(output_path)

    print("Merging all videos...")
    merge_videos(processed_files, merged_output)

    # 删除临时的处理文件
    for processed_file in processed_files:
        os.remove(processed_file)

    print(f"All videos have been merged into {merged_output}. Temporary files deleted.")


if __name__ == "__main__":
    # 配置部分
    input_directory = "videos/input"  # 输入视频的目录
    output_directory = "videos/processed"  # 处理后视频的目录
    speed = 0.8  # 倍速因子，例如0.5表示减慢一倍，2表示加速两倍
    merged_video_output = "videos/final_output.mp4"  # 合并后的视频输出路径

    process_videos(input_directory, output_directory, speed, merged_video_output)
