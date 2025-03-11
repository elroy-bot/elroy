import React from 'react';
import { View, StyleSheet, Alert } from 'react-native';
import { List, Switch, Button, Divider, Text } from 'react-native-paper';
import { Api } from '@elroy/shared';

interface SettingsScreenProps {
  navigation: any;
  route: {
    params: {
      setIsAuthenticated: (value: boolean) => void;
    };
  };
}

const SettingsScreen: React.FC<SettingsScreenProps> = ({ navigation, route }) => {
  const [darkMode, setDarkMode] = React.useState(false);
  const [notifications, setNotifications] = React.useState(true);
  const { setIsAuthenticated } = route.params;

  const handleLogout = () => {
    Alert.alert(
      'Confirm Logout',
      'Are you sure you want to log out?',
      [
        {
          text: 'Cancel',
          style: 'cancel',
        },
        {
          text: 'Logout',
          onPress: () => {
            Api.Auth.logout();
            setIsAuthenticated(false);
          },
          style: 'destructive',
        },
      ]
    );
  };

  const handleClearContext = () => {
    Alert.alert(
      'Clear Conversation Context',
      'This will clear the current conversation context. Are you sure?',
      [
        {
          text: 'Cancel',
          style: 'cancel',
        },
        {
          text: 'Clear',
          onPress: async () => {
            try {
              await Api.Messages.refreshContext();
              Alert.alert('Success', 'Conversation context has been cleared.');
            } catch (error) {
              Alert.alert('Error', 'Failed to clear conversation context.');
            }
          },
        },
      ]
    );
  };

  return (
    <View style={styles.container}>
      <List.Section>
        <List.Subheader>Appearance</List.Subheader>
        <List.Item
          title="Dark Mode"
          right={() => (
            <Switch value={darkMode} onValueChange={setDarkMode} />
          )}
        />
        <Divider />

        <List.Subheader>Notifications</List.Subheader>
        <List.Item
          title="Enable Notifications"
          right={() => (
            <Switch value={notifications} onValueChange={setNotifications} />
          )}
        />
        <Divider />

        <List.Subheader>Data</List.Subheader>
        <List.Item
          title="Clear Conversation Context"
          description="Reset the current conversation with Elroy"
          onPress={handleClearContext}
        />
        <Divider />

        <List.Subheader>API Connection</List.Subheader>
        <List.Item
          title="API URL"
          description={Api.getApiClient().getBaseUrl()}
        />
        <Divider />

        <List.Subheader>Account</List.Subheader>
        <Button
          mode="contained"
          onPress={handleLogout}
          style={styles.logoutButton}
          buttonColor="#f44336"
        >
          Logout
        </Button>
      </List.Section>

      <View style={styles.footer}>
        <Text style={styles.version}>Elroy Mobile v1.0.0</Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  logoutButton: {
    marginHorizontal: 16,
    marginTop: 8,
  },
  footer: {
    padding: 16,
    alignItems: 'center',
    marginTop: 'auto',
  },
  version: {
    color: '#666',
    fontSize: 12,
  },
});

export default SettingsScreen;
