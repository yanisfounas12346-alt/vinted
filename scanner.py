"""Surveillance séquentielle interrompable ; suspension immédiate sur erreur."""
import threading
from datetime import datetime, timezone
from connectors import VintedClient, ebay_search


def now():
    return datetime.now(timezone.utc).isoformat()


class Scanner:
    def __init__(self, ingest, log, token_getter):
        self.ingest, self.log, self.token_getter = ingest, log, token_getter
        self.guard = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self.status = dict(running=False, stage='idle', source=None, query=None, last_check=None,
                           next_check=None, received=0, new=0, error=None, jobs=[], interval=90)

    def snapshot(self):
        with self.guard:
            return dict(self.status)

    def start(self, jobs, interval):
        if self.thread and self.thread.is_alive():
            raise ValueError('Une recherche est déjà active ; arrêter puis attendre sa fin')
        interval = int(interval)
        if not 60 <= interval <= 3600:
            raise ValueError('Intervalle : de 60 à 3600 secondes entre deux requêtes')
        if not isinstance(jobs, list) or not 1 <= len(jobs) <= 20:
            raise ValueError('Choisir de 1 à 20 recherches')
        clean = []
        for job in jobs:
            source, query = job.get('source'), str(job.get('query', '')).strip()
            if source not in ('vinted','ebay') or not 1 <= len(query) <= 150:
                raise ValueError('Source ou recherche invalide')
            if source == 'ebay' and not self.token_getter():
                raise ValueError('Ajouter le jeton eBay dans Connexions')
            clean.append(dict(source=source, query=query))
        self.stop_event = threading.Event()
        with self.guard:
            self.status.update(running=True, stage='starting', error=None, jobs=clean, interval=interval)
        self.thread = threading.Thread(target=self._run, args=(clean, interval, self.stop_event), daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        with self.guard:
            self.status.update(running=False, stage='stopping' if self.thread and self.thread.is_alive() else 'idle', next_check=None)
        self.log('Surveillance arrêtée. Une requête en cours sera ignorée à son retour.')

    def _run(self, jobs, interval, event):
        client = VintedClient()
        index = 0
        try:
            while not event.is_set():
                job = jobs[index % len(jobs)]
                with self.guard:
                    self.status.update(source=job['source'], query=job['query'], stage='request', next_check=None)
                try:
                    rows, skipped = client.search(job['query']) if job['source']=='vinted' else ebay_search(job['query'], self.token_getter())
                    if event.is_set():
                        break
                    count = self.ingest(rows, event)
                    self.log(f"{job['source']} · {job['query']} : {len(rows)} reçue(s), {count} nouvelle(s), {skipped} ignorée(s).")
                    with self.guard:
                        self.status.update(last_check=now(), received=len(rows), new=count, stage='waiting',
                            next_check=__import__('time').time()+interval)
                except Exception as exc:
                    message = str(exc)[:400]
                    with self.guard:
                        self.status.update(error=message, stage='error')
                    self.log(f"{job['source']} : {message}", 'error')
                    break  # Aucun nouvel essai automatique après refus ou changement de schéma.
                index += 1
                if event.wait(interval):
                    break
        finally:
            with self.guard:
                self.status.update(running=False, next_check=None)
                if self.status['stage'] != 'error':
                    self.status['stage'] = 'idle'
