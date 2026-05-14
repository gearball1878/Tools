# Symbol_Wizard

PySide6 MVP für einen modellgetriebenen Symboleditor.

## Start

```bash
pip install -r requirements.txt
python main.py
```

## Aktueller Funktionsumfang

- Mehrere Symbole, jedes Symbol hat einen eigenen Reiter
- `New Symbol` legt ein neues Symbol an, ohne bestehende Symbole zu überschreiben
- Defaultnamen: `Symbol 1`, `Symbol 2`, ...
- Importierte Symbole mit gleichem Namen erhalten `_2`, `_3`, ...
- Wahl pro Symbol: Single Symbol oder Split Symbol
- Split Symbols werden als zusammengehöriges Symbol behandelt
- Pin-Validierung über alle Units eines Split Symbols hinweg
- Doppelte Pinnummern sind pro Symbol verboten, auch über Split-Units hinweg
- Automatische Pin-Nummern-Inkrementierung
- Extra Split-Symbol-Ansicht und Add-Unit/Split-Part-Funktion
- Objektbaum: Body, Attribute, Pins, Text, Graphics
- Pin-Tabelle mit Live-Bearbeitung
- Direkte Zeichenflächen-Bearbeitung:
  - Objekte auswählen und verschieben
  - Body und Grafikobjekte über den schwarzen Griff unten rechts vergrößern/verkleinern
  - ausgewählte Objekte mit `R` / `Q` rotieren
  - mit `Shift+R` / `Shift+Q` in 90°-Schritten rotieren
  - mit `+` / `-` skalieren
  - mit `Ctrl + Mouse Wheel` skalieren
- Draw Ribbon für Select/Edit, Pins, Text, Linie, Rechteck, Ellipse
- Linienart und Linienstärke für Body, Pins und Graphics
- RGB-Farben
- Sichtbare Symbolbody-Attribute werden im Zeichenfeld gerendert
- Visibility-Checkbox je Symbolbody-Attribut
- Stabilere Live-Aktualisierung: Änderungen in Attributfeldern werden entkoppelt aktualisiert, damit die GUI beim Tippen nicht abstürzt
- Copy/Paste/Delete ausgewählter Zeichenobjekte
- JSON Export: einzelnes Symbol oder komplette Symbolbibliothek

## JSON

- `Save Current Symbol JSON`: speichert nur das aktuell gewählte Symbol
- `Save All Symbols JSON`: speichert alle Symbole als Library
