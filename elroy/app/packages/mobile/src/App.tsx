import React, { useState, useEffect } from 'react';
import { Platform } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Provider as PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';

import { createApiClient, Api } from '@elroy/shared';

// Import screens
import LoginScreen from './screens/LoginScreen';
import RegisterScreen from './screens/RegisterScreen';
import HomeScreen from './screens/HomeScreen';
import ChatScreen from './screens/ChatScreen';
import GoalsScreen from './screens/GoalsScreen';
import GoalDetailScreen from './screens/GoalDetailScreen';
import MemoriesScreen from './screens/MemoriesScreen';
import SettingsScreen from './screens/SettingsScreen';

// Define the navigation stack
const Stack = createNativeStackNavigator();

// Initialize API client
// For Android emulator, use 10.0.2.2 instead of localhost to connect to the host machine
const apiUrl = Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000';
createApiClient({
  baseURL: apiUrl,
});

export default function App() {
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
    // You could show a splash screen here
    return null;
  }

  return (
    <SafeAreaProvider>
      <PaperProvider>
        <NavigationContainer>
          <StatusBar style="auto" />
          <Stack.Navigator>
            {!isAuthenticated ? (
              // Auth screens
              <>
                <Stack.Screen
                  name="Login"
                  component={LoginScreen}
                  initialParams={{ setIsAuthenticated }}
                />
                <Stack.Screen
                  name="Register"
                  component={RegisterScreen}
                />
              </>
            ) : (
              // App screens
              <>
                <Stack.Screen name="Home" component={HomeScreen} />
                <Stack.Screen name="Chat" component={ChatScreen} />
                <Stack.Screen name="Goals" component={GoalsScreen} />
                <Stack.Screen name="GoalDetail" component={GoalDetailScreen} />
                <Stack.Screen name="Memories" component={MemoriesScreen} />
                <Stack.Screen name="Settings" component={SettingsScreen} initialParams={{ setIsAuthenticated }} />
              </>
            )}
          </Stack.Navigator>
        </NavigationContainer>
      </PaperProvider>
    </SafeAreaProvider>
  );
}
