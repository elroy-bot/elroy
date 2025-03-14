import React from 'react';
import { Container, Typography, Grid, Paper, Button, Box } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import ChatIcon from '@mui/icons-material/Chat';
import FlagIcon from '@mui/icons-material/Flag';
import MemoryIcon from '@mui/icons-material/Memory';
import SettingsIcon from '@mui/icons-material/Settings';

const HomeScreen: React.FC = () => {
  const navigate = useNavigate();

  const features = [
    {
      title: 'Chat',
      description: 'Have a conversation with Elroy',
      icon: <ChatIcon fontSize="large" />,
      path: '/chat',
      color: '#2196f3'
    },
    {
      title: 'Goals',
      description: 'Create and manage your goals',
      icon: <FlagIcon fontSize="large" />,
      path: '/goals',
      color: '#4caf50'
    },
    {
      title: 'Memories',
      description: 'Search and create memories',
      icon: <MemoryIcon fontSize="large" />,
      path: '/memories',
      color: '#ff9800'
    },
    {
      title: 'Settings',
      description: 'Configure your preferences',
      icon: <SettingsIcon fontSize="large" />,
      path: '/settings',
      color: '#9c27b0'
    }
  ];

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <Typography variant="h3" component="h1" gutterBottom align="center">
        Welcome to Elroy
      </Typography>

      <Typography variant="h6" paragraph align="center" color="textSecondary">
        Your personal AI assistant
      </Typography>

      <Grid container spacing={4} sx={{ mt: 4 }}>
        {features.map((feature) => (
          <Grid item xs={12} sm={6} md={3} key={feature.title}>
            <Paper
              elevation={3}
              sx={{
                p: 3,
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                transition: 'transform 0.2s',
                '&:hover': {
                  transform: 'translateY(-5px)',
                  boxShadow: 6
                }
              }}
            >
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'center',
                  mb: 2,
                  color: feature.color
                }}
              >
                {feature.icon}
              </Box>
              <Typography variant="h5" component="h2" gutterBottom align="center">
                {feature.title}
              </Typography>
              <Typography paragraph align="center">
                {feature.description}
              </Typography>
              <Box sx={{ flexGrow: 1 }} />
              <Button
                variant="contained"
                fullWidth
                onClick={() => navigate(feature.path)}
                sx={{
                  mt: 2,
                  bgcolor: feature.color,
                  '&:hover': {
                    bgcolor: feature.color,
                    filter: 'brightness(0.9)'
                  }
                }}
              >
                Go to {feature.title}
              </Button>
            </Paper>
          </Grid>
        ))}
      </Grid>
    </Container>
  );
};

export default HomeScreen;
