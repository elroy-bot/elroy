import React from 'react';

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

export default App;
