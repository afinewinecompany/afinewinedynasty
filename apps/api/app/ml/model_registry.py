"""
Model versioning and artifact storage system with MLflow integration.
Handles model registry, versioning, tagging, and rollback capabilities.
"""

import logging
import os
import json
import pickle
import hashlib
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
from dataclasses import dataclass, asdict
import mlflow
import mlflow.sklearn
import mlflow.xgboost
from mlflow.tracking import MlflowClient
from mlflow.exceptions import MlflowException
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


@dataclass
class ModelMetadata:
    """Model metadata structure."""
    model_id: str
    version: str
    name: str
    algorithm: str
    framework: str
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    roc_auc: float
    target_accuracy_met: bool
    training_data_hash: str
    feature_names: List[str]
    hyperparameters: Dict[str, Any]
    created_at: str
    created_by: str
    tags: Dict[str, str]
    artifact_paths: Dict[str, str]
    status: str  # 'training', 'validated', 'staging', 'production', 'archived'


@dataclass
class ModelArtifacts:
    """Model artifacts collection."""
    model_file: str
    feature_engineering_pipeline: Optional[str] = None
    evaluation_metrics: Optional[str] = None
    shap_analysis: Optional[str] = None
    training_logs: Optional[str] = None
    validation_results: Optional[str] = None


class MLflowModelRegistry:
    """MLflow-based model registry with versioning and lifecycle management."""

    def __init__(self, tracking_uri: Optional[str] = None,
                 experiment_name: str = "prospect_prediction_models"):
        """
        Initialize MLflow model registry.

        Args:
            tracking_uri: MLflow tracking server URI
            experiment_name: MLflow experiment name
        """
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)

        self.experiment_name = experiment_name
        self.client = MlflowClient()

        # Set or create experiment
        try:
            self.experiment = mlflow.get_experiment_by_name(experiment_name)
            if self.experiment is None:
                self.experiment_id = mlflow.create_experiment(experiment_name)
            else:
                self.experiment_id = self.experiment.experiment_id
        except Exception as e:
            logger.warning(f"MLflow setup issue: {e}. Using default experiment.")
            self.experiment_id = "0"  # Default experiment

        logger.info(f"MLflow registry initialized with experiment: {experiment_name}")

    def register_model(self, model, model_name: str, model_metadata: ModelMetadata,
                      artifacts: ModelArtifacts,
                      run_description: Optional[str] = None) -> str:
        """
        Register a new model version in MLflow.

        Args:
            model: Trained model object
            model_name: Name for the registered model
            model_metadata: Model metadata
            artifacts: Model artifacts
            run_description: Description for this run

        Returns:
            MLflow run ID
        """
        logger.info(f"Registering model '{model_name}' version {model_metadata.version}")

        with mlflow.start_run(experiment_id=self.experiment_id,
                             run_name=f"{model_name}_v{model_metadata.version}",
                             description=run_description) as run:

            # Log model parameters
            mlflow.log_params(model_metadata.hyperparameters)

            # Log model metrics
            mlflow.log_metrics({
                'accuracy': model_metadata.accuracy,
                'precision': model_metadata.precision,
                'recall': model_metadata.recall,
                'f1_score': model_metadata.f1_score,
                'roc_auc': model_metadata.roc_auc,
                'target_accuracy_met': float(model_metadata.target_accuracy_met)
            })

            # Log model based on framework
            if model_metadata.framework.lower() == 'xgboost':
                mlflow.xgboost.log_model(
                    model,
                    "model",
                    registered_model_name=model_name
                )
            else:
                mlflow.sklearn.log_model(
                    model,
                    "model",
                    registered_model_name=model_name
                )

            # Log artifacts
            self._log_artifacts(artifacts)

            # Set tags
            mlflow.set_tags({
                'model_version': model_metadata.version,
                'algorithm': model_metadata.algorithm,
                'framework': model_metadata.framework,
                'status': model_metadata.status,
                'training_data_hash': model_metadata.training_data_hash,
                **model_metadata.tags
            })

            run_id = run.info.run_id

        logger.info(f"Model registered successfully with run ID: {run_id}")
        return run_id

    def _log_artifacts(self, artifacts: ModelArtifacts) -> None:
        """Log model artifacts to MLflow."""

        if artifacts.evaluation_metrics and os.path.exists(artifacts.evaluation_metrics):
            mlflow.log_artifact(artifacts.evaluation_metrics, "evaluation")

        if artifacts.shap_analysis and os.path.exists(artifacts.shap_analysis):
            mlflow.log_artifact(artifacts.shap_analysis, "interpretability")

        if artifacts.training_logs and os.path.exists(artifacts.training_logs):
            mlflow.log_artifact(artifacts.training_logs, "logs")

        if artifacts.validation_results and os.path.exists(artifacts.validation_results):
            mlflow.log_artifact(artifacts.validation_results, "validation")

        if artifacts.feature_engineering_pipeline and os.path.exists(artifacts.feature_engineering_pipeline):
            mlflow.log_artifact(artifacts.feature_engineering_pipeline, "preprocessing")

    def get_model_version(self, model_name: str, version: Union[str, int] = "latest") -> Dict[str, Any]:
        """
        Get specific model version information.

        Args:
            model_name: Registered model name
            version: Model version ("latest", "staging", "production", or version number)

        Returns:
            Dictionary with model version details
        """
        try:
            if version == "latest":
                model_version = self.client.get_latest_versions(model_name, stages=None)[0]
            elif version in ["staging", "production"]:
                model_versions = self.client.get_latest_versions(model_name, stages=[version.title()])
                if not model_versions:
                    raise ValueError(f"No model in {version} stage")
                model_version = model_versions[0]
            else:
                model_version = self.client.get_model_version(model_name, str(version))

            return {
                'name': model_version.name,
                'version': model_version.version,
                'stage': model_version.current_stage,
                'status': model_version.status,
                'creation_timestamp': model_version.creation_timestamp,
                'last_updated_timestamp': model_version.last_updated_timestamp,
                'description': model_version.description,
                'tags': model_version.tags,
                'run_id': model_version.run_id,
                'source': model_version.source
            }

        except MlflowException as e:
            logger.error(f"Error getting model version: {e}")
            raise

    def promote_model(self, model_name: str, version: str, stage: str,
                     archive_existing: bool = True) -> None:
        """
        Promote model to a specific stage.

        Args:
            model_name: Registered model name
            version: Model version to promote
            stage: Target stage ("Staging", "Production", "Archived")
            archive_existing: Whether to archive existing model in target stage
        """
        logger.info(f"Promoting model {model_name} v{version} to {stage}")

        try:
            # Archive existing model in target stage if requested
            if archive_existing and stage in ["Staging", "Production"]:
                existing_models = self.client.get_latest_versions(model_name, stages=[stage])
                for existing_model in existing_models:
                    self.client.transition_model_version_stage(
                        name=model_name,
                        version=existing_model.version,
                        stage="Archived"
                    )
                    logger.info(f"Archived existing model v{existing_model.version}")

            # Promote new model
            self.client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage=stage
            )

            logger.info(f"Model {model_name} v{version} promoted to {stage}")

        except MlflowException as e:
            logger.error(f"Error promoting model: {e}")
            raise

    def rollback_model(self, model_name: str, target_version: Optional[str] = None) -> str:
        """
        Rollback to a previous model version.

        Args:
            model_name: Registered model name
            target_version: Specific version to rollback to (if None, rollback to previous production)

        Returns:
            Version that was rolled back to
        """
        logger.info(f"Rolling back model {model_name}")

        try:
            if target_version is None:
                # Get all production versions ordered by creation time
                all_versions = self.client.search_model_versions(f"name='{model_name}'")
                production_versions = [
                    v for v in all_versions
                    if v.current_stage == "Production"
                ]

                if len(production_versions) < 2:
                    # Look for staging versions if no previous production version
                    staging_versions = [
                        v for v in all_versions
                        if v.current_stage == "Staging"
                    ]
                    if staging_versions:
                        target_version = staging_versions[0].version
                    else:
                        raise ValueError("No suitable version found for rollback")
                else:
                    # Get second most recent production version
                    production_versions.sort(key=lambda x: x.creation_timestamp, reverse=True)
                    target_version = production_versions[1].version

            # Archive current production
            current_production = self.client.get_latest_versions(model_name, stages=["Production"])
            if current_production:
                self.client.transition_model_version_stage(
                    name=model_name,
                    version=current_production[0].version,
                    stage="Archived"
                )

            # Promote target version to production
            self.client.transition_model_version_stage(
                name=model_name,
                version=target_version,
                stage="Production"
            )

            logger.info(f"Rolled back to model {model_name} v{target_version}")
            return target_version

        except MlflowException as e:
            logger.error(f"Error during rollback: {e}")
            raise

    def load_model(self, model_name: str, version: Union[str, int] = "latest"):
        """
        Load model from registry.

        Args:
            model_name: Registered model name
            version: Model version to load

        Returns:
            Loaded model object
        """
        try:
            if version == "latest":
                model_uri = f"models:/{model_name}/latest"
            elif version in ["staging", "production"]:
                model_uri = f"models:/{model_name}/{version.title()}"
            else:
                model_uri = f"models:/{model_name}/{version}"

            model = mlflow.pyfunc.load_model(model_uri)
            logger.info(f"Model {model_name} v{version} loaded successfully")
            return model

        except MlflowException as e:
            logger.error(f"Error loading model: {e}")
            raise

    def list_models(self, filter_string: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all registered models.

        Args:
            filter_string: Optional filter for model search

        Returns:
            List of model information dictionaries
        """
        try:
            if filter_string:
                models = self.client.search_registered_models(filter_string)
            else:
                models = self.client.search_registered_models()

            model_list = []
            for model in models:
                latest_versions = self.client.get_latest_versions(model.name)

                model_info = {
                    'name': model.name,
                    'description': model.description,
                    'creation_timestamp': model.creation_timestamp,
                    'last_updated_timestamp': model.last_updated_timestamp,
                    'tags': model.tags,
                    'latest_versions': [
                        {
                            'version': v.version,
                            'stage': v.current_stage,
                            'status': v.status
                        } for v in latest_versions
                    ]
                }
                model_list.append(model_info)

            return model_list

        except MlflowException as e:
            logger.error(f"Error listing models: {e}")
            raise


class S3ArtifactStore:
    """S3-compatible artifact storage for model files and metadata."""

    def __init__(self, bucket_name: str, aws_access_key_id: Optional[str] = None,
                 aws_secret_access_key: Optional[str] = None,
                 endpoint_url: Optional[str] = None):
        """
        Initialize S3 artifact store.

        Args:
            bucket_name: S3 bucket name
            aws_access_key_id: AWS access key
            aws_secret_access_key: AWS secret key
            endpoint_url: Custom S3 endpoint URL (for S3-compatible services)
        """
        self.bucket_name = bucket_name

        try:
            # Initialize S3 client
            session = boto3.Session(
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key
            )

            self.s3_client = session.client(
                's3',
                endpoint_url=endpoint_url
            )

            # Test connection and create bucket if it doesn't exist
            try:
                self.s3_client.head_bucket(Bucket=bucket_name)
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    self.s3_client.create_bucket(Bucket=bucket_name)
                    logger.info(f"Created S3 bucket: {bucket_name}")
                else:
                    raise

            logger.info(f"S3 artifact store initialized with bucket: {bucket_name}")

        except NoCredentialsError:
            logger.warning("S3 credentials not found. S3 storage will not be available.")
            self.s3_client = None

    def upload_artifact(self, local_path: str, s3_key: str,
                       metadata: Optional[Dict[str, str]] = None) -> str:
        """
        Upload artifact to S3.

        Args:
            local_path: Local file path
            s3_key: S3 object key
            metadata: Optional metadata to attach

        Returns:
            S3 URI of uploaded artifact
        """
        if self.s3_client is None:
            raise RuntimeError("S3 client not available")

        try:
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = metadata

            self.s3_client.upload_file(
                local_path, self.bucket_name, s3_key, ExtraArgs=extra_args
            )

            s3_uri = f"s3://{self.bucket_name}/{s3_key}"
            logger.info(f"Uploaded artifact to {s3_uri}")
            return s3_uri

        except ClientError as e:
            logger.error(f"Error uploading to S3: {e}")
            raise

    def download_artifact(self, s3_key: str, local_path: str) -> None:
        """
        Download artifact from S3.

        Args:
            s3_key: S3 object key
            local_path: Local destination path
        """
        if self.s3_client is None:
            raise RuntimeError("S3 client not available")

        try:
            # Ensure local directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            self.s3_client.download_file(self.bucket_name, s3_key, local_path)
            logger.info(f"Downloaded artifact from s3://{self.bucket_name}/{s3_key}")

        except ClientError as e:
            logger.error(f"Error downloading from S3: {e}")
            raise

    def list_artifacts(self, prefix: str = "") -> List[Dict[str, Any]]:
        """
        List artifacts in S3 bucket.

        Args:
            prefix: S3 key prefix to filter by

        Returns:
            List of artifact information
        """
        if self.s3_client is None:
            raise RuntimeError("S3 client not available")

        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, Prefix=prefix
            )

            artifacts = []
            for obj in response.get('Contents', []):
                artifacts.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    's3_uri': f"s3://{self.bucket_name}/{obj['Key']}"
                })

            return artifacts

        except ClientError as e:
            logger.error(f"Error listing S3 artifacts: {e}")
            raise


class ModelVersioningSystem:
    """Complete model versioning system combining MLflow and S3 storage."""

    def __init__(self, mlflow_tracking_uri: Optional[str] = None,
                 s3_bucket: Optional[str] = None,
                 local_artifacts_dir: str = "./model_artifacts"):
        """
        Initialize model versioning system.

        Args:
            mlflow_tracking_uri: MLflow tracking server URI
            s3_bucket: S3 bucket for artifact storage
            local_artifacts_dir: Local directory for artifacts
        """
        self.local_artifacts_dir = Path(local_artifacts_dir)
        self.local_artifacts_dir.mkdir(exist_ok=True)

        # Initialize MLflow registry
        self.mlflow_registry = MLflowModelRegistry(mlflow_tracking_uri)

        # Initialize S3 storage if configured
        self.s3_store = None
        if s3_bucket:
            try:
                self.s3_store = S3ArtifactStore(s3_bucket)
            except Exception as e:
                logger.warning(f"S3 storage not available: {e}")

        logger.info("Model versioning system initialized")

    def create_model_artifacts(self, model_name: str, version: str,
                              model, training_results: Dict[str, Any],
                              feature_pipeline=None,
                              shap_analysis: Optional[Dict[str, Any]] = None) -> ModelArtifacts:
        """
        Create and save model artifacts.

        Args:
            model_name: Model name
            version: Model version
            model: Trained model object
            training_results: Training results dictionary
            feature_pipeline: Feature engineering pipeline
            shap_analysis: SHAP analysis results

        Returns:
            ModelArtifacts object with file paths
        """
        logger.info(f"Creating artifacts for {model_name} v{version}")

        # Create version directory
        version_dir = self.local_artifacts_dir / model_name / version
        version_dir.mkdir(parents=True, exist_ok=True)

        artifacts = ModelArtifacts(model_file="")

        # Save model
        model_path = version_dir / "model.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        artifacts.model_file = str(model_path)

        # Save feature pipeline
        if feature_pipeline:
            pipeline_path = version_dir / "feature_pipeline.pkl"
            with open(pipeline_path, 'wb') as f:
                pickle.dump(feature_pipeline, f)
            artifacts.feature_engineering_pipeline = str(pipeline_path)

        # Save evaluation metrics
        if training_results:
            metrics_path = version_dir / "evaluation_metrics.json"
            with open(metrics_path, 'w') as f:
                json.dump(training_results, f, indent=2, default=str)
            artifacts.evaluation_metrics = str(metrics_path)

        # Save SHAP analysis
        if shap_analysis:
            shap_path = version_dir / "shap_analysis.json"
            with open(shap_path, 'w') as f:
                json.dump(shap_analysis, f, indent=2, default=str)
            artifacts.shap_analysis = str(shap_path)

        # Upload to S3 if available
        if self.s3_store:
            self._upload_artifacts_to_s3(model_name, version, artifacts)

        logger.info(f"Artifacts created for {model_name} v{version}")
        return artifacts

    def _upload_artifacts_to_s3(self, model_name: str, version: str,
                               artifacts: ModelArtifacts) -> None:
        """Upload artifacts to S3 storage."""
        try:
            s3_prefix = f"models/{model_name}/{version}/"

            # Upload model file
            if artifacts.model_file:
                s3_key = f"{s3_prefix}model.pkl"
                self.s3_store.upload_artifact(artifacts.model_file, s3_key)

            # Upload other artifacts
            artifact_files = [
                (artifacts.feature_engineering_pipeline, "feature_pipeline.pkl"),
                (artifacts.evaluation_metrics, "evaluation_metrics.json"),
                (artifacts.shap_analysis, "shap_analysis.json"),
                (artifacts.training_logs, "training_logs.txt"),
                (artifacts.validation_results, "validation_results.json")
            ]

            for file_path, s3_name in artifact_files:
                if file_path and os.path.exists(file_path):
                    s3_key = f"{s3_prefix}{s3_name}"
                    self.s3_store.upload_artifact(file_path, s3_key)

        except Exception as e:
            logger.warning(f"Failed to upload artifacts to S3: {e}")

    def register_model_version(self, model_name: str, model,
                              training_results: Dict[str, Any],
                              feature_names: List[str],
                              hyperparameters: Dict[str, Any],
                              tags: Optional[Dict[str, str]] = None,
                              feature_pipeline=None,
                              shap_analysis: Optional[Dict[str, Any]] = None) -> str:
        """
        Register a new model version with complete artifacts.

        Args:
            model_name: Model name
            model: Trained model object
            training_results: Training results
            feature_names: List of feature names
            hyperparameters: Model hyperparameters
            tags: Optional tags
            feature_pipeline: Feature engineering pipeline
            shap_analysis: SHAP analysis results

        Returns:
            MLflow run ID
        """
        # Generate version string
        version = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create model metadata
        test_results = training_results.get('test_results', {})
        metadata = ModelMetadata(
            model_id=f"{model_name}_{version}",
            version=version,
            name=model_name,
            algorithm=training_results.get('tuning_results', {}).get('tuning_method', 'xgboost'),
            framework='xgboost',
            accuracy=test_results.get('accuracy', 0.0),
            precision=test_results.get('precision', 0.0),
            recall=test_results.get('recall', 0.0),
            f1_score=test_results.get('f1', 0.0),
            roc_auc=test_results.get('roc_auc', 0.0),
            target_accuracy_met=training_results.get('target_accuracy_achieved', False),
            training_data_hash=self._calculate_data_hash(feature_names),
            feature_names=feature_names,
            hyperparameters=hyperparameters,
            created_at=datetime.now().isoformat(),
            created_by="training_pipeline",
            tags=tags or {},
            artifact_paths={},
            status="validated" if test_results.get('accuracy', 0) >= 0.65 else "training"
        )

        # Create artifacts
        artifacts = self.create_model_artifacts(
            model_name, version, model, training_results,
            feature_pipeline, shap_analysis
        )

        # Register in MLflow
        run_id = self.mlflow_registry.register_model(
            model, model_name, metadata, artifacts,
            f"Model training run for {model_name} v{version}"
        )

        logger.info(f"Model {model_name} v{version} registered successfully")
        return run_id

    def _calculate_data_hash(self, feature_names: List[str]) -> str:
        """Calculate hash of training data configuration."""
        data_config = {
            'feature_names': sorted(feature_names),
            'timestamp': datetime.now().date().isoformat()
        }
        return hashlib.md5(json.dumps(data_config, sort_keys=True).encode()).hexdigest()

    def get_production_model(self, model_name: str):
        """Get current production model."""
        return self.mlflow_registry.load_model(model_name, "production")

    def promote_to_production(self, model_name: str, version: str) -> None:
        """Promote model version to production."""
        self.mlflow_registry.promote_model(model_name, version, "Production")

    def rollback_production(self, model_name: str, target_version: Optional[str] = None) -> str:
        """Rollback production model."""
        return self.mlflow_registry.rollback_model(model_name, target_version)

    def cleanup_old_versions(self, model_name: str, keep_versions: int = 5) -> None:
        """
        Archive old model versions, keeping only the specified number.

        Args:
            model_name: Model name
            keep_versions: Number of versions to keep
        """
        try:
            all_versions = self.mlflow_registry.client.search_model_versions(f"name='{model_name}'")

            # Sort by creation time, newest first
            all_versions.sort(key=lambda x: x.creation_timestamp, reverse=True)

            # Skip production and staging versions, and keep the specified number
            versions_to_archive = []
            kept_count = 0

            for version in all_versions:
                if version.current_stage in ["Production", "Staging"]:
                    continue
                if kept_count < keep_versions:
                    kept_count += 1
                    continue
                versions_to_archive.append(version)

            # Archive old versions
            for version in versions_to_archive:
                self.mlflow_registry.client.transition_model_version_stage(
                    name=model_name,
                    version=version.version,
                    stage="Archived"
                )

            logger.info(f"Archived {len(versions_to_archive)} old versions of {model_name}")

        except Exception as e:
            logger.error(f"Error cleaning up old versions: {e}")

    def export_model_lineage(self, model_name: str) -> Dict[str, Any]:
        """
        Export complete model lineage and version history.

        Args:
            model_name: Model name

        Returns:
            Dictionary with model lineage information
        """
        try:
            all_versions = self.mlflow_registry.client.search_model_versions(f"name='{model_name}'")

            lineage = {
                'model_name': model_name,
                'total_versions': len(all_versions),
                'export_timestamp': datetime.now().isoformat(),
                'versions': []
            }

            for version in all_versions:
                version_info = {
                    'version': version.version,
                    'stage': version.current_stage,
                    'status': version.status,
                    'creation_timestamp': version.creation_timestamp,
                    'description': version.description,
                    'tags': version.tags,
                    'run_id': version.run_id
                }

                # Get run details if available
                try:
                    run = self.mlflow_registry.client.get_run(version.run_id)
                    version_info['metrics'] = run.data.metrics
                    version_info['params'] = run.data.params
                except Exception:
                    pass

                lineage['versions'].append(version_info)

            return lineage

        except Exception as e:
            logger.error(f"Error exporting model lineage: {e}")
            raise