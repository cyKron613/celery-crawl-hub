import asyncio
from playwright.async_api import TimeoutError as PlaywrightTimeoutError, async_playwright
from loguru import logger
import random
import socket
from threading import Lock
from contextlib import asynccontextmanager
import gc
from typing import Any, Dict, Optional

# 借用 ChromiumManager 的端口锁
port_lock = Lock()

class PlaywrightManager:
    """Playwright 资源管理器"""
    _leased_ports = set()

    @classmethod
    def _get_available_port(cls):
        """获取可用的端口号"""
        with port_lock:
            for _ in range(20):
                port = random.randint(10000, 15000)
                if port in cls._leased_ports:
                    continue
                sock = None
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    sock.bind(('127.0.0.1', port))
                    cls._leased_ports.add(port)
                    return port
                except Exception:
                    continue
                finally:
                    if sock:
                        sock.close()
        raise RuntimeError("未能分配可用端口")

    @classmethod
    def _release_port(cls, port):
        if port:
            with port_lock:
                cls._leased_ports.discard(port)

    @asynccontextmanager
    async def get_browser_context(self, timeout=30000, headless: bool = True):
        """异步获取浏览器上下文"""
        port = self._get_available_port()
        pw = None
        browser = None
        try:
            pw = await async_playwright().start()
            # 模拟随机指纹和通用配置
            browser = await pw.chromium.launch(
                headless=headless,
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--ignore-certificate-errors',
                    '--disable-features=BlockInsecurePrivateNetworkRequests',
                    f'--remote-debugging-port={port}'
                ]
            )
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ignore_https_errors=True,
                locale="ja-JP",
                timezone_id="Asia/Tokyo",
                extra_http_headers={
                    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                },
            )
            yield context
        finally:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()
            self._release_port(port)
            gc.collect()

async def playwright_fetch(
    url,
    timeout=300,
    wait_xpath=None,
    need_click=False,
    headless: bool = True,
    request_headers: Optional[Dict[str, str]] = None,
):
    """Playwright 版本的请求实现"""
    manager = PlaywrightManager()
    async with manager.get_browser_context(headless=headless) as context:
        last_error = None
        max_attempts = 3
        for attempt in range(max_attempts):
            page = await context.new_page()
            try:
                page.set_default_timeout(timeout * 1000)
                if request_headers:
                    await page.set_extra_http_headers(request_headers)

                navigation_error = None
                for wait_until in ('domcontentloaded', 'commit'):
                    try:
                        await page.goto(url, wait_until=wait_until, timeout=timeout * 1000)
                        navigation_error = None
                        break
                    except PlaywrightTimeoutError as exc:
                        navigation_error = exc
                    except Exception as exc:
                        navigation_error = exc

                if navigation_error is not None:
                    raise navigation_error

                if wait_xpath:
                    if isinstance(wait_xpath, list):
                        wait_tasks = [
                            asyncio.create_task(page.wait_for_selector(f"xpath={xpath}", state='attached'))
                            for xpath in wait_xpath
                        ]
                        done, pending = await asyncio.wait(wait_tasks, return_when=asyncio.FIRST_COMPLETED)
                        for task in pending:
                            task.cancel()
                        if not done:
                            raise ValueError("未命中任何等待节点")
                    else:
                        xpath_selector = wait_xpath if wait_xpath.startswith(('xpath=', '//', '(')) else f"xpath={wait_xpath}"
                        await page.wait_for_selector(xpath_selector, state='attached')

                await asyncio.sleep(2)
                html = await page.content()
                if html:
                    return {
                        "status": True,
                        "html": html,
                        "url": page.url
                    }
                raise ValueError("页面内容为空")
            except Exception as e:
                last_error = e
                logger.warning(f"Playwright 第{attempt + 1}次请求失败: {url}, 错误: {str(e)}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(attempt + 1)
            finally:
                await page.close()

        logger.error(f"Playwright 请求失败: {url}, 错误: {str(last_error)}")
        return {"status": False, "error": str(last_error)}


async def _playwright_login_and_get_headers(
    login_url: str,
    username: str,
    password: str,
    username_xpath: str,
    password_xpath: str,
    submit_xpath: str,
    login_entry_xpath: Optional[str] = None,
    success_wait_xpath: Optional[str] = None,
    timeout: int = 60,
    headless: bool = True,
) -> Dict[str, Any]:
    """使用 Playwright 执行一次登录流程并返回后续请求可用的 headers。"""
    result: Dict[str, Any] = {"status": False, "headers": {}, "error": ""}

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=headless,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                ignore_https_errors=True,
            )

            page = await context.new_page()
            page.set_default_timeout(timeout * 1000)
            await page.goto(login_url, wait_until="domcontentloaded", timeout=timeout * 1000)

            if login_entry_xpath:
                await page.click(f"xpath={login_entry_xpath}")

            await page.fill(f"xpath={username_xpath}", username)
            await page.fill(f"xpath={password_xpath}", password)
            await page.click(f"xpath={submit_xpath}")

            if success_wait_xpath:
                await page.wait_for_selector(f"xpath={success_wait_xpath}", state="attached")
            else:
                await page.wait_for_load_state("networkidle")

            ua = await page.evaluate("() => navigator.userAgent")
            result["headers"] = {
                "User-Agent": ua,
            }
            result["status"] = True

            await page.close()
            await context.close()
            await browser.close()
    except Exception as exc:
        logger.warning(f"Playwright 登录并提取请求头失败: {exc}")
        result["error"] = str(exc)

    return result


def playwright_login_and_get_headers_sync(
    login_url: str,
    username: str,
    password: str,
    username_xpath: str,
    password_xpath: str,
    submit_xpath: str,
    login_entry_xpath: Optional[str] = None,
    success_wait_xpath: Optional[str] = None,
    timeout: int = 60,
    headless: bool = True,
) -> Dict[str, Any]:
    """同步封装，便于在 Celery 同步任务中复用 Playwright 登录态。"""
    return asyncio.run(
        _playwright_login_and_get_headers(
            login_url=login_url,
            username=username,
            password=password,
            username_xpath=username_xpath,
            password_xpath=password_xpath,
            submit_xpath=submit_xpath,
            login_entry_xpath=login_entry_xpath,
            success_wait_xpath=success_wait_xpath,
            timeout=timeout,
            headless=headless,
        )
    )
