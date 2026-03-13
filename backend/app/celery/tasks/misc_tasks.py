from ._common import *

@celery_app.task(bind=True)
def example_task(self, *args, **kwargs):
    """
    示例任务
    """
    logger.info(f"Example task executed with args: {args}, kwargs: {kwargs}")
    return {"status": "success"}


