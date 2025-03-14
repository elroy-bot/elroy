# Elroy Mobile App

This is the mobile app for Elroy, built with React Native and Expo.

## Prerequisites

Before running the app, make sure you have the following installed:

- Node.js (v16 or later)
- Yarn (v1.22 or later)
- Expo CLI: `npm install -g expo-cli`
- For Android development:
  - Android Studio (for the Android emulator)
  - Android SDK
  - Java Development Kit (JDK)

## Running the App

### Option 1: Using the Convenience Scripts

We've provided several convenience scripts that start both the Elroy Web API and the Expo development server:

```bash
# For Android
./run_android.sh

# For iOS
./run_ios.sh

# For Web (browser testing)
./run_web.sh
```

### Option 2: Manual Setup

If you prefer to start the services separately:

1. Start the Elroy Web API:

```bash
cd /Users/tombedor/development/elroy
elroy web-api run
```

2. In a separate terminal, start the Expo Development Server:

```bash
cd /Users/tombedor/development/elroy/app/packages/mobile
npx expo start
```

This will start the Expo development server and display a QR code and options for running the app.

## Viewing the App

### Option 1: On a Physical Android Device

1. Install the Expo Go app from the Google Play Store on your Android device.
2. Make sure your Android device is on the same Wi-Fi network as your computer.
3. Scan the QR code displayed in the terminal with the Expo Go app.

### Option 2: Using an Android Emulator

1. Start an Android emulator from Android Studio:
   - Open Android Studio
   - Click on "Device Manager" in the right sidebar
   - Launch an existing emulator or create a new one
   - Wait for the emulator to fully boot up

2. In the terminal where Expo is running, press 'a' to open the app in the Android emulator.

### Option 3: Using Expo Web (for quick testing)

1. In the terminal where Expo is running, press 'w' to open the app in a web browser.
   Note: Some native features may not work in the web version.

## Troubleshooting

### Android Emulator Issues

- If the app doesn't connect to the emulator, try running:
  ```bash
  adb reverse tcp:8081 tcp:8081
  ```

- If you get an error about the Metro bundler, try:
  ```bash
  npx expo start --clear
  ```

### API Connection Issues

- Make sure the API URL in `src/App.tsx` is correctly set to your local API server.
- For Android emulator, use `10.0.2.2` instead of `localhost` to connect to your computer's localhost.

## Development

### Adding Dependencies

```bash
yarn add [package-name]
```

### Building for Production

```bash
npx expo build:android
```

This will start the build process for creating an APK or AAB file that can be installed on Android devices.
