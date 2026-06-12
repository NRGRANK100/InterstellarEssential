import React from 'react';
import { StyleSheet, View } from 'react-native';
import Svg, { Ellipse, G, Path, Text as SvgText } from 'react-native-svg';

import { colors, severityColor } from '../theme';
import { FacialZoneId, ZoneResult } from '../types';

interface Props {
  zones: ZoneResult[];
  onSelectZone?: (id: FacialZoneId) => void;
  size?: number;
}

function topSeverity(zone: ZoneResult | undefined) {
  if (!zone) return 'minimal';
  return [...zone.concerns].sort((a, b) => b.score - a.score)[0]?.severity ?? 'minimal';
}

/**
 * Stylized front-facing face map. Each zone is a tappable region tinted by the
 * severity of its leading concern, giving an at-a-glance heat map of the face.
 */
export function FaceZoneMap({ zones, onSelectZone, size = 280 }: Props) {
  const byId = (id: FacialZoneId) => zones.find((z) => z.id === id);
  const fill = (id: FacialZoneId) => {
    const sev = topSeverity(byId(id));
    return `${severityColor[sev]}99`;
  };

  return (
    <View style={[styles.wrap, { width: size, height: size * 1.2 }]}>
      <Svg viewBox="0 0 200 240" width={size} height={size * 1.2}>
        {/* Face outline */}
        <Path
          d="M100 8 C150 8 168 50 168 100 C168 165 138 224 100 224 C62 224 32 165 32 100 C32 50 50 8 100 8 Z"
          fill={colors.surface}
          stroke={colors.border}
          strokeWidth={2}
        />

        {/* Forehead */}
        <Path
          d="M55 40 C70 24 130 24 145 40 C140 64 60 64 55 40 Z"
          fill={fill('forehead')}
          onPress={() => onSelectZone?.('forehead')}
        />
        {/* Under eyes */}
        <G onPress={() => onSelectZone?.('under_eyes')}>
          <Ellipse cx={73} cy={92} rx={18} ry={9} fill={fill('under_eyes')} />
          <Ellipse cx={127} cy={92} rx={18} ry={9} fill={fill('under_eyes')} />
        </G>
        {/* Cheeks */}
        <Path
          d="M48 100 C52 140 70 150 86 138 C84 118 74 104 60 102 Z"
          fill={fill('left_cheek')}
          onPress={() => onSelectZone?.('left_cheek')}
        />
        <Path
          d="M152 100 C148 140 130 150 114 138 C116 118 126 104 140 102 Z"
          fill={fill('right_cheek')}
          onPress={() => onSelectZone?.('right_cheek')}
        />
        {/* Nose */}
        <Path
          d="M92 96 C92 120 88 134 100 140 C112 134 108 120 108 96 Z"
          fill={fill('nose')}
          onPress={() => onSelectZone?.('nose')}
        />
        {/* Chin */}
        <Ellipse
          cx={100}
          cy={186}
          rx={26}
          ry={16}
          fill={fill('chin')}
          onPress={() => onSelectZone?.('chin')}
        />
        {/* Jawline */}
        <Path
          d="M52 150 C60 196 80 214 100 216 C120 214 140 196 148 150 C140 178 120 196 100 196 C80 196 60 178 52 150 Z"
          fill={fill('jawline')}
          onPress={() => onSelectZone?.('jawline')}
        />

        <SvgText x={100} y={232} fill={colors.textFaint} fontSize={9} textAnchor="middle">
          tap a zone for detail
        </SvgText>
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignSelf: 'center' },
});
