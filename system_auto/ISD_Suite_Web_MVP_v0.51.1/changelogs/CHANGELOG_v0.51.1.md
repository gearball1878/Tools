# v0.51.1 – Modell-Dropdown und ECAD-Systemauswahl

Kumulativer Stand auf v0.51.0 einschließlich aller bisherigen KI- und Xpedition-Funktionen.

- Dokumentierte Modellvorschläge bleiben beim API-Laden sichtbar. Leere oder
  eingeschränkte API-Kataloge entfernen die neuen Modelle nicht mehr.
- Bestehende Modellwahl bleibt erhalten; Suche im Modell-Dropdown.
- Zusätzliche dokumentierte Modelle für Gemini, Mistral, DeepSeek, Groq und
  OpenRouter. Lokale/benutzerdefinierte Modelle werden über die API bzw. exakte ID gewählt.
- Sichtbare Schaltfläche API-Modelle laden; scrollbarer Konfigurationsdialog.
- Direktes ECAD-System-Dropdown für KiCad und Xpedition in beiden Dialogen.
  Wechsel entfernt den vorherigen Dialog; Projektverknüpfung bleibt beim
  Ansichtswechsel erhalten. Nicht verfügbare COM-Installation blockiert die
  Auswahl von Xpedition nicht.
- Versionsanzeige in beiden Konfigurationsdialogen; Handbuch und kontextbezogene
  Hilfe mit Auswahl- und Neustartanleitung ergänzt.
- Interaktionstests prüfen sichtbare Modelloptionen, API-Ergänzung bei leerem
  Katalog und wiederholten ECAD-Wechsel in beiden Richtungen.

API-Zugriff und native ECAD-Nachweise weiterhin arbeitsplatz-/accountabhängig.
