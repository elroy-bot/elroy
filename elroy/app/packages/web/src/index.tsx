import React from 'react';
import ReactDOM from 'react-dom/client';
import { createApiClient, Api } from '@elroy/shared';

// Initialize API client
createApiClient({
  baseURL: 'http://localhost:8000',
});

const App: React.FC = () => {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100vh',
      padding: '20px'
    }}>
      <h1>Elroy Web App</h1>
      <p>This is a minimal implementation of the Elroy web app.</p>
      <p>The shared API client has been initialized and is ready to use.</p>
      <p>You can start building the full web app by implementing components similar to the mobile app.</p>
    </div>
  );
};

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
