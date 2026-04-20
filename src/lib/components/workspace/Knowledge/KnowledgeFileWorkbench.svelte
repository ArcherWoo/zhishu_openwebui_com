<script lang="ts">
	import { getContext, onDestroy, onMount } from 'svelte';

	import KnowledgeMarkdownDocument from './KnowledgeMarkdownDocument.svelte';
	import {
		deriveSaveState,
		hasPendingMarkdownChanges,
		shouldWarnBeforeUnload
	} from './knowledgeMarkdownEditorState';
	import { parseMarkdownBlocks, replaceMarkdownBlockRaw } from './knowledgeMarkdownBlocks';

	const i18n = getContext('i18n');
	const AUTOSAVE_DELAY = 900;

	export let fileId: string;
	export let fileName: string;
	export let content = '';
	export let saving = false;
	export let writeAccess = false;
	export let onSave: ((content: string) => Promise<void>) | null = null;

	let activeBlockId: string | null = null;
	let draftMarkdown = content;
	let lastSavedMarkdown = content;
	let saveError: string | null = null;
	let internalSaving = false;
	let syncedFileId = fileId;
	let syncedContent = content;
	let autosaveTimer: ReturnType<typeof setTimeout> | null = null;
	let queuedSaveMarkdown: string | null = null;

	const clearAutosaveTimer = () => {
		if (autosaveTimer) {
			clearTimeout(autosaveTimer);
			autosaveTimer = null;
		}
	};

	$: if (fileId !== syncedFileId || content !== syncedContent) {
		const switchedFiles = fileId !== syncedFileId;
		const incomingMatchesDraft = content === draftMarkdown;

		clearAutosaveTimer();
		queuedSaveMarkdown = null;
		lastSavedMarkdown = content;

		if (switchedFiles || !incomingMatchesDraft) {
			draftMarkdown = content;
			activeBlockId = null;
			saveError = null;
		}

		syncedFileId = fileId;
		syncedContent = content;
	}

	$: blocks = parseMarkdownBlocks(draftMarkdown);
	$: dirty = hasPendingMarkdownChanges(draftMarkdown, lastSavedMarkdown);
	$: saveState = deriveSaveState({
		saving: saving || internalSaving,
		error: saveError,
		dirty
	});
	$: saveStateLabel =
		saveState === 'saving'
			? '保存中...'
			: saveState === 'error'
				? '保存失败'
				: saveState === 'dirty'
					? '待自动保存'
					: '已保存';

	const persistMarkdown = async (initialMarkdown: string) => {
		if (!onSave) {
			lastSavedMarkdown = initialMarkdown;
			return;
		}

		if (internalSaving) {
			queuedSaveMarkdown = initialMarkdown;
			return;
		}

		internalSaving = true;
		saveError = null;

		try {
			let markdownToSave = initialMarkdown;

			while (true) {
				await onSave(markdownToSave);
				lastSavedMarkdown = markdownToSave;
				syncedContent = markdownToSave;

				if (!queuedSaveMarkdown || queuedSaveMarkdown === markdownToSave) {
					queuedSaveMarkdown = null;
					break;
				}

				markdownToSave = queuedSaveMarkdown;
				queuedSaveMarkdown = null;
			}
		} catch (error) {
			saveError = error instanceof Error ? error.message : `${error}`;
		} finally {
			internalSaving = false;
		}
	};

	const queueAutosave = (nextMarkdown: string, { closeEditor = false } = {}) => {
		draftMarkdown = nextMarkdown;
		saveError = null;

		if (closeEditor) {
			activeBlockId = null;
		}

		clearAutosaveTimer();
		autosaveTimer = setTimeout(() => {
			autosaveTimer = null;
			void persistMarkdown(nextMarkdown);
		}, AUTOSAVE_DELAY);
	};

	const handleBeforeUnload = (event: BeforeUnloadEvent) => {
		if (!shouldWarnBeforeUnload({ dirty, saving: saving || internalSaving })) {
			return;
		}

		event.preventDefault();
		event.returnValue = '';
	};

	onMount(() => {
		window.addEventListener('beforeunload', handleBeforeUnload);
	});

	onDestroy(() => {
		clearAutosaveTimer();
		window.removeEventListener('beforeunload', handleBeforeUnload);
	});
</script>

<div class="knowledge-workbench-shell flex h-full min-h-0 flex-col">
	<div class="knowledge-workbench-toolbar">
		<div class="knowledge-workbench-toolbar__copy">
			<div class="knowledge-workbench-toolbar__eyebrow">知识文档工作台</div>
			<div class="knowledge-workbench-toolbar__filename">{fileName}</div>
			<div class="knowledge-workbench-toolbar__hint">
				{writeAccess ? '默认像文稿一样阅读，悬停后轻触即可编辑。' : '当前为只读文稿视图。'}
			</div>
		</div>

		<div class="knowledge-workbench-toolbar__status" data-state={saveState}>
			<span class="knowledge-workbench-toolbar__status-dot" />
			<span>{saveStateLabel}</span>
		</div>
	</div>

	<div class="knowledge-workbench-canvas min-h-0 flex-1 overflow-y-auto px-5 py-6 md:px-8">
		{#if saveError}
			<div class="knowledge-workbench-inline-alert mx-auto mb-4 w-full max-w-6xl">
				保存失败：{saveError}
			</div>
		{/if}

		{#if draftMarkdown.trim()}
			<KnowledgeMarkdownDocument
				{blocks}
				{activeBlockId}
				{writeAccess}
				onEditBlock={(blockId) => {
					activeBlockId = blockId;
				}}
				onCommitBlock={(blockId, nextRaw, { closeEditor = false } = {}) => {
					const nextMarkdown = replaceMarkdownBlockRaw(blocks, blockId, nextRaw);
					queueAutosave(nextMarkdown, { closeEditor });
				}}
			/>
		{:else}
			<div class="knowledge-workbench-document">
				<article class="knowledge-workbench-paper">
					<div class="rounded-2xl border border-dashed border-slate-300/90 px-6 py-10 text-sm text-slate-500">
						{$i18n.t('No content found')}
					</div>
				</article>
			</div>
		{/if}
	</div>
</div>
