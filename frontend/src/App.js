import React, { useState, useEffect, useRef } from 'react';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';
const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws';
const SUBSCRIPTION_KEY = process.env.REACT_APP_APIM_SUBSCRIPTION_KEY || '';

function App() {
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState([]);
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState('Disconnected');
  const wsRef = useRef(null);

  useEffect(() => {
    // Connect to WebSocket
    connectWebSocket();

    // Cleanup on unmount
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const connectWebSocket = () => {
    try {
      // Add subscription key to WebSocket URL if available
      const wsUrlWithKey = SUBSCRIPTION_KEY 
        ? `${WS_URL}?subscription-key=${SUBSCRIPTION_KEY}`
        : WS_URL;
      
      console.log('Connecting to WebSocket:', wsUrlWithKey.replace(/subscription-key=[^&]+/, 'subscription-key=***'));
      const ws = new WebSocket(wsUrlWithKey);

      ws.onopen = () => {
        console.log('WebSocket connected');
        setConnected(true);
        setStatus('Connected');
        addMessage('System', 'Connected to WebSocket', 'success');
      };

      ws.onmessage = (event) => {
        console.log('Received message:', event.data);
        try {
          const data = JSON.parse(event.data);
          addMessage('Backend', data.data || JSON.stringify(data), 'received');
        } catch (e) {
          addMessage('Backend', event.data, 'received');
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setStatus('Error');
        addMessage('System', 'WebSocket error occurred', 'error');
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setConnected(false);
        setStatus('Disconnected');
        addMessage('System', 'Disconnected from WebSocket', 'error');
        
        // Attempt to reconnect after 3 seconds
        setTimeout(() => {
          console.log('Attempting to reconnect...');
          connectWebSocket();
        }, 3000);
      };

      wsRef.current = ws;
    } catch (error) {
      console.error('Failed to connect:', error);
      setStatus('Error');
    }
  };

  const addMessage = (sender, content, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setMessages(prev => [...prev, { sender, content, type, timestamp }]);
  };

  const publishMessage = async () => {
    if (!message.trim()) {
      alert('Please enter a message');
      return;
    }

    try {
      const payload = {
        content: message,
        timestamp: new Date().toISOString(),
        sender: 'Frontend'
      };

      addMessage('You', message, 'sent');

      const headers = {
        'Content-Type': 'application/json',
      };
      
      // Add subscription key header if available
      if (SUBSCRIPTION_KEY) {
        headers['Ocp-Apim-Subscription-Key'] = SUBSCRIPTION_KEY;
      }

      const response = await fetch(`${BACKEND_URL}/publish`, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload),
      });

      const result = await response.json();
      
      if (result.error) {
        addMessage('System', `Error: ${result.error}`, 'error');
      } else {
        console.log('Message published successfully');
      }

      setMessage('');
    } catch (error) {
      console.error('Error publishing message:', error);
      addMessage('System', `Failed to publish: ${error.message}`, 'error');
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      publishMessage();
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Azure PubSub Demo</h1>
        <div className={`status-indicator ${connected ? 'connected' : 'disconnected'}`}>
          {status}
        </div>
      </header>

      <main className="App-main">
        <div className="message-container">
          <h2>Messages</h2>
          <div className="messages-list">
            {messages.length === 0 ? (
              <div className="no-messages">No messages yet. Send one to get started!</div>
            ) : (
              messages.map((msg, index) => (
                <div key={index} className={`message message-${msg.type}`}>
                  <div className="message-header">
                    <strong>{msg.sender}</strong>
                    <span className="message-time">{msg.timestamp}</span>
                  </div>
                  <div className="message-content">{msg.content}</div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="input-container">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message here..."
            rows="3"
          />
          <button 
            onClick={publishMessage} 
            disabled={!connected || !message.trim()}
            className="publish-button"
          >
            Publish to Azure PubSub
          </button>
        </div>
      </main>
    </div>
  );
}

export default App;
