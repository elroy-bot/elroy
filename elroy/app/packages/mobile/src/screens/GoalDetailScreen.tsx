import React, { useState, useEffect } from 'react';
import { View, StyleSheet, ScrollView, ActivityIndicator, Alert } from 'react-native';
import { Card, Title, Paragraph, Button, TextInput, Divider, Text } from 'react-native-paper';
import { Api, Goal } from '@elroy/shared';

interface GoalDetailScreenProps {
  navigation: any;
  route: {
    params: {
      goalName: string;
    };
  };
}

const GoalDetailScreen: React.FC<GoalDetailScreenProps> = ({ navigation, route }) => {
  const { goalName } = route.params;
  const [goal, setGoal] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusUpdate, setStatusUpdate] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [closingComments, setClosingComments] = useState('');

  useEffect(() => {
    fetchGoalDetails();
  }, []);

  const fetchGoalDetails = async () => {
    try {
      setError(null);
      setLoading(true);
      const goalDetails = await Api.Goals.getGoalByName(goalName);
      setGoal(goalDetails);
    } catch (err) {
      console.error('Error fetching goal details:', err);
      setError('Failed to load goal details. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleAddStatusUpdate = async () => {
    if (!statusUpdate.trim()) return;

    setSubmitting(true);
    try {
      await Api.Goals.addStatusUpdate(goalName, {
        goal_name: goalName,
        status_update_or_note: statusUpdate,
      });
      setStatusUpdate('');
      fetchGoalDetails(); // Refresh goal details
      Alert.alert('Success', 'Status update added successfully');
    } catch (err) {
      console.error('Error adding status update:', err);
      Alert.alert('Error', 'Failed to add status update');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCompleteGoal = async () => {
    Alert.alert(
      'Complete Goal',
      'Are you sure you want to mark this goal as completed?',
      [
        {
          text: 'Cancel',
          style: 'cancel',
        },
        {
          text: 'Complete',
          onPress: async () => {
            setSubmitting(true);
            try {
              await Api.Goals.completeGoal(goalName, {
                goal_name: goalName,
                closing_comments: closingComments.trim() || undefined,
              });
              Alert.alert('Success', 'Goal marked as completed', [
                { text: 'OK', onPress: () => navigation.goBack() },
              ]);
            } catch (err) {
              console.error('Error completing goal:', err);
              Alert.alert('Error', 'Failed to complete goal');
              setSubmitting(false);
            }
          },
        },
      ]
    );
  };

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" />
        <Text style={styles.loadingText}>Loading goal details...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>{error}</Text>
        <Button mode="contained" onPress={fetchGoalDetails} style={styles.retryButton}>
          Retry
        </Button>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      <Card style={styles.card}>
        <Card.Content>
          <Title style={styles.title}>{goalName}</Title>

          {goal?.description && (
            <Paragraph style={styles.description}>{goal.description}</Paragraph>
          )}

          {goal?.strategy && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Strategy</Text>
              <Paragraph>{goal.strategy}</Paragraph>
            </View>
          )}

          {goal?.end_condition && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>End Condition</Text>
              <Paragraph>{goal.end_condition}</Paragraph>
            </View>
          )}

          {goal?.time_to_completion && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Time to Completion</Text>
              <Paragraph>{goal.time_to_completion}</Paragraph>
            </View>
          )}

          {goal?.created_at && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Created</Text>
              <Paragraph>{new Date(goal.created_at).toLocaleString()}</Paragraph>
            </View>
          )}

          {goal?.priority !== undefined && (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>Priority</Text>
              <Paragraph>{goal.priority}</Paragraph>
            </View>
          )}
        </Card.Content>
      </Card>

      {goal?.status_updates && goal.status_updates.length > 0 && (
        <Card style={styles.card}>
          <Card.Content>
            <Title>Status Updates</Title>
            {goal.status_updates.map((update: string, index: number) => (
              <View key={index} style={styles.update}>
                <Paragraph>{update}</Paragraph>
                {index < goal.status_updates.length - 1 && <Divider style={styles.divider} />}
              </View>
            ))}
          </Card.Content>
        </Card>
      )}

      {!goal?.completed_at && (
        <Card style={styles.card}>
          <Card.Content>
            <Title>Add Status Update</Title>
            <TextInput
              mode="outlined"
              value={statusUpdate}
              onChangeText={setStatusUpdate}
              placeholder="Enter a status update or note"
              multiline
              numberOfLines={3}
              style={styles.input}
            />
            <Button
              mode="contained"
              onPress={handleAddStatusUpdate}
              loading={submitting}
              disabled={submitting || !statusUpdate.trim()}
              style={styles.button}
            >
              Add Update
            </Button>
          </Card.Content>
        </Card>
      )}

      {!goal?.completed_at && (
        <Card style={styles.card}>
          <Card.Content>
            <Title>Complete Goal</Title>
            <TextInput
              mode="outlined"
              value={closingComments}
              onChangeText={setClosingComments}
              placeholder="Enter closing comments (optional)"
              multiline
              numberOfLines={3}
              style={styles.input}
            />
            <Button
              mode="contained"
              onPress={handleCompleteGoal}
              loading={submitting}
              disabled={submitting}
              style={[styles.button, styles.completeButton]}
            >
              Mark as Completed
            </Button>
          </Card.Content>
        </Card>
      )}
    </ScrollView>
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
  card: {
    margin: 16,
    elevation: 2,
  },
  title: {
    fontSize: 22,
    fontWeight: 'bold',
    marginBottom: 10,
  },
  description: {
    fontSize: 16,
    marginBottom: 16,
  },
  section: {
    marginTop: 12,
  },
  sectionTitle: {
    fontWeight: 'bold',
    fontSize: 14,
    color: '#666',
    marginBottom: 4,
  },
  update: {
    marginVertical: 8,
  },
  divider: {
    marginTop: 8,
  },
  input: {
    marginVertical: 12,
  },
  button: {
    marginTop: 8,
  },
  completeButton: {
    backgroundColor: '#4CAF50',
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
});

export default GoalDetailScreen;
