# Elroy App

A cross-platform application for interacting with Elroy assistant. This monorepo contains both web and mobile applications that share code for API interactions.

## Project Structure

```
elroy/app/
├── package.json         # Root package.json for the monorepo
├── packages/
│   ├── shared/          # Shared code between web and mobile
│   │   ├── src/
│   │   │   ├── api/     # API client and services
│   │   │   └── index.ts
│   │   └── package.json
│   ├── mobile/          # React Native mobile app
│   │   ├── src/
│   │   │   ├── screens/ # Mobile app screens
│   │   │   └── App.tsx  # Main app component
│   │   └── package.json
│   └── web/             # React web app (to be implemented)
│       ├── src/
│       └── package.json
```

## Prerequisites

- Node.js (v16 or later)
- Yarn (v1.22 or later)
- For mobile development:
  - Expo CLI
  - iOS Simulator (for macOS) or Android Emulator

## Getting Started

1. Install dependencies:

```bash
cd elroy/app
yarn install
```

2. Start the Elroy Web API server:

```bash
cd /Users/tombedor/development/elroy
elroy web-api run
```

3. Run the mobile app:

```bash
cd elroy/app
yarn start:mobile
```

4. Run the web app (when implemented):

```bash
cd elroy/app
yarn start:web
```

## Features

- **Authentication**: Login and registration
- **Chat**: Conversational interface with Elroy
- **Goals**: Create and manage goals
- **Memories**: Search and create memories

## Shared Code

The `shared` package contains code that is used by both the web and mobile apps:

- API client for communicating with the Elroy Web API
- Type definitions
- Utility functions

## Mobile App

The mobile app is built with React Native and Expo, providing a native experience on both iOS and Android platforms.

### Screens

- **Login/Register**: Authentication screens
- **Home**: Main navigation hub
- **Chat**: Conversational interface
- **Goals**: Goal management
- **Memories**: Memory search and creation
- **Settings**: App configuration

## Web App

The web app will be implemented using React and Material-UI, providing a responsive web interface for desktop and mobile browsers.

## Development

### Adding Dependencies

To add a dependency to a specific package:

```bash
cd elroy/app/packages/[package-name]
yarn add [dependency-name]
```

### Building

To build all packages:

```bash
cd elroy/app
yarn build
```

To build a specific package:

```bash
cd elroy/app
yarn workspace @elroy/[package-name] build
