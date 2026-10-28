# Fornello Order Tool

Einmal vom Organisator bereitstellen, von allen Hackathon-Teilnehmern nutzen:
eine fertige OpenAPI fuer simulierte Pizza-Abholbestellungen. Die Teilnehmer
muessen das Tool **nicht programmieren**.

## Voraussetzungen

- Azure CLI und PowerShell 5.1 oder neuer; fuer `git clone` ausserdem Git.
- Azure-Subscription mit Berechtigungen zum Erstellen der Ressourcen und
  Rollenzuweisungen, z. B. Owner. Organisationsrichtlinien muessen die unten
  genannten Ressourcen erlauben.
- Kein Docker, lokales Python oder Foundry-Projekt fuer das API-Deployment.

## Bereitstellen

```powershell
git clone https://github.com/MartinWehrsig/fornello-order-tool.git
cd fornello-order-tool
az login
.\deploy.ps1 -SubscriptionId "<SUBSCRIPTION-ID>" -ResourceGroup "rg-pizza-hackathon-swc"
```

Das Skript erstellt alles in **Sweden Central** und gibt die OpenAPI-URL aus.
Das erste Deployment kann wegen der Netzwerkressourcen mehrere Minuten dauern.
Erneutes Ausfuehren aktualisiert die API und behaelt den bestehenden API-Key.

Die Zugangsdaten stehen anschliessend in `.local/connection.json`.
**Diese Datei enthaelt den geheimen API-Key und darf nicht veroeffentlicht werden.**

## An die Teilnehmer weitergeben

1. Die ausgegebene **OpenAPI-URL** oder die erzeugte `.local/openapi.json`.
2. Den **API-Key separat ueber einen sicheren Kanal**. Header: `x-functions-key`.
3. Das gemeinsame [Menue](menu.txt) als Wissensquelle fuer ihren Agenten.

Im Foundry-Portal beim eigenen Agenten ein **Custom OpenAPI Tool** hinzufuegen,
die Spezifikation importieren und eine API-Key-Projektverbindung konfigurieren.
Zum Erstellen der Verbindung werden passende Projektberechtigungen benoetigt.
Die genaue Portalbeschriftung kann variieren. Die `/orders`-URL allein reicht
nicht; importiert wird die OpenAPI-Beschreibung.

Kurze Agentenanweisung zum Kopieren, zusaetzlich zum Menue:

```text
Du bist der Menue- und Demo-Bestellassistent von Pizzeria Fornello.
Nutze das Menue und die Parameterbeschreibung von submit_order.
Frage fehlende Groessen, Mengen, Extras und Varianten ab.
Zeige die exakte Bestellung und den Gesamtpreis ohne Rabatt.
Sage, dass es eine Demo ist, und frage vor dem Toolaufruf nach Bestaetigung.
Rufe submit_order erst nach Bestaetigung auf, mit confirmed=true.
Nenne danach die tatsaechliche Demo-Bestellnummer und den API-Gesamtpreis.
Erfinde bei Fehlern keine Bestaetigung und sende nicht automatisch erneut.
Fordere keine persoenlichen Daten an und garantiere keine Allergiesicherheit.
```

## Testen

Im Agenten: **"Eine grosse Margherita mit extra Pilzen zur Abholung."**
Erwartet: **12,40 EUR**, Rueckfrage zur Bestaetigung und erst danach ein
`submit_order`-Aufruf mit einer `DEMO-...`-Nummer.

Optionaler direkter API-Test mit Python 3.10+; keine Python-Pakete erforderlich:

```powershell
python verify_live_api.py
```

## Umfang, Infrastruktur und Kosten

- 39 Menue-Artikel, Pizza-Groessen und bis zu fuenf verschiedene Extra-Toppings.
- Nur Demo-Abholung: keine Lieferung, Rabatte, Sonderboeden, Kaeseersetzungen
  oder Half-and-half; keine echten Bestellungen, Speicherung oder Bezahlung.
- `confirmed=true` wird validiert. Eine echte Chat-Bestaetigung kann die
  zustandslose API nicht pruefen; das steuern die Agentenanweisungen.
- Neue Function/Flex-Plan, privater Storage mit Managed Identity, VNet und
  drei Private Endpoints fuer Blob/Queue/Table. API oeffentlich per HTTPS,
  Bestellungen API-Key-geschuetzt; Storage ohne oeffentlichen Netzwerkzugriff
  oder Shared Key. Private DNS ist global.
- Nutzungsabhaengige Function-/Storage-Kosten und **laufende Kosten fuer drei
  Private Endpoints**, auch ohne Anfragen. Kein Application Insights.
- Nach dem Hackathon die eigens angelegte Ressourcengruppe im Azure-Portal
  entfernen, nachdem geprueft wurde, dass keine anderen Anwendungen darin liegen.

Die API ist eine Hackathon-Demo, keine produktive Bestellplattform.
