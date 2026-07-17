<script lang="ts">
    let { label = "Svelte island ready" }: { label?: string } = $props()
</script>

<span class="badge text-bg-success">{label}</span>
