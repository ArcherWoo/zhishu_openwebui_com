<script lang="ts">
	import { tick } from 'svelte';

	import Markdown from '$lib/components/chat/Messages/Markdown.svelte';
	import KnowledgeMarkdownTableEditor from './KnowledgeMarkdownTableEditor.svelte';
	import {
		parseMarkdownTable,
		stringifyMarkdownTable,
		type MarkdownTableData
	} from './knowledgeMarkdownTables';
	import { deriveKnowledgeBlockPresentation } from './knowledgeMarkdownEditorState';

	import type { KnowledgeMarkdownBlock } from './knowledgeMarkdownBlocks';

	export let block: KnowledgeMarkdownBlock;
	export let active = false;
	export let writeAccess = false;
	export let onEdit = () => {};
	export let onCommit = (_nextRaw: string, _options: { closeEditor?: boolean } = {}) => {};

	let draft = '';
	let tableDraft: MarkdownTableData | null = null;
	let editorElement: HTMLTextAreaElement | null = null;

	$: if (active) {
		draft = block.raw;
	}

	$: if (active && writeAccess && block.kind !== 'table') {
		void tick().then(() => {
			editorElement?.focus();
		});
	}

	$: if (block.kind === 'table') {
		tableDraft = parseMarkdownTable(block.raw);
	} else {
		tableDraft = null;
	}

	$: presentation = deriveKnowledgeBlockPresentation({
		kind: block.kind,
		active,
		writeAccess
	});
</script>

<section
	class="knowledge-workbench-block"
	data-kind={block.kind}
	data-layout={presentation.layout}
	data-chrome={presentation.chrome}
>
	{#if active && writeAccess && block.kind !== 'table'}
		<textarea
			bind:this={editorElement}
			class="knowledge-workbench-block__editor font-mono text-sm outline-none ring-0"
			bind:value={draft}
			on:blur={() => onCommit(draft, { closeEditor: true })}
			on:keydown={(event) => {
				if (event.key === 'Escape') {
					event.stopPropagation();
					onCommit(draft, { closeEditor: true });
				}
			}}
		></textarea>
	{:else if active && writeAccess && block.kind === 'table' && tableDraft}
		<KnowledgeMarkdownTableEditor
			table={tableDraft}
			onInput={(nextTable) => {
				tableDraft = nextTable;
				onCommit(stringifyMarkdownTable(nextTable));
			}}
		/>
	{:else if writeAccess}
		<div
			role="button"
			tabindex="0"
			class="knowledge-workbench-block__surface"
			on:click={onEdit}
			on:keydown={(event) => {
				if (event.key === 'Enter' || event.key === ' ') {
					event.preventDefault();
					onEdit();
				}
			}}
		>
			<div class="markdown-prose-sm">
				<Markdown id={`knowledge-block-${block.id}`} content={block.raw} />
			</div>
		</div>
	{:else}
		<div class="knowledge-workbench-block__surface">
			<div class="markdown-prose-sm">
				<Markdown id={`knowledge-block-${block.id}`} content={block.raw} />
			</div>
		</div>
	{/if}
</section>
