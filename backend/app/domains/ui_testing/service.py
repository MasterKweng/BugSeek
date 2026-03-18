"""UI automation runner and persistence service."""
from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import List
import logging

from sqlalchemy.orm import Session

from app.domains.ui_testing.schemas import (
    UITestExecutionRequest,
    UITestExecutionSummary,
    UITestStepResult,
    UITestStepSpec,
)
from app.platform.db.base import TestExecution, TestExecutionResult

logger = logging.getLogger(__name__)


class UIPlaywrightRunner:
    """Executes a single UI case with Playwright."""

    async def run(self, request: UITestExecutionRequest) -> UITestExecutionSummary:
        start = perf_counter()
        step_results: List[UITestStepResult] = []

        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=request.headless)
            try:
                page = await browser.new_page()

                if request.start_url:
                    await page.goto(request.start_url, wait_until="domcontentloaded")

                for index, step in enumerate(request.steps, start=1):
                    step_results.append(await self._execute_step(page, index, step))
                    if step_results[-1].status != "passed":
                        break
            finally:
                await browser.close()

        duration_ms = int((perf_counter() - start) * 1000)
        failed_steps = sum(1 for item in step_results if item.status != "passed")
        passed_steps = len(step_results) - failed_steps
        status = "completed" if failed_steps == 0 and len(step_results) == len(request.steps) else "failed"
        return UITestExecutionSummary(
            execution_id=0,
            status=status,
            total_steps=len(request.steps),
            passed_steps=passed_steps,
            failed_steps=failed_steps,
            duration_ms=duration_ms,
            steps=step_results,
        )

    async def _execute_step(self, page, index: int, step: UITestStepSpec) -> UITestStepResult:
        started_at = perf_counter()
        try:
            if step.action == "goto":
                await page.goto(step.value or "", wait_until="domcontentloaded", timeout=step.timeout_ms)
                message = f"Navigated to {step.value}"
            elif step.action == "click":
                await page.locator(step.selector or "").click(timeout=step.timeout_ms)
                message = f"Clicked {step.selector}"
            elif step.action == "fill":
                await page.locator(step.selector or "").fill(step.value or "", timeout=step.timeout_ms)
                message = f"Filled {step.selector}"
            elif step.action == "press":
                await page.locator(step.selector or "body").press(step.value or "Enter", timeout=step.timeout_ms)
                message = f"Pressed {step.value or 'Enter'} on {step.selector or 'body'}"
            elif step.action == "wait_for":
                await page.locator(step.selector or "").wait_for(timeout=step.timeout_ms)
                message = f"Waited for {step.selector}"
            elif step.action == "assert_text":
                actual_text = await page.locator(step.selector or "").text_content(timeout=step.timeout_ms)
                expected_text = step.value or ""
                if expected_text not in (actual_text or ""):
                    raise AssertionError(f"Expected text '{expected_text}', got '{actual_text}'")
                message = f"Asserted text on {step.selector}"
            elif step.action == "assert_url":
                current_url = page.url
                expected_url = step.value or ""
                if expected_url not in current_url:
                    raise AssertionError(f"Expected url containing '{expected_url}', got '{current_url}'")
                message = f"Asserted url contains {expected_url}"
            else:
                raise ValueError(f"Unsupported UI action: {step.action}")

            return UITestStepResult(
                index=index,
                name=step.name,
                action=step.action,
                selector=step.selector,
                status="passed",
                duration_ms=int((perf_counter() - started_at) * 1000),
                message=message,
                url=page.url,
            )
        except Exception as exc:
            logger.warning("UI step failed: step=%s, action=%s, error=%s", step.name, step.action, exc)
            return UITestStepResult(
                index=index,
                name=step.name,
                action=step.action,
                selector=step.selector,
                status="failed",
                duration_ms=int((perf_counter() - started_at) * 1000),
                message=f"Step failed: {step.name}",
                url=page.url if hasattr(page, "url") else None,
                error_message=str(exc),
            )


class UIExecutionService:
    """Runs UI automation and persists execution artifacts."""

    def __init__(self, db: Session):
        self.db = db
        self.runner = UIPlaywrightRunner()

    async def run_and_persist(self, project_id: int, request: UITestExecutionRequest) -> UITestExecutionSummary:
        execution = TestExecution(
            project_id=project_id,
            execution_type="ui",
            target_id=request.target_id,
            triggered_by="manual",
            status="running",
            started_at=datetime.now(timezone.utc),
            execution_mode="serial",
        )
        self.db.add(execution)
        self.db.flush()

        summary: UITestExecutionSummary | None = None
        try:
            summary = await self.runner.run(request)
            execution.status = "completed" if summary.failed_steps == 0 else "failed"
            execution.finished_at = datetime.now(timezone.utc)
            execution.duration = summary.duration_ms
            execution.total = summary.total_steps
            execution.passed = summary.passed_steps
            execution.failed = summary.failed_steps
            execution.skipped = max(summary.total_steps - len(summary.steps), 0)

            for step in summary.steps:
                self.db.add(
                    TestExecutionResult(
                        execution_id=execution.id,
                        target_type="ui_step",
                        target_id=step.index,
                        status=step.status,
                        response_time=step.duration_ms,
                        response_code=200 if step.status == "passed" else 500,
                        request_body={
                            "name": step.name,
                            "action": step.action,
                            "selector": step.selector,
                        },
                        response_body={
                            "message": step.message,
                            "url": step.url,
                        },
                        assertion_results=None,
                        extracted_variables=None,
                        error_message=step.error_message,
                    )
                )

            self.db.commit()
            return summary.model_copy(update={"execution_id": execution.id})
        except Exception as exc:
            self.db.rollback()
            logger.error("UI execution failed: project_id=%s, error=%s", project_id, exc, exc_info=True)

            fallback_execution = TestExecution(
                project_id=project_id,
                execution_type="ui",
                target_id=request.target_id,
                triggered_by="manual",
                status="failed",
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                execution_mode="serial",
                duration=0,
                total=len(request.steps),
                passed=0,
                failed=1,
                skipped=max(len(request.steps) - 1, 0),
            )
            self.db.add(fallback_execution)
            self.db.flush()
            self.db.add(
                TestExecutionResult(
                    execution_id=fallback_execution.id,
                    target_type="ui_step",
                    target_id=0,
                    status="failed",
                    response_time=0,
                    response_code=500,
                    request_body={"name": request.name},
                    response_body={"message": "UI execution bootstrap failed"},
                    assertion_results=None,
                    extracted_variables=None,
                    error_message=str(exc),
                )
            )
            self.db.commit()
            return UITestExecutionSummary(
                execution_id=fallback_execution.id,
                status="failed",
                total_steps=len(request.steps),
                passed_steps=0,
                failed_steps=1,
                duration_ms=0,
                steps=[
                    UITestStepResult(
                        index=0,
                        name=request.name,
                        action="bootstrap",
                        status="failed",
                        duration_ms=0,
                        message="UI execution bootstrap failed",
                        error_message=str(exc),
                    )
                ],
            )

    def get_execution_detail(self, project_id: int, execution_id: int) -> UITestExecutionSummary | None:
        execution = self.db.query(TestExecution).filter(
            TestExecution.id == execution_id,
            TestExecution.project_id == project_id,
            TestExecution.execution_type == "ui",
        ).first()
        if not execution:
            return None

        rows = self.db.query(TestExecutionResult).filter(
            TestExecutionResult.execution_id == execution_id
        ).order_by(TestExecutionResult.id.asc()).all()

        steps = [
            UITestStepResult(
                index=row.target_id,
                name=(row.request_body or {}).get("name", f"Step {row.target_id}"),
                action=(row.request_body or {}).get("action", row.target_type),
                selector=(row.request_body or {}).get("selector"),
                status=row.status,
                duration_ms=row.response_time or 0,
                message=(row.response_body or {}).get("message"),
                url=(row.response_body or {}).get("url"),
                error_message=row.error_message,
            )
            for row in rows
        ]

        return UITestExecutionSummary(
            execution_id=execution.id,
            status=execution.status,
            total_steps=execution.total or len(steps),
            passed_steps=execution.passed or 0,
            failed_steps=execution.failed or 0,
            duration_ms=execution.duration or 0,
            steps=steps,
        )
