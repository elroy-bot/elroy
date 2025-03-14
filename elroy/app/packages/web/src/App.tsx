import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import { createApiClient, Api } from '@elroy/shared';

// Import components
import Header from './components/Header';

// Import screens
import HomeScreen from './screens/HomeScreen';
import LoginScreen from './screens/LoginScreen';
import RegisterScreen from './screens/RegisterScreen';
import ChatScreen from './screens/ChatScreen';

// Initialize API client
createApiClient({
  baseURL: 'http://localhost:8000',
});

const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
});

const App: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check if user is already authenticated
    const checkAuth = async () => {
      const isAuth = Api.Auth.isAuthenticated();
      setIsAuthenticated(isAuth);
      setIsLoading(false);
    };

    checkAuth();
  }, []);

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <Header isAuthenticated={isAuthenticated} setIsAuthenticated={setIsAuthenticated} />
        <Routes>
          {isAuthenticated ? (
            <>
              <Route path="/" element={<HomeScreen />} />
              <Route path="/chat" element={<ChatScreen />} />
              <Route path="/login" element={<Navigate to="/" />} />
              <Route path="/register" element={<Navigate to="/" />} />
              {/* Add more authenticated routes as needed */}
              <Route path="*" element={<Navigate to="/" />} />
            </>
          ) : (
            <>
              <Route path="/login" element={<LoginScreen setIsAuthenticated={setIsAuthenticated} />} />
              <Route path="/register" element={<RegisterScreen />} />
              <Route path="*" element={<Navigate to="/login" />} />
            </>
          )}
        </Routes>
      </Router>
    </ThemeProvider>
  );
};

export default App;
