# Symbol_Wizard

PySide6 MVP für einen modellgetriebenen Symboleditor.

## Start

```bash
pip install -r requirements.txt
python main.py
```

## Enthalten

- Mehrere Symbole, jedes Symbol hat einen eigenen Reiter
- `New Symbol` legt ein neues Symbol an, ohne bestehende Symbole zu überschreiben
- Defaultnamen: `Symbol 1`, `Symbol 2`, ...
- Importierte Symbole mit gleichem Namen erhalten `_2`, `_3`, ...
- Single- und Split-Symbol-Ansicht
- Units/Split-Symbols je Symbol
- Objektbaum: Body, Attribute, Pins, Text, Graphics
- Pin-Tabelle
- Verbot doppelter Pinnummern pro Symbol, auch über Split-Units hinweg
- Automatische Pin-Nummern-Inkrementierung
- Zeichenflächen-Editing mit Draw-Ribbon
- Copy/Paste/Delete ausgewählter Zeichenobjekte
- Linienart und Linienstärke für Body, Pins und Graphics
- RGB-Farben
- Sichtbare Symbolbody-Attribute werden im Zeichenfeld gerendert
- Visibility-Checkbox je Symbolbody-Attribut
- JSON Export: einzelnes Symbol oder komplette Symbolbibliothek

## JSON

- `Save Current Symbol JSON`: speichert nur das aktuell gewählte Symbol
- `Save All Symbols JSON`: speichert alle Symbole als Library
