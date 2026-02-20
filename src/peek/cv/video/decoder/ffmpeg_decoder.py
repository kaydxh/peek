# -*- coding: utf-8 -*-
"""FFmpegDecoder - 基于 PyAV(ffmpeg) 的视频解码器

使用 PyAV 库直接调用 FFmpeg 的 C API 进行视频解码，
对应 kingfisher InputFile 的解码逻辑，支持：
- 精确帧定位（seek + 逐帧解码）
- GPU 硬件加速解码（CUDA/NVDEC）
- 按时间段截取解码
- 自定义视频滤镜（scale/crop/transpose 等）
- 进度回调与取消机制

安装：pip install av
"""

import io
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Generator, List, Optional, Tuple, Union

from PIL import Image

from .base import BaseDecoder

logger = logging.getLogger(__name__)


@dataclass
class DecodeConfig:
    """解码配置

    对应 kingfisher InputFile 的各种配置参数。
    """

    # 时间范围截取
    start_time: Optional[float] = None  # 起始时间（秒），None 表示从头
    end_time: Optional[float] = None  # 结束时间（秒），None 表示到末尾
    duration: Optional[float] = None  # 截取时长（秒），与 end_time 二选一

    # GPU 硬件加速
    # gpu_id >= 0 时启用 CUDA 硬件解码（如 h264_cuvid, hevc_cuvid）
    # gpu_id < 0 时使用软件解码（默认）
    gpu_id: int = -1

    # 当 GPU 解码器不可用时，是否自动切换到软件解码器
    auto_switch_to_soft_codec: bool = True

    # 视频滤镜（ffmpeg filter 语法），如 "scale=1280:720", "transpose=1"
    video_filter: Optional[str] = None

    # 解码线程数，0 表示自动
    thread_count: int = 0

    # 是否只解码关键帧（速度快但帧数少）
    keyframes_only: bool = False


class FFmpegDecoder(BaseDecoder):
    """基于 PyAV(ffmpeg) 的视频解码器

    直接使用 FFmpeg C API 进行解码，功能最完整，对应 kingfisher InputFile。

    用法示例::

        # 基本用法
        decoder = FFmpegDecoder(fps=1.0, max_frames=10)
        frames = decoder.decode(video_bytes)

        # 指定时间段解码
        config = DecodeConfig(start_time=10.0, end_time=30.0)
        decoder = FFmpegDecoder(fps=1.0, decode_config=config)
        frames = decoder.decode(video_bytes)

        # GPU 硬件加速解码
        config = DecodeConfig(gpu_id=0)
        decoder = FFmpegDecoder(fps=1.0, decode_config=config)
        frames = decoder.decode(video_bytes)
    """

    def __init__(
        self,
        fps: float = 0.5,
        max_frames: int = -1,
        image_format: str = "JPEG",
        image_quality: int = 85,
        size: Optional[Dict[str, int]] = None,
        decode_config: Optional[DecodeConfig] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ):
        """初始化 FFmpeg 解码器

        Args:
            fps: 抽帧频率（帧/秒），0 或负数表示不采样（解码所有帧）
            max_frames: 最大帧数，-1 表示不限制
            image_format: 输出图片格式，JPEG 或 PNG
            image_quality: 图片压缩质量（仅 JPEG 有效），范围 1-100
            size: 分辨率缩放配置
            decode_config: 解码配置（时间范围、GPU、滤镜等）
            progress_callback: 进度回调函数，参数为进度百分比 [0.0, 1.0]
            cancel_callback: 取消检查函数，返回 True 时停止解码
        """
        super().__init__(fps, max_frames, image_format, image_quality, size)
        self._config = decode_config or DecodeConfig()
        self._progress_callback = progress_callback
        self._cancel_callback = cancel_callback
        self._check_available()

    @staticmethod
    def _check_available():
        """检查 PyAV 库是否可用"""
        try:
            import av  # noqa: F401
        except ImportError:
            raise ImportError(
                "使用 ffmpeg 解码方式需要安装 PyAV 库：\n"
                "  pip install av\n"
                "详见：https://pyav.org/"
            )

    def decode(self, video_bytes: bytes) -> List[str]:
        """使用 FFmpeg 解码视频为帧图片的 base64 列表"""
        return self._decode_frames(video_bytes, as_bytes=False)

    def decode_to_bytes(self, video_bytes: bytes) -> List[bytes]:
        """使用 FFmpeg 解码视频为帧图片的原始字节列表"""
        return self._decode_frames(video_bytes, as_bytes=True)

    def _decode_frames(self, video_bytes: bytes, as_bytes: bool = False) -> list:
        """使用 PyAV 解码视频帧

        对应 kingfisher InputFile::read_frames + decode_video 的流程：
        1. 打开视频容器（对应 InputFile::open）
        2. 获取视频流信息（对应 add_input_streams）
        3. 可选 seek 到起始位置（对应 InputFile::seek）
        4. 逐帧解码并采样（对应 InputFile::read_frames + decode_video）
        5. 帧格式转换和缩放（对应 send_frame_to_filters）

        Args:
            video_bytes: 视频原始字节数据
            as_bytes: 是否返回原始字节（True）或 base64 字符串（False）

        Returns:
            list: 帧图片列表
        """
        import av

        container = None
        tmp_file = None

        try:
            # 打开视频容器（对应 kingfisher InputFile::open）
            container, tmp_file = self._open_container(video_bytes)

            # 获取视频流（对应 kingfisher add_input_streams）
            video_stream = self._find_video_stream(container)
            if video_stream is None:
                raise RuntimeError("视频中未找到视频流")

            # 配置解码器
            self._configure_decoder(video_stream)

            # 获取视频信息（对应 kingfisher get_duration/get_frame_rate/get_total_frames）
            video_fps = self._get_frame_rate(video_stream)
            total_frames = self._get_total_frames(video_stream, container)
            duration = self._get_duration(container)

            logger.debug(
                f"ffmpeg 解码: total_frames={total_frames}, video_fps={video_fps:.2f}, "
                f"duration={duration:.2f}s"
            )

            # 计算采样帧索引
            effective_total = self._get_effective_total_frames(
                total_frames, video_fps, duration
            )
            frame_indices = self._compute_frame_indices(effective_total, video_fps)
            frame_set = set(frame_indices)

            logger.debug(
                f"采样计划: effective_total={effective_total}, "
                f"sample_frames={len(frame_indices)}"
            )

            # 可选 seek 到起始位置（对应 kingfisher InputFile::seek）
            start_frame_offset = 0
            if self._config.start_time is not None:
                start_frame_offset = self._seek_to_start(
                    container, video_stream, self._config.start_time
                )

            # 计算结束帧号
            end_frame = self._calculate_end_frame(
                video_fps, total_frames, duration
            )

            # 设置视频滤镜（对应 kingfisher init_filters + video_filter_spec_）
            graph = None
            if self._config.video_filter:
                graph = self._create_filter_graph(video_stream)

            # 逐帧解码（对应 kingfisher InputFile::read_frames + decode_video）
            frames = self._read_and_sample_frames(
                container=container,
                video_stream=video_stream,
                frame_set=frame_set,
                start_frame_offset=start_frame_offset,
                end_frame=end_frame,
                total_frames=total_frames,
                duration=duration,
                graph=graph,
                as_bytes=as_bytes,
            )

            logger.info(f"ffmpeg 解码完成: frames={len(frames)}")
            return frames

        finally:
            if container is not None:
                container.close()
            if tmp_file is not None:
                try:
                    Path(tmp_file).unlink(missing_ok=True)
                except Exception:
                    pass

    def _open_container(self, video_bytes: bytes):
        """打开视频容器

        对应 kingfisher InputFile::open 的功能。
        PyAV 支持直接从内存读取，无需临时文件。

        Args:
            video_bytes: 视频原始字节数据

        Returns:
            tuple: (container, tmp_file_path_or_None)
        """
        import av

        tmp_file = None

        try:
            # 优先尝试从内存直接打开
            buffer = io.BytesIO(video_bytes)
            container = av.open(buffer, format=None)
            return container, tmp_file
        except av.error.InvalidDataError:
            # 某些格式可能不支持从内存流打开，回退到临时文件
            logger.debug("从内存打开失败，回退到临时文件")
        except Exception as e:
            logger.debug(f"从内存打开失败: {e}，回退到临时文件")

        # 回退方案：写入临时文件
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.write(video_bytes)
        tmp.flush()
        tmp.close()
        tmp_file = tmp.name

        container = av.open(tmp_file)
        return container, tmp_file

    @staticmethod
    def _find_video_stream(container):
        """查找第一个视频流

        对应 kingfisher 中 first_video_stream_index_ 的查找逻辑。

        Args:
            container: PyAV 容器对象

        Returns:
            av.VideoStream 或 None
        """
        for stream in container.streams:
            if stream.type == "video":
                return stream
        return None

    def _configure_decoder(self, video_stream):
        """配置解码器参数

        对应 kingfisher InputFile::choose_decoder + InputStream 的配置：
        - 线程数
        - GPU 硬件加速
        - 只解码关键帧

        Args:
            video_stream: PyAV 视频流
        """
        import av

        codec_context = video_stream.codec_context

        # 设置线程数（对应 kingfisher 的线程配置）
        if self._config.thread_count > 0:
            codec_context.thread_count = self._config.thread_count
            codec_context.thread_type = av.codec.context.ThreadType.AUTO

        # 只解码关键帧
        if self._config.keyframes_only:
            codec_context.skip_frame = "NONKEY"

        # GPU 硬件加速（对应 kingfisher InputFile::gpu_id_）
        if self._config.gpu_id >= 0:
            self._try_enable_hw_accel(video_stream)

    def _try_enable_hw_accel(self, video_stream):
        """尝试启用 GPU 硬件加速解码

        对应 kingfisher 的 gpu_id_ 和 auto_switch_to_soft_codec_ 逻辑。
        支持 CUDA/NVDEC 硬件解码器（h264_cuvid, hevc_cuvid 等）。

        Args:
            video_stream: PyAV 视频流
        """
        import av

        codec_name = video_stream.codec_context.codec.name
        # 常见硬件解码器映射（对应 kingfisher ffmpeg_hw.cc 的逻辑）
        hw_codec_map = {
            "h264": "h264_cuvid",
            "hevc": "hevc_cuvid",
            "h265": "hevc_cuvid",
            "vp9": "vp9_cuvid",
            "mpeg4": "mpeg4_cuvid",
            "mpeg2video": "mpeg2_cuvid",
            "mjpeg": "mjpeg_cuvid",
            "av1": "av1_cuvid",
        }

        hw_codec_name = hw_codec_map.get(codec_name)
        if hw_codec_name:
            try:
                hw_codec = av.codec.Codec(hw_codec_name, "r")
                if hw_codec:
                    video_stream.codec_context.codec = hw_codec
                    logger.info(
                        f"启用 GPU 硬件解码: {codec_name} -> {hw_codec_name}, "
                        f"gpu_id={self._config.gpu_id}"
                    )
                    return
            except Exception as e:
                logger.warning(f"GPU 硬件解码器 {hw_codec_name} 不可用: {e}")

        if self._config.auto_switch_to_soft_codec:
            logger.info(f"回退到软件解码: {codec_name}")
        else:
            raise RuntimeError(
                f"GPU 硬件解码器不可用且未启用自动回退: {codec_name}"
            )

    @staticmethod
    def _get_frame_rate(video_stream) -> float:
        """获取视频帧率

        对应 kingfisher InputFile::get_frame_rate：
        优先使用 r_frame_rate（实际帧率），回退到 avg_frame_rate，
        再回退到 codec context framerate。

        Args:
            video_stream: PyAV 视频流

        Returns:
            float: 帧率
        """
        # 优先使用 guessed_rate（对应 r_frame_rate）
        if video_stream.guessed_rate:
            rate = video_stream.guessed_rate
            if rate.numerator and rate.denominator:
                return float(rate)

        # 回退到 average_rate（对应 avg_frame_rate）
        if video_stream.average_rate:
            rate = video_stream.average_rate
            if rate.numerator and rate.denominator:
                return float(rate)

        # 回退到 codec context framerate
        if video_stream.codec_context.framerate:
            rate = video_stream.codec_context.framerate
            if rate.numerator and rate.denominator:
                return float(rate)

        return 30.0  # 默认帧率

    @staticmethod
    def _get_duration(container) -> float:
        """获取视频时长（秒）

        对应 kingfisher InputFile::get_duration。

        Args:
            container: PyAV 容器

        Returns:
            float: 时长（秒）
        """
        if container.duration is not None:
            # container.duration 单位是微秒
            return container.duration / 1_000_000.0
        return 0.0

    @staticmethod
    def _get_total_frames(video_stream, container) -> int:
        """获取总帧数（估算）

        对应 kingfisher InputFile::get_total_frames：
        优先使用 stream.frames，回退到通过时长和帧率估算。

        Args:
            video_stream: PyAV 视频流
            container: PyAV 容器

        Returns:
            int: 总帧数
        """
        # 优先使用 nb_frames
        if video_stream.frames > 0:
            return video_stream.frames

        # 通过时长和帧率估算
        duration = 0.0
        if container.duration is not None:
            duration = container.duration / 1_000_000.0
        elif video_stream.duration is not None and video_stream.time_base:
            duration = float(video_stream.duration * video_stream.time_base)

        if duration > 0:
            fps = FFmpegDecoder._get_frame_rate(video_stream)
            if fps > 0:
                return int(duration * fps)

        return 0

    def _get_effective_total_frames(
        self, total_frames: int, video_fps: float, duration: float
    ) -> int:
        """计算有效帧数（考虑时间范围配置）

        Args:
            total_frames: 原始总帧数
            video_fps: 视频帧率
            duration: 视频时长

        Returns:
            int: 有效帧数
        """
        start = self._config.start_time or 0.0
        end = self._config.end_time

        if self._config.duration is not None:
            end = start + self._config.duration

        if end is not None:
            effective_duration = min(end, duration) - start
        else:
            effective_duration = duration - start

        if effective_duration <= 0:
            return total_frames

        effective_frames = int(effective_duration * video_fps)
        return min(effective_frames, total_frames) if total_frames > 0 else effective_frames

    def _seek_to_start(self, container, video_stream, start_time: float) -> int:
        """Seek 到起始时间位置

        对应 kingfisher InputFile::seek 的逻辑：
        - 将秒转换为流的时间基单位
        - seek 到最近的关键帧
        - 返回起始帧号偏移

        Args:
            container: PyAV 容器
            video_stream: PyAV 视频流
            start_time: 起始时间（秒）

        Returns:
            int: 起始帧号偏移
        """
        # 将秒转换为 stream time_base 单位的 PTS
        # 对应 kingfisher: int64_t seek_target = static_cast<int64_t>(timestamp * AV_TIME_BASE)
        pts = int(start_time / float(video_stream.time_base))

        # 向后 seek 到最近的关键帧（对应 AVSEEK_FLAG_BACKWARD）
        container.seek(pts, stream=video_stream, backward=True)

        # 计算起始帧号偏移
        fps = self._get_frame_rate(video_stream)
        return int(start_time * fps)

    def _calculate_end_frame(
        self, video_fps: float, total_frames: int, duration: float
    ) -> Optional[int]:
        """计算结束帧号

        Args:
            video_fps: 视频帧率
            total_frames: 总帧数
            duration: 视频时长

        Returns:
            Optional[int]: 结束帧号，None 表示不限制
        """
        end_time = self._config.end_time

        if self._config.duration is not None and self._config.start_time is not None:
            end_time = self._config.start_time + self._config.duration
        elif self._config.duration is not None:
            end_time = self._config.duration

        if end_time is not None:
            return int(end_time * video_fps)

        return None

    def _create_filter_graph(self, video_stream):
        """创建视频滤镜图

        对应 kingfisher InputFile::init_filters + video_filter_spec_。

        Args:
            video_stream: PyAV 视频流

        Returns:
            av.filter.Graph: 滤镜图
        """
        import av

        graph = av.filter.Graph()

        # 配置输入 buffer
        buffer = graph.add_buffer(template=video_stream)

        # 解析并添加滤镜
        # 支持 ffmpeg 滤镜语法，如 "scale=1280:720,transpose=1"
        filter_specs = self._config.video_filter.split(",")
        last_filter = buffer
        for spec in filter_specs:
            spec = spec.strip()
            if "=" in spec:
                name, args = spec.split("=", 1)
                filt = graph.add(name.strip(), args.strip())
            else:
                filt = graph.add(spec)
            last_filter.link_to(filt)
            last_filter = filt

        # 添加输出 buffersink
        buffersink = graph.add("buffersink")
        last_filter.link_to(buffersink)

        graph.configure()
        return graph

    def _read_and_sample_frames(
        self,
        container,
        video_stream,
        frame_set: set,
        start_frame_offset: int,
        end_frame: Optional[int],
        total_frames: int,
        duration: float,
        graph,
        as_bytes: bool,
    ) -> list:
        """读取并采样视频帧

        对应 kingfisher InputFile::read_frames 的主循环逻辑：
        - 从容器逐帧读取
        - 按采样索引筛选
        - 进度回调和取消检查
        - 帧格式转换

        Args:
            container: PyAV 容器
            video_stream: 视频流
            frame_set: 需要采样的帧索引集合
            start_frame_offset: 起始帧偏移
            end_frame: 结束帧号
            total_frames: 总帧数
            duration: 视频时长
            graph: 滤镜图（可选）
            as_bytes: 是否返回字节数据

        Returns:
            list: 帧图片列表
        """
        frames = []
        frame_count = 0
        decoded_count = 0

        for frame in container.decode(video_stream):
            # 取消检查（对应 kingfisher is_cancelled）
            if self._cancel_callback and self._cancel_callback():
                logger.info("解码操作已取消")
                break

            decoded_count += 1

            # 将全局帧号调整为有效帧号（考虑 seek 偏移）
            effective_idx = frame_count

            # 检查结束帧
            if end_frame is not None and (start_frame_offset + effective_idx) >= end_frame:
                break

            # 按采样索引筛选
            if effective_idx in frame_set:
                # 应用滤镜（对应 kingfisher send_frame_to_filters）
                if graph is not None:
                    graph.push(frame)
                    try:
                        frame = graph.pull()
                    except av.error.BlockingIOError:
                        frame_count += 1
                        continue
                    except av.error.EOFError:
                        break

                # 转换为 PIL Image（对应 kingfisher Frame 中 AVFrame -> cv::Mat 的转换）
                img = frame.to_image()  # 自动转换为 RGB PIL Image
                img = self._resize_frame(img)

                if as_bytes:
                    frames.append(self._image_to_bytes(img))
                else:
                    frames.append(self._image_to_base64(img))

            frame_count += 1

            # 进度回调（对应 kingfisher progress_callback_）
            if self._progress_callback and frame_count % 10 == 0:
                if total_frames > 0:
                    progress = min(1.0, frame_count / total_frames)
                elif duration > 0 and frame.pts is not None and video_stream.time_base:
                    current_time = float(frame.pts * video_stream.time_base)
                    progress = min(1.0, current_time / duration)
                else:
                    progress = 0.0
                self._progress_callback(progress)

        # 最终进度回调
        if self._progress_callback:
            self._progress_callback(1.0)

        return frames

    # =================== 流式批量读帧 ===================

    def decode_batches(
        self, video_bytes: bytes, batch_size: int = 8
    ) -> Generator[List[str], None, None]:
        """流式批量解码视频帧（base64 输出）

        对应 kingfisher InputFile::read_frames(batch_size) 的循环模式：
        每次 yield 一批帧（最多 batch_size 个），调用者通过 for 循环消费。
        内存占用恒定（只持有当前 batch），适合处理超长视频。

        kingfisher 对应关系::

            // kingfisher C++
            while (!finished) {
                video_frames.clear();
                input_file.read_frames(video_frames, audio_frames, 8, finished);
                // 处理 video_frames...
            }

            # peek Python
            for batch in decoder.decode_batches(video_bytes, batch_size=8):
                for frame_base64 in batch:
                    process(frame_base64)

        Args:
            video_bytes: 视频原始字节数据
            batch_size: 每批帧数，对应 kingfisher read_frames 的 batch_size 参数

        Yields:
            List[str]: 每批帧图片的 base64 字符串列表，最后一批可能不足 batch_size
        """
        yield from self._decode_frames_batched(
            video_bytes, batch_size=batch_size, as_bytes=False
        )

    def decode_batches_to_bytes(
        self, video_bytes: bytes, batch_size: int = 8
    ) -> Generator[List[bytes], None, None]:
        """流式批量解码视频帧（原始字节输出）

        与 decode_batches 相同，但输出为原始字节。

        Args:
            video_bytes: 视频原始字节数据
            batch_size: 每批帧数

        Yields:
            List[bytes]: 每批帧图片的原始字节列表
        """
        yield from self._decode_frames_batched(
            video_bytes, batch_size=batch_size, as_bytes=True
        )

    def _decode_frames_batched(
        self, video_bytes: bytes, batch_size: int = 8, as_bytes: bool = False
    ) -> Generator[list, None, None]:
        """流式批量解码视频帧的内部实现

        对应 kingfisher InputFile::read_batch_frames 的逻辑：
        - 逐帧解码，累积到 batch_size 个帧后 yield
        - 最后不足 batch_size 的帧也会 yield
        - 支持采样、时间范围、滤镜、进度回调、取消等所有功能

        Args:
            video_bytes: 视频原始字节数据
            batch_size: 每批帧数
            as_bytes: 是否返回原始字节

        Yields:
            list: 每批帧图片列表
        """
        import av

        container = None
        tmp_file = None

        try:
            # 打开视频容器
            container, tmp_file = self._open_container(video_bytes)

            # 获取视频流
            video_stream = self._find_video_stream(container)
            if video_stream is None:
                raise RuntimeError("视频中未找到视频流")

            # 配置解码器
            self._configure_decoder(video_stream)

            # 获取视频信息
            video_fps = self._get_frame_rate(video_stream)
            total_frames = self._get_total_frames(video_stream, container)
            duration = self._get_duration(container)

            logger.debug(
                f"ffmpeg 批量解码: total_frames={total_frames}, video_fps={video_fps:.2f}, "
                f"duration={duration:.2f}s, batch_size={batch_size}"
            )

            # 计算采样帧索引
            effective_total = self._get_effective_total_frames(
                total_frames, video_fps, duration
            )
            frame_indices = self._compute_frame_indices(effective_total, video_fps)
            frame_set = set(frame_indices)

            # 可选 seek 到起始位置
            start_frame_offset = 0
            if self._config.start_time is not None:
                start_frame_offset = self._seek_to_start(
                    container, video_stream, self._config.start_time
                )

            # 计算结束帧号
            end_frame = self._calculate_end_frame(
                video_fps, total_frames, duration
            )

            # 设置视频滤镜
            graph = None
            if self._config.video_filter:
                graph = self._create_filter_graph(video_stream)

            # 逐帧解码，累积到 batch_size 后 yield
            # 对应 kingfisher read_batch_frames 中的缓冲区累积逻辑
            batch = []
            frame_count = 0
            decoded_count = 0
            total_yielded = 0

            for frame in container.decode(video_stream):
                # 取消检查
                if self._cancel_callback and self._cancel_callback():
                    logger.info("批量解码操作已取消")
                    break

                decoded_count += 1
                effective_idx = frame_count

                # 检查结束帧
                if end_frame is not None and (start_frame_offset + effective_idx) >= end_frame:
                    break

                # 按采样索引筛选
                if effective_idx in frame_set:
                    # 应用滤镜
                    if graph is not None:
                        graph.push(frame)
                        try:
                            frame = graph.pull()
                        except av.error.BlockingIOError:
                            frame_count += 1
                            continue
                        except av.error.EOFError:
                            break

                    # 转换为 PIL Image
                    img = frame.to_image()
                    img = self._resize_frame(img)

                    if as_bytes:
                        batch.append(self._image_to_bytes(img))
                    else:
                        batch.append(self._image_to_base64(img))

                    # 累积到 batch_size 后 yield（对应 kingfisher read_batch_frames 的返回逻辑）
                    if len(batch) >= batch_size:
                        total_yielded += len(batch)
                        logger.debug(
                            f"yield batch: {len(batch)} 帧, 累计 {total_yielded} 帧"
                        )
                        yield batch
                        batch = []

                frame_count += 1

                # 进度回调
                if self._progress_callback and frame_count % 10 == 0:
                    if total_frames > 0:
                        progress = min(1.0, frame_count / total_frames)
                    elif duration > 0 and frame.pts is not None and video_stream.time_base:
                        current_time = float(frame.pts * video_stream.time_base)
                        progress = min(1.0, current_time / duration)
                    else:
                        progress = 0.0
                    self._progress_callback(progress)

            # yield 最后不足 batch_size 的帧
            if batch:
                total_yielded += len(batch)
                logger.debug(
                    f"yield 最后一批: {len(batch)} 帧, 累计 {total_yielded} 帧"
                )
                yield batch

            # 最终进度回调
            if self._progress_callback:
                self._progress_callback(1.0)

            logger.info(
                f"ffmpeg 批量解码完成: 总计 {total_yielded} 帧, "
                f"batch_size={batch_size}"
            )

        finally:
            if container is not None:
                container.close()
            if tmp_file is not None:
                try:
                    Path(tmp_file).unlink(missing_ok=True)
                except Exception:
                    pass

    # =================== 扩展功能 ===================

    def get_video_info(self, video_bytes: bytes) -> dict:
        """获取视频元信息

        对应 kingfisher InputFile::get_duration/get_frame_rate/get_total_frames。

        Args:
            video_bytes: 视频原始字节数据

        Returns:
            dict: 视频信息字典
        """
        import av

        container = None
        tmp_file = None

        try:
            container, tmp_file = self._open_container(video_bytes)
            video_stream = self._find_video_stream(container)

            info = {
                "duration": self._get_duration(container),
                "total_frames": 0,
                "frame_rate": 0.0,
                "width": 0,
                "height": 0,
                "codec": "",
                "pixel_format": "",
            }

            if video_stream:
                info["total_frames"] = self._get_total_frames(video_stream, container)
                info["frame_rate"] = self._get_frame_rate(video_stream)
                info["width"] = video_stream.codec_context.width
                info["height"] = video_stream.codec_context.height
                info["codec"] = video_stream.codec_context.codec.name
                info["pixel_format"] = (
                    video_stream.codec_context.pix_fmt
                    if hasattr(video_stream.codec_context, "pix_fmt")
                    else ""
                )

            return info

        finally:
            if container is not None:
                container.close()
            if tmp_file is not None:
                try:
                    Path(tmp_file).unlink(missing_ok=True)
                except Exception:
                    pass

    def decode_specific_frames(
        self,
        video_bytes: bytes,
        frame_numbers: List[int],
        as_bytes: bool = False,
    ) -> list:
        """解码指定帧号的帧

        对应 kingfisher InputFile::seek_frame + read_frames 的组合。

        Args:
            video_bytes: 视频原始字节数据
            frame_numbers: 指定帧号列表
            as_bytes: 是否返回字节数据

        Returns:
            list: 帧图片列表
        """
        import av

        container = None
        tmp_file = None

        try:
            container, tmp_file = self._open_container(video_bytes)
            video_stream = self._find_video_stream(container)
            if video_stream is None:
                raise RuntimeError("视频中未找到视频流")

            self._configure_decoder(video_stream)
            target_set = set(frame_numbers)

            frames = []
            frame_count = 0
            max_target = max(frame_numbers) if frame_numbers else 0

            for frame in container.decode(video_stream):
                if frame_count > max_target:
                    break

                if frame_count in target_set:
                    img = frame.to_image()
                    img = self._resize_frame(img)
                    if as_bytes:
                        frames.append(self._image_to_bytes(img))
                    else:
                        frames.append(self._image_to_base64(img))

                frame_count += 1

            return frames

        finally:
            if container is not None:
                container.close()
            if tmp_file is not None:
                try:
                    Path(tmp_file).unlink(missing_ok=True)
                except Exception:
                    pass

    def decode_time_range(
        self,
        video_bytes: bytes,
        start_time: float,
        end_time: Optional[float] = None,
        duration: Optional[float] = None,
        as_bytes: bool = False,
    ) -> list:
        """解码指定时间范围内的帧

        对应 kingfisher InputFile::seek + read_frames 的组合。

        Args:
            video_bytes: 视频原始字节数据
            start_time: 起始时间（秒）
            end_time: 结束时间（秒）
            duration: 时长（秒），与 end_time 二选一
            as_bytes: 是否返回字节数据

        Returns:
            list: 帧图片列表
        """
        # 临时修改配置
        original_config = self._config
        self._config = DecodeConfig(
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            gpu_id=original_config.gpu_id,
            auto_switch_to_soft_codec=original_config.auto_switch_to_soft_codec,
            video_filter=original_config.video_filter,
            thread_count=original_config.thread_count,
            keyframes_only=original_config.keyframes_only,
        )

        try:
            if as_bytes:
                return self.decode_to_bytes(video_bytes)
            else:
                return self.decode(video_bytes)
        finally:
            self._config = original_config
