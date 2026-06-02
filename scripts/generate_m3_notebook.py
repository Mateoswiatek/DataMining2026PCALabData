#!/usr/bin/env python3
"""Generates notebooks/03_m3_process_discovery.ipynb"""

import json
from pathlib import Path

ROOT   = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'notebooks' / '03_m3_process_discovery.ipynb'


def code(src):
    return {'cell_type': 'code', 'execution_count': None,
            'metadata': {}, 'outputs': [], 'source': src}

def md(src):
    return {'cell_type': 'markdown', 'metadata': {}, 'source': src}


cells = []

# ── 0  Title ──────────────────────────────────────────────────────────────
cells.append(md(
"# Milestone 3 — Odkrywanie procesu i reguł\n"
"**PCR Lab Data** | 6 166 przypadków Sample | Process Mining z pm4py\n\n"
"1. Ładowanie danych i konwersja do EventLog\n"
"2. DFG (Directly-Follows Graph) — częstość i wydajność\n"
"3. Odkrywanie modelu: Alpha Miner · Inductive Miner · IMf · Heuristic Miner\n"
"4. Conformance Checking — token-based replay\n"
"5. Model BPMN + propozycje usprawnień\n"
"6. Reguły decyzyjne (sklearn Decision Tree)\n"
"7. Analiza zasobów — endpointy jako proxy usług\n"
"8. Wąskie gardła i symulacja Monte Carlo\n"
"9. Mini Dashboard HTML (Plotly)"
))

# ── 1  Imports ─────────────────────────────────────────────────────────────
cells.append(code(
"from pathlib import Path\n"
"import re\n"
"import warnings\n"
"\n"
"import numpy as np\n"
"import pandas as pd\n"
"import matplotlib.pyplot as plt\n"
"import matplotlib.patches as mpatches\n"
"import seaborn as sns\n"
"import networkx as nx\n"
"import plotly.graph_objects as go\n"
"from plotly.subplots import make_subplots\n"
"import pm4py\n"
"from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree\n"
"from sklearn.metrics import accuracy_score\n"
"from sklearn.model_selection import cross_val_score\n"
"\n"
"warnings.filterwarnings('ignore')\n"
"\n"
"ROOT = Path('.').resolve()\n"
"if ROOT.name == 'notebooks':\n"
"    ROOT = ROOT.parent\n"
"\n"
"PROCESSED_DIR = ROOT / 'data' / 'processed'\n"
"RESULTS_DIR   = ROOT / 'results' / 'm3'\n"
"RESULTS_DIR.mkdir(parents=True, exist_ok=True)\n"
"\n"
"RANDOM_STATE = 42\n"
"plt.rcParams['figure.dpi']     = 120\n"
"plt.rcParams['figure.figsize'] = (12, 6)\n"
"sns.set_style('whitegrid')\n"
"\n"
"print(f'pm4py {pm4py.__version__}')\n"
"print(f'Wyniki -> {RESULTS_DIR}')"
))

# ── 2  Data loading ────────────────────────────────────────────────────────
cells.append(md("## 1. Ładowanie i przygotowanie danych"))

cells.append(code(
"df_events = pd.read_parquet(PROCESSED_DIR / 'pcr_events_biz.parquet')\n"
"df_cases  = pd.read_parquet(PROCESSED_DIR / 'pcr_cases.parquet')\n"
"\n"
"sample_ids      = set(df_cases[df_cases['process_type'] == 'sample']['instance_uuid'])\n"
"df_ev_sample    = df_events[df_events['instance_uuid'].isin(sample_ids)].copy()\n"
"df_complete     = df_ev_sample[df_ev_sample['lifecycle'] == 'complete'].copy()\n"
"df_start_ev     = df_ev_sample[df_ev_sample['lifecycle'] == 'start'].copy()\n"
"df_cases_sample = df_cases[df_cases['process_type'] == 'sample'].copy()\n"
"\n"
"print(f'Przypadki Sample:     {len(sample_ids):>6,}')\n"
"print(f'Zdarzenia (lacznie):  {len(df_ev_sample):>6,}')\n"
"print(f'  lifecycle=complete: {len(df_complete):>6,}')\n"
"print(f'  lifecycle=start:    {len(df_start_ev):>6,}')\n"
"print(f'Unikalne aktywnosci:  {df_complete[\"activity\"].nunique():>6}')\n"
"print(f'\\nRozklad aktywnosci (complete):')\n"
"print(df_complete['activity'].value_counts().to_string())"
))

# ── 3  DFG header ──────────────────────────────────────────────────────────
cells.append(md(
"## 2. DFG — Directly-Follows Graph\n\n"
"- **Frequency DFG**: jak często aktywność A jest bezpośrednio poprzedzona przez B\n"
"- **Performance DFG**: mediana czasu przejścia między zdarzeniami complete\n\n"
"Wizualizacja przez networkx/matplotlib — brak zależności od systemowego graphviz."
))

# ── 4  DFG helpers ─────────────────────────────────────────────────────────
cells.append(code(
"def compute_dfg(df, case_col='instance_uuid', act_col='activity', ts_col='timestamp'):\n"
"    df = df.sort_values([case_col, ts_col]).copy()\n"
"    df['_next'] = df.groupby(case_col)[act_col].shift(-1)\n"
"    pairs = df.dropna(subset=['_next'])\n"
"    dfg   = {(a, b): int(cnt) for (a, b), cnt\n"
"             in pairs.groupby([act_col, '_next']).size().items()}\n"
"    starts = df.groupby(case_col).first()[act_col].value_counts().to_dict()\n"
"    ends   = df.groupby(case_col).last()[act_col].value_counts().to_dict()\n"
"    return dfg, starts, ends\n"
"\n"
"\n"
"def plot_dfg_mpl(dfg, start_acts=None, end_acts=None,\n"
"                 title='DFG', min_freq=50, figsize=(14, 8), save_path=None):\n"
"    dfg_f = {k: v for k, v in dfg.items() if v >= min_freq}\n"
"    G = nx.DiGraph()\n"
"    for (s, t), w in dfg_f.items():\n"
"        G.add_edge(s, t, weight=w)\n"
"    if G.number_of_nodes() == 0:\n"
"        print('Brak krawedzi po filtrowaniu.')\n"
"        return None\n"
"\n"
"    try:\n"
"        from networkx.drawing.nx_agraph import graphviz_layout\n"
"        pos = graphviz_layout(G, prog='dot', args='-Grankdir=LR')\n"
"    except Exception:\n"
"        pos = nx.spring_layout(G, k=2.8, seed=42)\n"
"\n"
"    weights  = [G[u][v]['weight'] for u, v in G.edges()]\n"
"    max_w    = max(weights)\n"
"    widths   = [0.8 + 5.0 * (w / max_w) ** 0.55 for w in weights]\n"
"    e_colors = [plt.cm.YlOrRd(0.25 + 0.75 * (w / max_w) ** 0.5) for w in weights]\n"
"\n"
"    node_in = {n: sum(G[u][v]['weight'] for u, v in G.in_edges(n)) for n in G.nodes()}\n"
"    max_nf  = max(node_in.values()) if node_in else 1\n"
"    node_colors = []\n"
"    for n in G.nodes():\n"
"        if start_acts and n in start_acts:\n"
"            node_colors.append('#27ae60')\n"
"        elif end_acts and n in end_acts:\n"
"            node_colors.append('#e74c3c')\n"
"        else:\n"
"            node_colors.append(plt.cm.Blues(0.28 + 0.65 * (node_in.get(n, 0) / max_nf) ** 0.5))\n"
"\n"
"    fig, ax = plt.subplots(figsize=figsize)\n"
"    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors,\n"
"                           node_size=3200, node_shape='s', alpha=0.93)\n"
"    nx.draw_networkx_labels(G, pos, ax=ax, font_size=7.5, font_weight='bold',\n"
"                            labels={n: n.replace(' ', '\\n') for n in G.nodes()})\n"
"    nx.draw_networkx_edges(G, pos, ax=ax, width=widths, edge_color=e_colors,\n"
"                           alpha=0.82, arrows=True, arrowsize=22,\n"
"                           connectionstyle='arc3,rad=0.06',\n"
"                           min_source_margin=28, min_target_margin=28)\n"
"    threshold = sorted(weights, reverse=True)[min(5, len(weights) - 1)]\n"
"    edge_labels = {(u, v): f\"{G[u][v]['weight']:,}\"\n"
"                   for u, v in G.edges() if G[u][v]['weight'] >= threshold}\n"
"    nx.draw_networkx_edge_labels(G, pos, edge_labels, ax=ax, font_size=6.5, alpha=0.9)\n"
"\n"
"    handles = [\n"
"        mpatches.Patch(color='#27ae60', label='Aktywnosc startowa'),\n"
"        mpatches.Patch(color='#e74c3c', label='Aktywnosc koncowa'),\n"
"        mpatches.Patch(color=plt.cm.Blues(0.7), label='Pozostale'),\n"
"    ]\n"
"    ax.legend(handles=handles, loc='upper left', fontsize=8)\n"
"    ax.set_title(title, fontsize=13, fontweight='bold', pad=12)\n"
"    ax.axis('off')\n"
"    plt.tight_layout()\n"
"    if save_path:\n"
"        fig.savefig(save_path, dpi=120, bbox_inches='tight')\n"
"    return fig"
))

# ── 5  Frequency DFG ───────────────────────────────────────────────────────
cells.append(code(
"dfg_freq, start_acts, end_acts = compute_dfg(df_complete)\n"
"\n"
"print(f'Luki DFG (wszystkie):  {len(dfg_freq)}')\n"
"print(f'Luki DFG (freq >= 50): {sum(1 for v in dfg_freq.values() if v >= 50)}')\n"
"print('\\nTop 15 przejsc:')\n"
"for (s, t), cnt in sorted(dfg_freq.items(), key=lambda x: -x[1])[:15]:\n"
"    print(f'  {s:35s} -> {t:35s}: {cnt:,}')\n"
"\n"
"fig_dfg = plot_dfg_mpl(\n"
"    dfg_freq, start_acts, end_acts,\n"
"    title='DFG — czestotliwosc przejsc (min_freq=50), PCR Lab Sample',\n"
"    min_freq=50, figsize=(14, 9),\n"
"    save_path=RESULTS_DIR / 'fig_dfg_frequency.png',\n"
")\n"
"plt.show()"
))

# ── 6  Activity service times + Performance DFG ────────────────────────────
cells.append(code(
"# Czasy aktywnosci: start -> complete\n"
"df_s = df_start_ev.groupby(['instance_uuid', 'activity'])['timestamp'].first()\n"
"df_c = df_complete.groupby(['instance_uuid', 'activity'])['timestamp'].first()\n"
"common = df_s.index.intersection(df_c.index)\n"
"dur_s  = (df_c.loc[common] - df_s.loc[common]).dt.total_seconds()\n"
"dur_s  = dur_s[(dur_s >= 0) & (dur_s < 86400)]\n"
"df_act_dur = dur_s.reset_index()\n"
"df_act_dur.columns = ['instance_uuid', 'activity', 'duration_s']\n"
"\n"
"stats = (df_act_dur.groupby('activity')['duration_s']\n"
"         .agg(n='count', median_s='median', mean_s='mean')\n"
"         .assign(median_min=lambda x: (x['median_s'] / 60).round(2))\n"
"         .sort_values('median_s', ascending=False))\n"
"print('Czasy aktywnosci (start->complete):')\n"
"print(stats.to_string())\n"
"\n"
"# Performance DFG\n"
"df_perf = df_complete.sort_values(['instance_uuid', 'timestamp']).copy()\n"
"df_perf['_next_act'] = df_perf.groupby('instance_uuid')['activity'].shift(-1)\n"
"df_perf['_next_ts']  = df_perf.groupby('instance_uuid')['timestamp'].shift(-1)\n"
"df_perf = df_perf.dropna(subset=['_next_act', '_next_ts']).copy()\n"
"df_perf['_dur_s'] = (df_perf['_next_ts'] - df_perf['timestamp']).dt.total_seconds()\n"
"df_perf = df_perf[df_perf['_dur_s'] >= 0]\n"
"\n"
"perf_dfg_df = (df_perf.groupby(['activity', '_next_act'])['_dur_s']\n"
"               .agg(median='median', mean='mean', count='count')\n"
"               .reset_index())\n"
"\n"
"pivot_min = perf_dfg_df.pivot(index='activity', columns='_next_act', values='median').fillna(0) / 60\n"
"fig_perf, ax = plt.subplots(figsize=(13, 7))\n"
"sns.heatmap(pivot_min, annot=True, fmt='.0f', cmap='YlOrRd', ax=ax,\n"
"            cbar_kws={'label': 'mediana [min]'})\n"
"ax.set_title('Performance DFG — mediana czasu przejscia [min]', fontsize=13, fontweight='bold')\n"
"ax.set_xlabel('Aktywnosc nastepna')\n"
"ax.set_ylabel('Aktywnosc poprzednia')\n"
"plt.xticks(rotation=35, ha='right')\n"
"plt.yticks(rotation=0)\n"
"plt.tight_layout()\n"
"fig_perf.savefig(RESULTS_DIR / 'fig_dfg_performance.png', dpi=120, bbox_inches='tight')\n"
"plt.show()\n"
"\n"
"print('\\nTop 8 najdluzszych przejsc (mediana):')\n"
"top_perf = perf_dfg_df.nlargest(8, 'median').copy()\n"
"top_perf['median_min'] = (top_perf['median'] / 60).round(1)\n"
"print(top_perf[['activity', '_next_act', 'median_min', 'count']].to_string(index=False))"
))

# ── 7  Process discovery header ────────────────────────────────────────────
cells.append(md(
"## 3. Odkrywanie modelu procesu\n\n"
"| Algorytm | Charakterystyka |\n"
"|---|---|\n"
"| **Alpha Miner** | Klasyczny (1987), kontrprzykład — problemy z petlami, brakujace miejsca |\n"
"| **Inductive Miner (IM)** | Gwarancja soundness, model blokowy, rekurencyjne dzielenie logu |\n"
"| **IMf** (IM Infrequent) | Jak IM + filtrowanie rzadkich sciezek — czystszy model |\n"
"| **Heuristic Miner** | Oparty na DFG z progami czestosci, najlepszy dla danych z szumem |"
))

# ── 8  pm4py EventLog ──────────────────────────────────────────────────────
cells.append(code(
"df_pm = pm4py.format_dataframe(\n"
"    df_complete.copy(),\n"
"    case_id='instance_uuid',\n"
"    activity_key='activity',\n"
"    timestamp_key='timestamp',\n"
")\n"
"log = pm4py.convert_to_event_log(df_pm)\n"
"\n"
"print(f'EventLog: {len(log)} traces, {sum(len(t) for t in log):,} events')\n"
"print('Przykladowy trace (pierwsze 5 zdarzen):')\n"
"for ev in list(log[0])[:5]:\n"
"    print(f'  {ev[\"concept:name\"]}')"
))

# ── 9  Helper: visualize Petri net ─────────────────────────────────────────
cells.append(code(
"def show_petri(net, im, fm, name, fname):\n"
"    print(f'  Miejsca: {len(net.places)}, Przejscia: {len(net.transitions)}, Luki: {len(net.arcs)}')\n"
"    try:\n"
"        from pm4py.visualization.petri_net import visualizer as pn_viz\n"
"        gviz = pn_viz.apply(net, im, fm, parameters={'format': 'png'})\n"
"        pn_viz.save(gviz, str(RESULTS_DIR / fname))\n"
"        from IPython.display import Image, display\n"
"        display(Image(str(RESULTS_DIR / fname)))\n"
"    except Exception as e:\n"
"        print(f'  [Graphviz niedostepny: {e}]')\n"
"        visible = [t.label for t in net.transitions if t.label]\n"
"        print(f'  Przejscia widzialne: {visible}')"
))

# ── 10  Alpha Miner ────────────────────────────────────────────────────────
cells.append(code(
"print('=== Alpha Miner ===')\n"
"net_alpha, im_alpha, fm_alpha = pm4py.discover_petri_net_alpha(log)\n"
"show_petri(net_alpha, im_alpha, fm_alpha, 'Alpha Miner', 'fig_petri_alpha.png')"
))

# ── 11  Inductive Miner ────────────────────────────────────────────────────
cells.append(code(
"print('=== Inductive Miner (IM) ===')\n"
"net_im, im_im, fm_im = pm4py.discover_petri_net_inductive(log)\n"
"show_petri(net_im, im_im, fm_im, 'IM', 'fig_petri_im.png')"
))

# ── 12  IMf ────────────────────────────────────────────────────────────────
cells.append(code(
"NOISE = 0.2\n"
"print(f'=== Inductive Miner Infrequent (IMf, noise={NOISE}) ===')\n"
"net_imf, im_imf, fm_imf = pm4py.discover_petri_net_inductive(log, noise_threshold=NOISE)\n"
"print(f'  IM:  {len(net_im.places)} miejsc, {len(net_im.transitions)} przejsc')\n"
"print(f'  IMf: {len(net_imf.places)} miejsc, {len(net_imf.transitions)} przejsc')\n"
"show_petri(net_imf, im_imf, fm_imf, 'IMf', 'fig_petri_imf.png')"
))

# ── 13  Heuristic Miner ────────────────────────────────────────────────────
cells.append(code(
"print('=== Heuristic Miner (dep=0.5) ===')\n"
"heu_net = pm4py.discover_heuristics_net(log, dependency_threshold=0.5,\n"
"                                         and_threshold=0.65, loop_two_threshold=0.5)\n"
"net_hm, im_hm, fm_hm = None, None, None\n"
"try:\n"
"    net_hm, im_hm, fm_hm = pm4py.convert_to_petri_net(heu_net)\n"
"    show_petri(net_hm, im_hm, fm_hm, 'HM', 'fig_petri_hm.png')\n"
"except Exception as e:\n"
"    print(f'  Konwersja HM->Petri: {e}')\n"
"\n"
"try:\n"
"    from pm4py.visualization.heuristics_net import visualizer as hn_viz\n"
"    gviz = hn_viz.apply(heu_net, parameters={'format': 'png'})\n"
"    hn_viz.save(gviz, str(RESULTS_DIR / 'fig_heuristic_net.png'))\n"
"    from IPython.display import Image, display\n"
"    display(Image(str(RESULTS_DIR / 'fig_heuristic_net.png')))\n"
"except Exception as e:\n"
"    print(f'  [HN viz: {e}]')"
))

# ── 14  Conformance header ─────────────────────────────────────────────────
cells.append(md(
"## 4. Analiza zgodności (Conformance Checking)\n\n"
"**Token-based replay**: symuluje wykonanie każdego śladu na sieci Petriego.\n"
"- **Fitness**: czy log pasuje do modelu (1.0 = wszystkie ślady pasują)\n"
"- **Precision**: czy model nie jest zbyt ogólny (1.0 = model nie pozwala na nic poza logiem)\n"
"- **F1**: harmoniczna średnia Fitness i Precision"
))

# ── 15  Conformance ────────────────────────────────────────────────────────
cells.append(code(
"models = {\n"
"    'Alpha Miner':     (net_alpha, im_alpha, fm_alpha),\n"
"    'Inductive (IM)':  (net_im,    im_im,    fm_im),\n"
"    'IMf (noise=0.2)': (net_imf,   im_imf,   fm_imf),\n"
"}\n"
"if net_hm is not None:\n"
"    models['Heuristic Miner'] = (net_hm, im_hm, fm_hm)\n"
"\n"
"rows = []\n"
"for name, (net, im, fm) in models.items():\n"
"    print(f'  {name} ...', end=' ', flush=True)\n"
"    try:\n"
"        fit  = pm4py.fitness_token_based_replay(log, net, im, fm)\n"
"        prec = pm4py.precision_token_based_replay(log, net, im, fm)\n"
"        fv   = fit.get('average_trace_fitness', fit.get('log_fitness', float('nan')))\n"
"        pct  = fit.get('percentage_of_fitting_traces', float('nan'))\n"
"        f1   = 2 * fv * prec / (fv + prec) if (fv + prec) > 0 else 0\n"
"        rows.append({'Algorytm': name, 'Fitness': round(fv, 4),\n"
"                     '% pasujacych tras': round(pct, 1),\n"
"                     'Precision': round(prec, 4), 'F1': round(f1, 4),\n"
"                     'Miejsca': len(net.places), 'Przejscia': len(net.transitions)})\n"
"        print('OK')\n"
"    except Exception as e:\n"
"        print(f'BLAD: {e}')\n"
"\n"
"df_conform = pd.DataFrame(rows)\n"
"print()\n"
"print(df_conform.to_string(index=False))\n"
"\n"
"fig_cf, axes = plt.subplots(1, 3, figsize=(14, 5))\n"
"colors_cf = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12']\n"
"for i, metric in enumerate(['Fitness', 'Precision', 'F1']):\n"
"    vals = df_conform[metric].fillna(0)\n"
"    bars = axes[i].bar(df_conform['Algorytm'], vals, color=colors_cf[:len(df_conform)])\n"
"    axes[i].set_ylim(0, 1.12)\n"
"    axes[i].set_title(metric, fontweight='bold')\n"
"    axes[i].tick_params(axis='x', rotation=20)\n"
"    axes[i].axhline(1.0, color='gray', linestyle='--', alpha=0.4)\n"
"    for bar, val in zip(bars, vals):\n"
"        axes[i].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,\n"
"                     f'{val:.3f}', ha='center', va='bottom', fontsize=9, fontweight='bold')\n"
"plt.suptitle('Porownanie algorytmow — Fitness, Precision, F1', fontsize=13, fontweight='bold')\n"
"plt.tight_layout()\n"
"fig_cf.savefig(RESULTS_DIR / 'fig_conformance_comparison.png', dpi=120, bbox_inches='tight')\n"
"plt.show()"
))

# ── 16  BPMN ──────────────────────────────────────────────────────────────
cells.append(md("## 5. Model BPMN i propozycje usprawnień"))

cells.append(code(
"best_name = df_conform.loc[df_conform['F1'].idxmax(), 'Algorytm']\n"
"best_net, best_im, best_fm = models[best_name]\n"
"print(f'Najlepszy model: {best_name}')\n"
"\n"
"try:\n"
"    bpmn_graph = pm4py.convert_to_bpmn(best_net, best_im, best_fm)\n"
"    try:\n"
"        from pm4py.visualization.bpmn import visualizer as bpmn_viz\n"
"        gviz = bpmn_viz.apply(bpmn_graph, parameters={'format': 'png'})\n"
"        bpmn_viz.save(gviz, str(RESULTS_DIR / 'fig_bpmn.png'))\n"
"        from IPython.display import Image, display\n"
"        display(Image(str(RESULTS_DIR / 'fig_bpmn.png')))\n"
"    except Exception as e:\n"
"        nodes_cnt = len(list(bpmn_graph.get_nodes()))\n"
"        flows_cnt = len(list(bpmn_graph.get_flows()))\n"
"        print(f'  BPMN: {nodes_cnt} wezlow, {flows_cnt} przeplywow')\n"
"        print(f'  [Wizualizacja: {e}]')\n"
"except Exception as e:\n"
"    print(f'Konwersja BPMN: {e}')\n"
"\n"
"print('''\n"
"=== PROPOZYCJE USPRAWNIENIA PROCESU ===\n"
"\n"
"1. Optymalizacja Wait for plate validation (~165 min mediana):\n"
"   Zmniejszenie rozmiaru partii plytek lub zwiekszenie czestosci\n"
"   walidacji moze skrocic ten czas o 30-50%.\n"
"\n"
"2. Rownolegle wykonanie eksportow (AND-split):\n"
"   Export result, Export to EMS i Send notification moga byc\n"
"   wykonywane rownolegle — oszczednosc ~20-30 min/przypadek.\n"
"\n"
"3. SLA dla przypadkow przekraczajacych 8h:\n"
"   ~0.5% przypadkow (outliers z M2) czeka ponad 7h.\n"
"   Alert lub priorytet dla wstrzymanych prob.\n"
"\n"
"4. Redukcja overhead timeout CPEE:\n"
"   Aktywnosc timeout to mechanizm kolejkowania (~175 min mediana).\n"
"   Optymalizacja konfiguracji silnika CPEE.\n"
"''')"
))

# ── 17  Decision rules header ──────────────────────────────────────────────
cells.append(md(
"## 6. Odkrycie reguł decyzyjnych\n\n"
"1. **Predykcja wyniku PCR** — czy cechy procesu determinują POSITIVE/NEGATIVE?\n"
"2. **Predykcja wariantu** — co determinuje obecność aktywności eksportu?"
))

# ── 18  Feature engineering ────────────────────────────────────────────────
cells.append(code(
"df_sorted_c = df_complete.sort_values(['instance_uuid', 'timestamp'])\n"
"traces = (df_sorted_c.groupby('instance_uuid')['activity']\n"
"          .apply(lambda x: ' -> '.join(x))\n"
"          .reset_index()\n"
"          .rename(columns={'activity': 'trace'}))\n"
"\n"
"variant_counts = traces['trace'].value_counts()\n"
"main_variant   = variant_counts.index[0]\n"
"print(f'Wariantow: {len(variant_counts)}')\n"
"print(f'Top wariant ({variant_counts.iloc[0]} przypadkow, '\n"
"      f'{100*variant_counts.iloc[0]/len(traces):.1f}%):')\n"
"print(f'  {main_variant[:120]}')\n"
"\n"
"feat = df_cases_sample.merge(traces, on='instance_uuid', how='left')\n"
"feat['hour']            = feat['first_ts'].dt.hour\n"
"feat['dayofweek']       = feat['first_ts'].dt.dayofweek\n"
"feat['is_main_variant'] = (feat['trace'] == main_variant).astype(int)\n"
"feat['has_export']      = feat['trace'].str.contains('Export', na=False).astype(int)\n"
"feat['has_notification']= feat['trace'].str.contains('Send notification', na=False).astype(int)\n"
"feat['pcr_binary']      = (feat['pcr_result'] == 'POSITIVE').astype(int)\n"
"\n"
"feat_clean = feat.dropna(subset=['duration_min', 'pcr_result']).copy()\n"
"print(f'Cases z pelna informacja: {len(feat_clean):,}')\n"
"print(f'Udzial is_main_variant:  {feat_clean[\"is_main_variant\"].mean():.1%}')\n"
"print(f'Udzial has_export:       {feat_clean[\"has_export\"].mean():.1%}')\n"
"print(f'Udzial has_notification: {feat_clean[\"has_notification\"].mean():.1%}')"
))

# ── 19  DT pcr_result ─────────────────────────────────────────────────────
cells.append(code(
"FEAT1 = ['duration_min', 'n_events', 'hour', 'dayofweek']\n"
"X1, y1 = feat_clean[FEAT1], feat_clean['pcr_binary']\n"
"\n"
"dt_pcr = DecisionTreeClassifier(max_depth=4, min_samples_leaf=50, random_state=RANDOM_STATE)\n"
"cv1    = cross_val_score(dt_pcr, X1, y1, cv=5, scoring='accuracy')\n"
"dt_pcr.fit(X1, y1)\n"
"\n"
"print('=== Drzewo: predykcja pcr_result ===')\n"
"print(f'Baseline (klasa wiodaca):  {max(y1.mean(), 1 - y1.mean()):.3f}')\n"
"print(f'CV Accuracy (5-fold):      {cv1.mean():.3f} +/- {cv1.std():.3f}')\n"
"print('Waznosc cech:')\n"
"for n, imp in sorted(zip(FEAT1, dt_pcr.feature_importances_), key=lambda x: -x[1]):\n"
"    print(f'  {n:<20}: {imp:.4f}')\n"
"print('\\nWniosek: wynik PCR nie jest predykowalny z cech procesu.')\n"
"print('Potwierdza findings M1 — czas i przebieg niezalezne od wyniku.')\n"
"\n"
"fig_dt1, ax = plt.subplots(figsize=(14, 6))\n"
"plot_tree(dt_pcr, feature_names=FEAT1, class_names=['NEGATIVE', 'POSITIVE'],\n"
"          filled=True, rounded=True, ax=ax, fontsize=8, max_depth=3)\n"
"ax.set_title('Drzewo decyzyjne: predykcja pcr_result', fontweight='bold')\n"
"plt.tight_layout()\n"
"fig_dt1.savefig(RESULTS_DIR / 'fig_dt_pcr_result.png', dpi=120, bbox_inches='tight')\n"
"plt.show()"
))

# ── 20  DT variant ────────────────────────────────────────────────────────
cells.append(code(
"FEAT2 = ['duration_min', 'n_events', 'hour', 'dayofweek', 'pcr_binary']\n"
"X2    = feat_clean[FEAT2]\n"
"\n"
"for tgt_name, tgt_col in [('is_main_variant', 'is_main_variant'),\n"
"                           ('has_export',      'has_export'),\n"
"                           ('has_notification','has_notification')]:\n"
"    y2  = feat_clean[tgt_col]\n"
"    dt2 = DecisionTreeClassifier(max_depth=4, min_samples_leaf=30, random_state=RANDOM_STATE)\n"
"    cv2 = cross_val_score(dt2, X2, y2, cv=5)\n"
"    dt2.fit(X2, y2)\n"
"    top = FEAT2[dt2.feature_importances_.argmax()]\n"
"    base= max(y2.mean(), 1 - y2.mean())\n"
"    print(f'{tgt_name:25s}  base={base:.3f}  CV={cv2.mean():.3f}+/-{cv2.std():.3f}  top_feat={top}')\n"
"\n"
"y_exp  = feat_clean['has_export']\n"
"dt_exp = DecisionTreeClassifier(max_depth=4, min_samples_leaf=30, random_state=RANDOM_STATE)\n"
"dt_exp.fit(X2, y_exp)\n"
"\n"
"fig_dt2, ax = plt.subplots(figsize=(15, 6))\n"
"plot_tree(dt_exp, feature_names=FEAT2, class_names=['bez eksportu', 'z eksportem'],\n"
"          filled=True, rounded=True, ax=ax, fontsize=8, max_depth=3)\n"
"ax.set_title('Drzewo decyzyjne: predykcja czy przypadek zawiera eksport', fontweight='bold')\n"
"plt.tight_layout()\n"
"fig_dt2.savefig(RESULTS_DIR / 'fig_dt_variant.png', dpi=120, bbox_inches='tight')\n"
"plt.show()\n"
"\n"
"print('\\nReguly tekstowe (depth=2):')\n"
"print(export_text(dt_exp, feature_names=FEAT2, max_depth=2))"
))

# ── 21  Resource analysis header ───────────────────────────────────────────
cells.append(md(
"## 7. Analiza zasobów — endpointy jako proxy usług\n\n"
"> **Uwaga metodyczna**: log PCR Lab nie zawiera identyfikatorów pracowników/maszyn.\n"
"> Używamy **endpointów URL** jako reprezentacji mikrousług CPEE — każdy endpoint\n"
"> odpowiada konkretnej usłudze laboratoryjnej (korelator, timeout, powiadomienia, itp.)."
))

# ── 22  Endpoint workload ─────────────────────────────────────────────────
cells.append(code(
"def normalize_ep(url):\n"
"    return re.sub(r'/engine/\\d+/', '/engine/{id}/', str(url))\n"
"\n"
"def shorten_ep(url):\n"
"    url = (url.replace('https://', '')\n"
"              .replace('https-get://', 'GET:')\n"
"              .replace('https-post://', 'POST:'))\n"
"    url = url.rstrip('/')\n"
"    return url[:52] + '...' if len(url) > 55 else url\n"
"\n"
"df_res = df_start_ev[\n"
"    df_start_ev['endpoint'].notna() & (df_start_ev['endpoint'] != '')\n"
"].copy()\n"
"df_res['ep_norm']  = df_res['endpoint'].apply(normalize_ep)\n"
"df_res['ep_short'] = df_res['ep_norm'].apply(shorten_ep)\n"
"\n"
"ep_workload = df_res['ep_short'].value_counts()\n"
"print(f'Zdarzenia start z endpointem: {len(df_res):,}')\n"
"print(f'Endpointy raw: {df_res[\"endpoint\"].nunique()}, norm: {df_res[\"ep_norm\"].nunique()}')\n"
"print(f'\\nTop 12 endpointow:')\n"
"print(ep_workload.head(12).to_string())\n"
"\n"
"fig_ep, ax = plt.subplots(figsize=(12, 6))\n"
"ep_workload.head(12).sort_values().plot(kind='barh', ax=ax, color='#3498db', edgecolor='white')\n"
"ax.set_xlabel('Liczba wywolan')\n"
"ax.set_title('Obciazenie endpointow — liczba wywolan (start events)', fontweight='bold')\n"
"for i, v in enumerate(ep_workload.head(12).sort_values()):\n"
"    ax.text(v + 80, i, f'{v:,}', va='center', fontsize=8)\n"
"plt.tight_layout()\n"
"fig_ep.savefig(RESULTS_DIR / 'fig_resource_workload.png', dpi=120, bbox_inches='tight')\n"
"plt.show()"
))

# ── 23  Handover matrix ────────────────────────────────────────────────────
cells.append(code(
"df_res_s = df_res.sort_values(['instance_uuid', 'timestamp'])\n"
"df_res_s = df_res_s.copy()\n"
"df_res_s['_next_ep'] = df_res_s.groupby('instance_uuid')['ep_short'].shift(-1)\n"
"hw = df_res_s.dropna(subset=['_next_ep'])\n"
"hw = hw[hw['ep_short'] != hw['_next_ep']]\n"
"\n"
"top_ep  = ep_workload.head(10).index.tolist()\n"
"hw_mat  = hw.groupby(['ep_short', '_next_ep']).size().unstack(fill_value=0)\n"
"hw_top  = hw_mat.loc[\n"
"    hw_mat.index.isin(top_ep),\n"
"    [c for c in hw_mat.columns if c in top_ep]\n"
"]\n"
"\n"
"fig_hw, ax = plt.subplots(figsize=(11, 8))\n"
"sns.heatmap(hw_top, annot=True, fmt='d', cmap='Blues', ax=ax,\n"
"            cbar_kws={'label': 'Liczba przekazan'}, linewidths=0.5)\n"
"ax.set_title('Macierz handover of work — przekazania miedzy endpointami (top 10)', fontweight='bold')\n"
"ax.set_xlabel('Endpoint nastepny')\n"
"ax.set_ylabel('Endpoint poprzedni')\n"
"plt.xticks(rotation=35, ha='right')\n"
"plt.yticks(rotation=0)\n"
"plt.tight_layout()\n"
"fig_hw.savefig(RESULTS_DIR / 'fig_handover_matrix.png', dpi=120, bbox_inches='tight')\n"
"plt.show()"
))

# ── 24  Resource network ───────────────────────────────────────────────────
cells.append(code(
"G_ep = nx.DiGraph()\n"
"for (src, tgt), cnt in hw.groupby(['ep_short', '_next_ep']).size().items():\n"
"    if cnt > 30:\n"
"        G_ep.add_edge(src, tgt, weight=int(cnt))\n"
"\n"
"if G_ep.number_of_nodes() > 0:\n"
"    pos_ep = nx.spring_layout(G_ep, k=3.5, seed=42)\n"
"    ep_w   = [G_ep[u][v]['weight'] for u, v in G_ep.edges()]\n"
"    max_ew = max(ep_w)\n"
"\n"
"    fig_sn, ax = plt.subplots(figsize=(13, 9))\n"
"    nx.draw_networkx_nodes(G_ep, pos_ep, ax=ax, node_size=2600,\n"
"                           node_color='#3498db', alpha=0.85)\n"
"    nx.draw_networkx_labels(G_ep, pos_ep, ax=ax, font_size=6.5, font_weight='bold',\n"
"                            labels={n: n.replace('/', '/\\n') for n in G_ep.nodes()})\n"
"    nx.draw_networkx_edges(G_ep, pos_ep, ax=ax,\n"
"                           width=[0.5 + 5*(w/max_ew)**0.5 for w in ep_w],\n"
"                           alpha=0.70, edge_color='#555', arrows=True, arrowsize=18,\n"
"                           connectionstyle='arc3,rad=0.07',\n"
"                           min_source_margin=20, min_target_margin=20)\n"
"    ax.set_title('Siec wspolpracy endpointow (przekazania > 30)', fontweight='bold')\n"
"    ax.axis('off')\n"
"    plt.tight_layout()\n"
"    fig_sn.savefig(RESULTS_DIR / 'fig_resource_network.png', dpi=120, bbox_inches='tight')\n"
"    plt.show()\n"
"else:\n"
"    print('Brak krawedzi po filtrowaniu.')"
))

# ── 25  Bottleneck header ─────────────────────────────────────────────────
cells.append(md(
"## 8. Analiza wąskich gardeł i symulacja Monte Carlo\n\n"
"**Symulacja Monte Carlo** (N=2 000): dla każdego przebiegu losujemy wariant\n"
"z rozkładu empirycznego, a czasy przejść z empirycznych rozkładów."
))

# ── 26  Bottleneck analysis ────────────────────────────────────────────────
cells.append(code(
"top_bn = perf_dfg_df.nlargest(8, 'median').copy()\n"
"top_bn['median_min'] = top_bn['median'] / 60\n"
"top_bn['label'] = top_bn['activity'] + ' ->\\n' + top_bn['_next_act']\n"
"\n"
"colors_bn = ['#e74c3c' if m > 100 else '#f39c12' if m > 30 else '#2ecc71'\n"
"             for m in top_bn['median_min']]\n"
"\n"
"fig_bn, ax = plt.subplots(figsize=(12, 6))\n"
"bars = ax.barh(top_bn['label'], top_bn['median_min'], color=colors_bn)\n"
"ax.set_xlabel('Mediana czasu przejscia [min]')\n"
"ax.set_title('Top 8 waskich gardel — mediana czasu przejscia', fontweight='bold')\n"
"for bar, val in zip(bars, top_bn['median_min']):\n"
"    ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,\n"
"            f'{val:.0f} min', va='center', fontsize=9)\n"
"handles_bn = [\n"
"    mpatches.Patch(color='#e74c3c', label='Krytyczne (>100 min)'),\n"
"    mpatches.Patch(color='#f39c12', label='Wysokie (30-100 min)'),\n"
"    mpatches.Patch(color='#2ecc71', label='Normalne (<30 min)'),\n"
"]\n"
"ax.legend(handles=handles_bn, loc='lower right', fontsize=9)\n"
"plt.tight_layout()\n"
"fig_bn.savefig(RESULTS_DIR / 'fig_bottlenecks.png', dpi=120, bbox_inches='tight')\n"
"plt.show()\n"
"\n"
"print('Waskie gardla (mediana):')\n"
"for _, r in top_bn.iterrows():\n"
"    flag = ' KRYTYCZNE' if r['median_min'] > 100 else (' Wysokie' if r['median_min'] > 30 else '')\n"
"    print(f'  {r[\"activity\"]:35s} -> {r[\"_next_act\"]:35s}: {r[\"median_min\"]:6.1f} min{flag}')"
))

# ── 27  Monte Carlo ────────────────────────────────────────────────────────
cells.append(code(
"np.random.seed(RANDOM_STATE)\n"
"N_SIM = 2000\n"
"\n"
"perf_dists = {}\n"
"for (act, nact), grp in df_perf.groupby(['activity', '_next_act']):\n"
"    perf_dists[(act, nact)] = grp['_dur_s'].values\n"
"\n"
"variant_list = [t.split(' -> ') for t in traces['trace'].tolist()]\n"
"\n"
"sim_durations = []\n"
"for _ in range(N_SIM):\n"
"    v = variant_list[np.random.randint(len(variant_list))]\n"
"    total = sum(\n"
"        float(np.random.choice(perf_dists[(v[i], v[i+1])]))\n"
"        for i in range(len(v) - 1)\n"
"        if (v[i], v[i+1]) in perf_dists and len(perf_dists[(v[i], v[i+1])]) > 0\n"
"    )\n"
"    sim_durations.append(total / 60)\n"
"\n"
"sim_arr    = np.array(sim_durations)\n"
"actual_dur = df_cases_sample['duration_min'].dropna()\n"
"\n"
"print(f'=== Symulacja Monte Carlo (N={N_SIM}) ===')\n"
"print(f'Symulacja:    mediana={np.median(sim_arr):.1f} min,  mean={np.mean(sim_arr):.1f} min')\n"
"print(f'Rzeczywiste:  mediana={actual_dur.median():.1f} min,  mean={actual_dur.mean():.1f} min')\n"
"print(f'P95 symulacja:    {np.percentile(sim_arr, 95):.1f} min')\n"
"print(f'P95 rzeczywiste:  {actual_dur.quantile(0.95):.1f} min')\n"
"\n"
"fig_sim, ax = plt.subplots(figsize=(12, 5))\n"
"ax.hist(actual_dur.clip(0, 600), bins=60, alpha=0.6, color='#3498db',\n"
"        density=True, label=f'Rzeczywiste (n={len(actual_dur):,})')\n"
"ax.hist(sim_arr, bins=60, alpha=0.6, color='#e74c3c',\n"
"        density=True, label=f'Symulacja MC (n={N_SIM:,})')\n"
"ax.axvline(actual_dur.median(), color='#2980b9', linestyle='--', lw=2,\n"
"           label=f'Med. rzecz.: {actual_dur.median():.0f} min')\n"
"ax.axvline(np.median(sim_arr), color='#c0392b', linestyle='--', lw=2,\n"
"           label=f'Med. sym.: {np.median(sim_arr):.0f} min')\n"
"ax.set_xlabel('Czas trwania przypadku [min]')\n"
"ax.set_ylabel('Gestosc')\n"
"ax.set_title('Symulacja Monte Carlo vs rzeczywisty czas trwania', fontweight='bold')\n"
"ax.legend(fontsize=9)\n"
"ax.set_xlim(0, 600)\n"
"plt.tight_layout()\n"
"fig_sim.savefig(RESULTS_DIR / 'fig_simulation.png', dpi=120, bbox_inches='tight')\n"
"plt.show()"
))

# ── 28  Dashboard header ───────────────────────────────────────────────────
cells.append(md("## 9. Mini Dashboard HTML\n\n"
               "6 paneli Plotly → jeden plik `results/m3/dashboard.html`."))

# ── 29  Dashboard ─────────────────────────────────────────────────────────
cells.append(code(
"fig_dash = make_subplots(\n"
"    rows=2, cols=3,\n"
"    subplot_titles=[\n"
"        'Top 15 przejsc DFG',\n"
"        'Rozklad czasu trwania [min]',\n"
"        'Top 10 wariantow',\n"
"        'Obciazenie endpointow (top 12)',\n"
"        'Waskie gardla — mediana [min]',\n"
"        'Conformance — Fitness / Precision / F1',\n"
"    ],\n"
"    vertical_spacing=0.18, horizontal_spacing=0.10,\n"
")\n"
"\n"
"top15 = sorted(dfg_freq.items(), key=lambda x: -x[1])[:15]\n"
"fig_dash.add_trace(go.Bar(\n"
"    x=[v for _, v in top15][::-1],\n"
"    y=[f'{s}->{t}' for (s, t), _ in top15][::-1],\n"
"    orientation='h', marker_color='#3498db'), row=1, col=1)\n"
"\n"
"fig_dash.add_trace(go.Histogram(\n"
"    x=df_cases_sample['duration_min'].clip(0, 500).tolist(),\n"
"    nbinsx=50, marker_color='#2ecc71'), row=1, col=2)\n"
"\n"
"top10v = variant_counts.head(10)\n"
"fig_dash.add_trace(go.Bar(\n"
"    x=top10v.values.tolist(),\n"
"    y=[f'V{i+1}' for i in range(len(top10v))],\n"
"    orientation='h', marker_color='#9b59b6',\n"
"    hovertext=list(top10v.index),\n"
"    hoverinfo='text+x'), row=1, col=3)\n"
"\n"
"ep12 = ep_workload.head(12)\n"
"fig_dash.add_trace(go.Bar(\n"
"    x=ep12.values.tolist(), y=list(ep12.index),\n"
"    orientation='h', marker_color='#e67e22'), row=2, col=1)\n"
"\n"
"bn_colors = ['#e74c3c' if m > 100 else '#f39c12' if m > 30 else '#2ecc71'\n"
"             for m in top_bn['median_min']]\n"
"fig_dash.add_trace(go.Bar(\n"
"    x=top_bn['median_min'].tolist(),\n"
"    y=[f\"{r['activity']}->{r['_next_act']}\" for _, r in top_bn.iterrows()],\n"
"    orientation='h', marker_color=bn_colors), row=2, col=2)\n"
"\n"
"for metric, color in [('Fitness', '#3498db'), ('Precision', '#e74c3c'), ('F1', '#2ecc71')]:\n"
"    fig_dash.add_trace(go.Bar(\n"
"        name=metric, x=df_conform['Algorytm'].tolist(),\n"
"        y=df_conform[metric].fillna(0).tolist(), marker_color=color), row=2, col=3)\n"
"\n"
"fig_dash.update_layout(\n"
"    height=900,\n"
"    title_text='<b>PCR Lab — Process Mining Dashboard (Milestone 3)</b>',\n"
"    title_font_size=16, showlegend=False, template='plotly_white', font=dict(size=9),\n"
")\n"
"\n"
"dash_path = RESULTS_DIR / 'dashboard.html'\n"
"fig_dash.write_html(str(dash_path), include_plotlyjs='cdn')\n"
"print(f'Dashboard zapisany: {dash_path}')\n"
"fig_dash.show()"
))

# ── ASSEMBLE ───────────────────────────────────────────────────────────────
notebook = {
    'nbformat': 4,
    'nbformat_minor': 5,
    'metadata': {
        'kernelspec': {
            'display_name': 'Python 3',
            'language': 'python',
            'name': 'python3',
        },
        'language_info': {'name': 'python', 'version': '3.12.0'},
    },
    'cells': cells,
}

with open(str(OUTPUT), 'w', encoding='utf-8') as f:
    json.dump(notebook, f, ensure_ascii=False, indent=1)

print(f'Notebook zapisany: {OUTPUT}')
print(f'Komorek: {len(cells)}')
