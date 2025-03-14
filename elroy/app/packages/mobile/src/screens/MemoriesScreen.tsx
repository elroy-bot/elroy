import React, { useState } from 'react';
import { View, StyleSheet, ScrollView, KeyboardAvoidingView, Platform } from 'react-native';
import { TextInput, Button, Card, Title, Paragraph, Divider, Text, ActivityIndicator } from 'react-native-paper';
import { Api, MemoryQuery } from '@elroy/shared';

const MemoriesScreen: React.FC = () => {
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newMemoryName, setNewMemoryName] = useState('');
  const [newMemoryText, setNewMemoryText] = useState('');
  const [creatingMemory, setCreatingMemory] = useState(false);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);

  const handleSearch = async () => {
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setSearchResults(null);

    try {
      const memoryQuery: MemoryQuery = { query };
      const results = await Api.Memories.queryMemory(memoryQuery);
      setSearchResults(results);
    } catch (err) {
      console.error('Error searching memories:', err);
      setError('Failed to search memories. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateMemory = async () => {
    if (!newMemoryName.trim() || !newMemoryText.trim()) {
      setCreateError('Please provide both a name and text for the memory.');
      return;
    }

    setCreatingMemory(true);
    setCreateError(null);
    setCreateSuccess(null);

    try {
      const result = await Api.Memories.createMemory({
        name: newMemoryName,
        text: newMemoryText,
      });

      setCreateSuccess('Memory created successfully!');
      setNewMemoryName('');
      setNewMemoryText('');
    } catch (err) {
      console.error('Error creating memory:', err);
      setCreateError('Failed to create memory. Please try again.');
    } finally {
      setCreatingMemory(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={80}
    >
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <Card style={styles.card}>
          <Card.Content>
            <Title>Search Memories</Title>
            <TextInput
              label="Search Query"
              value={query}
              onChangeText={setQuery}
              style={styles.input}
            />
            <Button
              mode="contained"
              onPress={handleSearch}
              loading={loading}
              disabled={loading || !query.trim()}
              style={styles.button}
            >
              Search
            </Button>

            {loading && (
              <View style={styles.loadingContainer}>
                <ActivityIndicator size="small" />
                <Text style={styles.loadingText}>Searching...</Text>
              </View>
            )}

            {error && <Text style={styles.errorText}>{error}</Text>}

            {searchResults && (
              <View style={styles.resultsContainer}>
                <Divider style={styles.divider} />
                <Title>Results</Title>
                <Paragraph>{searchResults}</Paragraph>
              </View>
            )}
          </Card.Content>
        </Card>

        <Card style={styles.card}>
          <Card.Content>
            <Title>Create New Memory</Title>
            <TextInput
              label="Memory Name"
              value={newMemoryName}
              onChangeText={setNewMemoryName}
              style={styles.input}
              placeholder="Give your memory a descriptive name"
            />
            <TextInput
              label="Memory Text"
              value={newMemoryText}
              onChangeText={setNewMemoryText}
              style={styles.textArea}
              multiline
              numberOfLines={4}
              placeholder="What would you like to remember?"
            />
            <Button
              mode="contained"
              onPress={handleCreateMemory}
              loading={creatingMemory}
              disabled={creatingMemory || !newMemoryName.trim() || !newMemoryText.trim()}
              style={styles.button}
            >
              Create Memory
            </Button>

            {createSuccess && <Text style={styles.successText}>{createSuccess}</Text>}
            {createError && <Text style={styles.errorText}>{createError}</Text>}
          </Card.Content>
        </Card>
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  scrollContent: {
    padding: 16,
  },
  card: {
    marginBottom: 16,
    elevation: 2,
  },
  input: {
    marginBottom: 16,
  },
  textArea: {
    marginBottom: 16,
    height: 100,
  },
  button: {
    marginBottom: 16,
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 16,
  },
  loadingText: {
    marginLeft: 10,
    fontStyle: 'italic',
  },
  errorText: {
    color: 'red',
    marginTop: 8,
  },
  successText: {
    color: 'green',
    marginTop: 8,
  },
  divider: {
    marginVertical: 16,
  },
  resultsContainer: {
    marginTop: 8,
  },
});

export default MemoriesScreen;
