export const PYODIDE_CACHE_SCHEMA_VERSION = 1;
export const PYODIDE_CACHE_METADATA_FILE = 'open-webui-pyodide-cache.json';

function normalizeList(values = []) {
	return [...new Set(values.filter(Boolean))].sort();
}

function listsMatch(left = [], right = []) {
	const normalizedLeft = normalizeList(left);
	const normalizedRight = normalizeList(right);

	return (
		normalizedLeft.length === normalizedRight.length &&
		normalizedLeft.every((value, index) => value === normalizedRight[index])
	);
}

export function buildCacheMetadata({
	pyodideVersion,
	packages,
	pypiPackages,
	pypiWheelFiles = []
}) {
	return {
		schemaVersion: PYODIDE_CACHE_SCHEMA_VERSION,
		pyodideVersion,
		packages: normalizeList(packages),
		pypiPackages: normalizeList(pypiPackages),
		pypiWheelFiles: normalizeList(pypiWheelFiles)
	};
}

export function validateCacheState({
	expectedMetadata,
	actualMetadata,
	existingFiles = [],
	requiredFiles = []
}) {
	const reasons = [];
	const existingFileSet = new Set(existingFiles);
	const missingRequiredFiles = normalizeList(requiredFiles).filter(
		(fileName) => !existingFileSet.has(fileName)
	);

	if (!actualMetadata) {
		reasons.push('Missing cache metadata file.');
	} else {
		if (
			(actualMetadata.schemaVersion ?? null) !==
			(expectedMetadata.schemaVersion ?? PYODIDE_CACHE_SCHEMA_VERSION)
		) {
			reasons.push('Cache metadata schema mismatch.');
		}

		if (actualMetadata.pyodideVersion !== expectedMetadata.pyodideVersion) {
			reasons.push(
				`Pyodide version mismatch: cached=${actualMetadata.pyodideVersion ?? 'unknown'} current=${expectedMetadata.pyodideVersion}`
			);
		}

		if (!listsMatch(actualMetadata.packages, expectedMetadata.packages)) {
			reasons.push('Requested Pyodide package list changed.');
		}

		if (!listsMatch(actualMetadata.pypiPackages, expectedMetadata.pypiPackages)) {
			reasons.push('Requested PyPI wheel package list changed.');
		}
	}

	const requiredWheelFiles = normalizeList(actualMetadata?.pypiWheelFiles ?? []);
	const missingWheelFiles = requiredWheelFiles.filter((fileName) => !existingFileSet.has(fileName));

	if (missingRequiredFiles.length > 0) {
		reasons.push(`Missing core Pyodide files: ${missingRequiredFiles.join(', ')}`);
	}

	if (missingWheelFiles.length > 0) {
		reasons.push(`Missing cached PyPI wheels: ${missingWheelFiles.join(', ')}`);
	}

	return {
		reusable: reasons.length === 0,
		reasons,
		missingRequiredFiles,
		missingWheelFiles
	};
}
