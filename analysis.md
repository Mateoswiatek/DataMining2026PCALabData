# Analiza niespójności i braków — M2 + M3 (stan po merge)

> Plik roboczy. Uwzględnia zmiany z ostatnich commitów (rework M2, rozszerzenie M3).

---

## Status uwag prowadzącego — co już zostało zrealizowane

### M3 TODO

| Uwaga | Status | Gdzie |
|---|---|---|
| Warto też oprócz sieci Petriego zrobić BPMN | ✅ Zrealizowane | Sekcja 6.1 (HM, fig_bpmn.png) + sekcja 6.2 (IMf, fig_bpmn_im.png) — dwa modele BPMN z dwóch algorytmów |
| Odkrywamy reguły dla rozdzielającego się przepływu w BPMN XOR | ✅ Zrealizowane | Sekcja 6.3 + fig_xor_decision.png — jawna bramka XOR po `Receive sample state`; sekcja 7.2 pokazuje, że wynik PCR POSITIVE uruchamia gałąź eksportu (86.9% eksportów = próbki dodatnie) |
| Porównanie z procesem na bazie wyników M2 | ✅ Zrealizowane | Sekcja 11 „Porównanie z procesem odkrytym w Milestone 2 (klasteryzacja)" — tabela porównawcza głównego przepływu, różnic w zakresie (8 vs 28 aktywności), pozycji `timeout` i braku widoczności gałęzi eksportu w M2 |

### Do Milestone 2

| Uwaga | Status | Gdzie |
|---|---|---|
| Typy danych endpointów, jaki zakres danych — statystyki | ✅ Zrealizowane | M2 przerobione na klasteryzację payloadu. Sekcja 2 ma pełną tabelę statystyk (317 905 zdarzeń, 6 339 przypadków, 51 209 jednostek klasteryzacji) i przykłady wierszy payloadu per czynność |
| Wykres 4.1 PCA — nieczytelny | ✅ Zrealizowane | Nowy PCA (fig_pca_events.png) pokazuje 51 209 punktów kolorowanych klastrem, nie 15 URL-i z nakładającymi się etykietami |
| Co klasteryzujecie? jakie dane — przykłady | ✅ Zrealizowane | Sekcja 2 (tabela payloadu), sekcja 3 (macierz cech 17 kolumn), sekcja 5 (tabela klastrów z sygnaturą argumentów i czystością) |
| TODO: klasteryzacja danych z sensorów. Zweryfikować czy sensowna | ✅ Zrealizowane | Sekcja 1 „Uwaga o danych" wprost: zbiór to log procesowy CPEE, nie telemetria, nie zawiera fizycznych czujników. Klasteryzacja niskopoziomowego payloadu uzasadniona wynikami (purity 0.93, ARI 0.87, NMI 0.92) |

---

## Pozostałe problemy i niespójności

### R1. Pętla na `Match patient data` w BPMN IMf — nieweryfikowalna lub artefakt

**Sekcja:** M3 §6.2

**Problem:** Raport mówi: „pętla (*) na `Match patient data` oznacza, że część próbek przechodzi ponowną identyfikację (rework)." Ale tabela DFG (§3.1) nie pokazuje żadnej krawędzi wchodzącej do `Match patient data` spoza startu — tylko `start → Match patient data`. W 28 łukach DFG nie ma żadnego back-edge'a do tej aktywności.

**Prawdopodobna przyczyna:** IMf widzi `timeout` jako aktywność pojawiającą się zarówno na początku śladu (równoległy start z Match patient data, sekcja 3.2) jak i na końcu (complete po Callback timeout). Algorytm może to błędnie zinterpretować jako pętlę i wymusić w process tree strukturę `*(Match patient data, timeout)`.

**Ryzyko:** Jeśli prowadzący zapyta o tę pętlę, odpowiedź „to rework próbek" jest niesprawdzona i może być nieprawdziwa.

**Co zrobić:** Albo sprawdzić w notebooku czy istnieje krawędź `Send notification → Match patient data` lub `timeout → Match patient data` w pełnym DFG (28 łuków, w tabeli pokazano tylko 6 najczęstszych), albo dodać do sekcji 6.2 zastrzeżenie: „Pętla może być artefaktem modelu wynikającym z równoległego startowania aktywności (patrz §3.2) — wymaga weryfikacji."

---

### R2. Stary notebook `02_m2_endpoint_clustering.ipynb` wciąż istnieje

**Ścieżka:** `notebooks/02_m2_endpoint_clustering.ipynb`

**Problem:** Stary notebook analizy endpointów nadal leży w repozytorium. Nowy raport M2 wskazuje na `02_m2_event_clustering.ipynb`. Stary notebook:
- nie jest przywoływany w żadnym raporcie,
- może mylić prowadzącego jeśli przegląda katalog `notebooks/`,
- ma ten sam numer (`02_`) co nowy.

**Co zrobić:** Usunąć `notebooks/02_m2_endpoint_clustering.ipynb` z repozytorium lub wyraźnie go oznaczyć jako przestarzały (np. przenieść do `notebooks/archive/`).

---

### R3. 8 endpointów w M3 — niepełne wyjaśnienie normalizacji

**Sekcja:** M3 §8.1

**Problem:** Raport mówi: „Po normalizacji (collapse per-instance IDs silnika CPEE) uzyskano 8 unikalnych logicznych endpointów." Collapse per-instance IDs (49 → 1 typ CPEE) dałby ~15 logicznych typów (jak w starym M2). Żeby dostać 8, trzeba też scalić domeny `mygreschner.com` i `greschner.azurewebsites.net` jako ten sam serwis fizyczny.

**Brakuje:** jednego zdania wyjaśniającego, że 8 = collapse instancji CPEE + collapse duplikowanych domen.

**Co zrobić:** W §8.1 dodać: „Normalizacja obejmuje dwa kroki: collapse per-instance IDs silnika (`/engine/\d+/` → `/engine/{id}/`) oraz scalenie domen `mygreschner.com` i `greschner.azurewebsites.net` jako tego samego serwisu fizycznego (por. M2 §9.2 — obie domeny clusterowały się razem)." — teraz to odniesienie do M2 jest już nieaktualne (M2 nie robi analizy endpointów), więc wystarczy pierwsze zdanie z wyjaśnieniem dwustopniowej normalizacji.

---

### R4. Outliery M2 (57) vs ścieżka alternatywna M3 (498) — brak połączenia

**Sekcja:** M3 §9.1 i §11 (tabela porównawcza)

**Problem:** M2 §8 identyfikuje **57 outlierów procesowych** (rzadkie przejścia klastrów, mediana czasu 408 min). M3 §9.1 identyfikuje **498 przypadków** na ścieżce alternatywnej `Match patient data → timeout` (mediana 420 min). To te same zjawisko (długie przypadki ~400–420 min) ale z bardzo różnymi liczebnościami (57 vs 498) i różnymi definicjami.

Tabela porównawcza w §11 nie wspomina o outlierach wcale.

**Wyjaśnienie różnicy:**
- M2 wykrywa outliery metodą *rzadkich przejść klastrów* — tylko przypadki z przejściami całkowicie spoza głównego grafu (np. `K9 → K4`, `K4 → K9`). Progi są restrykcyjne.
- M3 liczy *wszystkie* przypadki z DFG-krawędzią `Match patient data → timeout` (498 przypadków, ~8% wszystkich), niezależnie od dalszej ścieżki.

**Co zrobić:** W §11 tabeli porównawczej lub w §9.1 dodać linijkę wyjaśniającą tę różnicę: „57 outlierów procesowych M2 (rzadkie przejścia sekwencji klastrów) to podzbiór 498 przypadków ścieżki alternatywnej M3 — M2 stosuje bardziej restrykcyjne kryterium strukturalne."

---

### R5. Drobna niespójność liczbowa — M3 §3.1

**Sekcja:** M3 §3.1 i §11

**Problem nieistotny, ale może być pytany:** Sekcja 3.1 mówi: „Dominuje ścieżka główna … (65% przypadków)." Sekcja 11 mówi: `is_main_variant: 66.9%` (tabela sekcji 7.2). Różnica 65% vs 66.9% — prawdopodobnie wynika z tego, że DFG jest budowany na 6 162 śladach, a proporcja 66.9% pochodzi z innego filtru. Mała niespójność, ale warto ujednolicić jedną cyfrę (66.9% jest bardziej precyzyjne, pochodzi z drzewa decyzyjnego na tym samym zbiorze).

---

## Podsumowanie priorytetów

| # | Problem | Ryzyko | Nakład pracy |
|---|---|---|---|
| R1 | Pętla na Match patient data — artefakt IMf | Średnie (pytanie prowadzącego) | Mały (jedno zdanie zastrzeżenia lub weryfikacja w notebooku) |
| R2 | Stary notebook endpoint w repozytorium | Małe (estetyczny) | Minimalny (git rm) |
| R3 | Niewyjaśniona normalizacja do 8 endpointów | Małe | Minimalny (jedno zdanie) |
| R4 | Brak połączenia M2 outlierów z M3 ścieżką alt. | Małe | Mały (jedno zdanie w §11) |
| R5 | 65% vs 66.9% — niespójna liczba wariantu gł. | Minimalne | Minimalne (edit jednej cyfry) |