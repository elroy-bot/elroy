const createExpoWebpackConfigAsync = require('@expo/webpack-config');

module.exports = async function (env, argv) {
  const config = await createExpoWebpackConfigAsync(
    {
      ...env,
      // Customize the webpack config here
      babel: {
        dangerouslyAddModulePathsToTranspile: [
          // Add any modules that need to be transpiled
          '@elroy/shared',
        ],
      },
    },
    argv
  );

  // Ensure the entry point is correctly set
  config.entry = [require.resolve('./index.js')];

  return config;
};
