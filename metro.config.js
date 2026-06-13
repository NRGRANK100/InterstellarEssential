// Metro configuration for Expo + TensorFlow.js (tfjs-react-native).
// Adds the `bin` asset extension so model weight shards can be bundled if you
// later switch BlazeFace to offline `bundleResourceIO` loading.
const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

if (!config.resolver.assetExts.includes('bin')) {
  config.resolver.assetExts.push('bin');
}

module.exports = config;
