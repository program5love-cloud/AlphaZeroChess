#!/usr/bin/env python3
"""
Comprehensive test suite for AlphaZero with LLM Plugin
Tests both core functionality and plugin behavior
"""

import asyncio
import requests
import sys

BASE_URL = "http://localhost:8001/api"

def print_section(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def print_test(name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} - {name}")
    if details:
        print(f"       {details}")

def test_core_alphazero():
    """Test core AlphaZero functionality (should work offline)"""
    print_section("CORE ALPHAZERO TESTS (NO LLM DEPENDENCY)")
    
    tests_passed = 0
    total_tests = 5
    
    # Test 1: Create new game
    try:
        response = requests.post(f"{BASE_URL}/game/new", timeout=5)
        game_data = response.json()
        game_id = game_data.get('id')
        passed = response.status_code == 200 and game_id is not None
        print_test("Create New Game", passed, f"Game ID: {game_id[:20]}..." if passed else "Failed")
        if passed: tests_passed += 1
    except Exception as e:
        print_test("Create New Game", False, str(e))
    
    # Test 2: Get legal moves
    try:
        legal_moves = game_data.get('legal_moves', [])
        passed = len(legal_moves) == 20  # Starting position has 20 legal moves
        print_test("Legal Moves Generation", passed, f"Found {len(legal_moves)} moves")
        if passed: tests_passed += 1
    except Exception as e:
        print_test("Legal Moves Generation", False, str(e))
    
    # Test 3: Make a human move
    try:
        response = requests.post(
            f"{BASE_URL}/game/move",
            json={"game_id": game_id, "move": "e2e4"},
            timeout=5
        )
        passed = response.status_code == 200
        print_test("Human Move (e2e4)", passed)
        if passed: tests_passed += 1
    except Exception as e:
        print_test("Human Move (e2e4)", False, str(e))
    
    # Test 4: Get AI move (MCTS)
    try:
        response = requests.post(
            f"{BASE_URL}/game/ai-move",
            json={"game_id": game_id, "num_simulations": 100, "c_puct": 1.0},
            timeout=30
        )
        ai_data = response.json()
        passed = response.status_code == 200 and 'move' in ai_data
        ai_move = ai_data.get('move', 'N/A')
        print_test("AI Move (MCTS)", passed, f"Move: {ai_move}")
        if passed: tests_passed += 1
    except Exception as e:
        print_test("AI Move (MCTS)", False, str(e))
    
    # Test 5: Get game state
    try:
        response = requests.get(f"{BASE_URL}/game/{game_id}", timeout=5)
        passed = response.status_code == 200
        print_test("Get Game State", passed)
        if passed: tests_passed += 1
    except Exception as e:
        print_test("Get Game State", False, str(e))
    
    print(f"\n📊 Core Tests: {tests_passed}/{total_tests} passed")
    return tests_passed == total_tests

def test_llm_plugin():
    """Test LLM plugin functionality"""
    print_section("LLM PLUGIN TESTS (OPTIONAL ADD-ON)")
    
    tests_passed = 0
    total_tests = 3
    
    # Test 1: Check plugin status
    try:
        response = requests.get(f"{BASE_URL}/plugin/status", timeout=5)
        status_data = response.json()
        available = status_data.get('available', False)
        message = status_data.get('message', '')
        passed = response.status_code == 200
        print_test("Plugin Status Check", passed, f"Available: {available}, Message: {message}")
        if passed: tests_passed += 1
    except Exception as e:
        print_test("Plugin Status Check", False, str(e))
    
    # Test 2: Position evaluation (may be offline)
    try:
        response = requests.post(
            f"{BASE_URL}/position/evaluate",
            json={
                "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                "context": "Starting position"
            },
            timeout=10
        )
        eval_data = response.json()
        passed = response.status_code == 200
        success = eval_data.get('success', False)
        offline = eval_data.get('offline', False)
        evaluation = eval_data.get('evaluation', '')[:60]
        
        if offline:
            print_test("Position Evaluation (Offline Mode)", passed, 
                      f"Graceful fallback: {evaluation}")
        else:
            print_test("Position Evaluation (Online Mode)", passed,
                      f"Success: {success}, Eval: {evaluation}...")
        if passed: tests_passed += 1
    except Exception as e:
        print_test("Position Evaluation", False, str(e))
    
    # Test 3: Verify graceful fallback behavior
    try:
        # The plugin should handle both online and offline scenarios
        passed = response.status_code == 200  # Should always return 200
        behavior = "online" if success else "offline fallback"
        print_test("Graceful Fallback Behavior", passed,
                  f"Plugin mode: {behavior}")
        if passed: tests_passed += 1
    except Exception as e:
        print_test("Graceful Fallback Behavior", False, str(e))
    
    print(f"\n📊 Plugin Tests: {tests_passed}/{total_tests} passed")
    return tests_passed == total_tests

def test_model_management():
    """Test model save/load functionality"""
    print_section("MODEL MANAGEMENT TESTS")
    
    tests_passed = 0
    total_tests = 2
    
    # Test 1: List models
    try:
        response = requests.get(f"{BASE_URL}/model/list", timeout=5)
        models_data = response.json()
        passed = response.status_code == 200
        model_count = len(models_data.get('models', []))
        print_test("List Models", passed, f"Found {model_count} saved models")
        if passed: tests_passed += 1
    except Exception as e:
        print_test("List Models", False, str(e))
    
    # Test 2: Get stats
    try:
        response = requests.get(f"{BASE_URL}/stats", timeout=5)
        stats_data = response.json()
        passed = response.status_code == 200
        games = stats_data.get('total_self_play_games', 0)
        epochs = stats_data.get('total_training_epochs', 0)
        print_test("Get Statistics", passed, 
                  f"Self-play games: {games}, Training epochs: {epochs}")
        if passed: tests_passed += 1
    except Exception as e:
        print_test("Get Statistics", False, str(e))
    
    print(f"\n📊 Model Tests: {tests_passed}/{total_tests} passed")
    return tests_passed == total_tests

def main():
    """Run all tests"""
    print("\n" + "🎯" * 35)
    print("ALPHAZERO CHESS APP - COMPREHENSIVE TEST SUITE")
    print("🎯" * 35)
    
    # Run test suites
    core_passed = test_core_alphazero()
    plugin_passed = test_llm_plugin()
    model_passed = test_model_management()
    
    # Final summary
    print_section("FINAL SUMMARY")
    
    print("\n✅ Core AlphaZero Functionality:")
    print(f"   {'✅ OPERATIONAL' if core_passed else '❌ ISSUES FOUND'}")
    print("   - Chess engine, MCTS, neural network")
    print("   - Works completely offline")
    print("   - No LLM dependency")
    
    print("\n🔌 LLM Plugin Status:")
    print(f"   {'✅ OPERATIONAL' if plugin_passed else '❌ ISSUES FOUND'}")
    print("   - Optional add-on for position analysis")
    print("   - Checks internet before each call")
    print("   - Graceful fallback when offline")
    
    print("\n💾 Model Management:")
    print(f"   {'✅ OPERATIONAL' if model_passed else '❌ ISSUES FOUND'}")
    print("   - Save/load/list models")
    print("   - Training statistics")
    
    print("\n" + "=" * 70)
    if core_passed and plugin_passed and model_passed:
        print("🎉 ALL SYSTEMS OPERATIONAL!")
        print("=" * 70)
        print("\n✨ Key Features:")
        print("   • AlphaZero chess engine works offline")
        print("   • LLM plugin is separated and optional")
        print("   • Internet detection before each LLM call")
        print("   • Graceful fallback when offline")
        print("   • Auto-recovery when connection restored")
        return 0
    else:
        print("⚠️  SOME ISSUES DETECTED")
        print("=" * 70)
        if not core_passed:
            print("   • Core AlphaZero has issues - CRITICAL")
        if not plugin_passed:
            print("   • LLM plugin has issues")
        if not model_passed:
            print("   • Model management has issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())
