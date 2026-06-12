import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { radius, severityColor } from '../theme';
import { ConcernResult } from '../types';

export function SeverityPill({ severity }: { severity: ConcernResult['severity'] }) {
  const color = severityColor[severity];
  return (
    <View style={[styles.pill, { backgroundColor: `${color}22`, borderColor: color }]}>
      <Text style={[styles.text, { color }]}>{severity}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: radius.pill,
    borderWidth: 1,
    alignSelf: 'flex-start',
  },
  text: { fontSize: 11, fontWeight: '700', textTransform: 'capitalize' },
});
