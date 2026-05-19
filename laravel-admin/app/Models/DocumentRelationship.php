<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class DocumentRelationship extends Model
{
    protected $table = 'krai_core.document_relationships';

    protected $keyType = 'string';

    public $incrementing = false;

    protected $fillable = [
        'primary_document_id',
        'secondary_document_id',
        'relationship_type',
        'relationship_strength',
        'auto_discovered',
        'manual_verification',
        'verification_date',
        'verified_by',
        'notes',
    ];

    protected function casts(): array
    {
        return [
            'relationship_strength' => 'float',
            'auto_discovered' => 'boolean',
            'manual_verification' => 'boolean',
            'verification_date' => 'datetime',
            'created_at' => 'datetime',
            'updated_at' => 'datetime',
        ];
    }

    public function primaryDocument(): BelongsTo
    {
        return $this->belongsTo(Document::class, 'primary_document_id');
    }

    public function secondaryDocument(): BelongsTo
    {
        return $this->belongsTo(Document::class, 'secondary_document_id');
    }
}
