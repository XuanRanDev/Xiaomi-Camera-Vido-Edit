import subprocess


def add_background_music(video_path, audio_path, output_path):
    # 构建ffmpeg命令
    command = [
        'ffmpeg',
        '-i', video_path,  # 输入视频文件
        '-i', audio_path,  # 输入音频文件
        '-c:v', 'copy',  # 视频编码复制，避免重新编码视频
        '-map', '0:v:0',  # 从第一个输入（视频）中选择视频流
        '-map', '1:a:0',  # 从第二个输入（音频）中选择音频流
        '-shortest',  # 设置输出时长为视频或音频中较短的一个
        output_path  # 输出路径
    ]

    # 执行命令
    subprocess.run(command)


# 源文件 背景音乐 输出视频
add_background_music('final_video.mp4', 'bgm.mp3', 'output_video.mp4')
