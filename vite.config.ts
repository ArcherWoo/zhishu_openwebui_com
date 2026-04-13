import { sveltekit } from '@sveltejs/kit/vite';
import { createLogger, defineConfig } from 'vite';

import { viteStaticCopy } from 'vite-plugin-static-copy';

const viteLogger = createLogger();
const originalWarn = viteLogger.warn;

viteLogger.warn = (msg, options) => {
	if (
		typeof msg === 'string' &&
		(msg.includes('@sveltejs/svelte-virtual-list') ||
			msg.includes(
				'"isInputDOMNode" is imported from external module "@xyflow/system" but never used in "node_modules/@xyflow/svelte/dist/lib/components/KeyHandler/KeyHandler.svelte".'
			) ||
			(msg.includes('externalized for browser compatibility') &&
				msg.includes('node_modules/pyodide/pyodide.mjs')))
	) {
		return;
	}

	originalWarn(msg, options);
};

export default defineConfig({
	customLogger: viteLogger,
	plugins: [
		sveltekit(),
		viteStaticCopy({
			targets: [
				{
					src: 'node_modules/onnxruntime-web/dist/*.jsep.*',

					dest: 'wasm'
				}
			]
		})
	],
	define: {
		APP_VERSION: JSON.stringify(process.env.npm_package_version),
		APP_BUILD_HASH: JSON.stringify(process.env.APP_BUILD_HASH || 'dev-build')
	},
	build: {
		sourcemap: true,
		chunkSizeWarningLimit: 2500,
		rollupOptions: {
			onwarn(warning, defaultHandler) {
				const message = typeof warning === 'string' ? warning : warning.message ?? '';
				if (
					message.includes(
						'never used in "node_modules/@xyflow/svelte/dist/lib/components/KeyHandler/KeyHandler.svelte"'
					)
				) {
					return;
				}

				defaultHandler(warning);
			}
		}
	},
	server: {
		port: 5173
	},
	worker: {
		format: 'es'
	},
	esbuild: {
		pure: process.env.ENV === 'dev' ? [] : ['console.log', 'console.debug', 'console.error']
	}
});
