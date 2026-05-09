import socket
from loguru import logger
from DrissionPage import ChromiumOptions, ChromiumPage
import time
import random
from threading import Lock
from contextlib import contextmanager
import os
import shutil
import tempfile
import atexit

# 全局端口锁
port_lock = Lock()

class ChromiumOptionsManager:
    """ChromiumOptions 单例管理器，确保所有实例使用相同的配置"""
    _instance = None
    _lock = Lock()
    _options = None
    _port = None
    _leased_ports = set()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._port = cls.get_available_port()  # 为实例分配固定端口
                    cls._instance._init_options()
                    # 注册退出时的清理函数，确保程序结束时关闭所有残留浏览器
                    # atexit.register(cls.cleanup_orphans)
                    
                    logger.info(f"ChromiumOptions单例初始化完成，使用固定端口: {cls._instance._port}")
        return cls._instance
    
    def _init_options(self):
        """初始化ChromiumOptions配置"""
        if self._options is None:
            self._options = ChromiumOptions()
            # 设置通用配置
            self._options.set_argument('--no-sandbox')
            self._options.set_argument('--headless=new')
            self._options.set_argument('--disable-blink-features=AutomationControlled')
            self._options.set_argument('--disable-web-security')
            self._options.set_argument('--disable-dev-shm-usage')  # 减少内存使用
            self._options.set_argument('--disable-gpu')  # 减少GPU内存使用
            # self._options.set_argument('--incognito')  # 无痕模式，减少缓存占用

            # 可以根据需要添加更多配置

    @staticmethod
    def get_available_port():
        """获取可用的端口号（线程安全版本）"""
        with port_lock:
            # 尝试多次以避免竞态条件
            for _ in range(3):  # 最多尝试3次
                port = random.randint(9223, 9723)
                logger.debug(f"尝试端口: {port}")

                # 检查端口是否真正可用
                sock = None
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    # 尝试绑定端口
                    sock.bind(('127.0.0.1', port))
                    sock.close()
                    
                    # 稍微等待一下再次检查，确保端口确实可用且稳定
                    time.sleep(0.5)
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    sock.bind(('127.0.0.1', port))
                    sock.close()
                    
                    return port
                except Exception as e:
                    logger.debug(f"端口 {port} 不可用: {str(e)}")
                    continue
                finally:
                    if sock:
                        try:
                            sock.close()
                        except:
                            pass
        raise RuntimeError("在多次尝试后未找到可用端口")

    @classmethod
    def lease_available_port(cls):
        """为单个 ChromiumPage 实例租约一个独占端口。"""
        with port_lock:
            for _ in range(20):
                port = random.randint(9223, 9723)
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
                        try:
                            sock.close()
                        except:
                            pass

        raise RuntimeError("未能为 ChromiumPage 分配可用端口")

    @classmethod
    def release_port(cls, port):
        """释放端口租约。"""
        if port is None:
            return
        with port_lock:
            cls._leased_ports.discard(port)
    
    def get_options(self, port=None):
        """
        获取配置好的ChromiumOptions实例
        :param port: 可选端口号，如果提供则设置端口
        :return: ChromiumOptions实例
        """
        options = self._options.copy() if hasattr(self._options, 'copy') else ChromiumOptions()
        
        # 重新应用配置（确保copy后的实例也有相同的配置）
        options.set_argument('--no-sandbox')
        options.set_argument('--disable-blink-features=AutomationControlled')
        options.set_argument('--disable-web-security')
        options.set_argument('--disable-dev-shm-usage')
        # 隐藏"Chrome正受到自动测试软件的控制"
        options.set_argument('--disable-automation-controller')
        options.set_argument('--disable-gpu')
        options.set_argument('--headless=new')
        # options.set_argument('--incognito')

        # 使用实例的固定端口，除非明确指定其他端口
        final_port = port if port is not None else self._port
        if final_port is not None:
            options.set_local_port(final_port)
            
        return options
    
    def get_port(self):
        """获取当前单例实例使用的固定端口"""
        return self._port

    @staticmethod
    def cleanup_orphans():
        """更安全的孤儿进程清理（支持 Windows 和 Linux）"""
        logger.info("开始清理孤儿浏览器进程...")
        try:
            import psutil
            count = 0
            current_pid = os.getpid()
            for proc in psutil.process_iter(['pid', 'ppid', 'name', 'cmdline', 'status']):
                try:
                    # 排除当前进程及其父进程
                    if proc.info['pid'] == current_pid:
                        continue
                        
                    # 检查是否是 chrome/chromium 相关进程
                    name = proc.info['name'].lower()
                    cmdline = ' '.join(proc.info['cmdline'] or []).lower()
                    
                    is_browser = any(x in name for x in ['chrome', 'chromium', 'chromedriver']) or \
                                 any(x in cmdline for x in ['chrome', 'chromium', 'drissionpage'])

                    if is_browser:
                        pid = proc.info['pid']
                        ppid = proc.info['ppid']
                        status = proc.info['status']
                        
                        # 获取进程创建时间
                        try:
                            create_time = proc.create_time()
                            uptime = time.time() - create_time
                        except:
                            uptime = 0
                        
                        is_orphan = False
                        if os.name == 'nt':
                            try:
                                parent = psutil.Process(ppid)
                                if not parent.is_running():
                                    is_orphan = True
                            except psutil.NoSuchProcess:
                                is_orphan = True
                        else:
                            # Linux 下，PPID 为 1 或者是僵尸进程
                            if ppid == 1 or status == psutil.STATUS_ZOMBIE:
                                is_orphan = True
                        
                        # 清理逻辑：孤儿进程、僵尸进程、或运行超过 45 分钟的进程
                        if is_orphan or uptime > 2700: 
                            logger.warning(f"强制清理进程: {name} (PID: {pid}, PPID: {ppid}, Status: {status}, Uptime: {uptime:.1f}s)")
                            # 尝试优雅关闭，失败则强制杀死
                            try:
                                proc.terminate()
                                proc.wait(timeout=3)
                            except:
                                proc.kill()
                            count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if count > 0:
                logger.warning(f"共清理了 {count} 个异常浏览器进程")
        except ImportError:
            if os.name != 'nt':
                # 如果没装 psutil，且是 Linux，回退到基础清理
                try:
                    import subprocess
                    # 杀死所有 headless chrome 进程
                    subprocess.run(["pkill", "-9", "-f", "chrome"], capture_output=True)
                    subprocess.run(["pkill", "-9", "-f", "chromium"], capture_output=True)
                    logger.warning("未安装 psutil，已通过 pkill 强制清理所有浏览器进程")
                except Exception as e:
                    logger.error(f"基础清理失败: {e}")
            else:
                logger.warning("Windows 系统未安装 psutil，无法执行孤儿进程清理")
        except Exception as e:
            logger.error(f"清理过程中发生错误: {e}")

    @contextmanager
    def chromium_page(self, port=None):
        """
        上下文管理器，确保 ChromiumPage 在使用后正确关闭
        """
        page = None
        browser_pid = None
        tmp_user_data = tempfile.mkdtemp(prefix="chrome_user_data_")
        should_release_port = port is None
        use_port = port if port is not None else self.lease_available_port()
        
        try:
            options = self.get_options(port=use_port)
            options.set_user_data_path(tmp_user_data)
            
            page = ChromiumPage(options)
            
            # 记录浏览器主进程 PID，用于兜底清理
            try:
                browser_pid = page.browser.process_id
            except:
                pass
                
            yield page
        finally:
            if page:
                logger.info(f"关闭 ChromiumPage (端口: {use_port})")
                try:
                    # 1. 尝试标准退出
                    page.quit()
                    logger.info(f"ChromiumPage 已通过 quit() 关闭 (端口: {use_port})")
                except Exception as e:
                    logger.error(f"标准关闭失败，尝试强制清理 PID {browser_pid}: {e}")
                    
            # 2. 兜底清理：如果 quit() 没关掉，或者根本没创建成功但进程已启动
            if browser_pid:
                logger.info(f"开始兜底清理浏览器进程 (PID: {browser_pid})")
                try:
                    import psutil
                    parent = psutil.Process(browser_pid)
                    # 杀死该进程及其所有子进程（GPU, Renderer等）
                    for child in parent.children(recursive=True):
                        child.kill()
                    parent.kill()
                    logger.warning(f"已强制杀死残留浏览器进程树 (PID: {browser_pid})")
                except:
                    pass
            
            # 3. 清理临时目录
            try:
                logger.info(f"清理临时用户数据目录: {tmp_user_data}")
                if os.path.exists(tmp_user_data):
                    shutil.rmtree(tmp_user_data, ignore_errors=True)
            except:
                pass

            if should_release_port:
                self.release_port(use_port)


if __name__ == '__main__':
    # 清理故而进程
    ChromiumOptionsManager.cleanup_orphans()