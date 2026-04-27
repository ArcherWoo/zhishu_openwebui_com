<script lang="ts">
	import { getOllamaVersion } from '$lib/apis/ollama';
	import { WEBUI_VERSION } from '$lib/constants';
	import { WEBUI_NAME, config } from '$lib/stores';
	import { onMount, getContext } from 'svelte';

	const i18n = getContext('i18n');

	let ollamaVersion = '';

	onMount(async () => {
		if ($config?.features?.enable_ollama_api) {
			ollamaVersion = await getOllamaVersion(localStorage.token).catch((error) => {
				return '';
			});
		}
	});
</script>

<div id="tab-about" class="flex flex-col h-full justify-between space-y-3 text-sm mb-6">
	<div class=" space-y-3 overflow-y-scroll max-h-[28rem] md:max-h-full">
		<div>
			<div class=" mb-2.5 text-sm font-medium flex space-x-2 items-center">
				<div>
					{$WEBUI_NAME}
					{$i18n.t('Version')}
				</div>
			</div>
			<div class="flex w-full justify-between items-center">
				<div class="flex flex-col text-xs text-gray-700 dark:text-gray-200">
					<div class="flex gap-1">
						v{WEBUI_VERSION}
					</div>
				</div>
			</div>
		</div>

		{#if ollamaVersion}
			<hr class=" border-gray-100/30 dark:border-gray-850/30" />

			<div>
				<div class=" mb-2.5 text-sm font-medium">{$i18n.t('Ollama Version')}</div>
				<div class="flex w-full">
					<div class="flex-1 text-xs text-gray-700 dark:text-gray-200">
						{ollamaVersion ?? 'N/A'}
					</div>
				</div>
			</div>
		{/if}
	</div>
</div>
