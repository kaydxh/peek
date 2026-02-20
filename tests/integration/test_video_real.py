# -*- coding: utf-8 -*-
"""Video 模块集成测试 - 使用真实视频文件 bodyhead.text.mp4

对 video 模块的所有功能进行端到端的真实测试，不使用 mock。
需要测试数据文件：tests/testdata/bodyhead.text.mp4
"""

import base64
import io
import logging
import os
import shutil
from pathlib import Path

import pytest
from PIL import Image

# =================== 测试数据路径 ===================

TESTDATA_DIR = Path(__file__).parent.parent / "testdata"
VIDEO_PATH = TESTDATA_DIR / "bodyhead.text.mp4"
VIDEO_EXISTS = VIDEO_PATH.exists()

# 跳过条件：视频文件不存在时自动跳过
skip_no_video = pytest.mark.skipif(
    not VIDEO_EXISTS,
    reason=f"测试视频文件不存在: {VIDEO_PATH}",
)

# 检测外部依赖是否可用
def _has_module(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False

def _has_ffmpeg_cli():
    """检查 ffmpeg/ffprobe 可执行文件是否可用"""
    import subprocess
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

def _has_ffprobe_cli():
    """检查 ffprobe 可执行文件是否可用"""
    import subprocess
    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

HAS_DECORD = _has_module("decord")
HAS_OPENCV = _has_module("cv2")
HAS_AV = _has_module("av")
HAS_FFMPEG_CLI = _has_ffmpeg_cli()
HAS_FFPROBE = _has_ffprobe_cli()

skip_no_decord = pytest.mark.skipif(not HAS_DECORD, reason="decord 未安装")
skip_no_opencv = pytest.mark.skipif(not HAS_OPENCV, reason="opencv-python 未安装")
skip_no_av = pytest.mark.skipif(not HAS_AV, reason="av (PyAV) 未安装")
skip_no_ffmpeg_cli = pytest.mark.skipif(not HAS_FFMPEG_CLI, reason="ffmpeg CLI 未安装")
skip_no_ffprobe = pytest.mark.skipif(not HAS_FFPROBE, reason="ffprobe CLI 未安装")

logger = logging.getLogger(__name__)


# =================== Fixtures ===================


@pytest.fixture(scope="module")
def video_path():
    """真实视频文件路径"""
    return str(VIDEO_PATH)


@pytest.fixture(scope="module")
def video_bytes():
    """真实视频的字节数据"""
    return VIDEO_PATH.read_bytes()


@pytest.fixture(scope="module")
def video_base64(video_bytes):
    """真实视频的 base64 编码"""
    return base64.b64encode(video_bytes).decode("utf-8")


@pytest.fixture
def output_dir(tmp_path):
    """临时输出目录"""
    return tmp_path


# =================== 1. VideoInfo 探测测试 ===================


@skip_no_video
class TestVideoInfoReal:
    """使用真实视频测试 info.probe"""

    @skip_no_ffprobe

    def test_probe_ffprobe(self, video_path):
        """ffprobe 后端探测视频信息（需要 ffprobe CLI）"""
        from peek.cv.video.info import probe

        info = probe(video_path, backend="ffprobe")

        # 基本信息检查
        assert info.duration > 0, "视频时长应大于 0"
        assert info.width > 0, "视频宽度应大于 0"
        assert info.height > 0, "视频高度应大于 0"
        assert info.fps > 0, "帧率应大于 0"
        assert info.total_frames > 0, "总帧数应大于 0"
        assert info.has_video, "应包含视频流"
        assert info.video_codec != "", "视频编码不应为空"
        assert info.format_name != "", "容器格式不应为空"

        # 分辨率字符串
        assert "x" in info.resolution

        logger.info(f"\n{info}")

    @skip_no_opencv
    def test_probe_opencv(self, video_path):
        """opencv 后端探测视频信息（需要 opencv）"""
        from peek.cv.video.info import probe

        info = probe(video_path, backend="opencv")

        assert info.duration > 0
        assert info.width > 0
        assert info.height > 0
        assert info.fps > 0
        assert info.total_frames > 0

        logger.info(
            f"opencv 探测: {info.resolution}, "
            f"fps={info.fps:.2f}, duration={info.duration:.2f}s, "
            f"frames={info.total_frames}"
        )

    @pytest.mark.skipif(not (HAS_FFPROBE and HAS_OPENCV), reason="需要 ffprobe + opencv")
    def test_probe_consistency(self, video_path):
        """两种后端的探测结果应基本一致"""
        from peek.cv.video.info import probe

        info_ffprobe = probe(video_path, backend="ffprobe")
        info_opencv = probe(video_path, backend="opencv")

        # 分辨率应完全一致
        assert info_ffprobe.width == info_opencv.width
        assert info_ffprobe.height == info_opencv.height

        # 帧率应接近（允许 0.1 误差）
        assert abs(info_ffprobe.fps - info_opencv.fps) < 0.5

        # 时长应接近（允许 1 秒误差）
        assert abs(info_ffprobe.duration - info_opencv.duration) < 1.0


# =================== 2. 解码器测试 ===================


@skip_no_video
@skip_no_decord
class TestDecordDecoderReal:
    """使用真实视频测试 DecordDecoder（需要 decord）"""

    def test_decode_basic(self, video_bytes):
        """基本解码（base64 输出）"""
        from peek.cv.video.decoder.decord_decoder import DecordDecoder

        decoder = DecordDecoder(fps=0.5, max_frames=5)
        frames = decoder.decode(video_bytes)

        assert isinstance(frames, list)
        assert len(frames) > 0
        assert len(frames) <= 5

        # 验证每一帧都是有效的 base64 图片
        for i, frame_b64 in enumerate(frames):
            img_bytes = base64.b64decode(frame_b64)
            img = Image.open(io.BytesIO(img_bytes))
            assert img.size[0] > 0 and img.size[1] > 0
            logger.info(f"  帧 {i}: {img.size[0]}x{img.size[1]}, {img.mode}")

    def test_decode_to_bytes(self, video_bytes):
        """解码为字节输出"""
        from peek.cv.video.decoder.decord_decoder import DecordDecoder

        decoder = DecordDecoder(fps=0.5, max_frames=3)
        frames = decoder.decode_to_bytes(video_bytes)

        assert isinstance(frames, list)
        assert len(frames) > 0

        for frame_bytes in frames:
            assert isinstance(frame_bytes, bytes)
            img = Image.open(io.BytesIO(frame_bytes))
            assert img.size[0] > 0

    def test_decode_with_resize(self, video_bytes):
        """带分辨率缩放的解码"""
        from peek.cv.video.decoder.decord_decoder import DecordDecoder

        size = {"shortest_edge": 50000, "longest_edge": 200000}
        decoder = DecordDecoder(fps=0.5, max_frames=2, size=size)
        frames = decoder.decode_to_bytes(video_bytes)

        assert len(frames) > 0
        for frame_bytes in frames:
            img = Image.open(io.BytesIO(frame_bytes))
            pixels = img.size[0] * img.size[1]
            logger.info(f"  缩放后: {img.size[0]}x{img.size[1]}, pixels={pixels}")
            # 像素总数应在合理范围内
            assert pixels <= 200000 + 28 * 28 * 4  # 允许 patch 对齐误差


@skip_no_video
@skip_no_opencv
class TestOpenCVDecoderReal:
    """使用真实视频测试 OpenCVDecoder（需要 opencv）"""

    def test_decode_basic(self, video_bytes):
        """基本解码"""
        from peek.cv.video.decoder.opencv_decoder import OpenCVDecoder

        decoder = OpenCVDecoder(fps=0.5, max_frames=5)
        frames = decoder.decode(video_bytes)

        assert isinstance(frames, list)
        assert len(frames) > 0
        assert len(frames) <= 5

        # 验证第一帧
        img_bytes = base64.b64decode(frames[0])
        img = Image.open(io.BytesIO(img_bytes))
        assert img.size[0] > 0
        logger.info(f"opencv 解码: {len(frames)} 帧, 第一帧 {img.size[0]}x{img.size[1]}")

    def test_decode_to_bytes(self, video_bytes):
        """解码为字节输出"""
        from peek.cv.video.decoder.opencv_decoder import OpenCVDecoder

        decoder = OpenCVDecoder(fps=0.5, max_frames=3)
        frames = decoder.decode_to_bytes(video_bytes)

        assert len(frames) > 0
        for fb in frames:
            assert isinstance(fb, bytes)


@skip_no_video
@skip_no_av
class TestFFmpegDecoderReal:
    """使用真实视频测试 FFmpegDecoder（需要 PyAV）"""

    def test_decode_basic(self, video_bytes):
        """基本解码"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        decoder = FFmpegDecoder(fps=0.5, max_frames=5)
        frames = decoder.decode(video_bytes)

        assert isinstance(frames, list)
        assert len(frames) > 0
        assert len(frames) <= 5

        img_bytes = base64.b64decode(frames[0])
        img = Image.open(io.BytesIO(img_bytes))
        assert img.size[0] > 0
        logger.info(f"ffmpeg 解码: {len(frames)} 帧, 第一帧 {img.size[0]}x{img.size[1]}")

    def test_decode_to_bytes(self, video_bytes):
        """解码为字节输出"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        decoder = FFmpegDecoder(fps=0.5, max_frames=3)
        frames = decoder.decode_to_bytes(video_bytes)

        assert len(frames) > 0
        for fb in frames:
            assert isinstance(fb, bytes)

    def test_decode_with_time_range(self, video_bytes):
        """指定时间范围解码"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder, DecodeConfig

        config = DecodeConfig(start_time=1.0, duration=3.0)
        decoder = FFmpegDecoder(fps=1.0, max_frames=10, decode_config=config)
        frames = decoder.decode(video_bytes)

        assert len(frames) > 0
        logger.info(f"时间范围解码: {len(frames)} 帧 (1.0s ~ 4.0s)")

    def test_decode_with_filter(self, video_bytes):
        """带视频滤镜的解码"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder, DecodeConfig

        config = DecodeConfig(video_filter="scale=320:240")
        decoder = FFmpegDecoder(fps=0.5, max_frames=2, decode_config=config)
        frames = decoder.decode_to_bytes(video_bytes)

        assert len(frames) > 0
        img = Image.open(io.BytesIO(frames[0]))
        assert img.size == (320, 240), f"滤镜缩放后尺寸应为 320x240，实际: {img.size}"
        logger.info(f"滤镜解码: {img.size[0]}x{img.size[1]}")

    def test_decode_keyframes_only(self, video_bytes):
        """仅解码关键帧"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder, DecodeConfig

        config = DecodeConfig(keyframes_only=True)
        decoder = FFmpegDecoder(fps=0.5, max_frames=5, decode_config=config)
        frames = decoder.decode(video_bytes)

        assert isinstance(frames, list)
        logger.info(f"关键帧解码: {len(frames)} 帧")

    def test_get_video_info(self, video_bytes):
        """获取视频元信息"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        decoder = FFmpegDecoder()
        info = decoder.get_video_info(video_bytes)

        assert info["duration"] > 0
        assert info["width"] > 0
        assert info["height"] > 0
        assert info["frame_rate"] > 0
        assert info["codec"] != ""

        logger.info(
            f"视频信息: {info['width']}x{info['height']}, "
            f"fps={info['frame_rate']:.2f}, duration={info['duration']:.2f}s, "
            f"codec={info['codec']}"
        )

    def test_decode_specific_frames(self, video_bytes):
        """解码指定帧号"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        decoder = FFmpegDecoder()
        frames = decoder.decode_specific_frames(
            video_bytes, frame_numbers=[0, 10, 30]
        )

        assert len(frames) == 3
        for i, fb64 in enumerate(frames):
            img_bytes = base64.b64decode(fb64)
            img = Image.open(io.BytesIO(img_bytes))
            logger.info(f"  帧 [{0, 10, 30}[{i}]]: {img.size[0]}x{img.size[1]}")

    def test_decode_with_progress(self, video_bytes):
        """带进度回调的解码"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        progress_values = []

        def on_progress(p):
            progress_values.append(p)

        decoder = FFmpegDecoder(
            fps=0.5, max_frames=3,
            progress_callback=on_progress,
        )
        frames = decoder.decode(video_bytes)

        assert len(frames) > 0
        # 最后一次回调应为 1.0
        assert progress_values[-1] == 1.0
        logger.info(f"进度回调次数: {len(progress_values)}")

    def test_decode_with_cancel(self, video_bytes):
        """取消解码"""
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        call_count = [0]

        def cancel_after_1():
            call_count[0] += 1
            return call_count[0] > 1  # 第 2 次检查时取消

        decoder = FFmpegDecoder(
            fps=30.0, max_frames=-1,  # 高频率以便触发取消
            cancel_callback=cancel_after_1,
        )
        frames = decoder.decode(video_bytes)

        # 应该只解码了很少的帧就取消了
        logger.info(f"取消解码: 解码了 {len(frames)} 帧后取消")


# =================== 3. VideoDecoder 门面类测试 ===================


@skip_no_video
class TestVideoDecoderFacadeReal:
    """使用真实视频测试 VideoDecoder 门面类"""

    @skip_no_decord
    def test_decord_facade(self, video_base64):
        """通过门面类使用 decord 解码"""
        from peek.cv.video import VideoDecoder

        vd = VideoDecoder(method="decord", fps=0.5, max_frames=3)
        frames = vd.decode(video_base64)

        assert frames is not None
        assert len(frames) > 0
        assert len(frames) <= 3
        logger.info(f"门面 decord: {len(frames)} 帧")

    @skip_no_opencv
    def test_opencv_facade(self, video_base64):
        """通过门面类使用 opencv 解码"""
        from peek.cv.video import VideoDecoder

        vd = VideoDecoder(method="opencv", fps=0.5, max_frames=3)
        frames = vd.decode(video_base64)

        assert frames is not None
        assert len(frames) > 0
        logger.info(f"门面 opencv: {len(frames)} 帧")

    @skip_no_av
    def test_ffmpeg_facade(self, video_base64):
        """通过门面类使用 ffmpeg 解码"""
        from peek.cv.video import VideoDecoder

        vd = VideoDecoder(method="ffmpeg", fps=0.5, max_frames=3)
        frames = vd.decode(video_base64)

        assert frames is not None
        assert len(frames) > 0
        logger.info(f"门面 ffmpeg: {len(frames)} 帧")

    @skip_no_av
    def test_ffmpeg_facade_with_config(self, video_base64):
        """通过门面类使用 ffmpeg + 时间范围配置"""
        from peek.cv.video import VideoDecoder
        from peek.cv.video.decoder.ffmpeg_decoder import DecodeConfig

        config = DecodeConfig(start_time=0.0, duration=2.0)
        vd = VideoDecoder(method="ffmpeg", fps=1.0, max_frames=5, decode_config=config)
        frames = vd.decode(video_base64)

        assert frames is not None
        assert len(frames) > 0
        logger.info(f"门面 ffmpeg+config: {len(frames)} 帧")

    @skip_no_av
    def test_decode_to_bytes_facade(self, video_base64):
        """门面类 decode_to_bytes"""
        from peek.cv.video import VideoDecoder

        vd = VideoDecoder(method="ffmpeg", fps=0.5, max_frames=2)
        frames = vd.decode_to_bytes(video_base64)

        assert frames is not None
        assert len(frames) > 0
        for fb in frames:
            assert isinstance(fb, bytes)


# =================== 4. VideoClip 截取测试 ===================


@skip_no_video
@skip_no_ffmpeg_cli
class TestVideoClipReal:
    """使用真实视频测试 VideoClip（需要 ffmpeg CLI）"""

    def test_cut_by_time_range(self, video_path, output_dir):
        """按时间范围截取"""
        from peek.cv.video.clip import VideoClip

        output = str(output_dir / "cut_output.mp4")
        result = VideoClip.cut(
            video_path, output,
            start=1.0, end=3.0,
            accurate=True, copy_codec=True,
        )

        assert Path(result).exists()
        assert Path(result).stat().st_size > 0

        # 验证截取后的视频时长
        from peek.cv.video.info import probe
        info = probe(result)
        assert 1.0 <= info.duration <= 4.0  # 允许一些误差
        logger.info(f"截取结果: duration={info.duration:.2f}s, size={Path(result).stat().st_size}")

    def test_cut_by_duration(self, video_path, output_dir):
        """按时长截取"""
        from peek.cv.video.clip import VideoClip

        output = str(output_dir / "cut_duration.mp4")
        result = VideoClip.cut(
            video_path, output,
            start=0.0, duration=2.0,
            copy_codec=True,
        )

        assert Path(result).exists()
        assert Path(result).stat().st_size > 0

    def test_cut_fast_mode(self, video_path, output_dir):
        """快速模式截取（基于关键帧）"""
        from peek.cv.video.clip import VideoClip

        output = str(output_dir / "cut_fast.mp4")
        result = VideoClip.cut(
            video_path, output,
            start=2.0, duration=3.0,
            accurate=False, copy_codec=True,
        )

        assert Path(result).exists()

    def test_split_video(self, video_path, output_dir):
        """视频分割"""
        from peek.cv.video.clip import VideoClip

        segments = VideoClip.split(
            video_path, str(output_dir),
            segment_duration=5.0,
        )

        assert len(segments) > 0
        for seg in segments:
            assert Path(seg).exists()
            assert Path(seg).stat().st_size > 0

        logger.info(f"分割为 {len(segments)} 个片段")


# =================== 5. VideoFilter 滤镜测试 ===================


@skip_no_video
@skip_no_ffmpeg_cli
class TestVideoFilterReal:
    """使用真实视频测试 VideoFilter 链式滤镜（需要 ffmpeg CLI）"""

    def test_scale_filter(self, video_path, output_dir):
        """缩放滤镜"""
        from peek.cv.video.filter.scale import ScaleFilter

        output = str(output_dir / "scaled.mp4")
        result = ScaleFilter.apply(
            video_path, output,
            width=640, height=360,
        )

        assert Path(result).exists()

        from peek.cv.video.info import probe
        info = probe(result)
        assert info.width == 640
        assert info.height == 360
        logger.info(f"缩放: {info.resolution}")

    def test_scale_keep_aspect(self, video_path, output_dir):
        """保持宽高比缩放"""
        from peek.cv.video.filter.scale import ScaleFilter

        output = str(output_dir / "scaled_aspect.mp4")
        result = ScaleFilter.apply(
            video_path, output,
            width=640, height=-2,  # 保持比例且偶数
        )

        assert Path(result).exists()

        from peek.cv.video.info import probe
        info = probe(result)
        assert info.width == 640
        assert info.height > 0
        assert info.height % 2 == 0  # 偶数
        logger.info(f"保持宽高比缩放: {info.resolution}")

    def test_crop_filter(self, video_path, output_dir):
        """裁剪滤镜"""
        from peek.cv.video.filter.crop import CropFilter

        output = str(output_dir / "cropped.mp4")
        result = CropFilter.apply(
            video_path, output,
            x=100, y=50, width=400, height=300,
        )

        assert Path(result).exists()

        from peek.cv.video.info import probe
        info = probe(result)
        assert info.width == 400
        assert info.height == 300
        logger.info(f"裁剪: {info.resolution}")

    def test_center_crop_filter(self, video_path, output_dir):
        """居中裁剪"""
        from peek.cv.video.filter.crop import CropFilter

        output = str(output_dir / "center_cropped.mp4")
        result = CropFilter.apply(
            video_path, output,
            center_crop=True, out_width=400, out_height=300,
        )

        assert Path(result).exists()

        from peek.cv.video.info import probe
        info = probe(result)
        assert info.width == 400
        assert info.height == 300

    def test_transform_hflip(self, video_path, output_dir):
        """水平翻转"""
        from peek.cv.video.filter.transform import TransformFilter

        output = str(output_dir / "hflip.mp4")
        result = TransformFilter.apply(
            video_path, output,
            hflip=True,
        )

        assert Path(result).exists()

        # 翻转不改变分辨率
        from peek.cv.video.info import probe
        info_orig = probe(video_path)
        info_flip = probe(result)
        assert info_flip.width == info_orig.width
        assert info_flip.height == info_orig.height

    def test_transform_rotate_90(self, video_path, output_dir):
        """旋转 90 度"""
        from peek.cv.video.filter.transform import TransformFilter

        output = str(output_dir / "rotate90.mp4")
        result = TransformFilter.apply(
            video_path, output,
            rotation_angle=90,
        )

        assert Path(result).exists()

        # 旋转 90 度后宽高互换
        from peek.cv.video.info import probe
        info_orig = probe(video_path)
        info_rot = probe(result)
        assert info_rot.width == info_orig.height
        assert info_rot.height == info_orig.width
        logger.info(f"旋转 90°: {info_orig.resolution} -> {info_rot.resolution}")

    def test_video_filter_chain(self, video_path, output_dir):
        """链式滤镜组合"""
        from peek.cv.video.filter import VideoFilter

        output = str(output_dir / "chain_output.mp4")
        result = (
            VideoFilter(video_path)
            .scale(640, -2)
            .hflip()
            .output(output)
        )

        assert Path(result).exists()

        from peek.cv.video.info import probe
        info = probe(result)
        assert info.width == 640
        logger.info(f"链式滤镜: {info.resolution}")

    def test_video_filter_scale_crop_chain(self, video_path, output_dir):
        """链式: 缩放 + 居中裁剪"""
        from peek.cv.video.filter import VideoFilter

        output = str(output_dir / "scale_crop.mp4")
        result = (
            VideoFilter(video_path)
            .scale(800, -2)
            .crop(center_crop=True, out_width=400, out_height=300)
            .output(output)
        )

        assert Path(result).exists()

        from peek.cv.video.info import probe
        info = probe(result)
        assert info.width == 400
        assert info.height == 300


# =================== 6. 解码器一致性测试 ===================


@skip_no_video
@pytest.mark.skipif(
    not (HAS_DECORD and HAS_OPENCV and HAS_AV),
    reason="需要同时安装 decord + opencv + av 才能进行一致性对比",
)
class TestDecoderConsistency:
    """对比三种解码器的输出一致性（需要 decord + opencv + av）"""

    def test_frame_count_consistency(self, video_bytes):
        """三种解码器的帧数应一致"""
        from peek.cv.video.decoder.decord_decoder import DecordDecoder
        from peek.cv.video.decoder.opencv_decoder import OpenCVDecoder
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        fps, max_frames = 0.5, 5

        decord_frames = DecordDecoder(fps=fps, max_frames=max_frames).decode(video_bytes)
        opencv_frames = OpenCVDecoder(fps=fps, max_frames=max_frames).decode(video_bytes)
        ffmpeg_frames = FFmpegDecoder(fps=fps, max_frames=max_frames).decode(video_bytes)

        logger.info(
            f"帧数对比: decord={len(decord_frames)}, "
            f"opencv={len(opencv_frames)}, ffmpeg={len(ffmpeg_frames)}"
        )

        # 三种解码器的帧数应相等（允许 ±1 的差异，因为采样策略可能略有不同）
        assert abs(len(decord_frames) - len(opencv_frames)) <= 1
        assert abs(len(decord_frames) - len(ffmpeg_frames)) <= 1

    def test_frame_size_consistency(self, video_bytes):
        """三种解码器输出帧的分辨率应一致"""
        import io as _io
        from peek.cv.video.decoder.decord_decoder import DecordDecoder
        from peek.cv.video.decoder.opencv_decoder import OpenCVDecoder
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder

        fps, max_frames = 0.5, 1

        decord_frames = DecordDecoder(fps=fps, max_frames=max_frames).decode_to_bytes(video_bytes)
        opencv_frames = OpenCVDecoder(fps=fps, max_frames=max_frames).decode_to_bytes(video_bytes)
        ffmpeg_frames = FFmpegDecoder(fps=fps, max_frames=max_frames).decode_to_bytes(video_bytes)

        decord_img = Image.open(_io.BytesIO(decord_frames[0]))
        opencv_img = Image.open(_io.BytesIO(opencv_frames[0]))
        ffmpeg_img = Image.open(_io.BytesIO(ffmpeg_frames[0]))

        logger.info(
            f"分辨率对比: decord={decord_img.size}, "
            f"opencv={opencv_img.size}, ffmpeg={ffmpeg_img.size}"
        )

        # 分辨率应一致
        assert decord_img.size == opencv_img.size
        assert decord_img.size == ffmpeg_img.size


# =================== 7. smart_resize 与真实帧结合测试 ===================


@skip_no_video
@skip_no_av
class TestSmartResizeWithRealFrames:
    """使用真实视频帧测试 smart_resize（需要 PyAV）"""

    def test_resize_decoded_frame(self, video_bytes):
        """对真实解码帧应用 smart_resize"""
        import io as _io
        from peek.cv.video.decoder.ffmpeg_decoder import FFmpegDecoder
        from peek.cv.video.resize import smart_resize_image

        decoder = FFmpegDecoder(fps=0.5, max_frames=1)
        frames = decoder.decode_to_bytes(video_bytes)
        assert len(frames) > 0

        img = Image.open(_io.BytesIO(frames[0]))
        orig_w, orig_h = img.size
        logger.info(f"原始帧: {orig_w}x{orig_h}, pixels={orig_w * orig_h}")

        # 缩小
        resized = smart_resize_image(img, shortest_edge=0, longest_edge=100000)
        new_w, new_h = resized.size
        logger.info(f"缩放后: {new_w}x{new_h}, pixels={new_w * new_h}")

        assert new_w * new_h <= 100000 + 28 * 28 * 4
        assert new_w % 28 == 0
        assert new_h % 28 == 0


