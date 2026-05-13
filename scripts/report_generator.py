"""Report generation for production pipeline test runs."""

import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.core.types import Stage


class ReportGenerator:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, test_results: dict[str, Any]) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        quality_results = test_results.get("quality_results", {})
        quality_metrics = quality_results.get("metrics", {})
        quality_status = quality_results.get("status", "FAIL")
        dashboard_results = test_results.get("dashboard_results")
        dashboard_status = dashboard_results.get("status") if dashboard_results else None

        dashboard_failed = dashboard_status == "FAIL"
        overall_status = "PASS" if quality_status == "PASS" and not dashboard_failed else "FAIL"

        document_ids = test_results.get("document_ids", [])
        stage_status_metrics = quality_metrics.get("stage_status", {})
        expected_stage_records = stage_status_metrics.get("expected_stage_records")
        dynamic_total_stages = len(document_ids) * len(list(Stage))
        total_stages = int(expected_stage_records) if expected_stage_records is not None else dynamic_total_stages

        raw_completed_stages = int(stage_status_metrics.get("completed_stages", 0))
        completed_stages = min(raw_completed_stages, total_stages) if total_stages > 0 else 0
        success_rate = (completed_stages / total_stages) if total_stages > 0 else 0.0

        report = {
            "result": overall_status,
            "exit_code": 0 if overall_status == "PASS" else 1,
            "test_run": {
                "id": test_results.get("test_run_id"),
                "started_at": test_results.get("started_at"),
                "ended_at": test_results.get("ended_at"),
                "duration_seconds": test_results.get("duration_seconds", 0.0),
            },
            "summary": {
                "documents_processed": len(document_ids),
                "total_stages": total_stages,
                "completed_stages": completed_stages,
                "success_rate": success_rate,
            },
            "documents": {
                "document_ids": document_ids,
                "pdf_paths": test_results.get("pdf_paths", []),
            },
            "quality_metrics": quality_metrics,
            "artifacts": {
                "report_directory": str(self.output_dir),
            },
            "errors": test_results.get("errors", []),
        }

        if dashboard_results is not None:
            report["dashboard_validation"] = {
                "status": dashboard_results.get("status", "FAIL"),
                "checks": dashboard_results.get("checks", []),
                "screenshots": dashboard_results.get("screenshots", []),
                "error": dashboard_results.get("error"),
                "message": dashboard_results.get("message"),
            }

        output_path = self.output_dir / f"production_test_{timestamp}.json"
        report["artifacts"]["report_path"] = str(output_path)

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        self._print_console_summary(report)
        return str(output_path)

    def _print_console_summary(self, report: dict[str, Any]):
        status = report.get("result", "FAIL")
        status_icon = "\u2705" if status == "PASS" else "\u274c"
        color = "\033[92m" if status == "PASS" else "\033[91m"
        reset = "\033[0m"

        summary = report.get("summary", {})
        quality_metrics = report.get("quality_metrics", {})

        print("\n" + "=" * 72)
        print(f"{color}{status_icon} PRODUCTION TEST RESULT: {status}{reset}")
        print("=" * 72)
        print(f"Documents processed : {summary.get('documents_processed', 0)}")
        print(f"Total stages        : {summary.get('total_stages', 0)}")
        print(f"Success rate        : {summary.get('success_rate', 0.0):.2%}")
        print(f"Duration (seconds)  : {report.get('test_run', {}).get('duration_seconds', 0.0):.2f}")

        print("\nQuality Metrics:")
        for metric_name, metric_value in quality_metrics.items():
            metric_status = metric_value.get("status", "FAIL") if isinstance(metric_value, dict) else "FAIL"
            metric_icon = "\u2705" if metric_status == "PASS" else "\u274c"
            print(f"  {metric_icon} {metric_name}: {metric_status}")

        dashboard_validation = report.get("dashboard_validation")
        if dashboard_validation:
            dashboard_status = dashboard_validation.get("status", "FAIL")
            dashboard_icon = (
                "\u2705" if dashboard_status == "PASS" else "\u23f3" if dashboard_status == "PENDING" else "\u274c"
            )
            print(f"\n{dashboard_icon} Dashboard Validation: {dashboard_status}")
            if dashboard_status == "FAIL":
                print("\033[91m!! Dashboard validation failed and marks this run as FAILED.\033[0m")

            screenshots = dashboard_validation.get("screenshots", [])
            if screenshots:
                print("Dashboard screenshots:")
                for screenshot in screenshots:
                    print(f"  - {screenshot}")

        print(f"\nReport file: {report.get('artifacts', {}).get('report_path')}")
        print("=" * 72)

    def _generate_error_report(self, error: Exception, context: dict[str, Any]) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f"production_test_ERROR_{timestamp}.json"

        error_report = {
            "result": "ERROR",
            "timestamp": datetime.now().isoformat(),
            "error": {
                "message": str(error),
                "type": type(error).__name__,
                "stack_trace": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
            },
            "context": context or {},
        }

        with output_path.open("w", encoding="utf-8") as f:
            json.dump(error_report, f, indent=2)

        return str(output_path)
