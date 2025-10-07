#!/usr/bin/env python3
"""
Direct pipeline test - bypasses API for faster validation
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

import time
from neural_network import AlphaZeroNetwork, ModelManager
from self_play import SelfPlayManager
from trainer import AlphaZeroTrainer
from evaluator import ModelEvaluator
from model_export import ModelExporter

print("=" * 70)
print("  DIRECT PIPELINE TEST - Minimal Configuration")
print("=" * 70)

# Stage 1: Self-Play
print("\n🎮 Stage 1: Self-Play (1 game, 10 simulations)")
start = time.time()
network = AlphaZeroNetwork()
self_play_mgr = SelfPlayManager(network, num_simulations=10)
training_data, game_results = self_play_mgr.generate_games(num_games=1, store_fen=True)
print(f"✅ Generated {len(training_data)} positions in {time.time()-start:.2f}s")

# Stage 2: Training
print("\n🎓 Stage 2: Training (1 epoch, batch 64)")
start = time.time()
trainer = AlphaZeroTrainer(network, learning_rate=0.001)
history = trainer.train(training_data, num_epochs=1, batch_size=64)
print(f"✅ Training complete in {time.time()-start:.2f}s")
print(f"   Final loss: {history[-1]['loss']:.4f}")

# Stage 3: Save Model
print("\n💾 Stage 3: Saving Model")
start = time.time()
model_mgr = ModelManager()
model_path = model_mgr.save_versioned_model(network, metadata={
    "test": "pipeline_validation",
    "positions": len(training_data),
    "epochs": 1
})
model_name = Path(model_path).stem
print(f"✅ Model saved: {model_name} in {time.time()-start:.2f}s")

# Stage 4: Evaluation (if multiple models exist)
models = model_mgr.list_models()
print(f"\n🏆 Stage 4: Evaluation ({len(models)} models available)")
if len(models) >= 2:
    start = time.time()
    # Load two models
    models_sorted = sorted(models, reverse=True)
    model1, _ = model_mgr.load_model(models_sorted[0])
    model2, _ = model_mgr.load_model(models_sorted[1])
    
    evaluator = ModelEvaluator(num_evaluation_games=3, num_simulations=10, win_threshold=0.55)
    results, promoted = evaluator.evaluate_models(model1, model2, models_sorted[0], models_sorted[1])
    
    print(f"✅ Evaluation complete in {time.time()-start:.2f}s")
    print(f"   Win rate: {results['challenger_win_rate']:.1%}")
    print(f"   Promoted: {promoted}")
else:
    print(f"ℹ️  Skipping evaluation (need at least 2 models)")

# Stage 5: Export
print(f"\n📦 Stage 5: Model Export")
start = time.time()
exporter = ModelExporter()

# PyTorch export
pt_result = exporter.export_pytorch(model_name, metadata={"test": "validation"})
print(f"✅ PyTorch export: {pt_result['filename']} ({pt_result['file_size_mb']}MB)")

# ONNX export
onnx_result = exporter.export_onnx(model_name, metadata={"test": "validation"})
print(f"✅ ONNX export: {onnx_result['filename']} ({onnx_result['file_size_mb']}MB)")
print(f"   Total export time: {time.time()-start:.2f}s")

print("\n" + "=" * 70)
print("  ✅ PIPELINE VALIDATION SUCCESSFUL!")
print("=" * 70)
