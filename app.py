"""Application native PC. Aucun serveur ni compte Telegram."""
import csv
import json
import os
import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, simpledialog
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from engine import Store, evaluate, load_rows, money

BASE = Path(__file__).resolve().parent
DATA = BASE / 'data'
DEFAULT = dict(initial_capital=100, max_position=33, min_margin=25, sale_fee_rate=0,
               turnover_reserve_rate=0, sale_shipping=0, packaging=1, risk_reserve=5)


from connectors import ebay_search


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Repère • Arbitrage local')
        self.geometry('1180x760')
        self.minsize(900, 600)
        DATA.mkdir(exist_ok=True)
        self.config_path = DATA / 'config.json'
        self.settings = DEFAULT | (json.loads(self.config_path.read_text()) if self.config_path.exists() else {})
        self.store = Store(DATA / 'portfolio.sqlite3')
        self.demo = False
        self.results = queue.Queue()
        self.alerted = set()
        self.watched = None
        self.watch_stamp = None
        self.busy = False
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Treeview', rowheight=30, font=('Segoe UI', 10))
        style.configure('TButton', padding=8)
        style.configure('Title.TLabel', font=('Segoe UI', 23, 'bold'))
        frame = ttk.Frame(self, padding=22)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='REPÈRE / POSTE LOCAL', style='Title.TLabel').pack(anchor='w')
        ttk.Label(frame, text='Détecter • vérifier • suivre le cash   |   Aucun achat automatique').pack(anchor='w', pady=(5, 14))
        self.summary = ttk.Label(frame, font=('Segoe UI', 12, 'bold'))
        self.summary.pack(anchor='w', pady=8)
        tools = ttk.Frame(frame)
        tools.pack(fill='x', pady=8)
        for label, action in [('Importer CSV/JSON', self.import_file), ('Surveiller un fichier', self.watch), ('Démo / Réel', self.toggle_demo), ('Paramètres', self.configure_costs), ('Exporter le suivi', self.export)]:
            ttk.Button(tools, text=label, command=lambda f=action: self.guard(f)).pack(side='left', padx=(0, 5))
        search = ttk.Frame(frame)
        search.pack(fill='x', pady=6)
        self.query = ttk.Entry(search)
        self.query.insert(0, 'Nintendo 3DS XL')
        self.query.pack(side='left', fill='x', expand=True)
        ttk.Button(search, text='Rechercher eBay (API)', command=self.fetch_ebay).pack(side='left', padx=5)
        ttk.Button(search, text='Ouvrir Vinted', command=lambda: webbrowser.open('https://www.vinted.fr/catalog?' + urlencode({'search_text': self.query.get()}))).pack(side='left')
        columns = ('state', 'title', 'price', 'cost', 'floor', 'margin')
        wrap = ttk.Frame(frame)
        wrap.pack(fill='both', expand=True, pady=10)
        self.table = ttk.Treeview(wrap, columns=columns, show='headings', selectmode='browse')
        for col, label, width in zip(columns, ['État', 'Annonce', 'Prix €', 'Coût total €', 'Cote €', 'Marge estimée €'], [120, 370, 80, 100, 90, 130]):
            self.table.heading(col, text=label)
            self.table.column(col, width=width, stretch=(col == 'title'))
        scroll = ttk.Scrollbar(wrap, orient='vertical', command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.table.pack(fill='both', expand=True)
        self.table.tag_configure('Alerte', foreground='#087c56')
        self.table.bind('<<TreeviewSelect>>', self.details)
        self.detail = tk.Text(frame, height=5, wrap='word', font=('Segoe UI', 10))
        self.detail.pack(fill='x')
        self.detail.configure(state='disabled')
        actions = ttk.Frame(frame)
        actions.pack(fill='x', pady=8)
        for label, action in [('Ouvrir l’annonce', self.open_item), ('Enregistrer un achat', self.buy), ('Enregistrer une vente encaissée', self.sell)]:
            ttk.Button(actions, text=label, command=lambda f=action: self.guard(f)).pack(side='left', padx=5)
        self.status = ttk.Label(frame, text='Prêt. Aucune collecte Vinted automatique configurée.')
        self.status.pack(anchor='w')
        self.refresh()
        self.after(500, self.tick)

    def guard(self, fn):
        try:
            fn()
        except Exception as exc:
            messagebox.showerror('Action impossible', str(exc), parent=self)

    def references(self):
        return load_rows(BASE / ('references_demo.csv' if self.demo else 'references.csv'))

    def refresh(self):
        selected = self.table.selection()
        self.table.delete(*self.table.get_children())
        self.items = {}
        cash = self.store.cash(self.settings['initial_capital'])
        for row in self.store.rows():
            item = json.loads(row['payload'])
            result = evaluate(item, self.references(), self.settings, cash)
            self.items[row['id']] = (dict(row), item, result)
            state = result['status'] if row['status'] == 'repéré' else row['status']
            self.table.insert('', 'end', iid=row['id'], values=(state, item['title'], f"{money(item['price']) / 100:.2f}", f"{result['cost'] / 100:.2f}", f"{result['floor'] / 100:.2f}", (f"{result['margin'] / 100:.2f}" if result['margin'] is not None else 'À compléter')), tags=(state,))
            if state == 'Alerte' and row['id'] not in self.alerted:
                self.alerted.add(row['id'])
                self.bell()
                self.title('● Nouvelle opportunité — Repère')
                try:
                    from plyer import notification
                    notification.notify(title='Repère — À vérifier', message=item['title'][:120], app_name='Repère', timeout=8)
                except Exception:
                    pass  # Le son et l’alerte dans la fenêtre restent disponibles.
        if selected and self.table.exists(selected[0]):
            self.table.selection_set(selected[0])
        stock = sum(1 for r in self.store.rows() if r['status'] == 'acheté')
        self.summary.configure(text=f"{'DÉMONSTRATION — PRIX FICTIFS' if self.demo else 'MODE RÉEL'}    |    Disponible : {cash / 100:.2f} €    |    Stock : {stock} objet(s)    |    Plafond : {self.settings['max_position']} € / objet")

    def chosen(self):
        ids = self.table.selection()
        if not ids:
            raise ValueError('Sélectionner une annonce')
        return self.items[ids[0]]

    def details(self, _event=None):
        if not self.table.selection():
            return
        row, item, result = self.chosen()
        text = result['reason'] + '\n' + item.get('description', '') + '\n' + item.get('url', '')
        if row['bought_on']:
            text += '\nAchat enregistré le ' + row['bought_on']
        self.detail.configure(state='normal')
        self.detail.delete('1.0', 'end')
        self.detail.insert('1.0', text)
        self.detail.configure(state='disabled')

    def import_file(self):
        path = filedialog.askopenfilename(filetypes=[('Annonces', '*.csv *.json')])
        if path:
            count = self.store.ingest(load_rows(path))
            self.refresh()
            self.status.configure(text=f'{count} nouvelle(s) annonce(s). Doublons mis à jour sans nouvelle ligne.')

    def watch(self):
        if self.watched:
            self.watched = None
            self.status.configure(text='Surveillance arrêtée.')
            return
        path = filedialog.askopenfilename(filetypes=[('Annonces', '*.csv *.json')])
        if path:
            self.watched, self.watch_stamp = Path(path), None
            self.status.configure(text='Surveillance locale toutes les 5 s ; cliquer à nouveau pour arrêter.')

    def tick(self):
        try:
            if self.watched:
                stamp = self.watched.stat().st_mtime_ns
                if stamp != self.watch_stamp:
                    count = self.store.ingest(load_rows(self.watched))
                    self.watch_stamp = stamp
                    self.refresh()
                    self.status.configure(text=f'Surveillance active — {count} nouvelle(s) annonce(s).')
            while not self.results.empty():
                value = self.results.get_nowait()
                self.busy = False
                if isinstance(value, Exception):
                    raise value
                rows, skipped = value
                count = self.store.ingest(rows)
                self.refresh()
                self.status.configure(text=f'eBay : {count} nouvelle(s), {skipped} ignorée(s) faute de frais de port EUR connus. Vérifier les frais au paiement.')
        except Exception as exc:
            self.status.configure(text=str(exc))
        self.after(5000, self.tick)

    def fetch_ebay(self):
        if self.busy:
            return
        if self.demo:
            messagebox.showinfo('Démo', 'Repasser en mode réel pour utiliser eBay.')
            return
        query = self.query.get().strip()
        if not query:
            return
        self.busy = True
        self.status.configure(text='Recherche eBay en cours…')
        def worker():
            try:
                self.results.put(ebay_search(query))
            except Exception as exc:
                self.results.put(exc)
        threading.Thread(target=worker, daemon=True).start()

    def toggle_demo(self):
        if self.busy:
            raise ValueError('Attendre la fin de la recherche eBay')
        self.store.db.close()
        self.demo = not self.demo
        self.store = Store(DATA / ('demo.sqlite3' if self.demo else 'portfolio.sqlite3'))
        self.watched = None
        self.alerted.clear()
        if self.demo:
            self.store.ingest(load_rows(BASE / 'annonces_demo.csv'))
        self.refresh()

    def configure_costs(self):
        win = tk.Toplevel(self)
        win.title('Paramètres — tous les montants en euros')
        fields = {}
        labels = ['Capital initial', 'Plafond par achat', 'Marge minimale', 'Frais de vente (0 à 1)', 'Réserve sur CA (0 à 1, à renseigner)', 'Port revente', 'Emballage', 'Réserve défauts']
        for n, (key, label) in enumerate(zip(DEFAULT, labels)):
            ttk.Label(win, text=label).grid(row=n, column=0, padx=12, pady=6, sticky='w')
            field = ttk.Entry(win)
            field.insert(0, str(self.settings[key]))
            field.grid(row=n, column=1, padx=12)
            fields[key] = field
        def save():
            values = {k: float(v.get().replace(',', '.')) for k, v in fields.items()}
            for value in values.values():
                money(value)
            if any(values[k] > 1 for k in ('sale_fee_rate', 'turnover_reserve_rate')) or values['sale_fee_rate'] + values['turnover_reserve_rate'] > 1:
                raise ValueError('Taux cumulés : maximum 1')
            if self.store.cash(values['initial_capital']) < 0:
                raise ValueError('Capital incompatible avec les opérations enregistrées')
            self.settings = values
            self.config_path.write_text(json.dumps(values, indent=2), encoding='utf-8')
            win.destroy()
            self.refresh()
        ttk.Button(win, text='Enregistrer', command=lambda: self.guard(save)).grid(row=8, columnspan=2, pady=12)

    def open_item(self):
        _, item, _ = self.chosen()
        url = item.get('url', '')
        if urlparse(url).scheme not in ('https', 'http'):
            raise ValueError('Lien web absent ou invalide')
        webbrowser.open(url)

    def buy(self):
        row, item, _ = self.chosen()
        value = simpledialog.askstring('Achat effectué', 'Coût réellement payé, tous frais inclus (€) :', parent=self)
        if value is not None:
            self.store.buy(row['id'], money(value), self.settings)
            self.refresh()

    def sell(self):
        row, _, _ = self.chosen()
        value = simpledialog.askstring('Cash reçu', 'Montant net encaissé après TOUS frais et réserves (€) :', parent=self)
        if value is not None:
            self.store.sell(row['id'], money(value))
            self.refresh()

    def export(self):
        path = filedialog.asksaveasfilename(defaultextension='.csv', initialfile='suivi.csv')
        if path:
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'titre', 'statut', 'achat_eur', 'date_achat', 'encaissement_net_eur', 'date_vente', 'lien'])
                for row in self.store.rows():
                    item = json.loads(row['payload'])
                    writer.writerow([row['id'], item['title'], row['status'], (row['cost'] or 0) / 100, row['bought_on'], (row['proceeds'] or 0) / 100, row['sold_on'], item.get('url', '')])
            self.status.configure(text='Suivi exporté.')


if __name__ == '__main__':
    App().mainloop()
