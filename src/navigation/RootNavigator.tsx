import { createNativeStackNavigator } from '@react-navigation/native-stack';
import React from 'react';

import { colors } from '../theme';
import { AnalyzingScreen } from '../screens/AnalyzingScreen';
import { RecommendationsScreen } from '../screens/RecommendationsScreen';
import { ReferencePhotoScreen } from '../screens/ReferencePhotoScreen';
import { ResultsScreen } from '../screens/ResultsScreen';
import { ScanScreen } from '../screens/ScanScreen';
import { SkinToneSetupScreen } from '../screens/SkinToneSetupScreen';
import { WelcomeScreen } from '../screens/WelcomeScreen';
import { ZoneDetailScreen } from '../screens/ZoneDetailScreen';
import { RootStackParamList } from './types';

const Stack = createNativeStackNavigator<RootStackParamList>();

export function RootNavigator() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.background },
        headerTintColor: colors.text,
        headerTitleStyle: { fontWeight: '700' },
        headerShadowVisible: false,
        contentStyle: { backgroundColor: colors.background },
      }}
    >
      <Stack.Screen
        name="Welcome"
        component={WelcomeScreen}
        options={{ headerShown: false }}
      />
      <Stack.Screen
        name="SkinToneSetup"
        component={SkinToneSetupScreen}
        options={{ title: 'Your Skin Profile' }}
      />
      <Stack.Screen
        name="ReferencePhoto"
        component={ReferencePhotoScreen}
        options={{ title: 'Reference Photo' }}
      />
      <Stack.Screen name="Scan" component={ScanScreen} options={{ title: 'Face Scan' }} />
      <Stack.Screen
        name="Analyzing"
        component={AnalyzingScreen}
        options={{ headerShown: false, gestureEnabled: false }}
      />
      <Stack.Screen
        name="Results"
        component={ResultsScreen}
        options={{ title: 'Analysis', headerBackVisible: false }}
      />
      <Stack.Screen
        name="ZoneDetail"
        component={ZoneDetailScreen}
        options={{ title: 'Zone Detail' }}
      />
      <Stack.Screen
        name="Recommendations"
        component={RecommendationsScreen}
        options={{ title: 'Your Routine' }}
      />
    </Stack.Navigator>
  );
}
