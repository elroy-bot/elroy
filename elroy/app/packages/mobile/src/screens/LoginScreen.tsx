import React, { useState } from 'react';
import { View, StyleSheet, Alert } from 'react-native';
import { TextInput, Button, Title, Text } from 'react-native-paper';
import { Api } from '@elroy/shared';

interface LoginScreenProps {
  navigation: any;
  route: {
    params: {
      setIsAuthenticated: (value: boolean) => void;
    };
  };
}

const LoginScreen: React.FC<LoginScreenProps> = ({ navigation, route }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const { setIsAuthenticated } = route.params;

  const handleLogin = async () => {
    if (!username || !password) {
      Alert.alert('Error', 'Please enter both username and password');
      return;
    }

    setLoading(true);
    try {
      await Api.Auth.login({ username, password });
      setIsAuthenticated(true);
    } catch (error) {
      Alert.alert('Login Failed', error instanceof Error ? error.message : 'An unknown error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <Title style={styles.title}>Elroy Assistant</Title>
      <Text style={styles.subtitle}>Login to your account</Text>

      <TextInput
        label="Username"
        value={username}
        onChangeText={setUsername}
        style={styles.input}
        autoCapitalize="none"
      />

      <TextInput
        label="Password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        style={styles.input}
      />

      <Button
        mode="contained"
        onPress={handleLogin}
        loading={loading}
        disabled={loading}
        style={styles.button}
      >
        Login
      </Button>

      <Button
        mode="text"
        onPress={() => navigation.navigate('Register')}
        style={styles.registerButton}
      >
        Don't have an account? Register
      </Button>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    justifyContent: 'center',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 10,
  },
  subtitle: {
    fontSize: 16,
    textAlign: 'center',
    marginBottom: 30,
    color: '#666',
  },
  input: {
    marginBottom: 15,
  },
  button: {
    marginTop: 10,
    paddingVertical: 6,
  },
  registerButton: {
    marginTop: 20,
  },
});

export default LoginScreen;
