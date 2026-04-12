<div class="panel">
    <livewire:panel.listings :user="$user" />

    <flux:button wire:click="bulkActivate">Activate selected</flux:button>
    <flux:button wire:click="bulkDelete">Delete selected</flux:button>

    @include('partials.footer')
    @include('panel.components.pagination')
</div>
