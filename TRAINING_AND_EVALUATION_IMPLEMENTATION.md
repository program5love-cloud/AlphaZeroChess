# AlphaZero Training Loop and Model Evaluation Pipeline

## Implementation Summary

This document describes the complete training loop and model evaluation pipeline implemented for the AlphaZero chess application.

## 🎯 Goals Achieved

### 1. Training Loop ✅
- **Self-play data generation**: Generate training positions through self-play games
- **Neural network training**: Train policy-value network on self-play data
- **Configurable hyperparameters**: Learning rate, batch size, epochs, simulations
- **Automatic model versioning**: Models saved as `model_v1`, `model_v2`, etc.
- **MongoDB integration**: Store training metrics and game results

### 2. Model Evaluation ✅
- **Head-to-head matches**: Run evaluation games between challenger and champion models
- **Win-rate tracking**: Calculate statistics across 20 games with alternating colors
- **Automatic promotion**: Promote models that exceed 55% win rate
- **Evaluation history**: Store and display past evaluation results

### 3. Model Management ✅
- **Active model tracking**: MongoDB tracks which model is currently active
- **Version management**: Automatic version numbering for trained models
- **Manual activation**: Ability to manually switch active models
- **Model metadata**: Store training configuration and performance data

### 4. Frontend Integration ✅
- **Training configuration**: UI for all training parameters including learning rate
- **Model list**: Display all models with active model highlighted
- **Evaluation display**: Show evaluation results with win rates and statistics
- **Real-time status**: Monitor training and evaluation progress

## 📁 New Files Created

### Backend Files

#### `/app/backend/evaluator.py`
- `EvaluationMatch`: Runs games between two models
- `ModelEvaluator`: Manages evaluation workflow and promotion logic
- Configurable evaluation games (default: 20) and simulations (default: 400)

### Modified Files

#### `/app/backend/neural_network.py`
- Added `get_next_version()`: Automatic version numbering
- Added `save_versioned_model()`: Save with auto-incrementing version
- Added `get_model_info()`: Get model metadata without loading

#### `/app/backend/server.py`
Enhanced with new endpoints:
- `POST /api/evaluation/run`: Start evaluation between two models
- `GET /api/evaluation/status`: Check evaluation progress
- `GET /api/evaluation/history`: View past evaluations
- `GET /api/model/current`: Get active model info
- `POST /api/model/activate/{name}`: Manually activate a model

Enhanced training workflow:
- Training now uses versioned model names
- Automatic evaluation after training completes
- Auto-promotion if new model wins >= 55% of games
- Tracks active model in MongoDB

#### `/app/frontend/src/components/TrainingPanel.jsx`
- Added learning rate configuration input
- Added active model indicator with checkmark
- Added evaluation history display with win rates
- Added model activation on click
- Real-time evaluation status monitoring

## 🔄 Complete AlphaZero Workflow

### Training Workflow
```
1. User configures training parameters (games, epochs, learning rate, simulations)
2. Start Training → Generate self-play games
3. Train neural network on self-play data
4. Save model with version number (e.g., model_v3)
5. Load current active model (if exists)
6. Run evaluation: new model vs current best (20 games)
7. If win rate >= 55%: Promote new model to active
8. If win rate < 55%: Keep current model as active
9. Store all metrics in MongoDB
```

### Evaluation Workflow
```
1. User can manually trigger evaluation between any two models
2. Models play 20 games with alternating colors
3. Track wins, losses, draws
4. Calculate win rates
5. Display results in UI
6. Optionally promote winning model
```

### Model Management
```
- Active model used for MCTS gameplay
- Models versioned automatically (model_v1, model_v2, ...)
- Users can manually activate any saved model
- Cannot delete active model
- Export/import models for external training
```

## 🎮 Training Configuration

### Default Parameters
```json
{
  "num_games": 5,          // Self-play games to generate
  "num_epochs": 10,        // Training epochs
  "batch_size": 32,        // Training batch size
  "num_simulations": 400,  // MCTS simulations during training
  "learning_rate": 0.001   // Neural network learning rate
}
```

### Evaluation Parameters
```json
{
  "num_evaluation_games": 20,  // Games per evaluation
  "num_simulations": 400,      // Simulations per move (faster than training)
  "win_threshold": 0.55        // 55% win rate for promotion
}
```

## 📊 MongoDB Collections

### `active_model`
Stores currently active model:
```json
{
  "model_name": "model_v3",
  "promoted_at": "2025-01-15T10:30:00Z",
  "win_rate": 0.65,
  "previous_champion": "model_v2",
  "manual_activation": false
}
```

### `model_evaluations`
Stores evaluation results:
```json
{
  "challenger_name": "model_v3",
  "champion_name": "model_v2",
  "challenger_win_rate": 0.65,
  "champion_win_rate": 0.25,
  "games_played": 20,
  "model1_wins": 13,
  "model2_wins": 5,
  "draws": 2,
  "promoted": true,
  "automatic": true,
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### `training_metrics`
Stores training epoch metrics:
```json
{
  "epoch": 5,
  "loss": 0.4523,
  "policy_loss": 0.3012,
  "value_loss": 0.1511,
  "num_batches": 16,
  "training_session_id": "uuid",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

## 🚀 API Endpoints

### Training
- `POST /api/training/start` - Start training with config
- `GET /api/training/status` - Get training status
- `POST /api/training/stop` - Stop training
- `GET /api/training/history` - Get training history

### Evaluation
- `POST /api/evaluation/run` - Run evaluation match
- `GET /api/evaluation/status` - Get evaluation status
- `GET /api/evaluation/history` - Get evaluation history

### Model Management
- `GET /api/model/list` - List all models
- `GET /api/model/current` - Get active model
- `POST /api/model/activate/{name}` - Activate a model
- `POST /api/model/save` - Save current model
- `POST /api/model/load` - Load a model
- `DELETE /api/model/delete/{name}` - Delete a model
- `GET /api/model/export/{name}` - Export model file
- `POST /api/model/import` - Import model file

## 🎨 Frontend Features

### Training Tab
1. **Self-Play Data Collection**
   - Configure number of games and simulations
   - Run self-play to generate training data
   - Export datasets in JSON or CSV format

2. **Training System**
   - Configure training parameters (games, epochs, simulations, learning rate)
   - Start/stop training
   - View real-time training metrics
   - Save/load/import/export models

3. **Model Management**
   - View all saved models
   - Active model highlighted with checkmark
   - Click to activate any model
   - Export models for sharing
   - Delete unused models (except active)

4. **Evaluation Display**
   - View evaluation history
   - See win rates, games played, W-L-D records
   - "Promoted" badge for successful evaluations
   - Timestamp for each evaluation

## 🔧 Technical Details

### MCTS Simulations
- **Training**: 400 simulations per move (faster self-play generation)
- **Evaluation**: 400 simulations per move (consistent comparison)
- **Gameplay**: 800 simulations per move (highest quality)

### Model Architecture
- ResNet-style neural network
- 128 channels, 6 residual blocks
- Input: 14×8×8 board encoding
- Output: Policy (4096 moves) + Value (scalar)

### Training Process
1. Generate self-play games using current model
2. Each position stores: FEN, policy probabilities, game outcome
3. Train network to predict both policy and value
4. Combined loss: policy cross-entropy + value MSE
5. Adam optimizer with configurable learning rate

### Evaluation Process
1. Load both models
2. Play games with alternating colors
3. Use deterministic MCTS (temperature=0)
4. Track wins from each color
5. Calculate overall win rate
6. Promote if threshold exceeded

## 🎯 Usage Examples

### Training a New Model
```javascript
// Frontend: Configure and start training
const config = {
  num_games: 10,
  num_epochs: 15,
  batch_size: 32,
  num_simulations: 400,
  learning_rate: 0.001
};

// Training automatically:
// 1. Generates self-play games
// 2. Trains network
// 3. Saves as model_v{next_version}
// 4. Evaluates vs current best
// 5. Promotes if win rate >= 55%
```

### Manual Evaluation
```bash
# API: Run evaluation between two models
curl -X POST http://localhost:8001/api/evaluation/run \
  -H "Content-Type: application/json" \
  -d '{
    "challenger_name": "model_v3",
    "champion_name": "model_v2",
    "num_games": 20,
    "num_simulations": 400
  }'
```

### Activating a Model
```bash
# API: Manually activate a model
curl -X POST http://localhost:8001/api/model/activate/model_v2
```

## 🧪 Testing

### Backend Testing
```bash
# Test evaluation endpoint
curl -X POST http://localhost:8001/api/evaluation/run \
  -H "Content-Type: application/json" \
  -d '{"challenger_name": "model_v1", "champion_name": "model_v2", "num_games": 2}'

# Check evaluation status
curl http://localhost:8001/api/evaluation/status

# Get active model
curl http://localhost:8001/api/model/current

# List all models
curl http://localhost:8001/api/model/list
```

### Frontend Testing
1. Navigate to Training tab
2. Configure training parameters
3. Click "Start Training"
4. Monitor progress in real-time
5. View evaluation results after completion
6. Check active model indicator
7. Click model to activate

## 📈 Performance Considerations

- **Training**: CPU-based for compatibility (can use GPU if available)
- **Evaluation**: 20 games × ~100 moves × 400 sims = ~800K evaluations
- **Estimated time**: ~5-10 minutes per evaluation on CPU
- **Memory**: Models are ~5-10MB each
- **MongoDB**: Efficient indexing on timestamps and session IDs

## 🔮 Future Enhancements

1. **Advanced Evaluation**
   - ELO rating system
   - Opening book integration
   - Position-specific evaluation

2. **Training Improvements**
   - Learning rate scheduling
   - Data augmentation (board flips, rotations)
   - Prioritized experience replay

3. **Distributed Training**
   - Multi-worker self-play
   - GPU acceleration
   - Cloud model storage

4. **Analytics**
   - Training loss plots
   - Win rate over time
   - Model comparison matrix

## ✅ Verification Checklist

- [x] Training loop generates self-play data
- [x] Neural network trains on positions
- [x] Models saved with automatic versioning
- [x] Evaluation runs between models
- [x] Win rates calculated correctly
- [x] Automatic promotion at 55% threshold
- [x] Active model tracked in database
- [x] Frontend displays all features
- [x] Learning rate configurable
- [x] Model list shows active model
- [x] Evaluation history displayed
- [x] Real-time status updates

## 🎉 Implementation Complete

The AlphaZero training loop and model evaluation pipeline is fully implemented and operational. The system can now:

1. Train models through self-play
2. Evaluate models against each other
3. Automatically promote better models
4. Track active model for gameplay
5. Display comprehensive training and evaluation metrics

All chess rules, MCTS logic, and gameplay features remain intact and unmodified.
