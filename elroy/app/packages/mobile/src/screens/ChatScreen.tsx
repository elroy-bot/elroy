import React, { useState, useEffect, useRef } from 'react';
import { View, StyleSheet, FlatList, KeyboardAvoidingView, Platform } from 'react-native';
import { TextInput, Button, Card, Text, ActivityIndicator } from 'react-native-paper';
import { Api, MessageRequest } from '@elroy/shared';

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  timestamp: Date;
}

const ChatScreen: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const flatListRef = useRef<FlatList>(null);

  useEffect(() => {
    // Scroll to bottom when messages change
    if (flatListRef.current && messages.length > 0) {
      flatListRef.current.scrollToEnd({ animated: true });
    }
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputText.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: inputText,
      isUser: true,
      timestamp: new Date(),
    };

    setMessages((prevMessages) => [...prevMessages, userMessage]);
    setInputText('');
    setIsLoading(true);

    try {
      const request: MessageRequest = {
        input: inputText,
        enable_tools: true,
      };

      const response = await Api.Messages.sendMessage(request);

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: response.response,
        isUser: false,
        timestamp: new Date(response.timestamp),
      };

      setMessages((prevMessages) => [...prevMessages, assistantMessage]);
    } catch (error) {
      console.error('Error sending message:', error);

      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: 'Sorry, there was an error processing your message. Please try again.',
        isUser: false,
        timestamp: new Date(),
      };

      setMessages((prevMessages) => [...prevMessages, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const renderMessage = ({ item }: { item: Message }) => (
    <Card style={[styles.messageCard, item.isUser ? styles.userMessage : styles.assistantMessage]}>
      <Card.Content>
        <Text>{item.text}</Text>
      </Card.Content>
    </Card>
  );

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={80}
    >
      <FlatList
        ref={flatListRef}
        data={messages}
        renderItem={renderMessage}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.messagesContainer}
      />

      {isLoading && (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="small" />
          <Text style={styles.loadingText}>Elroy is thinking...</Text>
        </View>
      )}

      <View style={styles.inputContainer}>
        <TextInput
          mode="outlined"
          value={inputText}
          onChangeText={setInputText}
          placeholder="Type a message..."
          style={styles.input}
          multiline
        />
        <Button
          mode="contained"
          onPress={handleSendMessage}
          disabled={isLoading || !inputText.trim()}
          style={styles.sendButton}
        >
          Send
        </Button>
      </View>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  messagesContainer: {
    padding: 10,
    paddingBottom: 20,
  },
  messageCard: {
    marginVertical: 5,
    maxWidth: '80%',
  },
  userMessage: {
    alignSelf: 'flex-end',
    backgroundColor: '#E3F2FD',
  },
  assistantMessage: {
    alignSelf: 'flex-start',
    backgroundColor: '#F5F5F5',
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 10,
  },
  loadingText: {
    marginLeft: 10,
    fontStyle: 'italic',
  },
  inputContainer: {
    flexDirection: 'row',
    padding: 10,
    borderTopWidth: 1,
    borderTopColor: '#EEEEEE',
    backgroundColor: '#FFFFFF',
  },
  input: {
    flex: 1,
    maxHeight: 100,
  },
  sendButton: {
    marginLeft: 10,
    alignSelf: 'flex-end',
  },
});

export default ChatScreen;
