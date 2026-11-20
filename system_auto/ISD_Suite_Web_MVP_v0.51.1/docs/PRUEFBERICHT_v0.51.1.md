# Prüfbericht v0.51.1

Kumulativer Stand v0.51.0 plus korrigierte Modell- und ECAD-Auswahl.
Modelldropdown wird auf die tatsächlich an die Oberfläche übertragenen
Optionen geprüft, einschließlich leerer/eingeschränkter API-Kataloge.
ECAD-Interaktion umfasst Hin-/Rückwechsel und wiederholten Wechsel.

Native ECAD-Installation und Live-API-Zugänge stehen in dieser Umgebung nicht
zur Verfügung. Die Auswahl von Xpedition ist davon unabhängig prüfbar.

## Ergebnisse

- Python-Gesamtsuite: **468 bestanden**, **21 Subtests bestanden**, 3 native
  ECAD-Tests mangels Installation übersprungen (2 KiCad, 1 Xpedition).
- Gezielte Auswahl-/Dialogtests: **19 bestanden**, einschließlich sofortiger
  Modellvorschläge für alle voreingestellten Anbieter, gespeicherter Alt-ID,
  leerem API-Katalog und mehrfachen Wechseln KiCad ↔ Xpedition.
- JavaScript: **2 bestanden**. Python-Module kompilieren.
- Bekannte NiceGUI-Outbox-Warnung beim Testteardown; keine fehlgeschlagenen Tests.

Die konkrete Ursache für die fehlende Xpedition-Auswahl in der Installation des
Nutzers konnte hier nicht eindeutig reproduziert werden. Die bisherige Menüauswahl
wurde durch ein sichtbares, direkt getestetes Dropdown ersetzt. Serverversionen
können in beiden Dialogen geprüft werden; ein Update benötigt einen Serverneustart.
Modelle verschwanden nach dem API-Laden durch Ersetzen statt Ergänzen der Liste;
der neue Ablauf erhält die dokumentierten Vorschläge und die aktive Wahl.

## Auslieferungsprüfung

Runtime-ZIP separat entpackt und daraus gestartet: Anwendung und Nutzerhandbuch
liefern HTTP 200; Version v0.51.1 und Kapitel 49 sind vorhanden. Testprozess
anschließend beendet. Archive enthalten die bisherige KI-Anbindung und die
Xpedition-SPOT-/COM-Funktionen vollständig, ohne Abhängigkeiten oder Projektdateien.
