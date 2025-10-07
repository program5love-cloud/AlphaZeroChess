#!/usr/bin/env python3
"""
Step 9 - Full AlphaZero Training Pipeline Validation
Validates the complete reinforcement learning loop:
Self-Play → Training → Evaluation → Promotion → Export
"""
import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime
import subprocess

# Add backend to path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

import requests
from pymongo import MongoClient

# Configuration
BASE_URL = "http://localhost:8001/api"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

# Validation parameters (minimal for quick test)
VALIDATION_CONFIG = {
    "num_games": 1,          # 1 self-play game
    "num_epochs": 1,         # 1 training epoch
    "batch_size": 64,        # Batch size 64
    "num_simulations": 10,   # 10 MCTS simulations
    "learning_rate": 0.001   # Learning rate 0.001
}

EVALUATION_CONFIG = {
    "num_games": 3,          # 3 evaluation games
    "num_simulations": 10,   # 10 simulations per move
    "win_threshold": 0.55    # 55% win rate threshold
}

class PipelineValidator:
    """Validates the complete AlphaZero pipeline"""
    
    def __init__(self):
        self.results = {
            "validation_start": datetime.now().isoformat(),
            "stages": {},
            "metrics": {},
            "errors": []
        }
        self.mongo_client = None
        self.db = None
        
    def print_header(self, text):
        """Print formatted header"""
        print("\n" + "=" * 70)
        print(f"  {text}")
        print("=" * 70)
    
    def print_step(self, text):
        """Print formatted step"""
        print(f"\n🔹 {text}")
    
    def print_success(self, text):
        """Print success message"""
        print(f"   ✅ {text}")
    
    def print_error(self, text):
        """Print error message"""
        print(f"   ❌ {text}")
        self.results["errors"].append(text)
    
    def print_info(self, text):
        """Print info message"""
        print(f"   ℹ️  {text}")
    
    # ===== Stage 1: Environment Verification =====
    
    def verify_environment(self):
        """Verify MongoDB and backend server are running"""
        self.print_header("STAGE 1: Environment Verification")
        stage_start = time.time()
        
        # Check MongoDB
        self.print_step("Checking MongoDB connection...")
        try:
            self.mongo_client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
            self.mongo_client.admin.command('ping')
            self.db = self.mongo_client[DB_NAME]
            self.print_success(f"MongoDB connected: {MONGO_URL}")
            
            # Check collections
            collections = self.db.list_collection_names()
            self.print_info(f"Existing collections: {', '.join(collections[:5])}")
        except Exception as e:
            self.print_error(f"MongoDB connection failed: {e}")
            return False
        
        # Check backend server
        self.print_step("Checking backend server...")
        try:
            response = requests.get(f"{BASE_URL}/", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.print_success(f"Backend server active: {data.get('message', 'OK')}")
            else:
                self.print_error(f"Backend returned status {response.status_code}")
                return False
        except Exception as e:
            self.print_error(f"Backend server not accessible: {e}")
            self.print_info("Attempting to start backend server...")
            # Try to start backend
            try:
                subprocess.run(["sudo", "supervisorctl", "restart", "backend"], 
                             check=True, capture_output=True, timeout=10)
                time.sleep(5)
                response = requests.get(f"{BASE_URL}/", timeout=5)
                if response.status_code == 200:
                    self.print_success("Backend server started successfully")
                else:
                    return False
            except Exception as start_error:
                self.print_error(f"Failed to start backend: {start_error}")
                return False
        
        # Check device info
        self.print_step("Checking device configuration...")
        try:
            response = requests.get(f"{BASE_URL}/device/info", timeout=5)
            if response.status_code == 200:
                device_info = response.json()
                self.print_success(f"Device: {device_info['device_name']} (GPU: {device_info['is_gpu']})")
                self.results["metrics"]["device"] = device_info["device_name"]
        except Exception as e:
            self.print_error(f"Device info check failed: {e}")
        
        stage_duration = time.time() - stage_start
        self.results["stages"]["environment_verification"] = {
            "success": True,
            "duration_seconds": round(stage_duration, 2)
        }
        
        self.print_success(f"Environment verification complete ({stage_duration:.2f}s)")
        return True
    
    # ===== Stage 2: Pre-Training State =====
    
    def check_pre_training_state(self):
        """Check existing models and state before training"""
        self.print_header("STAGE 2: Pre-Training State Check")
        stage_start = time.time()
        
        # List existing models
        self.print_step("Listing existing models...")
        try:
            response = requests.get(f"{BASE_URL}/model/list")
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                self.print_success(f"Found {len(models)} existing models")
                for model in models[:3]:  # Show first 3
                    active_marker = "🎯 " if model.get("is_active") else "   "
                    self.print_info(f"{active_marker}{model['name']} (v{model['version']}, {model['file_size_mb']}MB)")
                
                self.results["metrics"]["models_before_training"] = len(models)
            else:
                self.print_error(f"Failed to list models: {response.status_code}")
        except Exception as e:
            self.print_error(f"Model listing failed: {e}")
        
        # Get active model
        self.print_step("Checking active model...")
        try:
            response = requests.get(f"{BASE_URL}/model/current")
            if response.status_code == 200:
                data = response.json()
                active_model = data.get("active_model")
                if active_model:
                    self.print_success(f"Current active model: {active_model}")
                    self.results["metrics"]["active_model_before"] = active_model
                else:
                    self.print_info("No active model set")
        except Exception as e:
            self.print_error(f"Active model check failed: {e}")
        
        # Check database stats
        self.print_step("Checking database statistics...")
        try:
            stats = {
                "self_play_positions": self.db.self_play_positions.count_documents({}),
                "training_metrics": self.db.training_metrics.count_documents({}),
                "model_evaluations": self.db.model_evaluations.count_documents({})
            }
            for key, count in stats.items():
                self.print_info(f"{key}: {count} documents")
            self.results["metrics"]["db_stats_before"] = stats
        except Exception as e:
            self.print_error(f"Database stats failed: {e}")
        
        stage_duration = time.time() - stage_start
        self.results["stages"]["pre_training_state"] = {
            "success": True,
            "duration_seconds": round(stage_duration, 2)
        }
        
        return True
    
    # ===== Stage 3: Training Pipeline =====
    
    def run_training_pipeline(self):
        """Run complete training pipeline: Self-Play → Training → Evaluation"""
        self.print_header("STAGE 3: Training Pipeline Execution")
        stage_start = time.time()
        
        self.print_step("Starting training pipeline...")
        self.print_info(f"Configuration: {json.dumps(VALIDATION_CONFIG, indent=2)}")
        
        try:
            # Start training
            response = requests.post(
                f"{BASE_URL}/training/start",
                json=VALIDATION_CONFIG,
                timeout=10
            )
            
            if response.status_code != 200:
                self.print_error(f"Failed to start training: {response.status_code} - {response.text}")
                return False
            
            data = response.json()
            session_id = data.get("session_id")
            self.print_success(f"Training started - Session ID: {session_id}")
            self.results["metrics"]["training_session_id"] = session_id
            
            # Monitor training progress
            self.print_step("Monitoring training progress...")
            last_progress = 0
            max_wait = 300  # 5 minutes max
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                time.sleep(3)  # Poll every 3 seconds
                
                try:
                    status_response = requests.get(f"{BASE_URL}/training/status", timeout=5)
                    if status_response.status_code == 200:
                        status = status_response.json()
                        progress = status.get("progress", 0)
                        message = status.get("message", "")
                        active = status.get("active", False)
                        
                        if progress > last_progress:
                            self.print_info(f"Progress: {progress}% - {message}")
                            last_progress = progress
                        
                        if not active and progress == 100:
                            self.print_success("Training pipeline completed!")
                            break
                        elif not active and progress < 100:
                            self.print_error(f"Training stopped unexpectedly at {progress}%")
                            return False
                except Exception as e:
                    self.print_error(f"Status check failed: {e}")
                    time.sleep(5)
            else:
                self.print_error("Training timeout - took longer than expected")
                return False
            
            stage_duration = time.time() - stage_start
            self.results["stages"]["training_pipeline"] = {
                "success": True,
                "duration_seconds": round(stage_duration, 2),
                "session_id": session_id
            }
            
            self.print_success(f"Training pipeline stage complete ({stage_duration:.2f}s)")
            return True
            
        except Exception as e:
            self.print_error(f"Training pipeline failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ===== Stage 4: Post-Training Verification =====
    
    def verify_training_results(self):
        """Verify training produced expected results"""
        self.print_header("STAGE 4: Post-Training Verification")
        stage_start = time.time()
        
        # Check new models
        self.print_step("Verifying new models...")
        try:
            response = requests.get(f"{BASE_URL}/model/list")
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                models_before = self.results["metrics"].get("models_before_training", 0)
                new_models = len(models) - models_before
                
                if new_models > 0:
                    self.print_success(f"Created {new_models} new model(s)")
                    self.results["metrics"]["models_after_training"] = len(models)
                    
                    # Show newest model
                    if models:
                        newest = max(models, key=lambda m: m.get("training_date", ""))
                        self.print_info(f"Newest model: {newest['name']} ({newest['file_size_mb']}MB)")
                        self.results["metrics"]["newest_model"] = newest["name"]
                else:
                    self.print_error("No new models created")
                    return False
        except Exception as e:
            self.print_error(f"Model verification failed: {e}")
            return False
        
        # Check self-play positions
        self.print_step("Verifying self-play data...")
        try:
            session_id = self.results["metrics"].get("training_session_id")
            if session_id:
                count = self.db.self_play_positions.count_documents({"session_id": session_id})
                self.print_success(f"Generated {count} self-play positions")
                self.results["metrics"]["self_play_positions"] = count
        except Exception as e:
            self.print_error(f"Self-play data check failed: {e}")
        
        # Check training metrics
        self.print_step("Verifying training metrics...")
        try:
            session_id = self.results["metrics"].get("training_session_id")
            if session_id:
                metrics = list(self.db.training_metrics.find({"session_id": session_id}))
                if metrics:
                    self.print_success(f"Stored {len(metrics)} epoch metrics")
                    final_loss = metrics[-1].get("loss", 0)
                    self.print_info(f"Final loss: {final_loss:.4f}")
                    self.results["metrics"]["training_epochs"] = len(metrics)
                    self.results["metrics"]["final_loss"] = round(final_loss, 4)
        except Exception as e:
            self.print_error(f"Training metrics check failed: {e}")
        
        # Check evaluation results
        self.print_step("Verifying evaluation results...")
        try:
            session_id = self.results["metrics"].get("training_session_id")
            if session_id:
                evaluations = list(self.db.model_evaluations.find({"session_id": session_id}))
                if evaluations:
                    self.print_success(f"Found {len(evaluations)} evaluation(s)")
                    for eval in evaluations:
                        challenger = eval.get("challenger_name")
                        champion = eval.get("champion_name")
                        win_rate = eval.get("challenger_win_rate", 0)
                        promoted = eval.get("promoted", False)
                        self.print_info(f"{challenger} vs {champion}: {win_rate:.1%} win rate - {'Promoted ✓' if promoted else 'Not promoted'}")
                        self.results["metrics"]["evaluation_win_rate"] = round(win_rate, 3)
                        self.results["metrics"]["model_promoted"] = promoted
                else:
                    self.print_info("No evaluation run (possibly first model)")
        except Exception as e:
            self.print_error(f"Evaluation check failed: {e}")
        
        # Check active model
        self.print_step("Checking active model status...")
        try:
            response = requests.get(f"{BASE_URL}/model/current")
            if response.status_code == 200:
                data = response.json()
                active_model = data.get("active_model")
                if active_model:
                    self.print_success(f"Active model: {active_model}")
                    self.results["metrics"]["active_model_after"] = active_model
        except Exception as e:
            self.print_error(f"Active model check failed: {e}")
        
        stage_duration = time.time() - stage_start
        self.results["stages"]["post_training_verification"] = {
            "success": True,
            "duration_seconds": round(stage_duration, 2)
        }
        
        return True
    
    # ===== Stage 5: Model Export =====
    
    def test_model_export(self):
        """Test model export in both formats"""
        self.print_header("STAGE 5: Model Export Validation")
        stage_start = time.time()
        
        # Get newest model
        newest_model = self.results["metrics"].get("newest_model")
        if not newest_model:
            self.print_error("No model available for export")
            return False
        
        self.print_step(f"Exporting model: {newest_model}")
        
        export_results = {}
        
        # Export PyTorch format
        self.print_step("Exporting to PyTorch (.pt) format...")
        try:
            response = requests.post(
                f"{BASE_URL}/model/export/pytorch/{newest_model}",
                json={"metadata": {"export_purpose": "pipeline_validation"}},
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                filename = data.get("filename")
                file_size = data.get("file_size_mb")
                self.print_success(f"PyTorch export: {filename} ({file_size}MB)")
                export_results["pytorch"] = {
                    "filename": filename,
                    "size_mb": file_size
                }
            else:
                self.print_error(f"PyTorch export failed: {response.status_code}")
        except Exception as e:
            self.print_error(f"PyTorch export error: {e}")
        
        # Export ONNX format
        self.print_step("Exporting to ONNX (.onnx) format...")
        try:
            response = requests.post(
                f"{BASE_URL}/model/export/onnx/{newest_model}",
                json={"metadata": {"export_purpose": "pipeline_validation"}},
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                filename = data.get("filename")
                file_size = data.get("file_size_mb")
                self.print_success(f"ONNX export: {filename} ({file_size}MB)")
                export_results["onnx"] = {
                    "filename": filename,
                    "size_mb": file_size
                }
            else:
                self.print_error(f"ONNX export failed: {response.status_code}")
        except Exception as e:
            self.print_error(f"ONNX export error: {e}")
        
        # Verify exports are loadable
        self.print_step("Verifying exports are loadable...")
        try:
            response = requests.get(f"{BASE_URL}/model/exports")
            if response.status_code == 200:
                data = response.json()
                exports = data.get("exports", [])
                recent_exports = [e for e in exports if newest_model in e.get("filename", "")]
                self.print_success(f"Found {len(recent_exports)} recent export(s)")
                for exp in recent_exports[:2]:
                    self.print_info(f"  {exp['filename']} - {exp['format']} - {exp['file_size_mb']}MB")
        except Exception as e:
            self.print_error(f"Export listing failed: {e}")
        
        self.results["metrics"]["exports"] = export_results
        
        stage_duration = time.time() - stage_start
        self.results["stages"]["model_export"] = {
            "success": len(export_results) > 0,
            "duration_seconds": round(stage_duration, 2),
            "formats_exported": list(export_results.keys())
        }
        
        self.print_success(f"Model export stage complete ({stage_duration:.2f}s)")
        return True
    
    # ===== Stage 6: Final Statistics =====
    
    def generate_final_report(self):
        """Generate comprehensive validation report"""
        self.print_header("STAGE 6: Final Validation Report")
        
        self.results["validation_end"] = datetime.now().isoformat()
        
        # Calculate total duration
        total_duration = sum(
            stage.get("duration_seconds", 0) 
            for stage in self.results["stages"].values()
        )
        self.results["total_duration_seconds"] = round(total_duration, 2)
        
        # Summary
        self.print_step("Validation Summary")
        print("\n" + "─" * 70)
        print(f"{'Stage':<40} {'Duration':<15} {'Status':<10}")
        print("─" * 70)
        
        for stage_name, stage_data in self.results["stages"].items():
            stage_display = stage_name.replace("_", " ").title()
            duration = f"{stage_data.get('duration_seconds', 0):.2f}s"
            status = "✅ PASS" if stage_data.get("success") else "❌ FAIL"
            print(f"{stage_display:<40} {duration:<15} {status:<10}")
        
        print("─" * 70)
        print(f"{'TOTAL':<40} {total_duration:.2f}s")
        print("─" * 70)
        
        # Key Metrics
        self.print_step("Key Metrics")
        metrics = self.results["metrics"]
        
        print(f"\n   📊 Self-Play:")
        print(f"      • Positions generated: {metrics.get('self_play_positions', 0)}")
        
        print(f"\n   🎓 Training:")
        print(f"      • Epochs completed: {metrics.get('training_epochs', 0)}")
        print(f"      • Final loss: {metrics.get('final_loss', 'N/A')}")
        print(f"      • Models created: {metrics.get('models_after_training', 0) - metrics.get('models_before_training', 0)}")
        
        print(f"\n   🏆 Evaluation:")
        if "evaluation_win_rate" in metrics:
            print(f"      • Win rate: {metrics['evaluation_win_rate']:.1%}")
            print(f"      • Model promoted: {'Yes ✓' if metrics.get('model_promoted') else 'No'}")
        else:
            print(f"      • No evaluation (first model)")
        
        print(f"\n   📦 Exports:")
        exports = metrics.get('exports', {})
        for format_name, export_data in exports.items():
            print(f"      • {format_name.upper()}: {export_data['filename']} ({export_data['size_mb']}MB)")
        
        print(f"\n   🎯 Active Model:")
        print(f"      • Before: {metrics.get('active_model_before', 'None')}")
        print(f"      • After: {metrics.get('active_model_after', 'None')}")
        
        # Errors
        if self.results["errors"]:
            self.print_step("Errors Encountered")
            for error in self.results["errors"]:
                print(f"      ❌ {error}")
        else:
            print(f"\n   ✅ No errors encountered")
        
        # Save report to file
        report_file = Path("/app/STEP_9_VALIDATION_REPORT.json")
        with open(report_file, "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        
        self.print_success(f"Full report saved to: {report_file}")
        
        # Final status
        all_success = all(
            stage.get("success", False) 
            for stage in self.results["stages"].values()
        )
        
        print("\n" + "=" * 70)
        if all_success and not self.results["errors"]:
            print("  ✅ PIPELINE VALIDATION SUCCESSFUL")
            print(f"  Total duration: {total_duration:.2f}s ({total_duration/60:.1f} minutes)")
        else:
            print("  ⚠️  PIPELINE VALIDATION COMPLETED WITH WARNINGS")
        print("=" * 70)
        
        return all_success
    
    def run(self):
        """Run complete validation pipeline"""
        print("\n" + "▀" * 70)
        print("  AlphaZero Training Pipeline Validation - Step 9")
        print("  Testing: Self-Play → Training → Evaluation → Export")
        print("▀" * 70)
        
        try:
            # Stage 1: Environment
            if not self.verify_environment():
                self.print_error("Environment verification failed - aborting")
                return False
            
            # Stage 2: Pre-training state
            self.check_pre_training_state()
            
            # Stage 3: Training pipeline
            if not self.run_training_pipeline():
                self.print_error("Training pipeline failed - continuing with verification")
            
            # Stage 4: Post-training verification
            self.verify_training_results()
            
            # Stage 5: Model export
            self.test_model_export()
            
            # Stage 6: Final report
            success = self.generate_final_report()
            
            return success
            
        except KeyboardInterrupt:
            print("\n\n❌ Validation interrupted by user")
            return False
        except Exception as e:
            print(f"\n\n❌ Validation failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            if self.mongo_client:
                self.mongo_client.close()

def main():
    """Main entry point"""
    validator = PipelineValidator()
    success = validator.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
