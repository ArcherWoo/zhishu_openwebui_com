<script lang="ts">
	import KnowledgeMarkdownBlock from './KnowledgeMarkdownBlock.svelte';
	import type { KnowledgeMarkdownBlock as Block } from './knowledgeMarkdownBlocks';

	export let blocks: Block[] = [];
	export let activeBlockId: string | null = null;
	export let writeAccess = false;
	export let onEditBlock = (_blockId: string) => {};
	export let onCommitBlock = (
		_blockId: string,
		_nextRaw: string,
		_options: { closeEditor?: boolean } = {}
	) => {};
</script>

<div class="knowledge-workbench-document">
	<article class="knowledge-workbench-paper" aria-label="Markdown 文稿">
		{#each blocks as block (block.id)}
			<KnowledgeMarkdownBlock
				{block}
				active={activeBlockId === block.id}
				{writeAccess}
				onEdit={() => onEditBlock(block.id)}
				onCommit={(nextRaw, options) => onCommitBlock(block.id, nextRaw, options)}
			/>
		{/each}
	</article>
</div>
