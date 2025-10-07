from emergentintegrations.llm.chat import LlmChat, UserMessage
from dotenv import load_dotenv
import os
import chess
import logging
from typing import Dict, List, Optional

load_dotenv()
logger = logging.getLogger(__name__)

class LLMChessEvaluator:
    """Use LLM for chess position evaluation and insights"""
    
    def __init__(self, session_id: str = "chess-evaluator"):
        self.api_key = os.environ.get('EMERGENT_LLM_KEY')
        self.session_id = session_id
        self.chat = LlmChat(
            api_key=self.api_key,
            session_id=session_id,
            system_message="You are an expert chess coach. Analyze positions, suggest moves, and provide strategic insights. Be encouraging and educational. Keep responses concise (2-4 sentences)."
        ).with_model("openai", "gpt-4o-mini")
        self.conversation_history = []
    
    async def evaluate_position(self, fen: str, context: str = ""):
        """
        Evaluate a chess position using LLM
        Returns: evaluation text
        """
        try:
            board = chess.Board(fen)
            
            # Create position description
            position_desc = f"Position (FEN): {fen}\n"
            position_desc += f"Turn: {'White' if board.turn == chess.WHITE else 'Black'}\n"
            position_desc += f"Legal moves: {len(list(board.legal_moves))}\n"
            
            if context:
                position_desc += f"\nContext: {context}"
            
            prompt = f"{position_desc}\n\nProvide a brief strategic evaluation (2-3 sentences)."
            
            message = UserMessage(text=prompt)
            response = await self.chat.send_message(message)
            
            return response
        except Exception as e:
            logger.error(f"LLM evaluation error: {e}")
            return "Evaluation unavailable"
    
    async def suggest_opening_strategy(self, fen: str):
        """Get opening strategy suggestions"""
        try:
            prompt = f"Position: {fen}\n\nSuggest opening strategy for this position (1-2 sentences)."
            message = UserMessage(text=prompt)
            response = await self.chat.send_message(message)
            return response
        except Exception as e:
            logger.error(f"LLM strategy error: {e}")
            return "No strategy available"
    
    async def analyze_game(self, moves_history: list, result: str):
        """Analyze a completed game"""
        try:
            moves_str = " ".join(moves_history[:20])  # First 20 moves
            prompt = f"Game moves: {moves_str}\nResult: {result}\n\nProvide brief analysis of key moments."
            message = UserMessage(text=prompt)
            response = await self.chat.send_message(message)
            return response
        except Exception as e:
            logger.error(f"LLM analysis error: {e}")
            return "Analysis unavailable"
    
    async def coach_with_mcts(self, fen: str, top_moves: List[Dict], position_value: float, context: str = ""):
        """
        Provide coaching using AlphaZero's MCTS evaluation
        top_moves: [{"move": "e2e4", "probability": 0.45, "visits": 360}, ...]
        position_value: estimated value from -1 (black winning) to +1 (white winning)
        """
        try:
            board = chess.Board(fen)
            turn = "White" if board.turn == chess.WHITE else "Black"
            
            # Format top moves
            moves_desc = "\n".join([
                f"{i+1}. {m['move']} ({m['probability']*100:.1f}% confidence, {m['visits']} visits)"
                for i, m in enumerate(top_moves[:3])
            ])
            
            # Interpret position value
            if position_value > 0.3:
                eval_text = f"White has a significant advantage ({position_value:.2f})"
            elif position_value > 0.1:
                eval_text = f"White is slightly better ({position_value:.2f})"
            elif position_value > -0.1:
                eval_text = f"Position is roughly equal ({position_value:.2f})"
            elif position_value > -0.3:
                eval_text = f"Black is slightly better ({position_value:.2f})"
            else:
                eval_text = f"Black has a significant advantage ({position_value:.2f})"
            
            prompt = f"""Position (FEN): {fen}
Turn: {turn} to move
AlphaZero Evaluation: {eval_text}

Top recommended moves by AlphaZero:
{moves_desc}

{context if context else "Provide coaching advice for this position."}

As a chess coach, explain the position and recommend the best move."""
            
            message = UserMessage(text=prompt)
            response = await self.chat.send_message(message)
            self.conversation_history.append({"role": "assistant", "content": response})
            
            return response
        except Exception as e:
            logger.error(f"LLM coaching error: {e}")
            return "Coaching unavailable. The AI recommends trying the top-rated move from AlphaZero's analysis."
    
    async def analyze_specific_move(self, fen: str, move: str, was_best: bool, better_moves: List[str] = None):
        """Analyze why a specific move was good or bad"""
        try:
            board = chess.Board(fen)
            turn = "White" if board.turn == chess.WHITE else "Black"
            
            if was_best:
                prompt = f"Position: {fen}\n{turn} played {move}.\n\nThis was the best move! Explain why this move is strong (2-3 sentences)."
            else:
                better_str = ", ".join(better_moves[:3]) if better_moves else "other options"
                prompt = f"Position: {fen}\n{turn} played {move}.\n\nThis wasn't the best choice. Better moves: {better_str}.\n\nExplain what's wrong with {move} and why the alternatives are better (2-3 sentences)."
            
            message = UserMessage(text=prompt)
            response = await self.chat.send_message(message)
            self.conversation_history.append({"role": "assistant", "content": response})
            
            return response
        except Exception as e:
            logger.error(f"LLM move analysis error: {e}")
            return "Move analysis unavailable."
    
    async def general_question(self, question: str, fen: str = None):
        """Answer general chess questions from the user"""
        try:
            context = f"\nCurrent position (FEN): {fen}" if fen else ""
            prompt = f"{question}{context}"
            
            message = UserMessage(text=prompt)
            response = await self.chat.send_message(message)
            self.conversation_history.append({"role": "user", "content": question})
            self.conversation_history.append({"role": "assistant", "content": response})
            
            return response
        except Exception as e:
            logger.error(f"LLM question error: {e}")
            return "Unable to answer right now."
    
    def reset_conversation(self):
        """Reset conversation history for a new game"""
        self.conversation_history = []
        logger.info(f"Conversation reset for session {self.session_id}")
    
    def get_conversation_history(self):
        """Get the conversation history"""
        return self.conversation_history
    
    async def analyze_training_metrics(self, training_data: dict, evaluation_data: dict, selfplay_data: dict):
        """
        Analyze training metrics and provide detailed coaching insights
        
        Args:
            training_data: Dictionary with training metrics (epochs, losses, etc.)
            evaluation_data: Dictionary with evaluation results (win rates, etc.)
            selfplay_data: Dictionary with self-play statistics
        
        Returns:
            Comprehensive analysis text with actionable recommendations
        """
        try:
            # Build comprehensive prompt
            prompt = f"""You are an expert AI training coach for AlphaZero chess models. Analyze the following training and evaluation metrics to provide detailed insights and actionable recommendations.

**TRAINING METRICS:**
- Total Sessions: {training_data.get('total_sessions', 0)}
- Total Epochs: {training_data.get('total_epochs', 0)}
- Recent Loss Trends: {training_data.get('loss_summary', 'N/A')}
- Average Loss (Recent): {training_data.get('avg_recent_loss', 'N/A')}
- Loss Improvement Rate: {training_data.get('loss_improvement', 'N/A')}

**EVALUATION RESULTS:**
- Total Evaluations: {evaluation_data.get('total_evaluations', 0)}
- Recent Win Rate: {evaluation_data.get('recent_win_rate', 'N/A')}
- Win Rate Trend: {evaluation_data.get('win_rate_trend', 'N/A')}
- Promoted Models: {evaluation_data.get('promoted_count', 0)}
- Current Champion: {evaluation_data.get('current_champion', 'Unknown')}

**SELF-PLAY STATISTICS:**
- Total Positions Generated: {selfplay_data.get('total_positions', 0)}
- Recent Games Played: {selfplay_data.get('recent_games', 0)}
- Data Quality Score: {selfplay_data.get('quality_score', 'N/A')}

**ANALYSIS REQUEST:**
Based on these metrics, provide:
1. **Performance Assessment**: How is the model training progressing? Identify key strengths and weaknesses.
2. **Loss Analysis**: Are the loss curves converging well? Any signs of overfitting, underfitting, or instability?
3. **Win Rate Insights**: How effective are the new models compared to previous versions? Is the improvement rate satisfactory?
4. **Data Quality**: Is the self-play data generation sufficient? Any recommendations for data collection?
5. **Actionable Recommendations**: Provide 3-5 specific, prioritized actions to improve model performance. Include concrete parameter suggestions (e.g., "increase MCTS simulations to 800", "reduce learning rate to 0.0005").

Be detailed, technical, and provide specific numerical recommendations where applicable. Focus on practical next steps."""

            message = UserMessage(text=prompt)
            response = await self.chat.send_message(message)
            
            return response
        except Exception as e:
            logger.error(f"LLM training analysis error: {e}")
            return "Training analysis unavailable. Continue training and evaluation to gather more metrics."