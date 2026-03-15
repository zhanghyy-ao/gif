"""
通义千问视频生成模块（升级：支持导演式提示词与 GIF 约束）
"""
import os
import time
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
import asyncio
import requests

logger = logging.getLogger(__name__)


class QwenVideoGenerator:
    def __init__(self, api_key: Optional[str] = None, output_dir: str = "./outputs"):
        self.api_key = api_key or os.getenv('DASHSCOPE_API_KEY')
        if not self.api_key:
            raise ValueError("需要提供API密钥或设置DASHSCOPE_API_KEY环境变量")
        self.base_url = "https://dashscope.aliyuncs.com/api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate_video_from_concept(
        self,
        concept_name: str,
        description: str,
        visual_type: str,
        output_dir: str = "./outputs",
        duration: int = 6,
        resolution: str = "720p",
        style: str = "educational",
        override_prompt: Optional[str] = None,
        gif_fps: int = 24,
        gif_width: int = 720,
    ) -> Dict[str, Any]:
        prompt = override_prompt or self._build_video_prompt(
            concept_name=concept_name,
            description=description,
            visual_type=visual_type,
            style=style
        )
        try:
            video_url = await self._call_video_generation_api(
                prompt=prompt,
                duration=duration,
                resolution=resolution,
                style=style
            )
            if not video_url:
                raise Exception("视频生成失败：未获取到视频URL")

            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            safe_name = concept_name.replace(' ', '_')
            video_filename = f"{safe_name}_{int(time.time())}.mp4"
            video_path = output_path / video_filename

            await self._download_video(video_url, str(video_path))

            gif_path = await self._convert_to_gif(
                str(video_path),
                str(output_path / f"{video_filename.replace('.mp4', '.gif')}"),
                fps=gif_fps,
                width=gif_width,
            )

            return {
                "success": True,
                "video_path": str(video_path),
                "gif_path": gif_path,
                "prompt": prompt,
                "concept_name": concept_name
            }
        except Exception as e:
            logger.error(f"视频生成失败: {e}")
            return {"success": False, "error": str(e), "concept_name": concept_name}

    def _build_video_prompt(self, concept_name: str, description: str, visual_type: str, style: str = "educational") -> str:
        style_descriptions = {
            "realistic": "photorealistic, highly detailed, professional photography",
            "animation": "smooth animation, vibrant colors, cartoon style",
            "3d": "3D rendered, cinematic lighting, high quality CGI",
            "cinematic": "cinematic shot, movie quality, dramatic lighting",
            "educational": "clean educational visualization, clear diagram, academic style"
        }
        type_enhancements = {
            "flow_chart": "showing dynamic process flow with moving elements and glowing paths",
            "diagram": "technical diagram with animated components and clear labels",
            "network": "interconnected nodes with data flowing through edges",
            "tree": "growing hierarchical structure with branching animation",
            "formula_animation": "mathematical symbols transforming and evolving",
            "graph": "dynamic data visualization with moving curves and points",
            "comparison": "side-by-side comparison with highlighting differences",
            "scene_animation": "physical scene with realistic movement and interactions"
        }
        style_desc = style_descriptions.get(style, style_descriptions["educational"])
        type_enhancement = type_enhancements.get(visual_type, "dynamic visualization")
        prompt = f"""
{concept_name}: {description}
Visual Style: {style_desc}
Animation Type: {type_enhancement}
Key Features: Smooth motion; clear hierarchy; academic tone
Camera: dynamic pans/zooms; Lighting: soft studio; BG: clean
"""
        return prompt.strip()

    async def _call_video_generation_api(self, prompt: str, duration: int = 6, resolution: str = "720p", style: str = "educational") -> Optional[str]:
        url = f"{self.base_url}/services/aigc/video-generation/video-synthesis"
        model = "wanx2.1-t2v-turbo"
        size = "1280*720"
        payload = {"model": model, "input": {"prompt": prompt}, "parameters": {"size": size}}
        headers = {**self.headers, "X-DashScope-Async": "enable"}
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: requests.post(url, headers=headers, json=payload, timeout=60))
        if response.status_code != 200:
            logger.error(f"API调用失败: {response.status_code} - {response.text}")
            return None
        result = response.json()
        task_id = result.get("output", {}).get("task_id") or result.get("task_id")
        if not task_id:
            logger.error(f"响应中未找到task_id: {result}")
            return None
        return await self._poll_task_result(task_id)

    async def _poll_task_result(self, task_id: str, max_attempts: int = 120) -> Optional[str]:
        url = f"{self.base_url}/tasks/{task_id}"
        for attempt in range(max_attempts):
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: requests.get(url, headers=self.headers, timeout=30))
            if response.status_code != 200:
                logger.error(f"查询任务失败: {response.status_code} - {response.text}")
                return None
            result = response.json()
            output = result.get("output", {})
            status = output.get("task_status") or output.get("status") or result.get("status")
            if status == "SUCCEEDED":
                return output.get("video_url")
            if status == "FAILED":
                logger.error(f"任务失败: {output.get('message') or result.get('message', '未知错误')}")
                return None
            await asyncio.sleep(5)
        logger.error(f"任务轮询超时: {task_id}")
        return None

    async def _download_video(self, video_url: str, output_path: str):
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: requests.get(video_url, stream=True, timeout=120))
        if response.status_code != 200:
            raise Exception(f"下载失败: {response.status_code}")
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    async def _convert_to_gif(self, video_path: str, gif_path: str, fps: int = 24, width: int = 720) -> str:
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
            import asyncio.subprocess
            ffmpeg_path = get_ffmpeg_exe()
            vf = f"fps={fps},scale={width}:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer"
            cmd = [ffmpeg_path, "-i", video_path, "-vf", vf, "-loop", "0", "-y", gif_path]
            p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            _, err = await p.communicate()
            if p.returncode != 0:
                raise Exception(err.decode() if err else "未知错误")
            return gif_path
        except Exception as e:
            logger.error(f"GIF转换失败: {e}")
            return video_path
