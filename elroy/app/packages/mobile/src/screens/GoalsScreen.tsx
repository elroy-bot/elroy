import React, { useState, useEffect } from 'react';
import { View, StyleSheet, FlatList, RefreshControl } from 'react-native';
import { Card, Title, Paragraph, Button, FAB, ActivityIndicator, Text } from 'react-native-paper';
import { Api } from '@elroy/shared';

interface GoalsScreenProps {
  navigation: any;
}

const GoalsScreen: React.FC<GoalsScreenProps> = ({ navigation }) => {
  const [goals, setGoals] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchGoals = async () => {
    try {
      setError(null);
      const activeGoals = await Api.Goals.getActiveGoals();
      setGoals(activeGoals);
    } catch (err) {
      console.error('Error fetching goals:', err);
      setError('Failed to load goals. Please try again.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchGoals();
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchGoals();
  };

  const handleCreateGoal = () => {
    // Navigate to a create goal screen (not implemented yet)
    // navigation.navigate('CreateGoal');
    alert('Create goal functionality will be implemented in a future update');
  };

  const handleGoalPress = (goalName: string) => {
    navigation.navigate('GoalDetail', { goalName });
  };

  const renderGoalItem = ({ item }: { item: string }) => (
    <Card style={styles.card} onPress={() => handleGoalPress(item)}>
      <Card.Content>
        <Title>{item}</Title>
        <Paragraph>Tap to view details</Paragraph>
      </Card.Content>
    </Card>
  );

  if (loading && !refreshing) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" />
        <Text style={styles.loadingText}>Loading goals...</Text>
      </View>
    );
  }

  if (error && goals.length === 0) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>{error}</Text>
        <Button mode="contained" onPress={fetchGoals} style={styles.retryButton}>
          Retry
        </Button>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {goals.length === 0 ? (
        <View style={styles.centerContainer}>
          <Text style={styles.emptyText}>No active goals found</Text>
          <Button mode="contained" onPress={handleCreateGoal} style={styles.createButton}>
            Create Your First Goal
          </Button>
        </View>
      ) : (
        <FlatList
          data={goals}
          renderItem={renderGoalItem}
          keyExtractor={(item) => item}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />
          }
        />
      )}

      <FAB
        style={styles.fab}
        icon="plus"
        onPress={handleCreateGoal}
        label="New Goal"
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  listContent: {
    padding: 16,
  },
  card: {
    marginBottom: 16,
    elevation: 2,
  },
  fab: {
    position: 'absolute',
    margin: 16,
    right: 0,
    bottom: 0,
  },
  loadingText: {
    marginTop: 10,
    fontSize: 16,
  },
  errorText: {
    color: 'red',
    fontSize: 16,
    textAlign: 'center',
    marginBottom: 20,
  },
  retryButton: {
    marginTop: 10,
  },
  emptyText: {
    fontSize: 16,
    color: '#666',
    marginBottom: 20,
    textAlign: 'center',
  },
  createButton: {
    marginTop: 10,
  },
});

export default GoalsScreen;
