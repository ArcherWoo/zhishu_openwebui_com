import { describe, expect, it } from 'vitest';

import { buildCacheMetadata, validateCacheState } from './pyodide-cache.js';

describe('pyodide cache validation', () => {
	it('treats a complete cache as reusable', () => {
		const metadata = buildCacheMetadata({
			pyodideVersion: '0.28.3',
			packages: ['micropip', 'numpy'],
			pypiPackages: ['black'],
			pypiWheelFiles: ['black-25.0.0-py3-none-any.whl']
		});

		const result = validateCacheState({
			expectedMetadata: metadata,
			actualMetadata: metadata,
			existingFiles: ['package.json', 'pyodide.js', 'black-25.0.0-py3-none-any.whl'],
			requiredFiles: ['package.json', 'pyodide.js']
		});

		expect(result.reusable).toBe(true);
		expect(result.reasons).toEqual([]);
	});

	it('invalidates the cache when the installed Pyodide version changed', () => {
		const expectedMetadata = buildCacheMetadata({
			pyodideVersion: '0.28.3',
			packages: ['micropip'],
			pypiPackages: []
		});
		const actualMetadata = buildCacheMetadata({
			pyodideVersion: '0.28.2',
			packages: ['micropip'],
			pypiPackages: []
		});

		const result = validateCacheState({
			expectedMetadata,
			actualMetadata,
			existingFiles: ['package.json'],
			requiredFiles: ['package.json']
		});

		expect(result.reusable).toBe(false);
		expect(result.reasons).toContain('Pyodide version mismatch: cached=0.28.2 current=0.28.3');
	});

	it('invalidates the cache when a recorded wheel file is missing', () => {
		const metadata = buildCacheMetadata({
			pyodideVersion: '0.28.3',
			packages: ['micropip'],
			pypiPackages: ['black'],
			pypiWheelFiles: ['black-25.0.0-py3-none-any.whl']
		});

		const result = validateCacheState({
			expectedMetadata: metadata,
			actualMetadata: metadata,
			existingFiles: ['package.json'],
			requiredFiles: ['package.json']
		});

		expect(result.reusable).toBe(false);
		expect(result.reasons).toContain(
			'Missing cached PyPI wheels: black-25.0.0-py3-none-any.whl'
		);
	});

	it('invalidates the cache when the requested package list changes', () => {
		const expectedMetadata = buildCacheMetadata({
			pyodideVersion: '0.28.3',
			packages: ['micropip', 'numpy'],
			pypiPackages: ['black']
		});
		const actualMetadata = buildCacheMetadata({
			pyodideVersion: '0.28.3',
			packages: ['micropip'],
			pypiPackages: ['black']
		});

		const result = validateCacheState({
			expectedMetadata,
			actualMetadata,
			existingFiles: ['package.json'],
			requiredFiles: ['package.json']
		});

		expect(result.reusable).toBe(false);
		expect(result.reasons).toContain('Requested Pyodide package list changed.');
	});
});
