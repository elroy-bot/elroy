import React from 'react';
import { AppBar, Toolbar, Typography, Button, Box } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { Api } from '@elroy/shared';

interface HeaderProps {
  isAuthenticated: boolean;
  setIsAuthenticated: (value: boolean) => void;
}

const Header: React.FC<HeaderProps> = ({ isAuthenticated, setIsAuthenticated }) => {
  const navigate = useNavigate();

  const handleLogout = () => {
    Api.Auth.logout();
    setIsAuthenticated(false);
    navigate('/login');
  };

  return (
    <AppBar position="static">
      <Toolbar>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          Elroy
        </Typography>
        {isAuthenticated ? (
          <Box>
            <Button color="inherit" onClick={() => navigate('/')}>Home</Button>
            <Button color="inherit" onClick={() => navigate('/chat')}>Chat</Button>
            <Button color="inherit" onClick={() => navigate('/goals')}>Goals</Button>
            <Button color="inherit" onClick={() => navigate('/memories')}>Memories</Button>
            <Button color="inherit" onClick={handleLogout}>Logout</Button>
          </Box>
        ) : (
          <Box>
            <Button color="inherit" onClick={() => navigate('/login')}>Login</Button>
            <Button color="inherit" onClick={() => navigate('/register')}>Register</Button>
          </Box>
        )}
      </Toolbar>
    </AppBar>
  );
};

export default Header;
