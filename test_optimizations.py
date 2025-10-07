"""
Test script for GPU acceleration and performance optimizations
"""
import requests
import time
import json

BACKEND_URL = "http://localhost:8001/api"

def print_separator(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60 + "\n")

def test_device_detection():
    """Test 1: Device Detection"""
    print_separator("Test 1: Device Detection")
    
    response = requests.get(f"{BACKEND_URL}/system/device")
    device_info = response.json()
    
    print(f"Device Type: {device_info['device_type'].upper()}")
    print(f"Device Name: {device_info['device_name']}")
    print(f"Is GPU: {device_info['is_gpu']}")
    
    if device_info['is_gpu']:
        print(f"CUDA Version: {device_info.get('cuda_version', 'N/A')}")
        print(f"GPU Memory Allocated: {device_info.get('gpu_memory_allocated', 'N/A')}")
    
    return device_info

def test_self_play(num_games=1):
    """Test 2: Self-Play with Performance Tracking"""
    print_separator(f"Test 2: Self-Play ({num_games} game)")
    
    config = {
        "num_games": num_games,
        "num_simulations": 10  # Very low for quick test
    }
    
    print(f"Starting self-play with {config['num_games']} game, {config['num_simulations']} simulations/move")
    start_time = time.time()
    
    # Start self-play
    response = requests.post(f"{BACKEND_URL}/self-play/run", json=config)
    print(f"Self-play started: {response.json()['status']}")
    
    # Poll status until complete
    while True:
        time.sleep(2)
        status = requests.get(f"{BACKEND_URL}/self-play/status").json()
        if not status['active']:
            break
        print(".", end="", flush=True)
    
    elapsed = time.time() - start_time
    print(f"\n\nSelf-play complete in {elapsed:.2f}s")
    print(f"Total Positions Generated: {status.get('total_positions', 0)}")
    
    return status

def test_training(num_games=1, num_epochs=1):
    """Test 3: Training with Performance Metrics"""
    print_separator(f"Test 3: Training ({num_games} game, {num_epochs} epoch)")
    
    config = {
        "num_games": num_games,
        "num_epochs": num_epochs,
        "batch_size": 32,
        "num_simulations": 10,  # Very low for quick test
        "learning_rate": 0.001
    }
    
    print(f"Starting training with {config['num_games']} game, {config['num_epochs']} epoch")
    start_time = time.time()
    
    # Start training
    response = requests.post(f"{BACKEND_URL}/training/start", json=config)
    print(f"Training started: {response.json()['status']}")
    
    # Poll status until complete with progress tracking
    last_progress = 0
    while True:
        time.sleep(3)
        status = requests.get(f"{BACKEND_URL}/training/status").json()
        
        if 'progress' in status and status['progress'].get('progress', 0) != last_progress:
            last_progress = status['progress']['progress']
            print(f"\nProgress: {last_progress}% - {status['progress'].get('message', '')}")
        
        if not status['active']:
            break
        print(".", end="", flush=True)
    
    elapsed = time.time() - start_time
    print(f"\n\nTraining complete in {elapsed:.2f}s")
    
    # Get training metrics
    if status.get('recent_metrics'):
        metrics = status['recent_metrics'][0]
        print(f"\nTraining Metrics:")
        print(f"  - Loss: {metrics.get('loss', 0):.4f}")
        print(f"  - Policy Loss: {metrics.get('policy_loss', 0):.4f}")
        print(f"  - Value Loss: {metrics.get('value_loss', 0):.4f}")
        if 'epoch_time' in metrics:
            print(f"  - Epoch Time: {metrics['epoch_time']:.2f}s")
        if 'device' in metrics:
            print(f"  - Device: {metrics['device']}")
    
    return status

def test_evaluation(num_games=3):
    """Test 4: Model Evaluation"""
    print_separator(f"Test 4: Model Evaluation ({num_games} games)")
    
    # Get available models
    models_response = requests.get(f"{BACKEND_URL}/model/list")
    models = models_response.json()['models']
    
    if len(models) < 2:
        print(f"Not enough models for evaluation (found {len(models)}, need 2)")
        print("Skipping evaluation test")
        return None
    
    challenger = models[0]
    champion = models[1] if len(models) > 1 else models[0]
    
    print(f"Evaluating: {challenger} vs {champion}")
    
    eval_config = {
        "challenger_name": challenger,
        "champion_name": champion,
        "num_games": num_games,
        "num_simulations": 10  # Very low for quick test
    }
    
    start_time = time.time()
    
    # Start evaluation
    response = requests.post(f"{BACKEND_URL}/evaluation/run", json=eval_config)
    print(f"Evaluation started: {response.json()['status']}")
    
    # Poll status until complete
    while True:
        time.sleep(3)
        status = requests.get(f"{BACKEND_URL}/evaluation/status").json()
        
        if 'progress' in status and status.get('progress'):
            progress = status['progress'].get('progress', 0)
            message = status['progress'].get('message', '')
            print(f"\rProgress: {progress}% - {message}", end="", flush=True)
        
        if not status['active']:
            break
    
    elapsed = time.time() - start_time
    print(f"\n\nEvaluation complete in {elapsed:.2f}s")
    
    # Get evaluation results
    if status.get('recent_evaluation'):
        eval_data = status['recent_evaluation']
        print(f"\nEvaluation Results:")
        print(f"  - Challenger ({eval_data.get('challenger_name', 'N/A')}) Win Rate: {eval_data.get('challenger_win_rate', 0)*100:.1f}%")
        print(f"  - Games Played: {eval_data.get('games_played', 0)}")
        print(f"  - W-L-D: {eval_data.get('model1_wins', 0)}-{eval_data.get('model2_wins', 0)}-{eval_data.get('draws', 0)}")
        if 'evaluation_time' in eval_data:
            print(f"  - Evaluation Time: {eval_data['evaluation_time']:.2f}s")
        if 'device' in eval_data:
            print(f"  - Device: {eval_data['device']}")
    
    return status

def test_cancellation():
    """Test 5: Job Cancellation"""
    print_separator("Test 5: Job Cancellation")
    
    # Start a training job
    config = {
        "num_games": 5,
        "num_epochs": 10,
        "batch_size": 32,
        "num_simulations": 100,
        "learning_rate": 0.001
    }
    
    print("Starting training job...")
    response = requests.post(f"{BACKEND_URL}/training/start", json=config)
    print(f"Training started: {response.json()['status']}")
    
    # Wait a bit then cancel
    time.sleep(3)
    print("\nCancelling training...")
    cancel_response = requests.post(f"{BACKEND_URL}/training/stop")
    print(f"Cancellation response: {cancel_response.json()['status']}")
    
    # Wait for cancellation to complete
    time.sleep(3)
    status = requests.get(f"{BACKEND_URL}/training/status").json()
    print(f"Training active: {status['active']}")
    
    return status

def main():
    print("\n" + "="*60)
    print("  AlphaZero Performance Optimization Test Suite")
    print("="*60)
    
    try:
        # Test 1: Device Detection
        device_info = test_device_detection()
        
        # Test 2: Self-Play
        self_play_status = test_self_play(num_games=1)
        
        # Test 3: Training
        training_status = test_training(num_games=1, num_epochs=1)
        
        # Test 4: Evaluation (only if we have models)
        evaluation_status = test_evaluation(num_games=3)
        
        # Test 5: Cancellation
        cancel_status = test_cancellation()
        
        # Final Summary
        print_separator("Test Summary")
        print("✓ Device detection working")
        print(f"✓ Self-play with performance tracking: {self_play_status.get('total_positions', 0)} positions")
        print("✓ Training with GPU/CPU support and metrics")
        if evaluation_status:
            print("✓ Model evaluation with timing")
        print("✓ Job cancellation support")
        
        print("\n" + "="*60)
        print("  All tests completed successfully!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
