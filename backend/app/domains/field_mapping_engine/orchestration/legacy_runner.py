"""Fallback adapter for the legacy field mapping processor."""

from __future__ import annotations

from app.platform.db.base import AsyncTask

from .job_runner import FieldMappingJobRunner


class LegacyFieldMappingJobRunner(FieldMappingJobRunner):
    """Adapter around the legacy field mapping processor."""

    async def run(self, task: AsyncTask) -> dict:
        from app.domains.data_mapping.processor import FieldMappingProcessor

        processor = FieldMappingProcessor(self.db, task)
        return await processor.process()
