<x-filament-panels::page>
    <div x-data="{
        copied: false,
        copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                this.copied = true;
                setTimeout(() => this.copied = false, 2000);
            });
        }
    }">
        {{ $this->infolist }}
    </div>

    <script>
        window.copyToClipboard = async (text) => {
            try {
                await navigator.clipboard.writeText(text);
                return true;
            } catch (err) {
                console.error('Failed to copy:', err);
                return false;
            }
        };
    </script>
</x-filament-panels::page>
