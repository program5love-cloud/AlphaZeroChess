import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs';
import { Card, CardHeader, CardTitle, CardContent } from './components/ui/card';
import { Toaster } from './components/ui/sonner';
import { toast } from 'sonner';
import { CheckCircle2, XCircle, AlertCircle } from 'lucide-react';
import ChessBoard from './components/ChessBoard';
import TrainingPanel from './components/TrainingPanel';
import AnalyticsPanel from './components/AnalyticsPanel';
import ModelManagement from './components/ModelManagement';
import GameTab from './components/GameTab';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [backendStatus, setBackendStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkBackendConnection();
  }, []);

  const checkBackendConnection = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API}/`);
      setBackendStatus({
        connected: true,
        message: response.data.message,
        status: response.data.status
      });
      toast.success('Connected to backend!');
    } catch (error) {
      console.error('Error connecting to backend:', error);
      setBackendStatus({
        connected: false,
        error: error.message
      });
      toast.error('Unable to connect to backend');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
        <div className="text-white text-2xl">Loading AlphaZero Chess...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4" data-testid="app-container">
      <Toaster richColors position="top-right" />
      
      <div className="max-w-7xl mx-auto">
        <header className="text-center mb-8 pt-8">
          <h1 className="text-5xl font-bold text-white mb-2 tracking-tight" data-testid="app-title">
            AlphaZero Chess
          </h1>
          <p className="text-slate-300 text-lg">
            Self-Learning Chess AI with Deep Reinforcement Learning
          </p>
          
          {/* Backend Status Indicator */}
          <div className="mt-4 flex items-center justify-center gap-2">
            {backendStatus?.connected ? (
              <>
                <CheckCircle2 className="text-green-500" size={20} />
                <span className="text-green-400">Backend Connected</span>
              </>
            ) : (
              <>
                <XCircle className="text-red-500" size={20} />
                <span className="text-red-400">Backend Disconnected</span>
              </>
            )}
          </div>
        </header>

        <Tabs defaultValue="training" className="w-full" data-testid="main-tabs">
          <TabsList className="grid w-full grid-cols-4 mb-6 bg-slate-800/50">
            <TabsTrigger value="game" data-testid="game-tab">Game</TabsTrigger>
            <TabsTrigger value="training" data-testid="training-tab">Training</TabsTrigger>
            <TabsTrigger value="analytics" data-testid="analytics-tab">Analytics</TabsTrigger>
            <TabsTrigger value="models" data-testid="models-tab">Models</TabsTrigger>
          </TabsList>

          <TabsContent value="game" data-testid="game-content">
            <GameTab />
          </TabsContent>

          <TabsContent value="training" data-testid="training-content">
            <TrainingPanel />
          </TabsContent>

          <TabsContent value="analytics" data-testid="analytics-content">
            <AnalyticsPanel />
          </TabsContent>

          <TabsContent value="models" data-testid="models-content">
            <ModelManagement />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

export default App;
