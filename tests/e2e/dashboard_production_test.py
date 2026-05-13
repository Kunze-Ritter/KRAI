"""Dashboard production validation using Playwright."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, Error, Page, async_playwright


class DashboardValidator:
    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        document_ids: list[str] | None = None,
        output_dir: str = "test_results",
        credentials: dict[str, str] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.document_ids = document_ids or []
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.credentials = credentials or {
            "email": "admin@krai.local",
            "password": "admin123",
        }
        self.navigation_timeout_ms = 30_000
        self.wait_timeout_ms = 10_000
        self.document_match_counts: dict[str, int] = {}

    async def validate(self) -> dict[str, Any]:
        results: dict[str, Any] = {
            "status": "PASS",
            "checks": [],
            "screenshots": [],
        }
        browser: Browser | None = None

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page()
                page.set_default_navigation_timeout(self.navigation_timeout_ms)
                page.set_default_timeout(self.wait_timeout_ms)

                if not self.document_ids:
                    raise RuntimeError("No document_ids provided for dashboard validation.")

                await self._login(page, results)
                await self._search_documents(page, results)
                await self._verify_document_count(page, results)
                await self._verify_document_details(page, results)
                await self._verify_images_load(page, results)
                await self._verify_stage_status(page, results)
        except Exception as error:
            results["status"] = "FAIL"
            results["error"] = str(error)
        finally:
            if browser:
                await browser.close()
            if any(check.get("status") != "PASS" for check in results.get("checks", [])):
                results["status"] = "FAIL"

        return results

    async def _login(self, page: Page, results: dict[str, Any]):
        check = {"name": "login", "status": "FAIL"}
        try:
            await page.goto(f"{self.base_url}/kradmin", wait_until="domcontentloaded")
            await page.get_by_label("Email address").fill(self.credentials["email"])
            await page.get_by_label("Password").fill(self.credentials["password"])
            await page.get_by_role("button", name="Sign in").click()
            await page.wait_for_url("**/kradmin**", timeout=self.wait_timeout_ms)
            check.update({"status": "PASS", "message": "Login successful"})
        except Exception as error:
            check["message"] = f"Login failed: {error}"
            screenshot = await self._capture_screenshot(page, "dashboard_login_error.png")
            if screenshot:
                results["screenshots"].append(screenshot)
        results["checks"].append(check)

    async def _search_documents(self, page: Page, results: dict[str, Any]):
        check = {"name": "search_documents", "status": "FAIL"}
        try:
            per_id_counts: dict[str, int] = {}
            for document_id in self.document_ids:
                match_count = await self._count_rows_for_document_id(page, document_id)
                per_id_counts[document_id] = match_count
                if match_count < 1:
                    raise RuntimeError(f"Document ID not found in dashboard: {document_id}")

            self.document_match_counts = per_id_counts

            screenshot = await self._capture_screenshot(page, "dashboard_search_results.png")
            if screenshot:
                results["screenshots"].append(screenshot)

            check.update(
                {
                    "status": "PASS",
                    "message": "Search completed for requested document IDs",
                    "document_match_counts": per_id_counts,
                }
            )
        except Exception as error:
            check["message"] = f"Search failed: {error}"
        results["checks"].append(check)

    async def _verify_document_count(self, page: Page, results: dict[str, Any]):
        expected_ids = len(self.document_ids)
        check = {
            "name": "verify_document_count",
            "status": "FAIL",
            "expected_ids": expected_ids,
            "actual_ids_found": 0,
            "document_match_counts": {},
        }
        try:
            counts = self.document_match_counts or {}
            if not counts:
                counts = {}
                for document_id in self.document_ids:
                    counts[document_id] = await self._count_rows_for_document_id(page, document_id)

            found_ids = sum(1 for count in counts.values() if count > 0)
            check["actual_ids_found"] = found_ids
            check["document_match_counts"] = counts

            missing_ids = [document_id for document_id, count in counts.items() if count < 1]
            if missing_ids:
                raise RuntimeError(f"Missing document IDs in dashboard: {', '.join(missing_ids)}")

            check.update({"status": "PASS", "message": "All requested document IDs found"})
        except Exception as error:
            check["message"] = f"Document count verification failed: {error}"
        results["checks"].append(check)

    async def _verify_document_details(self, page: Page, results: dict[str, Any]):
        for document_id in self.document_ids:
            check = {
                "name": f"verify_document_{document_id}_details",
                "status": "FAIL",
            }
            try:
                await self._open_document_detail_by_id(page, document_id)
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_selector("body", timeout=self.wait_timeout_ms)

                body_text = await page.locator("body").inner_text()
                has_document_id = document_id in body_text
                has_chunks = "chunk" in body_text.lower()

                screenshot = await self._capture_screenshot(
                    page,
                    f"dashboard_document_{document_id}_detail.png",
                )
                if screenshot:
                    results["screenshots"].append(screenshot)

                if has_document_id and has_chunks:
                    check.update({"status": "PASS", "message": "Document detail page loaded"})
                else:
                    check["message"] = "Document detail page missing requested document ID or chunk data"

                await page.go_back(wait_until="domcontentloaded")
                await page.wait_for_selector(".filament-table-row", timeout=self.wait_timeout_ms)
            except Exception as error:
                check["message"] = f"Document detail verification failed: {error}"
            results["checks"].append(check)

    async def _verify_images_load(self, page: Page, results: dict[str, Any]):
        for document_id in self.document_ids:
            check = {
                "name": f"verify_images_load_{document_id}",
                "status": "FAIL",
                "image_count": 0,
                "loaded_image_count": 0,
            }
            try:
                await self._open_document_detail_by_id(page, document_id)
                await page.wait_for_load_state("domcontentloaded")

                images = page.locator('img[src*="minio"], img[src*="storage"], img')
                image_count = await images.count()
                check["image_count"] = image_count

                if image_count < 1:
                    check["message"] = "No images found on document detail page"
                else:
                    loaded_count = await page.evaluate(
                        """
                        () => {
                            const imgs = Array.from(document.querySelectorAll('img'));
                            return imgs.filter(img => img.complete && img.naturalWidth > 0).length;
                        }
                        """
                    )
                    check["loaded_image_count"] = loaded_count
                    if loaded_count > 0:
                        check.update(
                            {
                                "status": "PASS",
                                "message": f"Images loaded successfully ({loaded_count}/{image_count})",
                            }
                        )
                    else:
                        check["message"] = "Image elements found but none loaded successfully"

                await page.go_back(wait_until="domcontentloaded")
                await page.wait_for_selector(".filament-table-row", timeout=self.wait_timeout_ms)
            except Exception as error:
                check["message"] = f"Image verification failed: {error}"
            results["checks"].append(check)

    async def _verify_stage_status(self, page: Page, results: dict[str, Any]):
        for document_id in self.document_ids:
            check = {
                "name": f"verify_stage_status_{document_id}",
                "status": "FAIL",
                "expected": 15,
                "actual": 0,
            }
            try:
                await self._open_document_detail_by_id(page, document_id)
                await page.wait_for_load_state("domcontentloaded")

                completed_stages = await page.locator(
                    ".stage-status.completed, .fi-badge:has-text('completed'), [class*='completed']"
                ).count()
                check["actual"] = completed_stages

                if completed_stages == 15:
                    check.update({"status": "PASS", "message": "All 15 stages are completed"})
                else:
                    check["message"] = f"Expected 15 completed stages, found {completed_stages}"

                await page.go_back(wait_until="domcontentloaded")
                await page.wait_for_selector(".filament-table-row", timeout=self.wait_timeout_ms)
            except Exception as error:
                check["message"] = f"Stage status verification failed: {error}"
            results["checks"].append(check)

    async def _count_rows_for_document_id(self, page: Page, document_id: str) -> int:
        await page.goto(f"{self.base_url}/kradmin/documents", wait_until="domcontentloaded")
        search_input = page.locator('input[type="search"], input[placeholder*="Search"], input[name*="search"]').first
        await search_input.wait_for(timeout=self.wait_timeout_ms)
        await search_input.fill(document_id)
        await search_input.press("Enter")
        await page.wait_for_timeout(800)
        return await page.locator(".filament-table-row", has_text=document_id).count()

    async def _open_document_detail_by_id(self, page: Page, document_id: str):
        match_count = await self._count_rows_for_document_id(page, document_id)
        if match_count < 1:
            raise RuntimeError(f"Document ID not found in dashboard: {document_id}")

        row = page.locator(".filament-table-row", has_text=document_id).first
        await row.click()

    async def _capture_screenshot(self, page: Page, filename: str) -> str | None:
        try:
            path = self.output_dir / filename
            await page.screenshot(path=str(path), full_page=True)
            return str(path)
        except Error:
            return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dashboard production validation")
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:8080",
        help="Dashboard base URL",
    )
    parser.add_argument(
        "--document-ids",
        nargs="+",
        required=True,
        help="Document IDs to validate",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="test_results",
        help="Directory for screenshots/results",
    )

    cli_args = parser.parse_args()
    validator = DashboardValidator(
        base_url=cli_args.base_url,
        document_ids=cli_args.document_ids,
        output_dir=cli_args.output_dir,
    )

    validation_results = asyncio.run(validator.validate())
    print(json.dumps(validation_results, indent=2))
    sys.exit(0 if validation_results.get("status") == "PASS" else 1)
