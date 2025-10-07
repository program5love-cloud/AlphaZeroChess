"""
Enhanced FastAPI Server with Full AlphaZero Pipeline
Includes training, evaluation, model management, and export endpoints
"""
from fastapi import FastAPI, APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import asyncio
from concurrent.futures import ThreadPoolExecutor
import sys

# Add backend to path
backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Import AlphaZero components
from neural_network import AlphaZeroNetwork, ModelManager
from self_play import SelfPlayManager
from trainer import AlphaZeroTrainer
from evaluator import ModelEvaluator
from model_export import ModelExporter, ModelLoader
from chess_engine import ChessEngine
from mcts import MCTS

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Thread pool for async operations
executor = ThreadPoolExecutor(max_workers=2)

# Global state
training_status = {
    "active": False,
    "progress": 0,
    "message": "",
    "session_id": None,
    "start_time": None
}

evaluation_status = {
    "active": False,
    "progress": 0,
    "message": "",
    "results": None
}

# Model manager instances
model_manager = ModelManager()
model_exporter = ModelExporter()
model_loader = ModelLoader()

# Game sessions storage (in-memory for now, can move to MongoDB)
active_games = {}  # {game_id: {"engine": ChessEngine, "history": [], "ai_color": "black"}}

# Coaching sessions storage (conversation memory per game)
coaching_sessions = {}  # {game_id: LLMChessEvaluator instance}

# ====================
# Data Models
# ====================

class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

class TrainingConfig(BaseModel):
    num_games: int = Field(default=1, ge=1, le=100)
    num_epochs: int = Field(default=1, ge=1, le=50)
    batch_size: int = Field(default=64, ge=8, le=256)
    num_simulations: int = Field(default=10, ge=5, le=1000)
    learning_rate: float = Field(default=0.001, ge=0.0001, le=0.1)

class EvaluationConfig(BaseModel):
    challenger_name: str
    champion_name: str
    num_games: int = Field(default=3, ge=1, le=50)
    num_simulations: int = Field(default=10, ge=5, le=1000)
    win_threshold: float = Field(default=0.55, ge=0.5, le=1.0)

class ExportRequest(BaseModel):
    metadata: Optional[Dict[str, Any]] = None

# ====================
# Basic Endpoints
# ====================

@api_router.get("/")
async def root():
    return {"message": "AlphaZero Chess API", "version": "1.0", "status": "active"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.dict()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.dict())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]

# ====================
# Training Endpoints
# ====================

async def store_data_async(collection, data):
    """Helper to store data asynchronously"""
    await collection.insert_many(data)

def run_training_pipeline(config: TrainingConfig, session_id: str):
    """Run complete training pipeline in background"""
    try:
        global training_status
        training_status["message"] = "Initializing neural network..."
        training_status["progress"] = 5
        
        # Initialize network
        network = AlphaZeroNetwork()
        
        # Stage 1: Self-Play
        training_status["message"] = f"Generating self-play games ({config.num_games} games)..."
        training_status["progress"] = 10
        logger.info(f"Starting self-play: {config.num_games} games, {config.num_simulations} simulations")
        
        self_play_manager = SelfPlayManager(network, num_simulations=config.num_simulations)
        training_data, game_results = self_play_manager.generate_games(
            num_games=config.num_games,
            store_fen=True
        )
        
        logger.info(f"Self-play complete: {len(training_data)} positions generated")
        training_status["message"] = f"Self-play complete: {len(training_data)} positions"
        training_status["progress"] = 40
        
        # Store self-play data in MongoDB (use sync client)
        sync_client = MongoClient(os.environ['MONGO_URL'])
        sync_db = sync_client[os.environ['DB_NAME']]
        
        if training_data:
            sync_db.self_play_positions.insert_many([
                {
                    "position": pos.get("position").tolist() if hasattr(pos.get("position"), "tolist") else pos.get("position"),
                    "policy": pos.get("policy"),
                    "value": pos.get("value"),
                    "fen": pos.get("fen"),
                    "move_number": pos.get("move_number"),
                    "session_id": session_id,
                    "timestamp": datetime.now(timezone.utc),
                    "source": "pipeline_test"
                }
                for pos in training_data[:100]  # Store sample
            ])
        
        # Stage 2: Training
        training_status["message"] = f"Training network ({config.num_epochs} epochs)..."
        training_status["progress"] = 50
        logger.info(f"Starting training: {config.num_epochs} epochs, batch size {config.batch_size}")
        
        trainer = AlphaZeroTrainer(network, learning_rate=config.learning_rate)
        training_history = trainer.train(
            training_data,
            num_epochs=config.num_epochs,
            batch_size=config.batch_size
        )
        
        logger.info(f"Training complete: {len(training_history)} epochs")
        training_status["message"] = "Training complete, saving model..."
        training_status["progress"] = 75
        
        # Store training metrics
        if training_history:
            sync_db.training_metrics.insert_many([
                {
                    **metrics,
                    "session_id": session_id,
                    "source": "pipeline_test"
                }
                for metrics in training_history
            ])
        
        # Save model with version
        metadata = {
            "training_date": datetime.now(timezone.utc).isoformat(),
            "num_games": config.num_games,
            "num_epochs": config.num_epochs,
            "num_positions": len(training_data),
            "learning_rate": config.learning_rate,
            "batch_size": config.batch_size,
            "num_simulations": config.num_simulations,
            "training_session_id": session_id,
            "final_loss": training_history[-1]["loss"] if training_history else 0.0,
            "source": "pipeline_test"
        }
        
        model_path = model_manager.save_versioned_model(network, metadata=metadata)
        new_model_name = Path(model_path).stem
        logger.info(f"Model saved: {new_model_name}")
        
        training_status["message"] = f"Model saved: {new_model_name}"
        training_status["progress"] = 90
        
        # Stage 3: Evaluation (if there's an existing model)
        existing_models = model_manager.list_models()
        if len(existing_models) > 1:
            training_status["message"] = "Running evaluation..."
            logger.info("Starting model evaluation")
            
            # Get current active model
            active_model_doc = sync_db.active_model.find_one({})
            champion_name = active_model_doc["model_name"] if active_model_doc else existing_models[0]
            
            # Load models for evaluation
            challenger_model, _ = model_manager.load_model(new_model_name)
            champion_model, _ = model_manager.load_model(champion_name)
            
            # Run evaluation (3 games, 10 simulations as per requirements)
            evaluator = ModelEvaluator(
                num_evaluation_games=3,
                num_simulations=10,
                win_threshold=0.55
            )
            
            eval_results, should_promote = evaluator.evaluate_models(
                challenger_model,
                champion_model,
                new_model_name,
                champion_name
            )
            
            # Store evaluation results
            sync_db.model_evaluations.insert_one({
                **eval_results,
                "timestamp": datetime.now(timezone.utc),
                "automatic": True,
                "session_id": session_id,
                "source": "pipeline_test"
            })
            
            # Promote if threshold met
            if should_promote:
                sync_db.active_model.replace_one(
                    {},
                    {
                        "model_name": new_model_name,
                        "promoted_at": datetime.now(timezone.utc),
                        "win_rate": eval_results["challenger_win_rate"],
                        "previous_champion": champion_name,
                        "manual_activation": False
                    },
                    upsert=True
                )
                logger.info(f"Model promoted: {new_model_name}")
                training_status["message"] = f"Model promoted! Win rate: {eval_results['challenger_win_rate']:.1%}"
            else:
                logger.info(f"Model not promoted. Win rate: {eval_results['challenger_win_rate']:.1%}")
                training_status["message"] = f"Model not promoted. Win rate: {eval_results['challenger_win_rate']:.1%}"
        else:
            # First model - make it active
            sync_db.active_model.replace_one(
                {},
                {
                    "model_name": new_model_name,
                    "promoted_at": datetime.now(timezone.utc),
                    "win_rate": 1.0,
                    "previous_champion": None,
                    "manual_activation": False
                },
                upsert=True
            )
        
        # Close sync client
        sync_client.close()
        
        training_status["progress"] = 100
        training_status["message"] = "Training pipeline complete!"
        logger.info("Training pipeline completed successfully")
        
    except Exception as e:
        logger.error(f"Training pipeline error: {str(e)}")
        training_status["message"] = f"Error: {str(e)}"
        training_status["progress"] = 0
        raise
    finally:
        training_status["active"] = False

@api_router.post("/training/start")
async def start_training(config: TrainingConfig, background_tasks: BackgroundTasks):
    """Start training pipeline in background"""
    global training_status
    
    if training_status["active"]:
        raise HTTPException(status_code=400, detail="Training already in progress")
    
    session_id = str(uuid.uuid4())
    training_status = {
        "active": True,
        "progress": 0,
        "message": "Starting training...",
        "session_id": session_id,
        "start_time": datetime.now(timezone.utc)
    }
    
    # Run in background
    background_tasks.add_task(run_training_pipeline, config, session_id)
    
    return {
        "success": True,
        "message": "Training started",
        "session_id": session_id,
        "config": config.dict()
    }

@api_router.get("/training/status")
async def get_training_status():
    """Get current training status"""
    return {
        "active": training_status["active"],
        "progress": training_status["progress"],
        "message": training_status["message"],
        "session_id": training_status.get("session_id"),
        "start_time": training_status.get("start_time")
    }

@api_router.get("/training/history")
async def get_training_history(limit: int = 10):
    """Get training history from database"""
    sessions = await db.training_metrics.aggregate([
        {"$group": {
            "_id": "$session_id",
            "epochs": {"$sum": 1},
            "avg_loss": {"$avg": "$loss"},
            "timestamp": {"$first": "$timestamp"}
        }},
        {"$sort": {"timestamp": -1}},
        {"$limit": limit}
    ]).to_list(limit)
    
    return {"sessions": sessions}

# ====================
# Evaluation Endpoints
# ====================

def run_evaluation_pipeline(config: EvaluationConfig):
    """Run evaluation in background"""
    try:
        global evaluation_status
        evaluation_status["message"] = "Loading models..."
        evaluation_status["progress"] = 10
        
        # Load models
        challenger_model, challenger_meta = model_manager.load_model(config.challenger_name)
        champion_model, champion_meta = model_manager.load_model(config.champion_name)
        
        if not challenger_model or not champion_model:
            raise Exception("Failed to load one or both models")
        
        evaluation_status["message"] = f"Running evaluation ({config.num_games} games)..."
        evaluation_status["progress"] = 30
        
        # Run evaluation
        evaluator = ModelEvaluator(
            num_evaluation_games=config.num_games,
            num_simulations=config.num_simulations,
            win_threshold=config.win_threshold
        )
        
        results, should_promote = evaluator.evaluate_models(
            challenger_model,
            champion_model,
            config.challenger_name,
            config.champion_name
        )
        
        evaluation_status["progress"] = 80
        evaluation_status["message"] = "Storing results..."
        
        # Store results using sync client
        sync_client = MongoClient(os.environ['MONGO_URL'])
        sync_db = sync_client[os.environ['DB_NAME']]
        
        sync_db.model_evaluations.insert_one({
            **results,
            "timestamp": datetime.now(timezone.utc),
            "automatic": False,
            "source": "pipeline_test"
        })
        
        sync_client.close()
        
        evaluation_status["progress"] = 100
        evaluation_status["message"] = "Evaluation complete!"
        evaluation_status["results"] = results
        
        logger.info(f"Evaluation complete: {results['challenger_win_rate']:.1%} win rate")
        
    except Exception as e:
        logger.error(f"Evaluation error: {str(e)}")
        evaluation_status["message"] = f"Error: {str(e)}"
        evaluation_status["progress"] = 0
        raise
    finally:
        evaluation_status["active"] = False

@api_router.post("/evaluation/run")
async def run_evaluation(config: EvaluationConfig, background_tasks: BackgroundTasks):
    """Run evaluation between two models"""
    global evaluation_status
    
    if evaluation_status["active"]:
        raise HTTPException(status_code=400, detail="Evaluation already in progress")
    
    evaluation_status = {
        "active": True,
        "progress": 0,
        "message": "Starting evaluation...",
        "results": None
    }
    
    background_tasks.add_task(run_evaluation_pipeline, config)
    
    return {
        "success": True,
        "message": "Evaluation started",
        "config": config.dict()
    }

@api_router.get("/evaluation/status")
async def get_evaluation_status():
    """Get current evaluation status"""
    return evaluation_status

@api_router.get("/evaluation/history")
async def get_evaluation_history(limit: int = 10):
    """Get evaluation history"""
    evaluations = await db.model_evaluations.find().sort("timestamp", -1).limit(limit).to_list(limit)
    return {"evaluations": evaluations}

# ====================
# Model Management Endpoints
# ====================

@api_router.get("/model/list")
async def list_models():
    """List all available models"""
    models = model_manager.list_models()
    
    # Get active model
    active_model_doc = await db.active_model.find_one({})
    active_model_name = active_model_doc["model_name"] if active_model_doc else None
    
    model_list = []
    for model_name in models:
        model_info = model_manager.get_model_info(model_name)
        if model_info:
            metadata = model_info.get("metadata", {})
            model_path = model_manager.get_model_path(model_name)
            file_size = os.path.getsize(model_path) / (1024 * 1024) if model_path.exists() else 0
            
            model_list.append({
                "name": model_name,
                "version": metadata.get("version", "unknown"),
                "training_date": metadata.get("training_date", "unknown"),
                "file_size_mb": round(file_size, 2),
                "metadata": metadata,
                "is_active": model_name == active_model_name
            })
    
    return {"success": True, "models": model_list, "count": len(model_list)}

@api_router.get("/model/current")
async def get_current_model():
    """Get current active model"""
    active_model_doc = await db.active_model.find_one({})
    return {
        "success": True,
        "active_model": active_model_doc["model_name"] if active_model_doc else None,
        "details": active_model_doc
    }

@api_router.post("/model/activate/{model_name}")
async def activate_model(model_name: str):
    """Activate a specific model"""
    # Verify model exists
    model_info = model_manager.get_model_info(model_name)
    if not model_info:
        raise HTTPException(status_code=404, detail=f"Model {model_name} not found")
    
    # Update active model
    await db.active_model.replace_one(
        {},
        {
            "model_name": model_name,
            "promoted_at": datetime.now(timezone.utc),
            "manual_activation": True
        },
        upsert=True
    )
    
    return {"success": True, "message": f"Model {model_name} activated"}

@api_router.get("/model/info/{model_name}")
async def get_model_info(model_name: str):
    """Get detailed model information"""
    model_info = model_manager.get_model_info(model_name)
    if not model_info:
        raise HTTPException(status_code=404, detail=f"Model {model_name} not found")
    
    return {"success": True, "model_info": model_info}

# ====================
# Model Export Endpoints
# ====================

@api_router.post("/model/export/{format}/{model_name}")
async def export_model(format: str, model_name: str, request: ExportRequest = ExportRequest()):
    """Export model in specified format"""
    if format not in ["pytorch", "onnx"]:
        raise HTTPException(status_code=400, detail="Format must be 'pytorch' or 'onnx'")
    
    try:
        if format == "pytorch":
            result = await asyncio.get_event_loop().run_in_executor(
                executor,
                model_exporter.export_pytorch,
                model_name,
                request.metadata
            )
        else:
            result = await asyncio.get_event_loop().run_in_executor(
                executor,
                model_exporter.export_onnx,
                model_name,
                request.metadata
            )
        
        return {
            "success": True,
            "message": f"Model exported successfully to {format} format",
            **result
        }
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/model/exports")
async def list_exports():
    """List all exported models"""
    exports = model_exporter.list_exports()
    return {"success": True, "exports": exports, "count": len(exports)}

@api_router.get("/model/download/{filename}")
async def download_export(filename: str):
    """Download an exported model file"""
    file_path = model_exporter.get_export_path(filename)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found")
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream"
    )

# ====================
# Statistics Endpoint
# ====================

@api_router.get("/stats")
async def get_stats():
    """Get overall statistics"""
    total_games = await db.self_play_positions.count_documents({})
    total_epochs = await db.training_metrics.count_documents({})
    total_evaluations = await db.model_evaluations.count_documents({})
    
    active_model_doc = await db.active_model.find_one({})
    
    return {
        "total_self_play_positions": total_games,
        "total_training_epochs": total_epochs,
        "total_evaluations": total_evaluations,
        "total_models": len(model_manager.list_models()),
        "active_model": active_model_doc["model_name"] if active_model_doc else None,
        "training_active": training_status["active"],
        "evaluation_active": evaluation_status["active"]
    }

# ====================
# Game Endpoints (Human vs AI)
# ====================

class GameRequest(BaseModel):
    ai_color: str = "black"  # "white" or "black"

class MoveRequest(BaseModel):
    game_id: str
    move: str  # UCI format

class AIRequest(BaseModel):
    game_id: str
    num_simulations: int = Field(default=800, ge=10, le=2000)

class CoachRequest(BaseModel):
    game_id: str
    question: Optional[str] = None
    num_simulations: int = Field(default=400, ge=10, le=1000)

class AnalyzeMoveRequest(BaseModel):
    game_id: str
    move: str
    num_simulations: int = Field(default=400, ge=10, le=1000)

# ====================
# Helper Functions for Coaching
# ====================

async def get_mcts_evaluation(engine: ChessEngine, network, num_simulations: int = 400):
    """
    Run MCTS and return top moves with probabilities and position value
    Returns: (top_moves_list, position_value)
    """
    try:
        mcts = MCTS(network, num_simulations=num_simulations, c_puct=1.5)
        best_move, move_probs, root_value = mcts.search(engine, temperature=0.1)
        
        # Sort moves by probability
        sorted_moves = sorted(move_probs.items(), key=lambda x: x[1], reverse=True)
        
        # Get top moves with visit counts (estimate from probabilities)
        top_moves = []
        total_visits = num_simulations
        for move, prob in sorted_moves[:5]:  # Get top 5
            visits = int(prob * total_visits)
            top_moves.append({
                "move": move,
                "probability": float(prob),
                "visits": visits
            })
        
        return top_moves, float(root_value)
    except Exception as e:
        logger.error(f"Error getting MCTS evaluation: {e}")
        return [], 0.0

@api_router.post("/game/new")
async def create_new_game(request: GameRequest):
    """Create a new game session"""
    game_id = str(uuid.uuid4())
    engine = ChessEngine()
    
    active_games[game_id] = {
        "engine": engine,
        "history": [],
        "ai_color": request.ai_color,
        "created_at": datetime.now(timezone.utc)
    }
    
    # Reset any existing coaching session for clean start
    if game_id in coaching_sessions:
        coaching_sessions[game_id].reset_conversation()
    
    # If AI plays white, make first move
    if request.ai_color == "white":
        try:
            # Get active model
            active_model_doc = await db.active_model.find_one({})
            if active_model_doc:
                model_name = active_model_doc["model_name"]
                network, _ = model_manager.load_model(model_name)
            else:
                # Use fresh network if no trained model
                network = AlphaZeroNetwork()
            
            # Run MCTS
            mcts = MCTS(network, num_simulations=800, c_puct=1.5)
            best_move, _, _ = mcts.search(engine, temperature=0.0)
            
            if best_move:
                engine.make_move(best_move)
                active_games[game_id]["history"].append(best_move)
        except Exception as e:
            logger.error(f"Error making AI's first move: {e}")
    
    return {
        "success": True,
        "game_id": game_id,
        "fen": engine.get_fen(),
        "legal_moves": engine.get_legal_moves(),
        "is_game_over": engine.is_game_over(),
        "result": engine.get_result() if engine.is_game_over() else None,
        "history": active_games[game_id]["history"]
    }

@api_router.get("/game/{game_id}/state")
async def get_game_state(game_id: str):
    """Get current game state"""
    if game_id not in active_games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = active_games[game_id]
    engine = game["engine"]
    
    return {
        "success": True,
        "game_id": game_id,
        "fen": engine.get_fen(),
        "legal_moves": engine.get_legal_moves(),
        "is_game_over": engine.is_game_over(),
        "result": engine.get_result() if engine.is_game_over() else None,
        "history": game["history"],
        "ai_color": game["ai_color"]
    }

@api_router.post("/game/move")
async def make_player_move(request: MoveRequest):
    """Make a player move"""
    if request.game_id not in active_games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = active_games[request.game_id]
    engine = game["engine"]
    
    # Validate and make move
    if not engine.make_move(request.move):
        raise HTTPException(status_code=400, detail="Illegal move")
    
    # Add to history
    game["history"].append(request.move)
    
    return {
        "success": True,
        "fen": engine.get_fen(),
        "legal_moves": engine.get_legal_moves(),
        "is_game_over": engine.is_game_over(),
        "result": engine.get_result() if engine.is_game_over() else None,
        "history": game["history"]
    }

@api_router.post("/game/ai-move")
async def get_ai_move(request: AIRequest):
    """Get AI's move using MCTS + Neural Network"""
    if request.game_id not in active_games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = active_games[request.game_id]
    engine = game["engine"]
    
    if engine.is_game_over():
        raise HTTPException(status_code=400, detail="Game is already over")
    
    try:
        # Get active model
        active_model_doc = await db.active_model.find_one({})
        if active_model_doc:
            model_name = active_model_doc["model_name"]
            network, _ = model_manager.load_model(model_name)
            logger.info(f"Using trained model: {model_name}")
        else:
            # Use fresh network if no trained model
            network = AlphaZeroNetwork()
            logger.info("Using fresh network (no trained models)")
        
        # Run MCTS
        start_time = datetime.now()
        mcts = MCTS(network, num_simulations=request.num_simulations, c_puct=1.5)
        best_move, move_probs, root_value = mcts.search(engine, temperature=0.0)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        if not best_move:
            raise HTTPException(status_code=500, detail="AI couldn't find a move")
        
        # Make the move
        engine.make_move(best_move)
        game["history"].append(best_move)
        
        logger.info(f"AI move: {best_move} (took {elapsed:.2f}s, {request.num_simulations} sims)")
        
        return {
            "success": True,
            "move": best_move,
            "fen": engine.get_fen(),
            "legal_moves": engine.get_legal_moves(),
            "is_game_over": engine.is_game_over(),
            "result": engine.get_result() if engine.is_game_over() else None,
            "history": game["history"],
            "computation_time": float(elapsed),
            "simulations": int(request.num_simulations)
        }
    except Exception as e:
        logger.error(f"Error getting AI move: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/game/{game_id}")
async def delete_game(game_id: str):
    """Delete a game session"""
    if game_id in active_games:
        del active_games[game_id]
    
    # Also clean up coaching session
    if game_id in coaching_sessions:
        del coaching_sessions[game_id]
    
    return {"success": True, "message": "Game deleted"}

# ====================
# LLM Explanation Endpoints
# ====================

class ExplainRequest(BaseModel):
    fen: str
    last_move: Optional[str] = None
    context: Optional[str] = None

@api_router.post("/llm/explain")
async def explain_position(request: ExplainRequest):
    """Get LLM explanation for a chess position"""
    try:
        from llm_evaluator import LLMChessEvaluator
        
        evaluator = LLMChessEvaluator()
        
        context = request.context or ""
        if request.last_move:
            context += f"\nLast move played: {request.last_move}"
        
        explanation = await evaluator.evaluate_position(request.fen, context)
        
        return {
            "success": True,
            "explanation": explanation,
            "fen": request.fen
        }
    except Exception as e:
        logger.error(f"LLM explanation error: {e}")
        # Return fallback explanation
        return {
            "success": True,
            "explanation": "Position analysis unavailable. Continue playing to improve the AI model.",
            "fen": request.fen,
            "offline": True
        }

@api_router.post("/llm/suggest-strategy")
async def suggest_strategy(request: ExplainRequest):
    """Get strategic suggestions from LLM"""
    try:
        from llm_evaluator import LLMChessEvaluator
        
        evaluator = LLMChessEvaluator()
        strategy = await evaluator.suggest_opening_strategy(request.fen)
        
        return {
            "success": True,
            "strategy": strategy,
            "fen": request.fen
        }
    except Exception as e:
        logger.error(f"LLM strategy error: {e}")
        return {
            "success": True,
            "strategy": "Focus on controlling the center and developing your pieces.",
            "fen": request.fen,
            "offline": True
        }

# ====================
# Coaching Mode Endpoints
# ====================

def get_or_create_coach(game_id: str):
    """Get or create coaching session for a game"""
    if game_id not in coaching_sessions:
        from llm_evaluator import LLMChessEvaluator
        coaching_sessions[game_id] = LLMChessEvaluator(session_id=f"coach-{game_id}")
    return coaching_sessions[game_id]

@api_router.post("/coaching/suggest")
async def get_coaching_suggestion(request: CoachRequest):
    """Get move suggestions and coaching advice with AlphaZero evaluation"""
    if request.game_id not in active_games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    try:
        game = active_games[request.game_id]
        engine = game["engine"]
        
        if engine.is_game_over():
            return {
                "success": True,
                "message": "Game is over. Start a new game to continue coaching.",
                "top_moves": [],
                "position_value": 0.0,
                "coaching": "The game has ended. Let's start a fresh game!"
            }
        
        # Get active model
        active_model_doc = await db.active_model.find_one({})
        if active_model_doc:
            model_name = active_model_doc["model_name"]
            network, _ = model_manager.load_model(model_name)
        else:
            network = AlphaZeroNetwork()
        
        # Get MCTS evaluation
        top_moves, position_value = await get_mcts_evaluation(engine, network, request.num_simulations)
        
        # Get LLM coaching
        coach = get_or_create_coach(request.game_id)
        fen = engine.get_fen()
        
        context = request.question if request.question else ""
        coaching_text = await coach.coach_with_mcts(fen, top_moves, position_value, context)
        
        return {
            "success": True,
            "fen": fen,
            "top_moves": top_moves[:3],  # Return top 3
            "position_value": position_value,
            "coaching": coaching_text,
            "conversation_history": coach.get_conversation_history()[-10:]  # Last 10 messages
        }
    except Exception as e:
        logger.error(f"Coaching suggestion error: {e}")
        return {
            "success": True,
            "coaching": "Coaching temporarily unavailable. Focus on controlling the center and developing your pieces.",
            "top_moves": [],
            "position_value": 0.0,
            "offline": True
        }

@api_router.post("/coaching/analyze-move")
async def analyze_move(request: AnalyzeMoveRequest):
    """Analyze a specific move to see if it was good or bad"""
    if request.game_id not in active_games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    try:
        game = active_games[request.game_id]
        engine = game["engine"]
        
        # Get the position BEFORE the move was made
        history = game["history"]
        if not history or history[-1] != request.move:
            return {
                "success": False,
                "message": "Move not found in history or not the last move"
            }
        
        # Recreate position before the move
        temp_engine = ChessEngine()
        for move in history[:-1]:
            temp_engine.make_move(move)
        
        fen_before = temp_engine.get_fen()
        
        # Get active model
        active_model_doc = await db.active_model.find_one({})
        if active_model_doc:
            model_name = active_model_doc["model_name"]
            network, _ = model_manager.load_model(model_name)
        else:
            network = AlphaZeroNetwork()
        
        # Get MCTS evaluation for the position
        top_moves, _ = await get_mcts_evaluation(temp_engine, network, request.num_simulations)
        
        # Check if the played move was in top moves
        played_move = request.move
        top_move_uci = [m["move"] for m in top_moves]
        
        was_best = top_move_uci[0] == played_move if top_move_uci else False
        was_in_top_3 = played_move in top_move_uci[:3]
        
        # Get LLM analysis
        coach = get_or_create_coach(request.game_id)
        analysis = await coach.analyze_specific_move(
            fen_before, 
            played_move, 
            was_best=was_best,
            better_moves=top_move_uci[:3] if not was_in_top_3 else None
        )
        
        return {
            "success": True,
            "move": played_move,
            "was_best": was_best,
            "was_in_top_3": was_in_top_3,
            "best_move": top_move_uci[0] if top_move_uci else None,
            "top_moves": top_moves[:3],
            "analysis": analysis
        }
    except Exception as e:
        logger.error(f"Move analysis error: {e}")
        return {
            "success": True,
            "analysis": "Move analysis temporarily unavailable.",
            "offline": True
        }

@api_router.post("/coaching/ask")
async def ask_coach_question(request: CoachRequest):
    """Ask the coach a general question"""
    if request.game_id not in active_games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    if not request.question:
        raise HTTPException(status_code=400, detail="Question is required")
    
    try:
        game = active_games[request.game_id]
        engine = game["engine"]
        fen = engine.get_fen()
        
        coach = get_or_create_coach(request.game_id)
        answer = await coach.general_question(request.question, fen)
        
        return {
            "success": True,
            "question": request.question,
            "answer": answer,
            "conversation_history": coach.get_conversation_history()[-10:]
        }
    except Exception as e:
        logger.error(f"Coach question error: {e}")
        return {
            "success": True,
            "answer": "I'm having trouble answering right now. Keep playing and learning!",
            "offline": True
        }

@api_router.post("/coaching/reset/{game_id}")
async def reset_coaching_session(game_id: str):
    """Reset coaching conversation for a game"""
    if game_id in coaching_sessions:
        coaching_sessions[game_id].reset_conversation()
        return {"success": True, "message": "Coaching session reset"}
    return {"success": True, "message": "No active coaching session"}

@api_router.get("/coaching/history/{game_id}")
async def get_coaching_history(game_id: str):
    """Get conversation history for a game"""
    if game_id in coaching_sessions:
        history = coaching_sessions[game_id].get_conversation_history()
        return {"success": True, "history": history}
    return {"success": True, "history": []}

# ====================
# LLM Analytics Insights Endpoint (Step 12)
# ====================

@api_router.post("/llm/insights")
async def generate_training_insights():
    """
    Generate comprehensive LLM-powered insights from training and evaluation metrics.
    This endpoint fetches data from MongoDB and uses LLM to provide coaching insights.
    """
    try:
        from llm_evaluator import LLMChessEvaluator
        
        # Initialize LLM evaluator for analytics
        evaluator = LLMChessEvaluator(session_id="analytics-coach")
        
        # Fetch training metrics (last 50 epochs)
        training_metrics = await db.training_metrics.find().sort("timestamp", -1).limit(50).to_list(50)
        
        # Fetch evaluation results (last 10)
        evaluations = await db.model_evaluations.find().sort("timestamp", -1).limit(10).to_list(10)
        
        # Fetch self-play statistics
        total_positions = await db.self_play_positions.count_documents({})
        recent_positions = await db.self_play_positions.find().sort("timestamp", -1).limit(1000).to_list(1000)
        
        # Get active model
        active_model_doc = await db.active_model.find_one({})
        
        # Process training data
        if training_metrics:
            recent_losses = [m.get("loss", 0) for m in training_metrics[:20] if m.get("loss")]
            avg_recent_loss = sum(recent_losses) / len(recent_losses) if recent_losses else 0
            
            # Calculate loss improvement (compare first 10 vs last 10)
            first_half = [m.get("loss", 0) for m in training_metrics[-10:] if m.get("loss")]
            second_half = [m.get("loss", 0) for m in training_metrics[:10] if m.get("loss")]
            
            if first_half and second_half:
                avg_first = sum(first_half) / len(first_half)
                avg_second = sum(second_half) / len(second_half)
                improvement = ((avg_first - avg_second) / avg_first * 100) if avg_first > 0 else 0
                loss_improvement = f"{improvement:.1f}% improvement"
            else:
                loss_improvement = "N/A"
            
            # Loss summary
            if len(recent_losses) >= 3:
                loss_summary = f"Min: {min(recent_losses):.4f}, Max: {max(recent_losses):.4f}, Latest: {recent_losses[0]:.4f}"
            else:
                loss_summary = "Insufficient data"
            
            # Count unique training sessions
            training_sessions = await db.training_metrics.distinct("session_id")
            total_sessions = len(training_sessions)
        else:
            avg_recent_loss = "N/A"
            loss_improvement = "No training data"
            loss_summary = "No training data"
            total_sessions = 0
        
        training_data = {
            "total_sessions": total_sessions,
            "total_epochs": len(training_metrics),
            "loss_summary": loss_summary,
            "avg_recent_loss": f"{avg_recent_loss:.4f}" if isinstance(avg_recent_loss, float) else avg_recent_loss,
            "loss_improvement": loss_improvement
        }
        
        # Process evaluation data
        if evaluations:
            recent_win_rates = []
            promoted_count = 0
            
            for eval_data in evaluations:
                win_rate = eval_data.get("challenger_win_rate", 0)
                recent_win_rates.append(win_rate)
                if eval_data.get("promoted", False) or win_rate > 0.55:
                    promoted_count += 1
            
            recent_win_rate = recent_win_rates[0] if recent_win_rates else 0
            avg_win_rate = sum(recent_win_rates) / len(recent_win_rates) if recent_win_rates else 0
            
            # Win rate trend
            if len(recent_win_rates) >= 3:
                recent_trend = sum(recent_win_rates[:3]) / 3
                older_trend = sum(recent_win_rates[-3:]) / 3
                if recent_trend > older_trend + 0.05:
                    win_rate_trend = "Improving"
                elif recent_trend < older_trend - 0.05:
                    win_rate_trend = "Declining"
                else:
                    win_rate_trend = "Stable"
            else:
                win_rate_trend = "Insufficient data"
        else:
            recent_win_rate = "N/A"
            win_rate_trend = "No evaluation data"
            promoted_count = 0
            avg_win_rate = 0
        
        evaluation_data = {
            "total_evaluations": len(evaluations),
            "recent_win_rate": f"{recent_win_rate * 100:.1f}%" if isinstance(recent_win_rate, float) else recent_win_rate,
            "win_rate_trend": win_rate_trend,
            "promoted_count": promoted_count,
            "current_champion": active_model_doc["model_name"] if active_model_doc else "None"
        }
        
        # Process self-play data
        recent_games = len(recent_positions) // 30  # Estimate games (avg 30 positions per game)
        quality_score = "Good" if total_positions > 1000 else "Low" if total_positions > 0 else "None"
        
        selfplay_data = {
            "total_positions": total_positions,
            "recent_games": recent_games,
            "quality_score": quality_score
        }
        
        # Generate LLM insights
        logger.info("Generating LLM insights from analytics data...")
        insights = await evaluator.analyze_training_metrics(training_data, evaluation_data, selfplay_data)
        
        return {
            "success": True,
            "insights": insights,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics_summary": {
                "training": training_data,
                "evaluation": evaluation_data,
                "selfplay": selfplay_data
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating insights: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate insights: {str(e)}")

# ====================
# Analytics Endpoints (Supporting Step 12)
# ====================

@api_router.get("/training/metrics")
async def get_training_metrics(limit: int = 50):
    """Get training metrics for analytics"""
    metrics = await db.training_metrics.find().sort("timestamp", -1).limit(limit).to_list(limit)
    return {"success": True, "metrics": metrics}

@api_router.get("/analytics/training-summary")
async def get_training_summary():
    """Get training summary statistics"""
    # Get unique sessions
    training_sessions_raw = await db.training_metrics.aggregate([
        {"$group": {
            "_id": "$session_id",
            "epochs": {"$sum": 1},
            "avg_loss": {"$avg": "$loss"},
            "timestamp": {"$first": "$timestamp"},
            "device": {"$first": "$device"}
        }},
        {"$sort": {"timestamp": -1}},
        {"$limit": 10}
    ]).to_list(10)
    
    training_sessions = [
        {
            "session_id": s["_id"],
            "epochs": s["epochs"],
            "avg_loss": s["avg_loss"],
            "device": s.get("device", "Unknown")
        }
        for s in training_sessions_raw
    ]
    
    total_sessions = len(await db.training_metrics.distinct("session_id"))
    total_epochs = await db.training_metrics.count_documents({})
    
    return {
        "success": True,
        "total_sessions": total_sessions,
        "total_epochs": total_epochs,
        "training_sessions": training_sessions
    }

@api_router.get("/analytics/evaluation-summary")
async def get_evaluation_summary(limit: int = 20):
    """Get evaluation summary with win rate progression"""
    evaluations = await db.model_evaluations.find().sort("timestamp", -1).limit(limit).to_list(limit)
    
    # Build win rate progression
    win_rate_progression = []
    for eval_data in reversed(evaluations):
        win_rate_progression.append({
            "challenger": eval_data.get("challenger_name", "Unknown"),
            "champion": eval_data.get("champion_name", "Unknown"),
            "win_rate": eval_data.get("challenger_win_rate", 0),
            "promoted": eval_data.get("promoted", False) or eval_data.get("challenger_win_rate", 0) > 0.55,
            "games_played": eval_data.get("games_played", 0)
        })
    
    return {
        "success": True,
        "count": len(evaluations),
        "evaluations": evaluations,
        "win_rate_progression": win_rate_progression
    }

@api_router.get("/analytics/model-history")
async def get_model_history():
    """Get model promotion history"""
    # Get all active model changes
    promotions = await db.model_evaluations.find({
        "$or": [
            {"promoted": True},
            {"challenger_win_rate": {"$gte": 0.55}}
        ]
    }).sort("timestamp", -1).limit(10).to_list(10)
    
    promotion_history = [
        {
            "model_name": p.get("challenger_name", "Unknown"),
            "defeated": p.get("champion_name", "N/A"),
            "win_rate": p.get("challenger_win_rate", 0),
            "promoted_at": p.get("timestamp", datetime.now(timezone.utc)).isoformat() if isinstance(p.get("timestamp"), datetime) else str(p.get("timestamp"))
        }
        for p in promotions
    ]
    
    active_model_doc = await db.active_model.find_one({})
    
    return {
        "success": True,
        "active_model": active_model_doc["model_name"] if active_model_doc else None,
        "promotion_history": promotion_history
    }

# ====================
# Device Info
# ====================

@api_router.get("/device/info")
async def get_device_info():
    """Get device information"""
    from device_manager import device_manager
    
    return {
        "success": True,
        "device_type": str(device_manager.device),
        "device_name": device_manager.device_name,
        "is_gpu": device_manager.device.type == "cuda"
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
