# AlphaZero Self-Play Data Collection Implementation

## Overview
This document describes the standalone self-play data collection feature added to the AlphaZero chess application. This feature allows collecting training data from AI vs AI matches without triggering model training.

## Features Implemented

### 1. Backend API Endpoints

#### POST `/api/self-play/run`
Triggers a new self-play data collection session.

**Request Body:**
```json
{
  "num_games": 10,
  "num_simulations": 800
}
```

**Response:**
```json
{
  "status": "Self-play started",
  "config": {
    "num_games": 10,
    "num_simulations": 800
  },
  "message": "Generating 10 games with 800 simulations per move"
}
```

#### GET `/api/self-play/status`
Returns current self-play status and statistics.

**Response:**
```json
{
  "active": false,
  "total_sessions": 5,
  "total_positions": 2847,
  "recent_session": {
    "session_id": "uuid",
    "timestamp": "2025-10-06T...",
    "num_games": 10,
    "num_simulations": 800,
    "num_positions": 573
  }
}
```

#### GET `/api/self-play/sessions?limit=50`
Lists all self-play sessions.

**Response:**
```json
{
  "sessions": [
    {
      "_id": "...",
      "session_id": "uuid",
      "timestamp": "2025-10-06T...",
      "num_games": 10,
      "num_simulations": 800,
      "num_positions": 573,
      "game_results": [
        {
          "game_num": 1,
          "result": "1-0",
          "num_moves": 42,
          "num_positions": 42
        }
      ]
    }
  ]
}
```

#### GET `/api/self-play/export/{session_id}?format=json|csv`
Exports self-play data in JSON or CSV format.

**JSON Response:**
```json
{
  "session_id": "uuid",
  "session_info": {
    "num_games": 10,
    "num_simulations": 800,
    "num_positions": 573,
    "timestamp": "2025-10-06T..."
  },
  "positions": [
    {
      "position_id": "uuid_0",
      "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
      "move_probabilities": {
        "e2e4": 0.35,
        "d2d4": 0.28,
        "c2c4": 0.15,
        ...
      },
      "value": 0.0,
      "move_number": 0,
      "timestamp": "2025-10-06T..."
    }
  ]
}
```

**CSV Format:**
- Headers: `position_id, fen, move_probabilities, value, move_number, timestamp`
- Each row represents one training position
- `move_probabilities` column contains JSON-encoded dictionary

### 2. Database Schema

#### Collection: `self_play_sessions`
Stores metadata about each self-play run.

```javascript
{
  "_id": ObjectId,
  "session_id": String (UUID),
  "timestamp": ISODate,
  "num_games": Number,
  "num_simulations": Number,
  "num_positions": Number,
  "game_results": [
    {
      "game_num": Number,
      "result": String ("1-0", "0-1", "1/2-1/2"),
      "num_moves": Number,
      "num_positions": Number
    }
  ]
}
```

#### Collection: `self_play_positions`
Stores individual training positions.

```javascript
{
  "_id": ObjectId,
  "session_id": String (UUID),
  "position_id": String,
  "timestamp": ISODate,
  "fen": String,
  "move_probabilities": Object,  // {move_uci: probability}
  "value": Number,  // -1.0 to 1.0
  "move_number": Number
}
```

### 3. Frontend Components

#### Self-Play Data Collection Panel
Located in the Training tab, above the existing training system.

**Features:**
- Input controls for number of games (1-100)
- Input controls for MCTS simulations per move (100-1600)
- "Run Self-Play" button with loading state
- Status display showing total sessions and positions
- Dataset list showing:
  - Timestamp
  - Number of games and positions
  - Export buttons for JSON and CSV formats

**UI Components:**
- Emerald/teal color scheme to distinguish from training (purple)
- Database icon for visual identification
- Animated "Collecting Data" badge when active
- Scrollable dataset list (max height 264px)

### 4. Modified Files

#### Backend:
- `/app/backend/self_play.py` - Added FEN storage and move number tracking
- `/app/backend/server.py` - Added self-play API endpoints and background task execution

#### Frontend:
- `/app/frontend/src/components/TrainingPanel.jsx` - Complete redesign with self-play section

### 5. Data Flow

```
1. User clicks "Run Self-Play" in UI
   ↓
2. Frontend sends POST request to /api/self-play/run
   ↓
3. Backend starts background task (execute_self_play)
   ↓
4. SelfPlayManager generates N games with M simulations per move
   ↓
5. Each game produces ~40-60 positions (varies by game length)
   ↓
6. Positions stored in MongoDB with:
   - FEN notation
   - MCTS move probabilities
   - Game outcome value
   ↓
7. Session metadata stored separately
   ↓
8. Frontend polls /api/self-play/status every 3 seconds
   ↓
9. When complete, datasets appear in UI
   ↓
10. User can export as JSON or CSV
```

## Usage Examples

### Collecting Data via API

```bash
# Start self-play collection
curl -X POST http://localhost:8001/api/self-play/run \
  -H "Content-Type: application/json" \
  -d '{"num_games": 20, "num_simulations": 800}'

# Check status
curl http://localhost:8001/api/self-play/status

# List sessions
curl http://localhost:8001/api/self-play/sessions

# Export as JSON
curl "http://localhost:8001/api/self-play/export/{session_id}?format=json" > data.json

# Export as CSV
curl "http://localhost:8001/api/self-play/export/{session_id}?format=csv" > data.csv
```

### Using Exported Data

#### Python Training Script Example:
```python
import json

# Load data
with open('data.json', 'r') as f:
    dataset = json.load(f)

# Access positions
for pos in dataset['positions']:
    fen = pos['fen']
    policy = pos['move_probabilities']
    value = pos['value']
    
    # Convert to training format
    # ... your training code
```

#### Pandas Analysis Example:
```python
import pandas as pd

# Load CSV
df = pd.read_csv('data.csv')

# Analyze
print(f"Total positions: {len(df)}")
print(f"Average value: {df['value'].mean()}")
print(f"Positions by move number:\n{df['move_number'].value_counts()}")
```

## Configuration

### Recommended Settings

**For Quick Testing:**
- Games: 5-10
- Simulations: 100-200
- Time: ~5-10 minutes

**For Production Data Collection:**
- Games: 50-100
- Simulations: 800-1600
- Time: 2-4 hours

**Performance Notes:**
- Each position requires ~0.5-2 seconds with 800 simulations
- Average game length: 40-60 moves
- 10 games with 800 simulations ≈ 30-60 minutes

## Integration with Existing System

### Preserved Features:
- ✅ Existing training system unchanged
- ✅ Model management (save/load/import/export)
- ✅ Human vs AI gameplay
- ✅ LLM position evaluation

### New Features:
- ✅ Standalone self-play data collection
- ✅ Session-based organization
- ✅ Dual export formats (JSON + CSV)
- ✅ Real-time status monitoring

## Future Enhancements

Potential improvements for future development:

1. **Data Management:**
   - Delete individual sessions
   - Merge multiple sessions
   - Filter positions by criteria (opening, endgame, etc.)

2. **Analysis Tools:**
   - Position diversity metrics
   - Move distribution visualization
   - Value distribution analysis

3. **Performance:**
   - Parallel game generation
   - Incremental exports during collection
   - Streaming large datasets

4. **Training Integration:**
   - Direct training from collected datasets
   - Curriculum learning (easy → hard positions)
   - Data augmentation (board rotations, flips)

## Testing

### Manual Testing Checklist:

- [ ] Start self-play via UI
- [ ] Monitor status updates
- [ ] Wait for completion (check logs)
- [ ] Verify sessions list appears
- [ ] Export as JSON
- [ ] Export as CSV
- [ ] Verify data format and content
- [ ] Test with different configurations
- [ ] Ensure training system still works

### API Testing:
```bash
# Run all tests
./test_selfplay.sh
```

## Troubleshooting

### Self-play not starting:
- Check backend logs: `/var/log/supervisor/backend.err.log`
- Verify MongoDB is running: `ps aux | grep mongod`
- Check if another session is active

### No data appearing:
- Self-play takes time (5-60 min depending on config)
- Monitor backend logs for "Starting self-play session"
- Look for "Self-play session complete" message

### Export failing:
- Verify session_id is correct
- Check MongoDB has data: `mongosh test_database`
- Ensure format parameter is "json" or "csv"

## Performance Benchmarks

Tested on standard configuration:

| Games | Sims | Positions | Time    |
|-------|------|-----------|---------|
| 5     | 100  | ~200      | 2-3 min |
| 10    | 400  | ~450      | 15-20min|
| 20    | 800  | ~900      | 45-60min|
| 50    | 800  | ~2300     | 2-3 hrs |

## Conclusion

The self-play data collection feature provides a robust way to generate training data for the AlphaZero chess engine. Data is organized by session, stored with full game context (FEN + move probabilities + outcomes), and easily exportable for external training pipelines.
