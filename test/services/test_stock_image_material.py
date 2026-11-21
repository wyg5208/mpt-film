# -*- coding: utf-8 -*-
"""库存图片下载源（Pexels/Pixabay 图片）契约测试。

与库存视频共用同一批 API Key，但检索图片库；复用按需图片编排（逐张渲染
成片段、凑够时长即停），免费源语义：搜索/下载/解码/渲染失败跳过候选或
关键词，不触发付费终止；搜索参与 24 小时缓存（CDN 直链稳定）。全部用
unittest.mock 替换 requests，CI 不依赖真实网络与真实 API Key。
"""
import io
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import requests
from PIL import Image

from app.config import config
from app.services import material, task


def _png_bytes(width=64, height=96, color=(120, 40, 200)):
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _search_response(payload, status_code=200):
    return SimpleNamespace(
        json=lambda: payload, status_code=status_code, headers={}
    )


def _download_response(content, status_code=200):
    return SimpleNamespace(
        status_code=status_code,
        content=content,
        headers={"Content-Length": str(len(content))},
        iter_content=lambda chunk_size: iter((content,)),
        close=lambda: None,
    )


def _candidate(provider, url, duration=5):
    item = material.MaterialInfo()
    item.provider = provider
    item.url = url
    item.duration = duration
    item.source_info = {
        "provider": provider,
        "search_term": "term",
        "asset_id": "11",
        "rendition": {"id": None, "width": 2000, "height": 3000},
    }
    return item


class _StockImageTestCase(unittest.TestCase):
    def setUp(self):
        self.original_app_config = dict(config.app)
        self.original_proxy_config = dict(config.proxy)
        self.save_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.save_dir, ignore_errors=True)
        config.app["pexels_api_keys"] = ["pexels-test-key"]
        config.app["pixabay_api_keys"] = ["pixabay-test-key"]
        config.app.pop("tls_verify", None)
        config.proxy.clear()

    def tearDown(self):
        config.app.clear()
        config.app.update(self.original_app_config)
        config.proxy.clear()
        config.proxy.update(self.original_proxy_config)


class TestStockImageSearch(_StockImageTestCase):
    def test_stock_image_sources_mapping_and_task_whitelist(self):
        """业务值到 Key 前缀的映射是契约；任务层白名单必须放行两个新源。"""
        self.assertEqual(
            material.STOCK_IMAGE_SOURCES,
            {"pexels_image": "pexels", "pixabay_image": "pixabay"},
        )
        for source in material.STOCK_IMAGE_SOURCES:
            self.assertIn(source, task._SUPPORTED_VIDEO_SOURCES)

    def test_search_images_pexels_request_and_candidates(self):
        """Pexels 图片检索：鉴权头、方向参数、宽高过滤与来源记录。"""
        payload = {
            "photos": [
                {
                    "id": 11,
                    "width": 2000,
                    "height": 3000,
                    "src": {
                        "large2x": "https://images.pexels.com/photos/11/l2x.jpeg",
                        "large": "https://images.pexels.com/photos/11/l.jpeg",
                        "original": "https://images.pexels.com/photos/11/o.jpeg",
                    },
                    "url": "https://www.pexels.com/photo/11/",
                    "photographer": "Alice",
                },
                {
                    "id": 12,
                    "width": 3000,
                    "height": 2000,
                    "src": {
                        "large2x": "https://images.pexels.com/photos/12/l2x.jpeg"
                    },
                    "url": "https://www.pexels.com/photo/12/",
                    "photographer": "Bob",
                },
            ]
        }
        with patch(
            "app.services.material.requests.get",
            return_value=_search_response(payload),
        ) as get:
            results = material.search_images_pexels(
                "cat", minimum_duration=5,
                video_aspect=material.VideoAspect.portrait,
            )

        url = get.call_args.args[0]
        self.assertTrue(url.startswith("https://api.pexels.com/v1/search?"))
        params = parse_qs(urlparse(url).query)
        self.assertEqual(params["query"], ["cat"])
        self.assertEqual(params["per_page"], ["20"])
        self.assertEqual(params["orientation"], ["portrait"])
        self.assertEqual(
            get.call_args.kwargs["headers"]["Authorization"], "pexels-test-key"
        )
        # 横屏照片在竖屏任务里必须被过滤，避免成片黑边。
        self.assertEqual(len(results), 1)
        item = results[0]
        self.assertEqual(item.provider, "pexels_image")
        self.assertEqual(
            item.url, "https://images.pexels.com/photos/11/l2x.jpeg"
        )
        # 图片没有原生时长，记录目标片段时长供按需编排核算。
        self.assertEqual(item.duration, 5)
        self.assertEqual(item.source_info["search_term"], "cat")
        self.assertEqual(item.source_info["asset_id"], "11")
        self.assertEqual(item.source_info["creator"], {"name": "Alice"})
        self.assertEqual(
            item.source_info["rendition"],
            {"id": None, "width": 2000, "height": 3000},
        )

    def test_search_images_pexels_landscape_orientation(self):
        payload = {
            "photos": [
                {
                    "id": 12,
                    "width": 3000,
                    "height": 2000,
                    "src": {
                        "large": "https://images.pexels.com/photos/12/l.jpeg"
                    },
                    "url": "https://www.pexels.com/photo/12/",
                    "photographer": "Bob",
                }
            ]
        }
        with patch(
            "app.services.material.requests.get",
            return_value=_search_response(payload),
        ) as get:
            results = material.search_images_pexels(
                "city", minimum_duration=3,
                video_aspect=material.VideoAspect.landscape,
            )

        params = parse_qs(urlparse(get.call_args.args[0]).query)
        self.assertEqual(params["orientation"], ["landscape"])
        self.assertEqual(len(results), 1)
        # large2x 缺失时回退 large。
        self.assertEqual(
            results[0].url, "https://images.pexels.com/photos/12/l.jpeg"
        )

    def test_search_images_pixabay_request_and_candidates(self):
        """Pixabay 图片检索：方向参数取值映射与直链回退顺序。"""
        payload = {
            "hits": [
                {
                    "id": 21,
                    "imageWidth": 1080,
                    "imageHeight": 1920,
                    "fullHDURL": "https://pixabay.com/get/fullhd.jpg",
                    "largeImageURL": "https://pixabay.com/get/large.jpg",
                    "imageURL": "https://pixabay.com/get/small.jpg",
                    "pageURL": "https://pixabay.com/photos/21/",
                    "user": "Carol",
                },
                {
                    "id": 22,
                    "imageWidth": 1080,
                    "imageHeight": 1920,
                    "largeImageURL": "https://pixabay.com/get/large22.jpg",
                    "pageURL": "https://pixabay.com/photos/22/",
                    "user": "Dave",
                },
            ]
        }
        with patch(
            "app.services.material.requests.get",
            return_value=_search_response(payload),
        ) as get:
            results = material.search_images_pixabay(
                "dog", minimum_duration=5,
                video_aspect=material.VideoAspect.portrait,
            )

        url = get.call_args.args[0]
        self.assertTrue(url.startswith("https://pixabay.com/api/?"))
        params = parse_qs(urlparse(url).query)
        self.assertEqual(params["key"], ["pixabay-test-key"])
        self.assertEqual(params["q"], ["dog"])
        self.assertEqual(params["image_type"], ["photo"])
        self.assertEqual(params["safesearch"], ["true"])
        # Pixabay 用 vertical/horizontal，而不是 Pexels 的 portrait/landscape。
        self.assertEqual(params["orientation"], ["vertical"])
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].provider, "pixabay_image")
        self.assertEqual(results[0].url, "https://pixabay.com/get/fullhd.jpg")
        self.assertEqual(results[0].source_info["creator"], {"name": "Carol"})
        self.assertEqual(results[1].url, "https://pixabay.com/get/large22.jpg")

    def test_search_images_pixabay_landscape_maps_horizontal(self):
        with patch(
            "app.services.material.requests.get",
            return_value=_search_response({"hits": []}),
        ) as get:
            results = material.search_images_pixabay(
                "city", minimum_duration=3,
                video_aspect=material.VideoAspect.landscape,
            )

        params = parse_qs(urlparse(get.call_args.args[0]).query)
        self.assertEqual(params["orientation"], ["horizontal"])
        self.assertEqual(results, [])

    def test_search_images_pexels_returns_empty_on_401(self):
        with patch(
            "app.services.material.requests.get",
            return_value=_search_response({}, status_code=401),
        ):
            self.assertEqual(
                material.search_images_pexels("cat", minimum_duration=5), []
            )

    def test_search_images_pixabay_returns_empty_on_connection_error(self):
        with patch(
            "app.services.material.requests.get",
            side_effect=requests.exceptions.ConnectionError("boom"),
        ):
            self.assertEqual(
                material.search_images_pixabay("dog", minimum_duration=5), []
            )


class TestStockImageGeneration(_StockImageTestCase):
    def test_generate_images_stock_uses_cache_and_normalizes_png(self):
        """搜索走 24 小时缓存（provider 带 _image 后缀），下载落盘为 PNG。"""
        remote_url = "https://images.pexels.com/photos/11/pexels-photo-11.jpeg"
        candidate = _candidate("pexels_image", remote_url)
        with (
            patch(
                "app.services.material._search_videos_with_cache",
                return_value=[candidate],
            ) as cached_search,
            patch(
                "app.services.material.requests.get",
                return_value=_download_response(_png_bytes(200, 300)),
            ),
        ):
            results = material.generate_images_stock(
                "pexels", "cat", minimum_duration=5, save_dir=self.save_dir
            )

        self.assertEqual(cached_search.call_args.kwargs["provider"], "pexels_image")
        self.assertIs(
            cached_search.call_args.kwargs["search_videos"],
            material.search_images_pexels,
        )
        self.assertEqual(len(results), 1)
        item = results[0]
        self.assertTrue(item.url.endswith(".png"))
        self.assertTrue(os.path.isfile(item.url))
        with Image.open(item.url) as saved:
            self.assertEqual(saved.size, (200, 300))
        # 远端直链留档，rendition 更新为落盘图片真实尺寸。
        self.assertEqual(item.source_info["remote_url"], remote_url)
        self.assertEqual(
            item.source_info["rendition"],
            {"id": None, "width": 200, "height": 300},
        )

    def test_generate_images_stock_skips_failed_download_candidate(self):
        first = _candidate("pexels_image", "https://cdn.example.com/a.jpg")
        second = _candidate("pexels_image", "https://cdn.example.com/b.jpg")
        with (
            patch(
                "app.services.material._search_videos_with_cache",
                return_value=[first, second],
            ),
            patch(
                "app.services.material._openai_image_download_bytes",
                side_effect=[(None, "http 404"), (_png_bytes(), None)],
            ),
        ):
            results = material.generate_images_stock(
                "pexels", "cat", minimum_duration=5, save_dir=self.save_dir
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0].source_info["remote_url"], "https://cdn.example.com/b.jpg"
        )

    def test_generate_images_stock_downgrades_paid_download_error_to_skip(self):
        """下载 helper 重试耗尽抛付费语义错误时，免费源降级为跳过候选。"""
        first = _candidate("pixabay_image", "https://cdn.example.com/a.jpg")
        second = _candidate("pixabay_image", "https://cdn.example.com/b.jpg")
        with (
            patch(
                "app.services.material._search_videos_with_cache",
                return_value=[first, second],
            ),
            patch(
                "app.services.material._openai_image_download_bytes",
                side_effect=[
                    material.OpenAIImagePaidResultError("retries exhausted"),
                    (_png_bytes(), None),
                ],
            ),
        ):
            results = material.generate_images_stock(
                "pixabay", "dog", minimum_duration=5, save_dir=self.save_dir
            )

        self.assertEqual(len(results), 1)
        self.assertTrue(os.path.isfile(results[0].url))

    def test_generate_images_stock_skips_undecodable_candidate(self):
        first = _candidate("pexels_image", "https://cdn.example.com/a.jpg")
        second = _candidate("pexels_image", "https://cdn.example.com/b.jpg")
        with (
            patch(
                "app.services.material._search_videos_with_cache",
                return_value=[first, second],
            ),
            patch(
                "app.services.material._openai_image_download_bytes",
                side_effect=[
                    (b"<html>gateway degraded</html>", None),
                    (_png_bytes(), None),
                ],
            ),
        ):
            results = material.generate_images_stock(
                "pexels", "cat", minimum_duration=5, save_dir=self.save_dir
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0].source_info["remote_url"], "https://cdn.example.com/b.jpg"
        )

    def test_generate_images_stock_returns_empty_when_all_candidates_fail(self):
        candidates = [
            _candidate("pexels_image", "https://cdn.example.com/a.jpg"),
            _candidate("pexels_image", "https://cdn.example.com/b.jpg"),
        ]
        with (
            patch(
                "app.services.material._search_videos_with_cache",
                return_value=candidates,
            ),
            patch(
                "app.services.material._openai_image_download_bytes",
                side_effect=[(None, "http 404"), (None, "http 404")],
            ),
        ):
            results = material.generate_images_stock(
                "pexels", "cat", minimum_duration=5, save_dir=self.save_dir
            )

        self.assertEqual(results, [])
        self.assertEqual(os.listdir(self.save_dir), [])


class TestStockImageOrchestration(_StockImageTestCase):
    def test_download_videos_routes_stock_image_with_free_semantics(self):
        """两个新源都必须路由到按需图片编排，且带免费语义与进度回调。"""
        for source, base in material.STOCK_IMAGE_SOURCES.items():
            with self.subTest(source=source):
                progress = lambda value: None  # noqa: E731
                with patch(
                    "app.services.material._download_videos_openai_image_on_demand",
                    return_value=["/tmp/x.mp4"],
                ) as orchestrator:
                    result = material.download_videos(
                        task_id="test-stock-image-routing",
                        search_terms=["a"],
                        source=source,
                        audio_duration=5,
                        max_clip_duration=5,
                        progress_callback=progress,
                        image_motion=material.ImageMotion.static,
                    )

                self.assertEqual(result, ["/tmp/x.mp4"])
                kwargs = orchestrator.call_args.kwargs
                self.assertEqual(kwargs["provider"], source)
                self.assertIs(kwargs["paid_source"], False)
                self.assertIs(kwargs["progress_callback"], progress)
                self.assertEqual(
                    kwargs["image_motion"], material.ImageMotion.static
                )
                # 注入的生成器必须把业务值翻译回基础 provider 再调库存生成。
                with patch(
                    "app.services.material.generate_images_stock",
                    return_value=[],
                ) as generate:
                    kwargs["image_generator"](
                        search_term="a",
                        minimum_duration=5,
                        video_aspect=material.VideoAspect.portrait,
                        save_dir="",
                    )
                generate.assert_called_once_with(
                    base,
                    search_term="a",
                    minimum_duration=5,
                    video_aspect=material.VideoAspect.portrait,
                    save_dir="",
                )

    def test_download_videos_stock_image_stops_at_required_duration(self):
        """逐张按需下载渲染，凑够配音时长即停；进度按覆盖比例报告。"""
        config.app["material_directory"] = self.save_dir
        items = {
            f"term-{i}": [_candidate("pixabay_image", f"/tmp/img-{i}.png")]
            for i in (1, 2, 3)
        }

        def fake_generate(base, search_term, minimum_duration, video_aspect, save_dir=""):
            self.assertEqual(base, "pixabay")
            return items[search_term]

        def fake_render(image_path, clip_duration, image_motion="zoom"):
            return f"{image_path}.mp4"

        progress = []
        with (
            patch(
                "app.services.material.generate_images_stock",
                side_effect=fake_generate,
            ) as generate,
            patch(
                "app.services.material._render_openai_image_video",
                side_effect=fake_render,
            ),
            patch("app.services.material._persist_material_sources"),
        ):
            result = material.download_videos(
                task_id="test-stock-image-stop",
                search_terms=["term-1", "term-2", "term-3"],
                source="pixabay_image",
                audio_duration=8,
                max_clip_duration=5,
                progress_callback=progress.append,
            )

        # 5s + 5s > 8s，第三个关键词不再发起搜索/下载。
        self.assertEqual(generate.call_count, 2)
        self.assertEqual(result, ["/tmp/img-1.png.mp4", "/tmp/img-2.png.mp4"])
        self.assertEqual(progress, [0.625, 1.0])

    def test_download_videos_stock_image_skips_render_failure_and_continues(self):
        """免费源渲染失败跳过该张继续下一关键词，不抛付费终止错误。"""
        config.app["material_directory"] = self.save_dir
        items = {
            "term-1": [_candidate("pexels_image", "/tmp/img-1.png")],
            "term-2": [_candidate("pexels_image", "/tmp/img-2.png")],
        }

        def fake_generate(base, search_term, minimum_duration, video_aspect, save_dir=""):
            return items[search_term]

        with (
            patch(
                "app.services.material.generate_images_stock",
                side_effect=fake_generate,
            ) as generate,
            patch(
                "app.services.material._render_openai_image_video",
                side_effect=["", "/tmp/img-2.png.mp4"],
            ),
            patch("app.services.material._persist_material_sources"),
        ):
            result = material.download_videos(
                task_id="test-stock-image-render-skip",
                search_terms=["term-1", "term-2"],
                source="pexels_image",
                audio_duration=5,
                max_clip_duration=5,
            )

        self.assertEqual(generate.call_count, 2)
        self.assertEqual(result, ["/tmp/img-2.png.mp4"])

    def test_download_videos_stock_image_skips_generation_without_audio(self):
        config.app["material_directory"] = self.save_dir
        with patch(
            "app.services.material.generate_images_stock"
        ) as generate:
            result = material.download_videos(
                task_id="test-stock-image-no-audio",
                search_terms=["term-1"],
                source="pexels_image",
                audio_duration=0,
                max_clip_duration=5,
            )

        generate.assert_not_called()
        self.assertEqual(result, [])

    def test_orchestrator_paid_source_default_still_raises_on_render_failure(self):
        """回归护栏：paid_source 默认值必须保持付费终止语义不变。"""
        with (
            patch(
                "app.services.material._render_openai_image_video",
                return_value="",
            ),
            patch("app.services.material._persist_material_sources"),
        ):
            with self.assertRaises(material.OpenAIImagePaidResultError):
                material._download_videos_openai_image_on_demand(
                    task_id="test-paid-guard",
                    search_terms=["a"],
                    video_aspect=material.VideoAspect.portrait,
                    audio_duration=10,
                    max_clip_duration=5,
                    material_directory=self.save_dir,
                    image_generator=lambda **kwargs: [
                        _candidate("openai_image", "/tmp/x.png")
                    ],
                )


if __name__ == "__main__":
    unittest.main()