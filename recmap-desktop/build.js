const esbuild = require('esbuild');
const fs = require('fs');
const path = require('path');

async function build() {
  const isWatch = process.argv.includes('--watch');

  // Ensure dist directories exist
  fs.mkdirSync(path.join(__dirname, 'dist', 'renderer'), { recursive: true });

  // Copy static renderer files
  fs.copyFileSync(
    path.join(__dirname, 'src', 'renderer', 'index.html'),
    path.join(__dirname, 'dist', 'renderer', 'index.html')
  );
  if (fs.existsSync(path.join(__dirname, 'src', 'renderer', 'styles.css'))) {
    fs.copyFileSync(
      path.join(__dirname, 'src', 'renderer', 'styles.css'),
      path.join(__dirname, 'dist', 'renderer', 'styles.css')
    );
  }

  // 1. Build Main Process
  const mainCtx = await esbuild.context({
    entryPoints: [path.join(__dirname, 'src', 'main.ts')],
    bundle: true,
    platform: 'node',
    target: 'node20',
    outfile: path.join(__dirname, 'dist', 'main.js'),
    external: ['electron', 'electron-store'],
    sourcemap: true,
  });

  // 2. Build Preload Script
  const preloadCtx = await esbuild.context({
    entryPoints: [path.join(__dirname, 'src', 'preload.ts')],
    bundle: true,
    platform: 'node',
    target: 'node20',
    outfile: path.join(__dirname, 'dist', 'preload.js'),
    external: ['electron'],
    sourcemap: true,
  });

  // 3. Build Renderer Script
  const rendererCtx = await esbuild.context({
    entryPoints: [path.join(__dirname, 'src', 'renderer', 'recorder.ts')],
    bundle: true,
    platform: 'browser',
    target: 'es2020',
    outfile: path.join(__dirname, 'dist', 'renderer', 'recorder.js'),
    sourcemap: true,
  });

  if (isWatch) {
    await Promise.all([mainCtx.watch(), preloadCtx.watch(), rendererCtx.watch()]);
    console.log('⚡ Watching for changes...');
  } else {
    await Promise.all([mainCtx.rebuild(), preloadCtx.rebuild(), rendererCtx.rebuild()]);
    await Promise.all([mainCtx.dispose(), preloadCtx.dispose(), rendererCtx.dispose()]);
    console.log('✅ Build completed successfully.');
  }
}

build().catch((err) => {
  console.error('❌ Build failed:', err);
  process.exit(1);
});
