/**
 * Post-build script to clean up generated files
 * Docusaurus generates both /path and /path/index.html
 * This script removes unnecessary .html.html files created by the redirect plugin
 */

const fs = require('fs-extra');
const path = require('path');
const glob = require('glob');

const buildDir = path.join(__dirname, '../build');

async function cleanupHtmlFiles() {
  // Find and remove .html.html files created by redirects
  const doubleHtmlFiles = glob.sync('**/*.html.html', {
    cwd: buildDir,
  });

  console.log(`Found ${doubleHtmlFiles.length} duplicate files to remove`);

  for (const file of doubleHtmlFiles) {
    const filePath = path.join(buildDir, file);
    await fs.remove(filePath);
    console.log(`Removed: ${file}`);
  }

  console.log('✓ Cleanup complete');
}

cleanupHtmlFiles().catch(console.error);
