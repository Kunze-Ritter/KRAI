
# FOLIANT REGISTRY EXTRACTION GUIDE

## Methode 1: JavaScript-Konsole (Empfohlen)

1. Öffne die PDF in Adobe Acrobat Reader DC
2. Drücke Ctrl+J um die JavaScript-Konsole zu öffnen
3. Gib folgende Befehle ein:

```javascript
// Export Logic Registry
console.println("=== LOGIC REGISTRY ===");
console.println(Registry.System.Logic.toXMLString());

// Export Atoms Registry
console.println("=== ATOMS REGISTRY ===");
console.println(Registry.System.Atoms.toXMLString());

// Export Enabled List
console.println("=== ENABLED LIST ===");
console.println(Registry.System.Logic.Enabled.toString());

// Export Groups
console.println("=== GROUPS ===");
console.println(Registry.System.Logic.Groups.toXMLString());
```

4. Kopiere die gesamte Ausgabe
5. Speichere als: `foliant_registry_export.txt`

## Methode 2: Einzelne Abfragen

```javascript
// Welche Optionen sind aktiviert?
Registry.System.Logic.Enabled.toString()

// Welche Gruppen gibt es?
Registry.System.Logic.Groups.toXMLString()

// Alle Items
Registry.System.Atoms.Item.toXMLString()

// Auswahl-Status
Registry.System.Logic.Selection.toString()
```

## Methode 3: Alle Sprites auflisten

```javascript
// Liste aller Sprite-Namen
var sprites = [];
for (var i = 0; i < this.numFields; i++) {
    var field = this.getNthFieldName(i);
    if (field.indexOf("Sprite_") === 0) {
        sprites.push(field.replace("Sprite_", ""));
    }
}
console.println(sprites.join(";"));
```

## Was wir brauchen:

- **Enabled**: Welche Optionen sind verfügbar
- **Groups**: Wie sind Optionen gruppiert (links/rechts/oben/unten)
- **Atoms**: Alle verfügbaren Items mit ihren Properties
- **FunctionGroups.Choice**: Auswahl-Logik und Abhängigkeiten
