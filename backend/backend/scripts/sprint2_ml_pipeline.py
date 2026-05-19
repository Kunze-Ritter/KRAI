#!/usr/bin/env python3
"""
Sprint 2 ML Pipeline: Complete workflow from Radix import to predictions.

Orchestrates:
1. Radix data import (service tickets)
2. Feature extraction
3. Model training with cross-validation
4. Batch predictions
5. Results persistence

Usage:
    python scripts/sprint2_ml_pipeline.py --radix-token <TOKEN> --limit 1000

Or with Radix login credentials (generates token):
    python scripts/sprint2_ml_pipeline.py \
        --radix-username HAT \
        --radix-password-b64 NzU1aGg2 \
        --radix-code 1FB \
        --radix-license APP-RX+SM_1FB \
        --limit 1000
"""

import asyncio
import logging
import os
from datetime import datetime

import click

from backend.pm.evaluation.model_evaluator import ModelEvaluator
from backend.pm.features.feature_engineer import FeatureEngineer
from backend.pm.models.long_tail_classifier import LongTailClassifier
from backend.pm.services.prediction_service import PredictionService
from backend.pm.services.radix_data_client import RadixDataClient
from backend.pm.services.radix_importer import RadixImporter
from backend.services.database_adapter import PostgreSQLAdapter

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def generate_radix_token(
    api_url: str,
    username: str,
    password_b64: str,
    code: str,
    license_id: str,
) -> str:
    """
    Generate Radix Bearer token via login endpoint.

    Args:
        api_url: Radix API base URL
        username: Radix username
        password_b64: Base64-encoded password
        code: Client code (e.g., "1FB")
        license_id: License ID (e.g., "APP-RX+SM_1FB")

    Returns:
        Bearer token (JWT)
    """
    import aiohttp

    login_url = f"{api_url}/api/authenticateApps/login/apps"
    headers = {"Content-Type": "application/json", "Accept-Language": "DE"}
    payload = {
        "username": username,
        "password": password_b64,
        "code": code,
        "language": "DE",
        "licenseId": license_id,
        "metaData": "string",
    }

    logger.info(f"Generating Radix Bearer token for user {username}...")

    async with aiohttp.ClientSession() as session:
        async with session.post(login_url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise ValueError(f"Radix login failed: {resp.status} {text[:200]}")

            data = await resp.json()
            token = data.get("token")
            expiration = data.get("expiration")

            if not token:
                raise ValueError(f"No token in response: {data}")

            logger.info(f"✓ Token generated (expires: {expiration})")
            return token


async def run_sprint2_pipeline(
    radix_token: str,
    import_limit: int = 1000,
    skip_import: bool = False,
    skip_training: bool = False,
) -> dict:
    """
    Execute complete Sprint 2 ML pipeline.

    Args:
        radix_token: Radix Bearer token
        import_limit: Max tickets to import from Radix
        skip_import: Skip Radix import (use existing tickets)
        skip_training: Skip model training (use existing model)

    Returns:
        Pipeline results summary
    """
    db = PostgreSQLAdapter()
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "import": {"status": "skipped"},
        "features": {"status": "skipped"},
        "training": {"status": "skipped"},
        "predictions": {"status": "skipped"},
    }

    try:
        # ===== STEP 1: RADIX IMPORT =====
        if not skip_import:
            logger.info("\n" + "=" * 70)
            logger.info("STEP 1: Import Radix service tickets")
            logger.info("=" * 70)

            api_url = os.getenv(
                "RADIX_API_URL",
                "https://radix.kunze-ritter.de/IM.RxPlusService.Api",
            )
            radix = RadixDataClient(api_url, radix_token)
            importer = RadixImporter(db, radix)

            try:
                async with radix:
                    import_result = await importer.import_activities(
                        limit=import_limit,
                        skip_duplicates=True,
                    )
                    results["import"] = {
                        "status": "success",
                        **import_result,
                    }
                    logger.info(
                        f"✓ Import complete: {import_result['imported']} imported, "
                        f"{import_result['skipped']} skipped, {import_result['errors']} errors"
                    )
            except Exception as e:
                logger.error(f"✗ Import failed: {e}")
                results["import"]["status"] = "error"
                results["import"]["error"] = str(e)
                raise

        # ===== STEP 2: FEATURE EXTRACTION =====
        logger.info("\n" + "=" * 70)
        logger.info("STEP 2: Extract features for all tickets")
        logger.info("=" * 70)

        engineer = FeatureEngineer(db)
        features_list = await engineer.extract_features_batch(limit=None)

        logger.info(f"✓ Extracted features for {len(features_list)} tickets")
        results["features"] = {
            "status": "success",
            "count": len(features_list),
        }

        if not features_list:
            logger.warning("⚠ No tickets found for feature extraction")
            return results

        # ===== STEP 3: BUILD LABELS =====
        logger.info("\n" + "=" * 70)
        logger.info("STEP 3: Build training labels (Common vs Long-Tail)")
        logger.info("=" * 70)

        top_problems = await engineer.get_top_problems(top_n=20)
        labels = LongTailClassifier.build_labels(features_list, top_problems)

        common_count = sum(labels)
        longtail_count = len(labels) - common_count

        logger.info("✓ Label distribution:")
        logger.info(f"  Common:    {common_count} ({100*common_count/len(labels):.1f}%)")
        logger.info(f"  Long-Tail: {longtail_count} ({100*longtail_count/len(labels):.1f}%)")

        # ===== STEP 4: TRAIN MODEL =====
        if not skip_training:
            logger.info("\n" + "=" * 70)
            logger.info("STEP 4: Train XGBoost classifier with 5-fold CV")
            logger.info("=" * 70)

            classifier = LongTailClassifier()
            train_metrics = await asyncio.to_thread(classifier.fit, features_list, labels)

            logger.info("✓ Training complete:")
            for metric, value in train_metrics.items():
                logger.info(f"  {metric}: {value:.4f}")

            results["training"] = {
                "status": "success",
                "metrics": train_metrics,
            }

            # ===== STEP 5: EVALUATE WITH CROSS-VALIDATION =====
            logger.info("\n" + "=" * 70)
            logger.info("STEP 5: Evaluate model (5-fold Stratified CV)")
            logger.info("=" * 70)

            evaluator = ModelEvaluator()
            cv_results = await asyncio.to_thread(evaluator.cross_validate, classifier, features_list, labels, cv=5)

            logger.info("✓ Cross-validation results:")
            for metric, scores in cv_results.items():
                mean = sum(scores) / len(scores)
                logger.info(f"  {metric}: {mean:.4f} (±{max(scores)-min(scores):.4f})")

            results["training"]["cv_metrics"] = cv_results

            # Feature importance
            importance = classifier.get_feature_importance()
            if importance:
                logger.info("\nTop 5 important features:")
                for feature, score in sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5]:
                    logger.info(f"  {feature}: {score:.4f}")

        # ===== STEP 6: BATCH PREDICTIONS =====
        logger.info("\n" + "=" * 70)
        logger.info("STEP 6: Run batch predictions on all tickets")
        logger.info("=" * 70)

        classifier = LongTailClassifier.load() if skip_training else classifier
        prediction_service = PredictionService(db, engineer, classifier)

        prediction_result = await prediction_service.run_batch()
        results["predictions"] = {
            "status": "success",
            **prediction_result,
        }

        logger.info(
            f"✓ Predictions complete: {prediction_result['predicted']} predicted, "
            f"{prediction_result['skipped']} skipped, {prediction_result['errors']} errors"
        )

        # ===== SUMMARY =====
        logger.info("\n" + "=" * 70)
        logger.info("PIPELINE COMPLETE ✓")
        logger.info("=" * 70)
        logger.info(f"Total tickets: {len(features_list)}")
        logger.info(f"Common: {common_count} | Long-Tail: {longtail_count}")
        if results["predictions"]["status"] == "success":
            logger.info(f"Predictions stored: {prediction_result['predicted']} → krai_pm.predictions")

        return results

    except Exception as e:
        logger.error(f"\n✗ Pipeline failed: {e}", exc_info=True)
        raise
    finally:
        await db.close()


@click.command()
@click.option(
    "--radix-token",
    type=str,
    help="Radix Bearer token (mutually exclusive with login credentials)",
)
@click.option(
    "--radix-username",
    type=str,
    help="Radix username (for token generation)",
)
@click.option(
    "--radix-password-b64",
    type=str,
    help="Radix password (Base64-encoded)",
)
@click.option(
    "--radix-code",
    type=str,
    default="1FB",
    help="Radix client code (default: 1FB)",
)
@click.option(
    "--radix-license",
    type=str,
    default="APP-RX+SM_1FB",
    help="Radix license ID (default: APP-RX+SM_1FB)",
)
@click.option(
    "--radix-api-url",
    type=str,
    default="https://radix.kunze-ritter.de/IM.RxPlusService.Api",
    help="Radix API URL",
)
@click.option(
    "--limit",
    type=int,
    default=1000,
    help="Max tickets to import (default: 1000)",
)
@click.option(
    "--skip-import",
    is_flag=True,
    help="Skip Radix import, use existing tickets",
)
@click.option(
    "--skip-training",
    is_flag=True,
    help="Skip model training, use existing model",
)
def main(
    radix_token: str,
    radix_username: str,
    radix_password_b64: str,
    radix_code: str,
    radix_license: str,
    radix_api_url: str,
    limit: int,
    skip_import: bool,
    skip_training: bool,
) -> None:
    """Sprint 2 ML Pipeline: Import → Features → Train → Predict."""

    # Get or generate token
    if not radix_token:
        if not (radix_username and radix_password_b64):
            raise click.UsageError("Either --radix-token or both --radix-username and --radix-password-b64 required")

        radix_token = asyncio.run(
            generate_radix_token(radix_api_url, radix_username, radix_password_b64, radix_code, radix_license)
        )

    # Run pipeline
    results = asyncio.run(
        run_sprint2_pipeline(
            radix_token=radix_token,
            import_limit=limit,
            skip_import=skip_import,
            skip_training=skip_training,
        )
    )

    click.echo(f"\n\n📊 Results saved to: {results['timestamp']}")


if __name__ == "__main__":
    main()
