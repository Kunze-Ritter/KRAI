-- Migration 023: AI Chat - Prompt Templates und Chat History
-- Erstellt Tabellen für konfigurierbare Prompt-Templates und persistente Chat-History

-- ============================================================
-- Prompt Templates (in krai_system Schema)
-- ============================================================
CREATE TABLE IF NOT EXISTS krai_system.prompt_templates (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(100) NOT NULL,
    description VARCHAR(255),
    prompt_text TEXT NOT NULL,
    category    VARCHAR(50) NOT NULL DEFAULT 'general',
    icon        VARCHAR(50) DEFAULT 'heroicon-o-chat-bubble-left',
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Seed mit Standard-Templates
INSERT INTO krai_system.prompt_templates (title, description, prompt_text, category, icon, sort_order) VALUES
('Fehlercode suchen',    'Fehlercode in der Datenbank nachschlagen',   'Suche nach Fehlercode: ',                            'error_codes', 'heroicon-o-magnifying-glass',   1),
('Ersatzteil finden',   'Ersatzteil nach Nummer oder Name suchen',     'Finde Ersatzteil: ',                                 'parts',       'heroicon-o-wrench-screwdriver',  2),
('Video Tutorial',      'Tutorial-Video für ein Gerät suchen',         'Zeige mir Video-Tutorials für: ',                    'videos',      'heroicon-o-play-circle',         3),
('Fehler diagnostizieren','Fehlerbeschreibung analysieren und Lösung finden', 'Analysiere diesen Fehler und schlage Lösungen vor: ', 'diagnosis',   'heroicon-o-light-bulb',          4),
('Gerät Daten',         'Technische Daten eines Gerätes abfragen',     'Zeige technische Informationen für: ',               'general',     'heroicon-o-information-circle',  5)
ON CONFLICT DO NOTHING;

-- ============================================================
-- Chat Sessions (in krai_users Schema)
-- ============================================================
CREATE TABLE IF NOT EXISTS krai_users.chat_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES krai_users.users(id) ON DELETE CASCADE,
    session_key VARCHAR(128) NOT NULL UNIQUE,
    title       VARCHAR(255),
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON krai_users.chat_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_session_key ON krai_users.chat_sessions (session_key);

-- ============================================================
-- Chat Messages (in krai_users Schema)
-- ============================================================
CREATE TABLE IF NOT EXISTS krai_users.chat_messages (
    id         BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES krai_users.chat_sessions(id) ON DELETE CASCADE,
    role       VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON krai_users.chat_messages (session_id);

-- ============================================================
-- Migrations Tracking
-- ============================================================
INSERT INTO krai_system.migrations (migration_name, applied_at, description)
VALUES ('023_ai_chat_prompt_templates_and_history', NOW(),
        'Prompt Templates (krai_system) und Chat History (krai_users) für AI Chat')
ON CONFLICT (migration_name) DO NOTHING;
