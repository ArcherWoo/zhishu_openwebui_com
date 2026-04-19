const packages = [
	'micropip',
	'packaging',
	'requests',
	'beautifulsoup4',
	'numpy',
	'pandas',
	'matplotlib',
	'scikit-learn',
	'scipy',
	'regex',
	'sympy',
	'tiktoken',
	'seaborn',
	'pytz',
	'black',
	'openai',
	'openpyxl'
];

// Pure-Python packages whose wheels must be downloaded from PyPI and saved into
// static/pyodide/ so that the browser can install them offline via micropip.
// Packages already provided by the Pyodide distribution (click, platformdirs,
// typing_extensions, etc.) do NOT need to be listed here.
const pypiPackages = ['black', 'pathspec', 'mypy_extensions'];

import { setGlobalDispatcher, ProxyAgent } from 'undici';
import { writeFile, readFile, copyFile, readdir, rm, access, mkdir } from 'fs/promises';
import {
	buildCacheMetadata,
	validateCacheState,
	PYODIDE_CACHE_METADATA_FILE
} from './lib/pyodide-cache.js';

const cacheDir = 'static/pyodide';
const nodePyodideDir = 'node_modules/pyodide';
const cacheMetadataPath = `${cacheDir}/${PYODIDE_CACHE_METADATA_FILE}`;

function trimTrailingSlash(value) {
	return value.replace(/\/+$/, '');
}

function joinUrl(base, suffix) {
	return `${trimTrailingSlash(base)}/${suffix.replace(/^\/+/, '')}`;
}

function envValue(...keys) {
	for (const key of keys) {
		const value = process.env[key];
		if (value && value.trim()) {
			return value.trim();
		}
	}
	return null;
}

const pyodideBaseUrl = envValue('OPEN_WEBUI_PYODIDE_BASE_URL');
const pypiJsonBaseUrl = envValue('OPEN_WEBUI_PYPI_JSON_BASE_URL', 'OPEN_WEBUI_PYPI_BASE_URL');
const pypiFilesBaseUrl = envValue('OPEN_WEBUI_PYPI_FILES_BASE_URL');
const allowPyodideDownload = envValue('OPEN_WEBUI_ALLOW_PYODIDE_DOWNLOAD')?.toLowerCase() === 'true';

async function isInstalledPyodidePackageAvailable() {
	try {
		await access(`${nodePyodideDir}/package.json`);
		return true;
	} catch {
		return false;
	}
}

async function loadPyodideModule() {
	try {
		const module = await import('pyodide');
		return module.loadPyodide;
	} catch (error) {
		console.warn('Pyodide npm package is not installed, skipping optional runtime preparation.');
		if (error) {
			console.warn(error);
		}
		return null;
	}
}

async function readJsonIfExists(path) {
	try {
		return JSON.parse(await readFile(path, 'utf-8'));
	} catch {
		return null;
	}
}

async function listFilesIfExists(path) {
	try {
		return await readdir(path);
	} catch {
		return [];
	}
}

async function getInstalledPyodideVersion() {
	const packageJson = JSON.parse(await readFile(`${nodePyodideDir}/package.json`, 'utf-8'));
	return packageJson.version;
}

async function getCacheState(pyodideVersion) {
	const actualMetadata = await readJsonIfExists(cacheMetadataPath);
	const cachedPackageJson = await readJsonIfExists(`${cacheDir}/package.json`);
	const existingFiles = await listFilesIfExists(cacheDir);
	const requiredFiles = await listFilesIfExists(nodePyodideDir);
	const expectedMetadata = buildCacheMetadata({
		pyodideVersion,
		packages,
		pypiPackages
	});
	const validation = validateCacheState({
		expectedMetadata,
		actualMetadata,
		existingFiles,
		requiredFiles
	});

	return {
		...validation,
		expectedMetadata,
		actualMetadata,
		existingFiles,
		cacheVersion: actualMetadata?.pyodideVersion ?? cachedPackageJson?.version ?? null
	};
}

function printCacheReasons(reasons) {
	if (reasons.length === 0) {
		return;
	}

	console.log('Pyodide cache refresh required because:');
	for (const reason of reasons) {
		console.log(`- ${reason}`);
	}
}

/**
 * Loading network proxy configurations from the environment variables.
 * And the proxy config with lowercase name has the highest priority to use.
 */
function initNetworkProxyFromEnv() {
	// we assume all subsequent requests in this script are HTTPS:
	// https://cdn.jsdelivr.net
	// https://pypi.org
	// https://files.pythonhosted.org
	const allProxy = process.env.all_proxy || process.env.ALL_PROXY;
	const httpsProxy = process.env.https_proxy || process.env.HTTPS_PROXY;
	const httpProxy = process.env.http_proxy || process.env.HTTP_PROXY;
	const preferedProxy = httpsProxy || allProxy || httpProxy;
	/**
	 * use only http(s) proxy because socks5 proxy is not supported currently:
	 * @see https://github.com/nodejs/undici/issues/2224
	 */
	if (!preferedProxy || !preferedProxy.startsWith('http')) return;
	let preferedProxyURL;
	try {
		preferedProxyURL = new URL(preferedProxy).toString();
	} catch {
		console.warn(`Invalid network proxy URL: "${preferedProxy}"`);
		return;
	}
	const dispatcher = new ProxyAgent({ uri: preferedProxyURL });
	setGlobalDispatcher(dispatcher);
	console.log(`Initialized network proxy "${preferedProxy}" from env`);
}

async function downloadPackages() {
	console.log('Setting up pyodide + micropip');

	const loadPyodide = await loadPyodideModule();
	if (!loadPyodide) {
		return false;
	}

	let pyodide;
	try {
		pyodide = await loadPyodide({
			packageCacheDir: cacheDir,
			indexURL: pyodideBaseUrl ? joinUrl(pyodideBaseUrl, '') : undefined
		});
	} catch (err) {
		console.error('Failed to load Pyodide:', err);
		return false;
	}

	try {
		console.log('Loading micropip package');
		await pyodide.loadPackage('micropip');

		const micropip = pyodide.pyimport('micropip');
		console.log('Downloading Pyodide packages:', packages);

		try {
			for (const pkg of packages) {
				console.log(`Installing package: ${pkg}`);
				await micropip.install(pkg);
			}
		} catch (err) {
			console.error('Package installation failed:', err);
			return false;
		}

		console.log('Pyodide packages downloaded, freezing into lock file');

		try {
			const lockFile = await micropip.freeze();
			await writeFile(`${cacheDir}/pyodide-lock.json`, lockFile);
		} catch (err) {
			console.error('Failed to write lock file:', err);
			return false;
		}
	} catch (err) {
		console.error('Failed to load or install micropip:', err);
		return false;
	}

	return true;
}

async function copyPyodide() {
	console.log('Copying Pyodide files into static directory');
	// Copy all files from node_modules/pyodide to static/pyodide
	for await (const entry of await readdir(nodePyodideDir)) {
		await copyFile(`${nodePyodideDir}/${entry}`, `${cacheDir}/${entry}`);
	}
}

/**
 * Download pure-Python wheels from PyPI and save them into static/pyodide/.
 * Also injects entries into pyodide-lock.json so that micropip resolves these
 * packages from the local server instead of fetching them from the internet.
 */
async function downloadPyPIWheels() {
	const lockPath = `${cacheDir}/pyodide-lock.json`;
	let lockData;
	try {
		lockData = JSON.parse(await readFile(lockPath, 'utf-8'));
	} catch {
		console.warn('Could not read pyodide-lock.json, skipping PyPI wheel download');
		return { ok: false, wheelFiles: [] };
	}

	const wheelFiles = [];
	let hadFailure = false;

	for (const pkg of pypiPackages) {
		console.log(`Fetching PyPI metadata for: ${pkg}`);
		const metadataUrl = pypiJsonBaseUrl
			? joinUrl(pypiJsonBaseUrl, `pypi/${pkg}/json`)
			: `https://pypi.org/pypi/${pkg}/json`;
		const res = await fetch(metadataUrl);
		if (!res.ok) {
			console.error(`Failed to fetch PyPI metadata for ${pkg}: ${res.status}`);
			hadFailure = true;
			continue;
		}
		const meta = await res.json();
		const version = meta.info.version;
		const files = meta.urls || [];
		// Find the pure-Python wheel (py3-none-any)
		const wheel = files.find(
			(f) => f.filename.endsWith('.whl') && f.filename.includes('py3-none-any')
		);
		if (!wheel) {
			console.warn(`No pure-Python wheel found for ${pkg}==${version}, skipping`);
			hadFailure = true;
			continue;
		}
		const dest = `${cacheDir}/${wheel.filename}`;
		// Download wheel if not already present
		try {
			await access(dest);
			console.log(`  Already exists: ${wheel.filename}`);
		} catch {
			console.log(`  Downloading: ${wheel.filename}`);
			const wheelUrl = pypiFilesBaseUrl
				? joinUrl(pypiFilesBaseUrl, wheel.filename)
				: wheel.url;
			const wheelRes = await fetch(wheelUrl);
			if (!wheelRes.ok) {
				console.error(`  Failed to download ${wheel.filename}: ${wheelRes.status}`);
				hadFailure = true;
				continue;
			}
			const buffer = Buffer.from(await wheelRes.arrayBuffer());
			await writeFile(dest, buffer);
			console.log(`  Saved: ${dest} (${buffer.length} bytes)`);
		}
		wheelFiles.push(wheel.filename);

		// Inject into pyodide-lock.json so micropip resolves locally
		const normalizedName = pkg.replace(/-/g, '_');
		if (!lockData.packages[normalizedName]) {
			lockData.packages[normalizedName] = {
				name: normalizedName,
				version: version,
				file_name: wheel.filename,
				install_dir: 'site',
				sha256: wheel.digests?.sha256 || '',
				package_type: 'package',
				imports: [normalizedName],
				depends: []
			};
			console.log(`  Added ${normalizedName}==${version} to pyodide-lock.json`);
		}
	}

	await writeFile(lockPath, JSON.stringify(lockData, null, 2));
	console.log('Updated pyodide-lock.json with PyPI packages');
	return { ok: !hadFailure, wheelFiles };
}

async function writeCacheMetadata(metadata) {
	await writeFile(cacheMetadataPath, JSON.stringify(metadata, null, 2));
}

async function ensureCacheDirectory() {
	await mkdir(cacheDir, { recursive: true });
}

async function main() {
	initNetworkProxyFromEnv();
	if (pyodideBaseUrl) {
		console.log(`Using custom Pyodide base URL: ${pyodideBaseUrl}`);
	}
	if (pypiJsonBaseUrl) {
		console.log(`Using custom PyPI metadata base URL: ${pypiJsonBaseUrl}`);
	}
	if (pypiFilesBaseUrl) {
		console.log(`Using custom PyPI wheel base URL: ${pypiFilesBaseUrl}`);
	}

	const pyodidePackageAvailable = await isInstalledPyodidePackageAvailable();
	if (!pyodidePackageAvailable) {
		console.warn('Pyodide npm package is unavailable; skipping optional Pyodide preparation.');
		return;
	}

	const pyodideVersion = await getInstalledPyodideVersion();
	const cacheState = await getCacheState(pyodideVersion);

	if (cacheState.reusable) {
		console.log('Pyodide cache is complete; skipping pyodide fetch.');
		return;
	}

	printCacheReasons(cacheState.reasons);

	if (cacheState.cacheVersion && cacheState.cacheVersion !== pyodideVersion) {
		console.log(
			`Pyodide runtime changed from ${cacheState.cacheVersion} to ${pyodideVersion}, clearing ${cacheDir}`
		);
		await rm(cacheDir, { recursive: true, force: true });
	}

	await ensureCacheDirectory();

	if (!allowPyodideDownload) {
		console.warn(
			'OPEN_WEBUI_ALLOW_PYODIDE_DOWNLOAD is not set to true; skipping network-based Pyodide cache refresh.'
		);
		await copyPyodide();
		return;
	}

	const packagesOk = await downloadPackages();
	await copyPyodide();
	const pypiResult = await downloadPyPIWheels();

	if (packagesOk && pypiResult.ok) {
		const metadata = buildCacheMetadata({
			pyodideVersion,
			packages,
			pypiPackages,
			pypiWheelFiles: pypiResult.wheelFiles
		});
		await writeCacheMetadata(metadata);
		console.log(`Wrote Pyodide cache metadata: ${cacheMetadataPath}`);
		return;
	}

	console.warn('Pyodide cache refresh finished with warnings; metadata was not written.');
}
await main();
