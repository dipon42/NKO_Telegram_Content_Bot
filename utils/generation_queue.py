import asyncio
import logging
from typing import Callable, Any, Awaitable, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class GenerationType(Enum):
    """Типы генерации"""
    TEXT = "text"
    IMAGE = "image"
    CONTENT_PLAN = "content_plan"
    ENHANCE_PROMPT = "enhance_prompt"


@dataclass
class GenerationTask:
    """Задача на генерацию"""
    task_id: str
    generation_type: GenerationType
    coro: Callable[[], Awaitable[Any]]
    retry_count: int = 0
    max_retries: int = 3
    retry_delay: float = 2.0  # Задержка перед повтором в секундах
    future: asyncio.Future = field(default_factory=asyncio.Future)
    on_start_callback: Optional[Callable[[], Awaitable[None]]] = None  # Callback для обновления сообщения при начале обработки


class GenerationQueue:
    """
    Очередь для последовательной обработки запросов генерации.
    Обеспечивает обработку запросов один за другим и автоматический retry при ошибке 429.
    """
    
    def __init__(self):
        self._queue: asyncio.Queue[GenerationTask] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._current_task: Optional[GenerationTask] = None
        
    async def start(self):
        """Запуск воркера для обработки очереди"""
        if not self._is_running:
            self._is_running = True
            self._worker_task = asyncio.create_task(self._worker())
            logger.info("Очередь генерации запущена")
    
    async def stop(self):
        """Остановка воркера"""
        self._is_running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Очередь генерации остановлена")
    
    async def add_task(
        self,
        generation_type: GenerationType,
        coro: Callable[[], Awaitable[Any]],
        task_id: Optional[str] = None,
        on_start_callback: Optional[Callable[[], Awaitable[None]]] = None
    ) -> tuple[Any, int]:
        """
        Добавить задачу в очередь и дождаться результата.
        
        :param generation_type: Тип генерации
        :param coro: Корутина для выполнения
        :param task_id: Уникальный ID задачи (опционально)
        :param on_start_callback: Callback для вызова при начале обработки задачи
        :return: Кортеж (результат выполнения корутины, позиция в очереди)
        """
        if not task_id:
            import uuid
            task_id = str(uuid.uuid4())
        
        task = GenerationTask(
            task_id=task_id,
            generation_type=generation_type,
            coro=coro,
            on_start_callback=on_start_callback
        )
        
        # Future создается в __post_init__
        future = task.future
        
        queue_size = self._queue.qsize()
        position = queue_size + 1
        await self._queue.put(task)
        logger.info(
            f"Задача {task_id} добавлена в очередь (тип: {generation_type.value}, "
            f"позиция в очереди: {position})"
        )
        
        # Ждем результата
        result = await future
        return result, position
    
    async def _worker(self):
        """Воркер для обработки задач из очереди"""
        while self._is_running:
            task = None
            try:
                # Получаем задачу из очереди (с таймаутом для возможности остановки)
                try:
                    task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                self._current_task = task
                logger.info(f"Обработка задачи {task.task_id} (тип: {task.generation_type.value})")
                
                # Вызываем callback при начале обработки (для обновления сообщения)
                if task.on_start_callback:
                    try:
                        await task.on_start_callback()
                    except Exception as e:
                        logger.error(f"Ошибка при вызове on_start_callback: {e}", exc_info=True)
                
                # Выполняем задачу с retry при ошибке 429
                result = await self._execute_with_retry(task)
                
                # Отправляем результат в Future
                if not task.future.done():
                    task.future.set_result(result)
                
                self._current_task = None
                self._queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в воркере очереди: {e}", exc_info=True)
                if task and not task.future.done():
                    task.future.set_exception(e)
                self._current_task = None
    
    async def _execute_with_retry(self, task: GenerationTask) -> Any:
        """Выполнить задачу с автоматическим retry при ошибке 429 и таймаутах"""
        from gigachat.exceptions import ResponseError
        import httpx
        
        while task.retry_count <= task.max_retries:
            try:
                # Выполняем корутину
                result = await task.coro()
                return result
                
            except (httpx.ReadTimeout, httpx.TimeoutException) as e:
                # Если это таймаут, делаем retry
                task.retry_count += 1
                if task.retry_count <= task.max_retries:
                    wait_time = task.retry_delay * task.retry_count
                    logger.warning(
                        f"Таймаут для задачи {task.task_id} (тип: {task.generation_type.value}). "
                        f"Попытка {task.retry_count}/{task.max_retries}. "
                        f"Ожидание {wait_time} сек..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Превышено количество попыток из-за таймаута для задачи {task.task_id}")
                    raise Exception(
                        "⏱ Генерация заняла слишком много времени. "
                        "Пожалуйста, попробуйте снова позже.\n\n"
                        "💡 Если проблема повторяется, попробуйте упростить запрос или добавить свой API-ключ GigaChat в настройках бота."
                    )
                
            except ResponseError as e:
                # Если это ошибка 429, делаем retry
                if e.status_code == 429:
                    task.retry_count += 1
                    if task.retry_count <= task.max_retries:
                        wait_time = task.retry_delay * task.retry_count  # Увеличиваем задержку с каждой попыткой
                        logger.warning(
                            f"Ошибка 429 для задачи {task.task_id}. "
                            f"Попытка {task.retry_count}/{task.max_retries}. "
                            f"Ожидание {wait_time} сек..."
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Превышено количество попыток для задачи {task.task_id}")
                        raise Exception(
                            "⏳ Слишком много одновременных запросов. "
                            "Пожалуйста, подождите немного и попробуйте снова.\n\n"
                            "💡 Чтобы избежать ожидания, добавьте свой API-ключ GigaChat в настройках бота."
                        )
                else:
                    # Другие ошибки ResponseError пробрасываем дальше
                    raise
            except Exception as e:
                # Все остальные ошибки пробрасываем дальше
                raise
    
    def get_queue_size(self) -> int:
        """Получить размер очереди"""
        return self._queue.qsize()
    
    def get_current_task(self) -> Optional[GenerationTask]:
        """Получить текущую выполняемую задачу"""
        return self._current_task


# Глобальный экземпляр очереди
_global_queue: Optional[GenerationQueue] = None


def get_generation_queue() -> GenerationQueue:
    """Получить глобальный экземпляр очереди генерации"""
    global _global_queue
    if _global_queue is None:
        _global_queue = GenerationQueue()
    return _global_queue

