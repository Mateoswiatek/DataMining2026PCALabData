W ramach projektu każda grupa powinna wybrać co najmniej jeden zestaw danych ze strony: https://zenodo.org/communities/iopt/ do szczegółowej analizy.

# Kamienie milowe

## Milestone 0 - PCR Lab Data
Przejrzenie zbioru danych https://zenodo.org/records/11617408 PCR Lab Data
Weryfikacja, czy nie będzie za proste, czy uda się coś sensownego z tego wyciągnąć.
W taki sposób, aby było możliwe zrealizowanie wszystkich milestone-ów.

## Milestone 1: Zrozumienie zbioru danych

opis zbioru danych i jego kontekstu (system, typ zdarzeń, liczba przypadków)
identyfikacja kluczowych atrybutów logu zdarzeń (case id, activity, timestamp, resource — które są, których brakuje)
analiza jakości danych (kompletność danych, brakujące wartości, duplikaty, niespójne timestampy, niespójne typy danych, itp.)
eksploracyjna analiza danych
podstawowe statystyki (liczba eventów, cases, activities)
podstawowe wizualizacje (timeline, distribution, frequency)

Wynik: raport + jupyter notebook (np. na Google Colab).

## Milestone 2: Eksploracja danych i analiza cech

przygotowanie lub wybór logu zdarzeń
czyszczenie i normalizacja danych
wykrywanie wartości odstających (outlierów),
analiza anomalii Isolation Forest / Local Outlier Factor / DBSCAN
redukcja wymiarowości PCA / t-SNE / UMAP
klasteryzacja / inne wizualizacje
analiza relacji między zdarzeniami
identyfikacja ciekawych wzorców, np. wzorce czasowe (zachowanie w porach dnia, dni tygodnia, sezonowość, heatmapa aktywności np. dzień tygodnia × godzina),
analiza częstości ścieżek, najczęstszych wariantów, porównanie grup przypadków
identyfikacja nietypowych zachowań, wykrywanie anomalii

Wynik: raport + jupyter notebook (np. na Google Colab).

## Milestone 3: Odkrywanie procesu i reguł

wygenerowanie modelu DFG (Directly-Follows Graph)
odkrycie modelu procesu odkrytego co najmniej dwoma różnymi algorytmami
analiza zgodności procesu z logiem
stworzenie końcowego modelu BPMN, zaproponować ulepszenia
odkrycie reguł decyzyjnych
analiza zasobów (sieci współpracy, obciążenie pracowników)
symulacja procesu, identyfikacja problemów / wąskich gardeł procesu
mini dashboard dla procesu

W raporcie końcowym należy także dokonać interpretacji procesu uwzględniającej:
co model mówi o analizowanym systemie
jakie są najczęstsze ścieżki procesu
gdzie pojawiają się opóźnienia
jakie mogą być potencjalne usprawnienia, wnioski i rekomendacje biznesowe

Wynik: raport z modelami procesu (ew. jupyter notebook)