"""
异步任务处理模块：处理长时间操作，如向量化、去重等
支持使用 Celery、RQ 或简单的后台线程
"""

import threading
import logging
from typing import Optional, List, Callable, Any
from queue import Queue
import time

logger = logging.getLogger(__name__)

# 简单的内存任务队列（无需额外依赖）
class SimpleTaskQueue:
    def __init__(self, max_workers: int = 4):
        self.queue: Queue = Queue()
        self.workers_count = max_workers
        self.active = True
        self._start_workers()
    
    def _start_workers(self):
        """启动工作线程"""
        for i in range(self.workers_count):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
    
    def _worker(self):
        """工作线程主循环"""
        while self.active:
            try:
                task = self.queue.get(timeout=1)
                if task is None:  # 哨兵值，停止信号
                    break
                
                func, args, kwargs = task
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Task execution failed: {e}", exc_info=True)
                finally:
                    self.queue.task_done()
            except Exception:
                # 队列空或其他异常，继续循环
                continue
    
    def submit(self, func: Callable, *args, **kwargs):
        """提交一个任务到队列"""
        if not self.active:
            logger.warning("Task queue is not active, executing synchronously")
            func(*args, **kwargs)
            return
        self.queue.put((func, args, kwargs))
    
    def shutdown(self):
        """关闭队列"""
        self.active = False
        # 发送哨兵值让工作线程退出
        for _ in range(self.workers_count):
            self.queue.put(None)

# 全局任务队列实例
_task_queue: Optional[SimpleTaskQueue] = None

def init_task_queue(max_workers: int = 4):
    """初始化全局任务队列"""
    global _task_queue
    if _task_queue is None:
        _task_queue = SimpleTaskQueue(max_workers=max_workers)
        logger.info(f"Task queue initialized with {max_workers} workers")

def get_task_queue() -> Optional[SimpleTaskQueue]:
    """获取全局任务队列"""
    return _task_queue

def submit_async_task(func: Callable, *args, **kwargs):
    """提交异步任务"""
    queue = get_task_queue()
    if queue:
        queue.submit(func, *args, **kwargs)
    else:
        logger.warning("Task queue not initialized, executing synchronously")
        func(*args, **kwargs)

def shutdown_task_queue():
    """关闭全局任务队列"""
    global _task_queue
    if _task_queue:
        _task_queue.shutdown()
        _task_queue = None
        logger.info("Task queue shut down")
