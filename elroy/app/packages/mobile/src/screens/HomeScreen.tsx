import React from 'react';
import { View, StyleSheet, ScrollView } from 'react-native';
import { Card, Title, Paragraph, Button, Avatar } from 'react-native-paper';

interface HomeScreenProps {
  navigation: any;
}

const HomeScreen: React.FC<HomeScreenProps> = ({ navigation }) => {
  const navigateTo = (screen: string) => {
    navigation.navigate(screen);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Avatar.Icon size={80} icon="robot" style={styles.avatar} />
        <Title style={styles.title}>Elroy Assistant</Title>
        <Paragraph style={styles.subtitle}>Your AI companion</Paragraph>
      </View>

      <Card style={styles.card} onPress={() => navigateTo('Chat')}>
        <Card.Content>
          <View style={styles.cardHeader}>
            <Avatar.Icon size={40} icon="chat" style={styles.cardIcon} />
            <Title>Chat</Title>
          </View>
          <Paragraph>Have a conversation with Elroy</Paragraph>
        </Card.Content>
        <Card.Actions>
          <Button onPress={() => navigateTo('Chat')}>Start Chat</Button>
        </Card.Actions>
      </Card>

      <Card style={styles.card} onPress={() => navigateTo('Goals')}>
        <Card.Content>
          <View style={styles.cardHeader}>
            <Avatar.Icon size={40} icon="flag" style={styles.cardIcon} />
            <Title>Goals</Title>
          </View>
          <Paragraph>Manage your goals and track progress</Paragraph>
        </Card.Content>
        <Card.Actions>
          <Button onPress={() => navigateTo('Goals')}>View Goals</Button>
        </Card.Actions>
      </Card>

      <Card style={styles.card} onPress={() => navigateTo('Memories')}>
        <Card.Content>
          <View style={styles.cardHeader}>
            <Avatar.Icon size={40} icon="brain" style={styles.cardIcon} />
            <Title>Memories</Title>
          </View>
          <Paragraph>Search and create memories</Paragraph>
        </Card.Content>
        <Card.Actions>
          <Button onPress={() => navigateTo('Memories')}>Access Memories</Button>
        </Card.Actions>
      </Card>

      <Card style={styles.card} onPress={() => navigateTo('Settings')}>
        <Card.Content>
          <View style={styles.cardHeader}>
            <Avatar.Icon size={40} icon="cog" style={styles.cardIcon} />
            <Title>Settings</Title>
          </View>
          <Paragraph>Configure app settings and account</Paragraph>
        </Card.Content>
        <Card.Actions>
          <Button onPress={() => navigateTo('Settings')}>Open Settings</Button>
        </Card.Actions>
      </Card>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  content: {
    padding: 16,
  },
  header: {
    alignItems: 'center',
    marginBottom: 24,
  },
  avatar: {
    backgroundColor: '#6200ee',
    marginBottom: 8,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
  },
  subtitle: {
    fontSize: 16,
    color: '#666',
  },
  card: {
    marginBottom: 16,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  cardIcon: {
    marginRight: 16,
    backgroundColor: '#6200ee',
  },
});

export default HomeScreen;
