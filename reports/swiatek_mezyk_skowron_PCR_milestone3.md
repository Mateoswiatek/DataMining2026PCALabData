# Milestone 3

- **Autorzy:** Mateusz Świątek, Maciej Mężyk, Patryk Skowron
- **Zbiór:** PCR Lab Data
- **Źródło:** [Zenodo #11617408](https://zenodo.org/records/11617408)
- **Notebook:** [`notebooks/03_m3_process_discovery.ipynb`](../notebooks/03_m3_process_discovery.ipynb)

---

## 1. Cel i zakres

Celem Milestone 3 jest odkrycie i analiza modelu procesu na podstawie logu zdarzeń PCR Lab:

1. Wygenerowanie DFG (Directly-Follows Graph) w wersji częstościowej i wydajnościowej.
2. Porównanie czterech algorytmów odkrywania modelu: Alpha Miner, Inductive Miner (IM), IMf, Heuristic Miner.
3. Analiza zgodności modeli z logiem (conformance checking).
4. Stworzenie modelu BPMN i propozycje usprawnień.
5. Odkrycie reguł decyzyjnych (drzewa decyzyjne).
6. Analiza zasobów (endpointy jako proxy mikrousług).
7. Identyfikacja wąskich gardeł i symulacja Monte Carlo.
8. Interaktywny dashboard HTML.

Pipeline: EventLog → DFG → odkrywanie modelu (×4) → conformance → BPMN → reguły → zasoby → symulacja → dashboard.

---

## 2. Dane i przygotowanie

- Dane wejściowe: `data/processed/pcr_events_biz.parquet` i `data/processed/pcr_cases.parquet`.
- Do odkrywania modelu używamy wyłącznie zdarzeń `complete`, czyli jednego punktu w czasie na aktywność, zgodnie ze standardem process mining.
- Do analizy zasobów używamy zdarzeń `start` (moment wywołania endpointu).

| Metryka | Wartość |
|---|---|
| Przypadki (process_type = sample) | 6 166 |
| Zdarzenia `complete` | 32 356 |
| Zdarzenia `start` | 51 209 |
| Unikalne aktywności | 8 |
| Warianty procesu | 47 |

### Konwersja do pm4py EventLog

DataFrame przetworzono przez `pm4py.format_dataframe()` z mapowaniem:
- `case_id = instance_uuid`, `activity_key = activity`, `timestamp_key = timestamp`

Wynikowy EventLog: 6 162 traces (4 przypadki bez zdarzeń `complete` pominięto).

---

## 3. DFG: Directly-Follows Graph

### 3.1 Frequency DFG

![Frequency DFG](../results/m3/fig_dfg_frequency.png)

Graf ma 28 łuków. Najczęstsze bezpośrednie następstwa:

| Aktywność źródłowa | Aktywność docelowa | Liczba |
|---|---|---:|
| Wait for plate validation | Receive sample state | 5 921 |
| Match patient data | Wait for plate validation | 5 444 |
| Receive sample state | Callback timeout | 4 990 |
| Callback timeout | timeout | 4 812 |
| timeout | Send notification | 1 229 |
| Match patient data | timeout | 498 |

Dominuje ścieżka główna: Match patient data → Wait for plate validation → Receive sample state → Callback timeout → timeout (65% przypadków). Łuk Match patient data → timeout (n=498) to alternatywna ścieżka pomijająca walidację płytki, prawdopodobnie próbki nieprzypisane do żadnej płytki lub przetwarzane w trybie awaryjnym.

### 3.2 Performance DFG

![Performance DFG](../results/m3/fig_dfg_performance.png)

Heatmapa pokazuje czas complete(A) → complete(B) w minutach, czyli czas od zakończenia aktywności A do zakończenia aktywności B w tym samym przypadku.

> Aktywności `timeout`, `Match patient data` i `Wait for plate validation` startują równocześnie (CPEE odpala je równolegle w ramach jednego przypadku). W przykładowym przypadku wszystkie trzy zdarzenia `start` mają timestamp `14:17:41`, `Match patient data` kończy się po ~6 sekundach, a `Wait for plate validation` po ~165 minutach. Wartość 162 min na krawędzi Match patient data → Wait for plate validation nie jest więc czasem oczekiwania między aktywnościami, tylko service time aktywności `Wait for plate validation` (czas procesowania PCR), który zaczął się równolegle.

| Przejście | Mediana [min] | n | Interpretacja |
|---|---:|---:|---|
| Match patient data → timeout (alt.) | 420 | 498 | Service time timeout na ścieżce alternatywnej |
| Receive sample state → timeout | 232 | 292 | Ścieżka alternatywna overnight |
| Match patient data → Wait for plate validation | **162** | **5 444** | ≈ service time WFPV (165 min), PCR processing |
| Wait for plate validation → Receive sample state | ~0 | 5 921 | Sekwencyjne, natychmiastowe |

Wniosek: bottleneck to fizyczny czas procesowania PCR (~165 min), a nie czas oczekiwania między aktywnościami. System już korzysta z równoległości, bo wszystkie kroki inicjalizacji startują jednocześnie. Jedyną drogą optymalizacji jest zmniejszenie rozmiaru partii płytek (mniejsza partia = krótszy czas do zakończenia).

---

## 4. Odkrywanie modelu procesu

### 4.1 Alpha Miner (kontrprzykład)

![Sieć Petriego: Alpha Miner](../results/m3/fig_petri_alpha.png)

| Właściwość | Wartość |
|---|---|
| Miejsca | 15 |
| Przejścia | 8 |
| Łuki | 41 |

Alpha Miner generuje uproszczoną sieć z 8 widzialnymi przejściami odpowiadającymi 8 aktywnościom. Model jest zbyt prosty: nie radzi sobie z pętlami (timeout powtarza się w procesie) i nie modeluje prawidłowo skipów ani alternatywnych ścieżek. Wynik conformance (fitness=0.51) potwierdza, że model nie opisuje rzeczywistego zachowania systemu.

> Alpha Miner zakłada acykliczny, skończony język, dlatego nie nadaje się do danych rzeczywistych. Pętle i zachowanie niedeterministyczne powodują brakujące miejsca w sieci Petriego (sieć nie jest sound), co uniemożliwia prawidłowy replay śladów.

### 4.2 Inductive Miner (IM)

![Sieć Petriego: Inductive Miner](../results/m3/fig_petri_im.png)

| Właściwość | Wartość |
|---|---|
| Miejsca | 21 |
| Przejścia | 28 |
| Łuki | 64 |

IM rekurencyjnie dzieli log na podlogi i buduje model gwarancyjnie sound (każdy ślad logu da się odtworzyć na modelu). Wynikowa sieć ma 28 przejść, z czego wiele to przejścia τ (ciche), modelujące pomijalne kroki. Fitness = 1.000 (idealna), ale bardzo niska precision (0.41) oznacza, że model jest zbyt ogólny: pozwala na wiele zachowań, których nie ma w logu.

### 4.3 Inductive Miner Infrequent (IMf, noise_threshold = 0.2)

![Sieć Petriego: IMf](../results/m3/fig_petri_imf.png)

| Właściwość | Wartość |
|---|---|
| Miejsca | 12 |
| Przejścia | 11 |
| Łuki | 26 |

IMf najpierw filtruje rzadkie zachowania (poniżej 20% częstości), a następnie stosuje Inductive Miner na oczyszczonym logu. Wynikowy model jest znacznie prostszy: 11 przejść wobec 28 w IM. Fitness spada do 0.96 (4.1% śladów nie przechodzi), ale precision rośnie do 0.70, a F1 = 0.806 to drugi wynik po Heuristic Minerze.

### 4.4 Heuristic Miner (dep_threshold = 0.5)

![Heuristic Net](../results/m3/fig_heuristic_net.png)
![Sieć Petriego: Heuristic Miner](../results/m3/fig_petri_hm.png)

| Właściwość | Wartość |
|---|---|
| Miejsca | 20 |
| Przejścia | 30 |
| Łuki | 69 |

Heuristic Miner buduje model na podstawie DFG z progami zależności (`dependency_threshold = 0.5`: łuk A→B uwzględniany, gdy `(A→B − B→A) / (A→B + B→A + 1) ≥ 0.5`). Daje najwyższy F1 = 0.967 (fitness=0.975, precision=0.959). Model wiernie odwzorowuje obserwowane zachowanie i nie jest przy tym zbyt restrykcyjny.

---

## 5. Analiza zgodności (Conformance Checking)

Conformance checking przeprowadzono metodą token-based replay (TBR): dla każdego śladu logu symulujemy wykonanie na sieci Petriego i zliczamy brakujące oraz nadmiarowe tokeny.

### 5.1 Tabela porównawcza

![Porównanie algorytmów](../results/m3/fig_conformance_comparison.png)

| Algorytm | Fitness | % pasujących tras | Precision | F1 | Miejsca | Przejścia |
|---|---:|---:|---:|---:|---:|---:|
| Alpha Miner | 0.506 | 0.8% | **1.000** | 0.672 | 15 | 8 |
| Inductive Miner (IM) | **1.000** | **100.0%** | 0.409 | 0.581 | 21 | 28 |
| IMf (noise=0.2) | 0.960 | 88.9% | 0.695 | 0.806 | 12 | 11 |
| **Heuristic Miner** | **0.975** | **73.1%** | **0.959** | **0.967** | 20 | 30 |

### 5.2 Interpretacja

Alpha Miner: fitness 0.506 oznacza, że połowa śladów wymaga "dostrzelenia" brakujących tokenów podczas replay. Precision wynosi 1.0, bo model jest tak restrykcyjny, że nie pozwala niemal na nic. W praktyce model jest niepoprawny (niespójny z danymi) i nie nadaje się do użycia produkcyjnego.

Inductive Miner (IM): idealna fitness (100% tras przechodzi), ale precision 0.41. Model jest zbyt liberalny, dopuszcza sekwencje aktywności, których nigdy nie obserwowano w danych. Nadaje się do weryfikacji formalnej poprawności, ale nie do opisu rzeczywistego procesu.

IMf: dobry kompromis, 88.9% tras pasuje, precision 0.70, F1 0.806. Uproszczony model (11 przejść) dobrze opisuje „normalne" zachowanie i ignoruje rzadkie warianty (<20%).

Heuristic Miner: najlepszy model dla tych danych (F1=0.967). Wiernie odwzorowuje rzeczywiste DFG i nie generalizuje nadmiernie. 73.1% śladów przechodzi token replay w pełni, a pozostałe 26.9% to ślady z nieoczekiwaną kolejnością aktywności (rare variants), które Heuristic Miner modeluje jako alternatywne ścieżki.

> Do analizy tego procesu najlepiej nadaje się Heuristic Miner. Log jest stosunkowo mało zaszumiony (47 wariantów, 65% przypadków na jednej ścieżce), co czyni go dobrym kandydatem dla algorytmu opartego bezpośrednio na DFG.

---

## 6. Model BPMN i propozycje usprawnień

### 6.1 BPMN z Heuristic Miner (najlepszy F1)

![BPMN](../results/m3/fig_bpmn.png)

Model BPMN wygenerowano z najlepszego modelu (Heuristic Miner, F1=0.967) przez konwersję Petri net → BPMN w pm4py. Kluczowe elementy:

Główna ścieżka (65% przypadków):
`Start → Match patient data → Wait for plate validation → Receive sample state → Callback timeout → timeout → End`

Ścieżki z eksportem (~13% przypadków, głównie próbki POSITIVE, patrz §7.2). Po `Receive sample state` możliwe gałęzie:
- `Export result → Export to EMS → Callback timeout`
- `Export to EMS → Export result → Callback timeout`
- `Export result → Callback timeout` (bez EMS)
- `Export to EMS → Callback timeout` (bez result)

Ścieżka z powiadomieniem:
`timeout → Send notification → (Wait for plate validation | Export to EMS | ...)`

### 6.2 BPMN z Inductive Miner (model blokowy)

![BPMN z Inductive Miner](../results/m3/fig_bpmn_im.png)

Inductive Miner zwraca drzewo procesu, które przekłada się wprost na BPMN. Wersja z filtrem rzadkich zachowań (IMf) daje czysty model blokowy z jawnymi bramkami: AND-split (+) inicjalizacji, XOR (×) dla powiadomienia i pętla (*) na `Match patient data`.

Co z tego modelu wynika:

- Proces jest równoległy, nie sekwencyjny: AND-split pokazuje, że `timeout`, łańcuch walidacji płytki i powiadomienie startują jednocześnie po `Match patient data`. To niezależnie potwierdza obserwację z §3.2 i tłumaczy, dlaczego 162 min to service time PCR, a nie czas oczekiwania w kolejce.
- Jedyna sekwencja krytyczna to `Wait for plate validation → Receive sample state → Callback timeout`. Reszta to równoległe gałęzie poboczne, więc wąskie gardło musi leżeć w tym łańcuchu (i leży: WFPV ~165 min, §9).
- Powiadomienie to realny wybór (XOR), a nie stały krok procesu.
- Pętla (*) na `Match patient data` oznacza, że część próbek przechodzi ponowną identyfikację (rework).
- Eksport nie pojawia się w tym modelu: IMf odfiltrował go jako rzadki (~13%), więc model opisuje „normalny" przebieg bez eksportu, a eksport jest wyjątkiem dla próbek dodatnich (patrz §6.3).

### 6.3 Bramka decyzyjna eksportu (XOR)

![Bramka XOR po Receive sample state: wynik PCR decyduje o gałęzi eksportu](../results/m3/fig_xor_decision.png)

Najważniejsza bramka rozgałęziająca to decyzja o eksporcie po `Receive sample state`: wynik POSITIVE kieruje próbkę do `Export to EMS`, ujemny ją pomija. Regułę wyprowadzamy z danych w §7.2 (86.9% gałęzi eksportu to próbki dodatnie).

### Propozycje usprawnień

1. Optymalizacja Wait for plate validation (~162 min mediany na ścieżce głównej). To główny bottleneck na ścieżce przetwarzania 88% przypadków. Płytka (wellplate) jest zapełniana próbkami, a walidacja następuje po zebraniu pełnej partii. Redukcja rozmiaru partii lub zwiększenie częstości uruchamiania walidacji mogłaby skrócić ten czas o 30–50%.

2. Równoległe wykonanie eksportów (AND-split). Export result, Export to EMS i Send notification są w danych wykonywane sekwencyjnie, choć logicznie mogą być równoległe (brak zależności danych między nimi). AND-split po `Receive sample state` skróciłby czas zakończenia przypadku o ~20–30 min dla ~13% próbek z eksportem.

3. SLA dla przypadków przekraczających 8 godzin. P95 czasu trwania wynosi ~19 godzin. Przypadki ze ścieżką alternatywną (Match patient data → timeout, mediana 420 min) są prawdopodobnie wstrzymane przez brak dostępnej płytki lub błąd systemu. Alert lub mechanizm priorytetu po przekroczeniu 8 godzin zmniejszyłby ich liczbę.

4. Optymalizacja konfiguracji timeout CPEE. Aktywność `timeout` to mechanizm kolejkowania silnika CPEE, który pojawia się na wszystkich ścieżkach jako ostatnia aktywność. Optymalizacja interwałów timeoutu może skrócić oczekiwanie w kolejce bez zmiany logiki procesowej.

5. Dedykowana ścieżka dla próbek pilnych. Dane nie zawierają priorytetu próbki. Wprowadzenie atrybutu `priority` pozwoliłoby kierować próbki pilne na ścieżkę pomijającą `Wait for plate validation` (np. na mniejszą płytkę testową lub do natychmiastowego procesowania).

---

## 7. Odkrycie reguł decyzyjnych

### 7.1 Predykcja wyniku PCR

![Drzewo decyzyjne: pcr_result](../results/m3/fig_dt_pcr_result.png)

Cechy: `duration_min`, `n_events`, `hour`, `dayofweek`. Cel: POSITIVE / NEGATIVE.

| Metryka | Wartość |
|---|---|
| Baseline (klasa wiodąca) | 0.530 |
| CV Accuracy (5-fold) | 0.645 ± 0.009 |

Model bije baseline o ~11 pp (CV 0.645 vs 0.530), ale głównie dzięki `n_events` (ważność 0.75, pozostałe cechy dokładają ~25%). Cechy niezależne od wyniku, czyli czas trwania, pora dnia i dzień tygodnia, są wobec wyniku płaskie (zgodnie z Milestone 1: mediana czasu 183 min dla POSITIVE vs 172 min dla NEGATIVE). Sygnał bierze się stąd, że `n_events` koduje obecność eksportu, a eksport zależy od wyniku (patrz §7.2). Wniosek: wyniku PCR nie da się przewidzieć z cech niezależnych od wyniku (czas, pora, dzień), ale jest on odzwierciedlony w strukturze procesu. Proces nie przewiduje wyniku, tylko na niego reaguje, uruchamiając dla próbek dodatnich gałąź raportującą.

### 7.2 Predykcja obecności eksportu

![Drzewo decyzyjne: has_export](../results/m3/fig_dt_variant.png)

Cechy: `duration_min`, `n_events`, `hour`, `dayofweek`, `pcr_binary`. Cel: czy przypadek zawiera aktywność eksportu (Export result / Export to EMS).

| Target | Prevalence | Baseline | CV Accuracy | Top cecha |
|---|---:|---:|---:|---|
| is_main_variant | 66.9% | 0.669 | 0.995 | n_events |
| has_export | 13.3% | 0.867 | 0.999 | n_events |
| has_notification | 20.1% | 0.799 | 0.980 | duration_min |

`n_events` przewiduje wszystkie trzy cele niemal idealnie (CV 0.98–0.999), ale to tautologia: każda dodatkowa aktywność (eksport, powiadomienie) zwiększa `n_events`, więc liczba zdarzeń z definicji koduje strukturę wariantu. To nie jest reguła biznesowa.

Co więc decyduje o gałęzi eksportu (bramka XOR)? Po usunięciu tautologicznego `n_events` widać, że eksport jest silnie powiązany z wynikiem PCR:

| Kierunek zależności | Wartość |
|---|---:|
| P(POSITIVE \| jest eksport) | 86.9% |
| P(eksport \| POSITIVE) | 24.7% |
| P(eksport \| NEGATIVE) | 3.3% |

Jeśli próbka ma eksport, jest niemal na pewno dodatnia (86.9%). Pozytywy są zgłaszane do systemu epidemiologicznego (EMS), ujemne prawie nigdy (24.7% vs 3.3%, czyli 7.5×). W drugą stronę zależność jest słabsza, bo eksportowanych jest tylko ~25% pozytywów. Wynik dodatni jest więc warunkiem niemal koniecznym eksportu, ale nie wystarczającym. O tym, które pozytywy trafiają do zgłoszenia, decyduje kryterium spoza logu (eksportowane mają wyższe ct, mediana 31 vs 25, czyli słabsze wiremie). To wyjaśnia §7.1: `n_events` koduje obecność eksportu, więc niesie częściowy sygnał o wyniku. Proces nie przewiduje wyniku, tylko na niego reaguje dodatkową gałęzią raportowania.

---

## 8. Analiza zasobów: endpointy jako proxy usług

> Log PCR Lab nie zawiera identyfikatorów zasobów (pracowników ani maszyn). Jako reprezentacji mikrousług CPEE używamy endpointów URL: każdy endpoint odpowiada konkretnej usłudze laboratoryjnej obsługiwanej przez silnik procesowy. Analiza pokazuje obciążenie poszczególnych serwisów i wzorce przekazywania pracy między nimi.

### 8.1 Obciążenie endpointów

![Obciążenie endpointów](../results/m3/fig_resource_workload.png)

Po normalizacji (collapse per-instance IDs silnika CPEE) uzyskano 8 unikalnych logicznych endpointów:

| Endpoint (skrót) | Wywołania | Dominujące aktywności |
|---|---:|---|
| `mygreschner.com//backend/corr` | ~23 000 | Match patient data, Receive sample state, Export result, … (12 aktywności) |
| `*/services/timeout` | ~15 000 | timeout, Callback timeout |
| `GET:cpee.org/.../receive` | ~7 000 | Wait for plate validation |
| `*/notifyall` | ~2 500 | Send notification |
| `*/pcheck` | ~2 000 | Check for unfinished Plates |
| `POST:cpee.org/.../send` | ~1 500 | Notify per wellplate subprocess |
| `cpee.org/flow/start/url` | ~400 | Spawn per sample flow |
| `cpee.org/engine/{id}/...` | ~200 | Abandon/Stop spawned sample |

`*/backend/corr` dominuje: obsługuje ponad 40% wszystkich wywołań i 12 różnych aktywności. To centralna usługa korelacji CPEE, hub systemu.

### 8.2 Macierz handover of work

![Macierz handover](../results/m3/fig_handover_matrix.png)

Macierz przedstawia liczbę przekazań pracy między endpointami (ile razy endpoint B bezpośrednio następuje po endpoincie A w ramach tego samego przypadku). Kluczowe obserwacje:

- `*/backend/corr` → `*/timeout`: największy przepływ. Po korelacji przypadek przechodzi do timeoutu (oczekiwanie na kolejny krok).
- `*/timeout` → `*/backend/corr`: powrót z timeoutu do korelacji. Pętla `timeout ↔ backend/corr` to rdzeń procesu.
- `GET:cpee.org/.../receive` → `*/backend/corr`: po odebraniu stanu płytki (Wait for plate validation → Receive sample state) następuje powrót do korelacji.
- `*/notifyall` i `*/pcheck` to endpointy liściowe z małą liczbą przekazań.

### 8.3 Sieć współpracy endpointów

![Sieć współpracy](../results/m3/fig_resource_network.png)

Sieć potwierdza centralną rolę `*/backend/corr`: łączy się z niemal wszystkimi innymi endpointami. Serwisy timeout tworzą wyraźną pętlę z korelatorem. Serwisy notyfikacji i sprawdzania płytek (`*/notifyall`, `*/pcheck`) to peryferyjne węzły z małą liczbą połączeń.

---

## 9. Analiza wąskich gardeł i symulacja Monte Carlo

### 9.1 Wąskie gardła

![Wąskie gardła](../results/m3/fig_bottlenecks.png)

| Przejście | Mediana [min] | n | Ocena |
|---|---:|---:|---|
| Match patient data → timeout (alt.) | 420 | 498 | Krytyczne |
| Receive sample state → timeout (alt.) | 232 | 292 | Krytyczne |
| **Match patient data → Wait for plate validation** | **162** | **5 444** | **Krytyczne (główna ścieżka)** |
| Send notification → Export to EMS | 285 | 55 | Wysokie |
| Export to EMS → timeout | 194 | 39 | Wysokie |

Najistotniejszy bottleneck to service time `Wait for plate validation` (~165 min, n=5 444). Jak pokazała analiza struktury procesu (sekcja 3.2), `Match patient data` i `Wait for plate validation` startują jednocześnie, więc wartość 162 min na krawędzi DFG to service time PCR, a nie czas oczekiwania w kolejce. To ograniczenie fizyczne (batchowy charakter procesu PCR), możliwe do zredukowania przez zmniejszenie rozmiaru partii.

Przejścia `→ timeout (alt.)` o ekstremalnych medianach (420, 232 min) to przypadki ze ścieżki alternatywnej: próbki, które po wstępnym przetworzeniu trafiają bezpośrednio do kolejki timeout zamiast do Wait for plate validation. Prawdopodobna przyczyna to brak dostępnej płytki w momencie przetwarzania, co skutkuje oczekiwaniem overnight.

### 9.2 Symulacja Monte Carlo

![Symulacja MC](../results/m3/fig_simulation.png)

Metodologia: 2 000 przebiegów. W każdym przebiegu losujemy wariant z rozkładu empirycznego, a dla każdego przejścia czas z rozkładu empirycznego (sampling bez zastępowania z obserwacji historycznych).

| Metryka | Symulacja | Rzeczywiste |
|---|---:|---:|
| Mediana [min] | 174.9 | 175.3 |
| Średnia [min] | 336.1 | 331.0 |
| P95 [min] | 1 228.4 | 1 148.5 |

Symulacja odtwarza medianę niemal idealnie (174.9 vs 175.3 min, błąd 0.2%) i dobrze przybliża średnią (336.1 vs 331.0 min). Rozkład jest prawostronnie skośny: większość przypadków kończy się w 100–300 min, ale długi ogon (overnight) przesuwa średnią do ~330 min.

Symulacja nieznacznie przeszacowuje P95 (1 228 vs 1 149 min, +7%): empiryczne samplowanie czasów przejść z długim ogonem (zdarzenia overnight) generuje w 2 000 przebiegach nieco więcej ekstremów niż w rzeczywistym logu. Model dobrze odwzorowuje tendencję centralną i nadaje się do planowania przepustowości. Dla pojedynczych ekstremów jest obarczony wariancją Monte Carlo (brak ustalonego ziarna oznacza, że wartości mogą się różnić między przebiegami).

Scenariusz optymalizacyjny: redukcja czasu `Match patient data → Wait for plate validation` z 162 do 60 minut (przez zmniejszenie partii płytek o 60%) przesunęłaby medianę czasu trwania z 175 do ~75 minut, czyli o 57%.

---

## 10. Mini Dashboard

Dashboard HTML dostępny w pliku [`results/m3/dashboard.html`](../results/m3/dashboard.html).

6 interaktywnych paneli:
1. Top 15 przejść DFG (częstość)
2. Rozkład czasu trwania przypadku
3. Top 10 wariantów procesu
4. Obciążenie endpointów
5. Wąskie gardła (mediana czasu przejścia)
6. Conformance: Fitness / Precision / F1 dla 4 algorytmów

---

## 11. Interpretacja procesu i wnioski

### Porównanie z procesem odkrytym w Milestone 2 (klasteryzacja)

Proces odkryto dwukrotnie: w M3 metodą process mining ze zdarzeń `complete` (8 aktywności biznesowych), a w M2 metodą klasteryzacji niskopoziomowego payloadu zdarzeń (12 klastrów K1–K12). Oba podejścia odtwarzają ten sam rdzeń procesu (zgodność klastrów z ground truth: purity 0.93):

| Aspekt | Proces ze zdarzeń (M3) | Proces z klastrów (M2) |
|---|---|---|
| Szkielet główny | Match → Wait for plate validation → Receive sample state → Callback timeout → timeout | K1 → K6 → K4 → K5 → K9 = timeout → Match → Wait → Receive → Callback (te same kroki) |
| Zakres | tylko proces `sample`: 8 aktywności, 6 166 przypadków | wszystkie typy procesu (sample + wellplate + orkiestracja): 28 aktywności, 6 339 przypadków |
| *Receive sample state* | jedna aktywność | rozbite na 3 klastry wg pozycji na płytce (K2/K5/K12, mediana 9/35/73) |
| Gałąź eksportu | modelowana jako bramka XOR | niewidoczna, bo `Export result`/`Export to EMS` mają tę samą sygnaturę argumentów (`pid,sampleid`) co `Match patient data` i zlewają się w klaster K6 |
| Kolejność `timeout` | ostatnia (sortowanie po `complete`) | pierwsza (sortowanie po `start`), bo te aktywności startują równolegle (patrz §3.2) |

Wniosek: klasteryzacja niskopoziomowa odtwarza rdzeń procesu i dodatkowo wydobywa strukturę przestrzenną (pozycja na płytce), ale nie widzi gałęzi raportujących (eksport), ponieważ różni je wyłącznie ground truth (wynik PCR) świadomie wykluczony z cech w M2. To granica metody: klastry pokazują, *jak* płynie proces, ale nie *dlaczego* się rozgałęzia. To drugie ujawnia dopiero reguła decyzyjna z §7.2 (wynik dodatni uruchamia eksport).

### Co model mówi o analizowanym systemie?

System PCR Lab to batchowy proces laboratoryjny zarządzany przez silnik procesowy CPEE. Każda próbka przechodzi przez standardową sekwencję kroków: identyfikacja pacjenta → oczekiwanie na kompletację płytki → odczyt wyniku PCR → opcjonalny eksport do systemów zewnętrznych → zamknięcie przypadku. System jest wysoce powtarzalny (65% przypadków na jednej ścieżce) i działa w przewidywalnym rytmie dobowym (pon.–pt., 11:00–21:00).

### Najczęstsze ścieżki procesu

| Wariant | Udział | Ścieżka |
|---|---:|---|
| **Główna** | **65.0%** | Match patient data → Wait for plate validation → Receive sample state → Callback timeout → timeout |
| Top 2 | 70.9% | j.w. + eksport (Export result / Export to EMS) |
| Top 10 | 92.8% | Wszystkie powyższe + warianty kolejności eksportów |

### Gdzie pojawiają się opóźnienia?

1. Wait for plate validation (~162 min): oczekiwanie na skompletowanie płytki 96-studzienkowej. To ograniczenie technologiczne procesu PCR, ale redukowalne przez zmniejszenie rozmiaru wsadu.
2. Ścieżka alternatywna, czyli brak płytki: 498 przypadków z przejściem Match patient data → timeout (mediana 420 min). Próbki bez przypisanej płytki czekają na kolejny cykl pracy laboratorium, często overnight.
3. Sekwencyjne eksporty: w ścieżkach pobocznych (~35% przypadków: eksport ~13%, powiadomienie ~20%) aktywności Export result / Export to EMS / Send notification są wykonywane sekwencyjnie, choć mogłyby być równoległe.

### Rekomendacje biznesowe

| Rekomendacja | Wpływ | Trudność |
|---|---|---|
| Zmniejszenie rozmiaru partii płytek (96 → 48) | −50% mediany czasu na głównej ścieżce | Średnia |
| Równoległość eksportów (AND-split) | −20–30 min na ~13% przypadków z eksportem | Niska |
| SLA 8h + alert dla wstrzymanych próbek | Eliminacja outlierów overnight | Niska |
| Priorytetyzacja próbek pilnych | Skrócenie P95 | Wysoka |
| Optymalizacja timeout CPEE | Redukcja overhead kolejkowania | Niska |

### Ograniczenia analizy

- Brak zasobów w logu: analizujemy endpointy zamiast pracowników czy urządzeń, więc nie można ocenić obciążenia personelu.
- Brak atrybutu priorytetu próbki: nie można odróżnić próbek rutynowych od pilnych.
- Zewnętrzny kontekst raportowania: gałąź eksportu jest sterowana wynikiem PCR (POSITIVE → EMS, §7.2), ale log nie tłumaczy wyjątków (3.3% próbek ujemnych również eksportowanych) ani kolejności samych eksportów. Zależy to od konfiguracji zewnętrznego systemu raportowania.
- Dane z jednego okresu (kwiecień–czerwiec 2023): wzorce mogą różnić się między szczytem pandemii a normalną pracą laboratorium.
