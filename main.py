# -*- coding: utf-8 -*-
import os
import shutil
from datetime import datetime
import kivy
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.lang import Builder
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.modalview import ModalView
from kivy.graphics import Color, Rectangle, RoundedRectangle, Ellipse, Line
from kivy.clock import Clock
from kivy.metrics import dp  # Per definire le dimensioni in modo indipendente dalla densità
from kivy.uix.dropdown import DropDown
from kivy.factory import Factory
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.scrollview import ScrollView
from kivy.properties import StringProperty, DictProperty, NumericProperty, BooleanProperty, ListProperty
from kivy.utils import platform
from tinydb import TinyDB, Query
import json  # Utile per visualizzare i dati per debug
from kivy.core.window import Window

# Importa i widget utilizzati nel KV
from kivy.uix.image import Image
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.spinner import Spinner


# Imposta la dimensione fissa della finestra
# Queste linee VANNO RIMOSSE (o commentate) prima di creare l'APK per usare la risoluzione nativa.
#Window.size = (360, 640)
#Window.size = (1080, 1920)
#Window.resizable = False

# Colore di default per i bottoni deselezionati
COLOR_DESELECTED_APP = (0.9, 0.9, 0.9, 0.7)


def get_export_folder():
    """
    Restituisce il percorso sicuro per l'esportazione:
    - Su Android: usa la cartella privata dell'app (accessibile e compatibile con tutte le versioni di Android)
    - Su Desktop: usa la cartella locale 'esportazioni'
    """
    if platform == 'android':
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            context = PythonActivity.mActivity

            # Utilizza la directory esterna privata dell'app (es. /storage/emulated/0/Android/data/tuo.pacchetto/files)
            ext_dir = context.getExternalFilesDir(None)
            if ext_dir:
                target_dir = ext_dir.getAbsolutePath()
            else:
                target_dir = context.getFilesDir().getAbsolutePath()
        except Exception as e:
            print(f"DEBUG: Errore recupero percorso Android: {e}")
            target_dir = os.getcwd()
    else:
        target_dir = os.path.join(os.getcwd(), "esportazioni")

    if not os.path.exists(target_dir):
        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception as e:
            print(f"DEBUG: Impossibile creare la cartella: {e}")

    return target_dir


def formatta_data(raw_date):
    """
    Converte una data in formato ISO (es. '2026-10-09T14:30:15')
    nel formato leggibile '09/10/26'.
    Se la data è vuota o non valida, restituisce una stringa vuota o il valore originale.
    """
    if not raw_date:
        return ""
    try:
        dt = datetime.fromisoformat(str(raw_date))
        return dt.strftime("%d/%m/%y")  # Es. "09/10/26"
    except Exception:
        return str(raw_date)

class ImageButton(ButtonBehavior, Image):
    pass

# Piccola classe helper per pulsanti-immagine proporzionati
class ArrowButton(ButtonBehavior, Image):
    def __init__(self, img_normal, img_down, action, on_click_callback, **kwargs):
        super().__init__(**kwargs)
        self.img_normal = img_normal
        self.img_down = img_down
        self.action = action
        self.on_click_callback = on_click_callback

        self.source = self.img_normal
        self.fit_mode = "fill"  # Riempie l'area esatta del pulsante senza lasciare bordi
        self.size_hint = (None, None)
        self.size = (dp(70), dp(32))

    def on_press(self):
        self.source = self.img_down

    def on_release(self):
        self.source = self.img_normal
        self.on_click_callback()
        self.action()


class ImageButtonMenu(ButtonBehavior, BoxLayout):
    """Pulsante personalizzato per le voci del sottomenu."""
    def __init__(self, img_normal, img_down, action, submenu, parent_app, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint = (None, None)
        self.size = (dp(220), dp(44))
        self.padding = [dp(10), dp(5)]

        self.img_normal = img_normal
        self.img_down = img_down
        self.action = action
        self.submenu = submenu
        self.parent_app = parent_app

        # Sfondo scuro disegnato sul Canvas
        with self.canvas.before:
            Color(0.18, 0.18, 0.18, 0.95)
            self.bg_rect = Rectangle(size=self.size, pos=self.pos)

        self.bind(pos=self._update_bg, size=self._update_bg)

        self.icon = Image(
            source=self.img_normal,
            size_hint=(1, 1),
            fit_mode="contain"
        )
        self.add_widget(self.icon)

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def on_press(self):
        self.icon.source = self.img_down

    def on_release(self):
        self.icon.source = self.img_normal
        if hasattr(self.parent_app, '_execute_menu_action'):
            self.parent_app._execute_menu_action(self.submenu, self.action)


class RoundedButton(ButtonBehavior, BoxLayout):
    """ Un bottone personalizzato che disegna il proprio sfondo arrotondato. """

    # Definiamo le proprietà Kivy a livello di classe
    text = StringProperty('')
    background_color = ListProperty([0.5, 0.5, 0.5, 1])  # Colore di default (grigio)

    def __init__(self, **kwargs):
        # 1. Estraiamo TUTTE le proprietà custom prima di chiamare super()
        # pop() rimuove la chiave dal dizionario kwargs e ne restituisce il valore
        self.text = kwargs.pop('text', '')
        self.background_color = kwargs.pop('background_color', [0.5, 0.5, 0.5, 1])

        # Estrai font_name e font_size (non sono proprietà Kivy standard per BoxLayout)
        f_name = kwargs.pop('font_name', 'Roboto')
        f_size = kwargs.pop('font_size', '15sp')

        # 2. Ora kwargs contiene solo proprietà valide per BoxLayout/ButtonBehavior
        super().__init__(**kwargs)

        # 2. DISEGNO DELLO SFONDO (Canvas)
        # Questo sostituisce quello che avresti messo nel file .kv
        with self.canvas.before:
            Color(rgba=self.background_color)
            self.rect = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[15, ]  # Angoli arrotondati
            )

        # 3. Binding per aggiornare lo sfondo se il bottone si muove o cambia dimensione
        self.bind(pos=self._update_rect, size=self._update_rect)

        # 4. Aggiunta della Label del testo
        self.label = Label(
            text=self.text,
            font_name=f_name,
            font_size=f_size,
            color=[1, 1, 1, 1],  # Testo Bianco
            bold=True
        )
        self.add_widget(self.label)
        self.bind(text=self.label.setter('text'))

    def _update_rect(self, instance, value):
        """Aggiorna la posizione e la dimensione del rettangolo sullo schermo."""
        self.rect.pos = instance.pos
        self.rect.size = instance.size


# Aggiungi questa classe subito dopo le tue classi esistenti (dopo RoundedButton)

class CustomOvalButton(Button):
    """ Bottone ovale/ellittico personalizzato con bordo colorato per esportazione """
    bg_color = ListProperty([0.18, 0.54, 0.34, 1])
    border_color = ListProperty([0.0, 0.7, 0.9, 1])

    def __init__(self, **kwargs):
        # Estraiamo eventuali argomenti non standard prima di super()
        action = kwargs.pop('action', None)

        super().__init__(**kwargs)

        self.action = action
        self.background_color = (0, 0, 0, 0)  # Rimuove lo sfondo rettangolare di Kivy

        # Binding per aggiornare il disegno su movimento o ridimensionamento
        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas,
            bg_color=self._update_canvas,
            border_color=self._update_canvas
        )

    def _update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            # Riempimento Ovale
            Color(*self.bg_color)
            Ellipse(pos=self.pos, size=self.size)

            # Bordo Ovale (Azzurro/Ciano)
            Color(*self.border_color)
            Line(ellipse=(self.x, self.y, self.width, self.height), width=2)


# Funzione Helper di Ordinamento Globale
def ordina_lista_vini(lista_vini, criterio="Inserimento", tipo_vino="rosso", crescente=False):
    """
    Ordina una lista di vini in base al criterio selezionato e al verso (crescente/decrescente).
    """
    if criterio == "Inserimento" or not criterio:
        # Se è per inserimento e si vuole invertire, basta invertire la lista
        return list(reversed(lista_vini)) if crescente else list(lista_vini)

    suf = f"_{tipo_vino}"

    def get_num(val, default=0.0):
        try:
            import re
            match = re.search(r"[-+]?\d*\.\d+|\d+", str(val))
            return float(match.group()) if match else default
        except Exception:
            return default

    vini_ordinati = list(lista_vini)

    # Determina l'ordinamento base
    if criterio == "Nome":
        vini_ordinati.sort(key=lambda x: str(x.get(f'nome{suf}', x.get('nome', ''))).lower(), reverse=not crescente)

    elif criterio == "Annata":
        vini_ordinati.sort(key=lambda x: get_num(x.get(f'annata{suf}', x.get('annata', 0))), reverse=not crescente)

    elif criterio == "Gradazione":
        vini_ordinati.sort(key=lambda x: get_num(x.get(f'alcol{suf}', x.get('alcol', 0))), reverse=not crescente)

    elif criterio == "Giudizio":
        vini_ordinati.sort(key=lambda x: str(x.get(f'qualita{suf}', x.get('qualita', ''))).lower(),
                           reverse=not crescente)

    elif criterio == "Data":
        vini_ordinati.sort(key=lambda x: str(x.get('data_modifica', '')), reverse=not crescente)

    return vini_ordinati


class BaseScreen(Screen):
    """Classe base per le schermate con logica di selezione bottoni."""

    # Bianco sporco trasparente al 70% come sfondo non selezionato (vedi <SelectionButton@Button> nel file kivi)
    COLOR_DESELECTED = (0.9, 0.9, 0.9, 0.7)

    # Giallo chiaro trasparente al 70% come sfondo selezionato
    COLOR_SELECTED = (0.96, 0.96, 0.5, 0.7)  # alternativa (0, 0.3, 0.3, 0.5) ciano molto scuro trasparente al 70%

    # Definisce le chiavi del DB che questa schermata gestisce
    # DEVE essere sovrascritta nelle classi figlie (es. RedWineVistaScreen)
    SELECTION_KEYS = []

    def on_enter(self, *args):
        """Metodo chiamato quando si naviga nella schermata."""
        super().on_enter(*args)
        app = App.get_running_app()

        # 1. Reset dei colori dei bottoni di selezione
        self._reset_button_colors()

        # 2. Reset dello stato del Menu con un piccolissimo ritardo (0.1 secondi)
        # Questo risolve il problema del bottone che resta "incastrato" in arancione
        Clock.schedule_once(self._force_menu_reset, 0.1)

        # 3. Se siamo in modalità modifica o degustazione, evidenzia i valori
        if self.SELECTION_KEYS:
            self._apply_selections(app, self.SELECTION_KEYS)

    def _force_menu_reset(self, dt):
        """Forza il tasto menu allo stato normale e rimuove eventuali tinte."""
        if 'menu_button' in self.ids:
            self.ids.menu_button.state = 'normal'
            # Molto importante: impostiamo il colore a Bianco pieno (1,1,1,1)
            # così l'immagine del menu non viene scurita dal grigio del reset
            self.ids.menu_button.background_color = (1, 1, 1, 1)

    def _apply_selections(self, app, selection_keys):
        """
        Applica i colori ai bottoni basandosi sui dati caricati.
        Gestisce stringhe singole, liste e stringhe separate da virgola.
        """
        for key in selection_keys:
            data_key = key.replace('_box', '')
            selected_value = app.selections.get(data_key)

            if selected_value:
                # --- NUOVA LOGICA DI TRASFORMAZIONE IN LISTA ---
                if isinstance(selected_value, str):
                    if ',' in selected_value:
                        # Se è una stringa con virgole (es: 'Ciliegia, Mora')
                        # Creiamo una lista pulendo gli spazi extra
                        target_list = [s.strip() for s in selected_value.split(',')]
                    else:
                        # Se è una stringa singola (es: 'Pulito')
                        target_list = [selected_value.strip()]
                elif isinstance(selected_value, list):
                    # Se è già una lista (es: ['Rubino', 'Granata'])
                    target_list = [str(v).strip() for v in selected_value]
                else:
                    target_list = []

                # Pulizia finale: uniformiamo tutto a "una sola riga senza spazi extra"
                target_list = [" ".join(val.split()) for val in target_list]

                # --- RICERCA NEI BOTTONI ---
                if key in self.ids:
                    container = self.ids[key]

                    def color_recursive(parent):
                        for child in parent.children:
                            if hasattr(child, 'text'):
                                # Puliamo il testo del bottone (rimuove \n e spazi extra)
                                clean_button_text = " ".join(child.text.split())

                                if clean_button_text in target_list:
                                    child.background_color = self.COLOR_SELECTED

                            if hasattr(child, 'children'):
                                color_recursive(child)

                    color_recursive(container)

    def _reset_button_colors(self):
        """Resetta i colori dei bottoni, escludendo quelli di sistema."""
        for widget in self.walk():
            if isinstance(widget, ButtonBehavior):
                # Controlliamo se è il tasto menu confrontando l'oggetto con l'ID
                is_menu = False
                if 'menu_button' in self.ids and widget == self.ids.menu_button:
                    is_menu = True

                # Se NON è il menu, resettiamo colore e stato
                if not is_menu:
                    if hasattr(widget, 'state'):
                        widget.state = 'normal'
                    if hasattr(widget, 'background_color'):
                        # Qui applichiamo il tuo bianco sporco trasparente
                        widget.background_color = self.COLOR_DESELECTED

    def on_button_press(self, group_name, button, other_buttons):
        """
        Gestisce la selezione esclusiva di un bottone e aggiorna lo stato.
        """
        app = App.get_running_app()
        current_selection = app.selections.get(group_name)

        if current_selection == button.text:
            # Deseleziona il bottone se è già premuto
            # (Resetta il colore Bianco sporco e trasparenza al 70%)
            button.background_color = self.COLOR_DESELECTED
            app.selections.pop(group_name, None)
        else:
            # Seleziona il nuovo bottone
            for widget in other_buttons:
                # Resetta il colore degli altri bottoni
                if isinstance(widget, Button):
                    widget.background_color = self.COLOR_DESELECTED

            # Colore evidenziato
            button.background_color = self.COLOR_SELECTED
            app.selections[group_name] = button.text

    def on_multiple_select_press(self, group_name, button):
        """
        Gestisce la selezione multipla di bottoni e aggiorna lo stato.
        """
        app = App.get_running_app()
        # Assicurati che la chiave sia una lista
        if group_name not in app.selections or not isinstance(app.selections[group_name], list):
            app.selections[group_name] = []

        if button.text in app.selections[group_name]:
            # Se il bottone è già nella lista, lo rimuovi
            app.selections[group_name].remove(button.text)
            button.background_color = self.COLOR_DESELECTED
        else:
            # Altrimenti, lo aggiungi alla lista
            app.selections[group_name].append(button.text)
            button.background_color = self.COLOR_SELECTED


# ==============================================================================
# DEFINIZIONE DELLE CLASSI SCREEN
# Queste classi non contengono logica (solo "pass") perché il loro layout
# e la navigazione sono gestiti nel file KV.
# ==============================================================================


class WelcomeScreen(Screen):
    """Schermata di Benvenuto con il tasto 'Inizia'."""
    pass


class WineSelectionScreen(Screen):
    """Schermata per la scelta del tipo di vino."""
    pass


class RedWineViewScreen(BaseScreen):
    """Schermata per la fase 'Vista' del vino rosso."""
    # Le chiavi devono corrispondere esattamente agli ID dei BoxLayout nel KV!
    SELECTION_KEYS = ['limpidezza_rosso_box', 'intensita_vista_rosso_box', 'colore_rosso_box']

    pass

class RedWineNoseScreen(BaseScreen):
    """Schermata per la fase 'Naso' del vino rosso."""
    # DEVONO ESSERE GLI ID KV CORRETTI, inclusi i suffissi _box
    SELECTION_KEYS = [
        'condizione_rosso_box',         # Corretto: era 'condizione_rosso' nel log
        'intensita_naso_rosso_box',     # Corretto: era 'intensita_naso_rosso' nel log
        'profumo_rosso_box'
    ]


class RedWineTasteScreen(BaseScreen):
    """Schermata per la fase 'Palato' del vino rosso."""
    # Chiavi del DB gestite in questa schermata:
    SELECTION_KEYS = ['dolcezza_rosso_box',
                      'acidita_rosso_box',
                      'tannicita_rosso_box',
                      'livello_alcolico_rosso_box',
                      'corpo_rosso_box',
                      'sapore_rosso_box',
                      'persistenza_rosso_box'
                      ]


class RedWineEpilogueScreen(BaseScreen):
    """Schermata di 'Conclusione' del vino rosso."""
    SELECTION_KEYS = ['qualita_rosso_box']
    def on_enter(self, *args):
        # 🚨 IMPORTANTE: Chiama la logica di caricamento dati del genitore
        super().on_enter(*args)


class RedWineInfoScreen(Screen):
    """Schermata di 'Info' del vino rosso."""

    # ----------------------------------------------------------------------
    # PRE-CARICAMENTO E CAMBIO DI TESTO DEL BOTTONE SALVA/AGGIORNA
    # ----------------------------------------------------------------------
    def on_enter(self, *args):
        """Metodo chiamato quando si naviga in questa schermata.
        Controlla se è attiva la modalità di modifica e pre-popola i campi.
        """
        super().on_enter(*args)
        app = App.get_running_app()

        # Riferimento al bottone "Salva Scheda" (Assumiamo l'ID 'nav_salva_rosso' nel KV)
        # NOTA: Devi assicurarti che il bottone nel file wineapp12.kv abbia questo ID.
        try:
            btn_salva = self.ids.nav_salva_rosso
        except KeyError:
            # Fallback se l'ID non è definito in KV, gestisci l'errore o ignora la modifica del testo
            btn_salva = None

        # Controlla se siamo in modalità di modifica E se ci sono dati da pre-popolare
        if app.card_to_update_id is not None and app.text_inputs:

            # 1. Popola i campi di testo
            # Nota: gli ID del TextInput nel KV dovrebbero essere 'nome_rosso', 'produttore_rosso', ecc.
            self.ids['nome_rosso'].text = app.text_inputs.get('nome_rosso', '')
            self.ids['produttore_rosso'].text = app.text_inputs.get('produttore_rosso', '')
            self.ids['annata_rosso'].text = app.text_inputs.get('annata_rosso', '')

            # Se hai un campo note, aggiungilo qui
            # self.ids['note_personali_rosso'].text = app.text_inputs.get('note_personali', '')

            # 2. Aggiorna lo Spinner alcolico
            # Lo spinner è un TextInput nel tuo modello, quindi usa .text
            alcol_val = app.text_inputs.get('alcol_rosso', 'Gradazione alcolica')
            self.ids['alcol_rosso'].text = alcol_val

            # 3. Aggiorna il testo del bottone
            if btn_salva:
                btn_salva.text = 'Aggiorna'

        else:
            # Se non è in modalità modifica, assicurati che i campi siano vuoti
            # (o resettati da confirm_and_save) e che il bottone dica "Salva Scheda"
            if btn_salva:
                btn_salva.text = 'Salva'

class WhiteWineViewScreen(BaseScreen):
    """Schermata per la fase 'Vista' del vino bianco."""
    # Le chiavi devono corrispondere esattamente agli ID dei BoxLayout nel KV!
    SELECTION_KEYS = ['limpidezza_bianco_box', 'intensita_vista_bianco_box', 'colore_bianco_box']

    pass

class WhiteWineNoseScreen(BaseScreen):
    """Schermata per la fase 'Naso' del vino bianco."""
    # DEVONO ESSERE GLI ID KV CORRETTI, inclusi i suffissi _box
    SELECTION_KEYS = [
        'condizione_bianco_box',
        'intensita_naso_bianco_box',
        # NOTA: Se hai suddiviso i profumi in box separati, includili tutti
        'profumo_bianco_box'
    ]


class WhiteWineTasteScreen(BaseScreen):
    """Schermata per la fase 'Palato' del vino bianco."""
    # Chiavi del DB gestite in questa schermata:
    SELECTION_KEYS = ['dolcezza_bianco_box',
                      'acidita_bianco_box',
                      'tannicita_bianco_box',
                      'livello_alcolico_bianco_box',
                      'corpo_bianco_box',
                      'sapore_bianco_box',
                      'persistenza_bianco_box'
                      ]

class WhiteWineEpilogueScreen(BaseScreen):
    """Schermata di 'Conclusione' del vino rosso."""
    SELECTION_KEYS = ['qualita_bianco_box']
    def on_enter(self, *args):
        # 🚨 IMPORTANTE: Chiama la logica di caricamento dati del genitore
        super().on_enter(*args)


class WhiteWineInfoScreen(Screen):
    """Schermata di 'Info' del vino bianco."""

    # ----------------------------------------------------------------------
    # PRE-CARICAMENTO E CAMBIO DI TESTO DEL BOTTONE SALVA/AGGIORNA
    # ----------------------------------------------------------------------
    def on_enter(self, *args):
        """Metodo chiamato quando si naviga in questa schermata.
		Controlla se è attiva la modalità di modifica e pre-popola i campi.
		"""
        super().on_enter(*args)
        app = App.get_running_app()

        # Riferimento al bottone "Salva Scheda" (Assumiamo l'ID 'nav_salva_rosso' nel KV)
        # NOTA: Devi assicurarti che il bottone nel file wineapp12.kv abbia questo ID.
        try:
            btn_salva = self.ids.nav_salva_bianco
        except KeyError:
            # Fallback se l'ID non è definito in KV, gestisci l'errore o ignora la modifica del testo
            btn_salva = None

        # Controlla se siamo in modalità di modifica E se ci sono dati da pre-popolare
        if app.card_to_update_id is not None and app.text_inputs:

            # 1. Popola i campi di testo
            # Nota: gli ID del TextInput nel KV dovrebbero essere 'nome_bianco', 'produttore_bianco', ecc.
            self.ids['nome_bianco'].text = app.text_inputs.get('nome_bianco', '')
            self.ids['produttore_bianco'].text = app.text_inputs.get('produttore_bianco', '')
            self.ids['annata_bianco'].text = app.text_inputs.get('annata_bianco', '')

            # Se hai un campo note, aggiungilo qui
            # self.ids['note_personali_bianco'].text = app.text_inputs.get('note_personali', '')

            # 2. Aggiorna lo Spinner alcolico
            # Lo spinner è un TextInput nel tuo modello, quindi usa .text
            alcol_val = app.text_inputs.get('alcol_bianco', 'Gradazione alcolica')
            self.ids['alcol_bianco'].text = alcol_val

            # 3. Aggiorna il testo del bottone
            if btn_salva:
                btn_salva.text = 'Aggiorna'

        else:
            # Se non è in modalità modifica, assicurati che i campi siano vuoti
            # (o resettati da confirm_and_save) e che il bottone dica "Salva Scheda"
            if btn_salva:
                btn_salva.text = 'Salva'

class PinkWineViewScreen(BaseScreen):
    """Schermata per la fase 'Vista' del vino rosato."""
    # Le chiavi devono corrispondere esattamente agli ID dei BoxLayout nel KV!
    SELECTION_KEYS = ['limpidezza_rosato_box', 'intensita_vista_rosato_box', 'colore_rosato_box']

    pass


class PinkWineNoseScreen(BaseScreen):
    """Schermata per la fase 'Olfatto' del vino rosato."""
    # DEVONO ESSERE GLI ID KV CORRETTI, inclusi i suffissi _box
    SELECTION_KEYS = [
        'condizione_rosato_box',
        'intensita_naso_rosato_box',
        # NOTA: Se hai suddiviso i profumi in box separati, includili tutti
        'profumo_rosato_box'
    ]


class PinkWineTasteScreen(BaseScreen):
    """Schermata per la fase 'Palato' del vino rosato."""
    # Chiavi del DB gestite in questa schermata:
    SELECTION_KEYS = ['dolcezza_rosato_box',
                      'acidita_rosato_box',
                      'tannicita_rosato_box',
                      'livello_alcolico_rosato_box',
                      'corpo_rosato_box',
                      'sapore_rosato_box',
                      'persistenza_rosato_box'
                      ]


class PinkWineEpilogueScreen(BaseScreen):
    """Schermata di 'Conclusione' del vino rosato."""
    SELECTION_KEYS = ['qualita_rosato_box']
    def on_enter(self, *args):
        # 🚨 IMPORTANTE: Chiama la logica di caricamento dati del genitore
        super().on_enter(*args)


class PinkWineInfoScreen(Screen):
    """Schermata di 'Info' del vino rosato."""

    # ----------------------------------------------------------------------
    # PRE-CARICAMENTO E CAMBIO DI TESTO DEL BOTTONE SALVA/AGGIORNA
    # ----------------------------------------------------------------------
    def on_enter(self, *args):
        """Metodo chiamato quando si naviga in questa schermata.
		Controlla se è attiva la modalità di modifica e pre-popola i campi.
		"""
        super().on_enter(*args)
        app = App.get_running_app()

        # Riferimento al bottone "Salva Scheda" (Assumiamo l'ID 'nav_salva_rosso' nel KV)
        # NOTA: Devi assicurarti che il bottone nel file wineapp12.kv abbia questo ID.
        try:
            btn_salva = self.ids.nav_salva_rosato
        except KeyError:
            # Fallback se l'ID non è definito in KV, gestisci l'errore o ignora la modifica del testo
            btn_salva = None

        # Controlla se siamo in modalità di modifica E se ci sono dati da pre-popolare
        if app.card_to_update_id is not None and app.text_inputs:

            # 1. Popola i campi di testo
            # Nota: gli ID del TextInput nel KV dovrebbero essere 'nome_rosato', 'produttore_rosato', ecc.
            self.ids['nome_rosato'].text = app.text_inputs.get('nome_rosato', '')
            self.ids['produttore_rosato'].text = app.text_inputs.get('produttore_rosato', '')
            self.ids['annata_rosato'].text = app.text_inputs.get('annata_rosato', '')

            # Se hai un campo note, aggiungilo qui
            # self.ids['note_personali_rosato'].text = app.text_inputs.get('note_personali', '')

            # 2. Aggiorna lo Spinner alcolico
            # Lo spinner è un TextInput nel tuo modello, quindi usa .text
            alcol_val = app.text_inputs.get('alcol_rosato', 'Gradazione alcolica')
            self.ids['alcol_rosato'].text = alcol_val

            # 3. Aggiorna il testo del bottone
            if btn_salva:
                btn_salva.text = 'Aggiorna'

        else:
            # Se non è in modalità modifica, assicurati che i campi siano vuoti
            # (o resettati da confirm_and_save) e che il bottone dica "Salva Scheda"
            if btn_salva:
                btn_salva.text = 'Salva'

class RedWineCardItem(ButtonBehavior, GridLayout):
    """
    Scheda per visualizzare i dati di un singolo vino.
    Definiamo la proprietà wine_data che riceverà il dizionario da TinyDB.
    """
    wine_data = DictProperty({})  # Usiamo DictProperty perché wine_data è un dizionario (il record di TinyDB)
    row_index = NumericProperty(0)  # Proprietà per l'indice della riga (0, 1, 2, 3...)
    expanded = BooleanProperty(False)  # Traccia se la scheda è espansa o meno
    card_doc_id = NumericProperty(0)  # per memorizzare l'ID univoco del documento (TinyDB doc_id)

    def toggle_expand_red(self):
        """Mostra un popup con i dettagli completi della degustazione."""

        # --- RECUPERA L'APP RUNNING INSTANCE ---
        app = App.get_running_app()
        # -------------------------------------------------------------

        # 1. Contenitore principale (Scrollview dentro un BoxLayout per gestire lo scroll)
        scroll_content = BoxLayout(
            orientation='vertical',
            spacing=dp(3),
            size_hint_y=None,
            padding=[dp(20), dp(5), dp(15), dp(5)]
        )
        scroll_content.bind(minimum_height=scroll_content.setter('height'))  # Auto-sizing del contenuto

        # 2. Intestazione (Produttore / Annata / Alcol)
        scroll_content.add_widget(Label(
            text=f"{self.wine_data.get('produttore_rosso', 'Produttore N/D')}   {self.wine_data.get('annata_rosso', 'Annata N/D')}"
                 f"   {self.wine_data.get('alcol_rosso', 'Grad. Alcolica N/D')}° vol.",
            markup=True, halign='left',  # Allinea a sinistra
            valign='middle',  # centra verticalmente
            size_hint_y=None,
            height=dp(35),
            color=(0.9, 0.2, 0.2, 1),  # Rosso Scuro/Vino
            font_size='16sp',
            font_name='materiale/comicbd.ttf',
            text_size=(dp(270), None)  # dimensione massima del testo affinché l'allineamento funzioni
        ))

        # 3. Funzione per aggiungere una riga di dettaglio
        def add_detail_row_red(title, keys):
            colore_titolo_rosso = "#F27373FF"   # Rosso Fragola
            colore_valori_rosso = "#E63333FF"   # Rosso Scuro/Vino
            values = [self.format_data_for_label_red(key) for key in keys]
            valori_stringa = " / ".join(values)
            detail_text = (
                    f"[color={colore_titolo_rosso}]{title}[/color]" +  # Prima parte (Titolo)
                    f"[color={colore_valori_rosso}][b]{valori_stringa}[/b][/color]"  # Seconda parte (Valori)
            )

            label = Label(
                text=detail_text,
                markup=True, halign='left', valign='top',
                size_hint_y=None,
                height=dp(30),
                text_size=(dp(260), None),
                font_name='materiale/comicbd.ttf',
                font_size='13sp'
            )
            label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1] + dp(6)))

            scroll_content.add_widget(label)

        # 4a. Dettagli Vista
        add_detail_row_red("Vista (Limpidezza / Intensità / Colore):\n", ['limpidezza_rosso', 'intensita_vista_rosso', 'colore_rosso'])

        # 4b. Dettagli Olfatto
        add_detail_row_red("Olfatto (Condizione / Intensità):\n", ['condizione_rosso', 'intensita_naso_rosso'])
        add_detail_row_red("Profumi: ", ['profumo_rosso'])

        # 4c. Dettagli Palato
        add_detail_row_red("Palato: ", ['dolcezza_rosso'])
        add_detail_row_red("Corpo / Acidità / Tannini / Alcol:\n", ['corpo_rosso', 'acidita_rosso', 'tannicita_rosso', 'livello_alcolico_rosso'])
        add_detail_row_red("Sapori: ", ['sapore_rosso'])
        add_detail_row_red("Persistenza / Qualità:\n", ['persistenza_rosso', 'qualita_rosso'])

        # 5. Contenitore dei bottoni (sotto i dettagli)
        button_box = BoxLayout(
            orientation='horizontal',
            spacing=dp(10),
            size_hint_y=None,
            height=dp(40),
            padding=dp(2)
        )

        FONT = 'materiale/comicbd.ttf'
        COMPACT_FONT_SIZE = '10sp'

        btn_delete = RoundedButton(
            text='Elimina Scheda',
            size_hint_x=0.35,
            font_name=FONT,
            font_size=COMPACT_FONT_SIZE,
            background_color=(0.8, 0.1, 0.1, 1)
        )
        button_box.add_widget(btn_delete)

        btn_edit = RoundedButton(
            text='Modifica Scheda',
            size_hint_x=0.35,
            font_name=FONT,
            font_size=COMPACT_FONT_SIZE,
            background_color=(0.1, 0.7, 0.1, 1)
        )
        button_box.add_widget(btn_edit)

        btn_close = RoundedButton(
            text="Chiudi",
            size_hint_x=0.30,
            font_name=FONT,
            font_size='12sp',
            background_color=(0.5, 0.5, 0.5, 1)
        )
        button_box.add_widget(btn_close)

        # 6. Contenitore finale del Popup (verticale)
        final_content = BoxLayout(orientation='vertical', padding=dp(6), spacing=dp(4))

        # --- INTESTAZIONE TITOLO PERSONALIZZATA CON DATA ---
        nome_vino = self.wine_data.get('nome_rosso', 'Vino Sconosciuto')
        data_raw = self.wine_data.get('data_modifica', '')
        data_str = formatta_data(data_raw)
        testo_data = f" [size=13sp][color=#888888]({data_str})[/color][/size]" if data_str else ""

        header_label = Label(
            text=f"[b]{nome_vino}[/b]{testo_data}",
            markup=True,
            font_name='materiale/comicbd.ttf',
            font_size='18sp',
            color=(0.9, 0.2, 0.2, 1),  # Rosso Scuro/Vino
            halign='left',
            valign='middle',
            size_hint_y=None,
            height=dp(30),
            text_size=(dp(280), None)
        )
        final_content.add_widget(header_label)

        # 7. Aggiungi la ScrollView contenente tutti i dettagli
        scroll_view = ScrollView(size_hint_y=0.9, do_scroll_x=False)
        scroll_view.add_widget(scroll_content)

        final_content.add_widget(scroll_view)
        final_content.add_widget(button_box)

        # 8. Creazione del Popup (Senza titolo nativo)
        popup = Popup(
            title='',
            separator_color=(0.6, 0, 0, 1),
            separator_height=dp(2),
            content=final_content,
            size_hint=(0.95, 0.9),
            background_color=(1, 1, 1, 0.7)
        )

        # =======================================================================
        # COLLEGAMENTO DELLE AZIONI
        # =======================================================================
        btn_delete.bind(on_release=lambda instance: app.confirm_delete_card(self.card_doc_id, 'rosso', popup))
        btn_edit.bind(on_release=lambda x: self.start_edit_flow(popup))
        btn_close.bind(on_release=popup.dismiss)

        popup.open()

        sm = App.get_running_app().root
        archive_screen = sm.get_screen('archivio_rosso')
        archive_screen.detail_popup = popup

    def format_data_for_label_red(self, key):
        """Recupera i dati, gestendo stringhe e liste (es. da selezione multipla)."""
        value = self.wine_data.get(key, 'N/D')

        if isinstance(value, list):
            return ", ".join(value)
        return str(value)

    def start_edit_flow(self, popup_instance):
        """Chiude il popup e avvia il flusso di modifica, chiamando il metodo nell'App."""
        if popup_instance:
            popup_instance.dismiss()

        app = App.get_running_app()
        wine_color = 'rosso'
        app.start_edit_card(wine_color, self.wine_data, self.card_doc_id)

class WhiteWineCardItem(ButtonBehavior, GridLayout):
    """
    Scheda per visualizzare i dati di un singolo vino.
    Definiamo la proprietà wine_data che riceverà il dizionario da TinyDB.
    """
    wine_data = DictProperty({})  # Usiamo DictProperty perché wine_data è un dizionario (il record di TinyDB)
    row_index = NumericProperty(0)  # Proprietà per l'indice della riga (0, 1, 2, 3...)
    expanded = BooleanProperty(False)  # Traccia se la scheda è espansa o meno
    card_doc_id = NumericProperty(0)  # per memorizzare l'ID univoco del documento (TinyDB doc_id)

    def toggle_expand_white(self):
        """Mostra un popup con i dettagli completi della degustazione."""

        # --- RECUPERA L'APP RUNNING INSTANCE ---
        app = App.get_running_app()
        # -------------------------------------------------------------

        # 1. Contenitore principale (Scrollview dentro un BoxLayout per gestire lo scroll)
        scroll_content = BoxLayout(
            orientation='vertical',
            spacing=dp(3),
            size_hint_y=None,
            padding=[dp(20), dp(5), dp(15), dp(5)]
        )
        scroll_content.bind(minimum_height=scroll_content.setter('height'))  # Auto-sizing del contenuto

        # 2. Intestazione (Produttore / Annata / Alcol)
        scroll_content.add_widget(Label(
            text=f"{self.wine_data.get('produttore_bianco', 'Produttore N/D')}   {self.wine_data.get('annata_bianco', 'Annata N/D')}"
                 f"   {self.wine_data.get('alcol_bianco', 'Grad. Alcolica N/D')}° vol.",
            markup=True, halign='left',
            valign='middle',
            size_hint_y=None,
            height=dp(35),
            color=(0.85, 0.75, 0.2, 1),  # Colore tema per il vino bianco (Giallo/Dorato)
            font_size='16sp',
            font_name='materiale/comicbd.ttf',
            text_size=(dp(270), None)
        ))

        # 3. Funzione per aggiungere una riga di dettaglio
        def add_detail_row_white(title, keys):
            colore_titolo_bianco = "#E6B31AFF"  # Giallo-oro luminoso
            colore_valori_bianco = "#B38000FF"  # Giallo-oro--ocra-scuro
            values = [self.format_data_for_label_white(key) for key in keys]
            valori_stringa = " / ".join(values)
            detail_text = (
                    f"[color={colore_titolo_bianco}]{title}[/color]" +  # Prima parte (Titolo)
                    f"[color={colore_valori_bianco}][b]{valori_stringa}[/b][/color]"  # Seconda parte (Valori)
            )

            label = Label(
                text=detail_text,
                markup=True, halign='left', valign='top',
                size_hint_y=None,
                height=dp(30),
                text_size=(dp(260), None),
                font_name='materiale/comicbd.ttf',
                font_size='13sp'
            )
            label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1] + dp(6)))

            scroll_content.add_widget(label)

        # 4a. Dettagli Vista
        add_detail_row_white("Vista (Limpidezza / Intensità / Colore):\n", ['limpidezza_bianco', 'intensita_vista_bianco', 'colore_bianco'])

        # 4b. Dettagli Olfatto
        add_detail_row_white("Olfatto (Condizione / Intensità):\n", ['condizione_bianco', 'intensita_naso_bianco'])
        add_detail_row_white("Profumi: ", ['profumo_bianco'])

        # 4c. Dettagli Palato
        add_detail_row_white("Palato: ", ['dolcezza_bianco'])
        add_detail_row_white("Corpo / Acidità / Tannini / Alcol:\n", ['corpo_bianco', 'acidita_bianco', 'tannicita_bianco', 'livello_alcolico_bianco'])
        add_detail_row_white("Sapori: ", ['sapore_bianco'])
        add_detail_row_white("Persistenza / Qualità:\n", ['persistenza_bianco', 'qualita_bianco'])

        # 5. Contenitore dei bottoni
        button_box = BoxLayout(
            orientation='horizontal',
            spacing=dp(10),
            size_hint_y=None,
            height=dp(40),
            padding=dp(2)
        )

        FONT = 'materiale/comicbd.ttf'
        COMPACT_FONT_SIZE = '10sp'

        btn_delete = RoundedButton(
            text='Elimina Scheda',
            size_hint_x=0.35,
            font_name=FONT,
            font_size=COMPACT_FONT_SIZE,
            background_color=(0.8, 0.1, 0.1, 1)
        )
        button_box.add_widget(btn_delete)

        btn_edit = RoundedButton(
            text='Modifica Scheda',
            size_hint_x=0.35,
            font_name=FONT,
            font_size=COMPACT_FONT_SIZE,
            background_color=(0.1, 0.7, 0.1, 1)
        )
        button_box.add_widget(btn_edit)

        btn_close = RoundedButton(
            text="Chiudi",
            size_hint_x=0.30,
            font_name=FONT,
            font_size='12sp',
            background_color=(0.5, 0.5, 0.5, 1)
        )
        button_box.add_widget(btn_close)

        # 6. Contenitore finale del Popup
        final_content = BoxLayout(orientation='vertical', padding=dp(6), spacing=dp(4))

        # --- INTESTAZIONE TITOLO PERSONALIZZATA CON DATA ---
        nome_vino = self.wine_data.get('nome_bianco', 'Vino Sconosciuto')
        data_raw = self.wine_data.get('data_modifica', '')
        data_str = formatta_data(data_raw)
        testo_data = f" [size=13sp][color=#888888]({data_str})[/color][/size]" if data_str else ""

        header_label = Label(
            text=f"[b]{nome_vino}[/b]{testo_data}",
            markup=True,
            font_name='materiale/comicbd.ttf',
            font_size='18sp',
            color=(0.85, 0.75, 0.2, 1),  # Colore tema per il vino bianco (Giallo/Dorato)
            halign='left',
            valign='middle',
            size_hint_y=None,
            height=dp(30),
            text_size=(dp(280), None)
        )
        final_content.add_widget(header_label)

        # 7. Aggiungi la ScrollView contenente i dettagli
        scroll_view = ScrollView(size_hint_y=0.9, do_scroll_x=False)
        scroll_view.add_widget(scroll_content)

        final_content.add_widget(scroll_view)
        final_content.add_widget(button_box)

        # 8. Creazione del Popup
        popup = Popup(
            title='',
            separator_color=(0.8, 0.7, 0.1, 1),
            separator_height=dp(2),
            content=final_content,
            size_hint=(0.95, 0.9),
            background_color=(1, 1, 1, 0.7)
        )

        # =======================================================================
        # COLLEGAMENTO DELLE AZIONI
        # =======================================================================
        btn_delete.bind(on_release=lambda instance: app.confirm_delete_card(self.card_doc_id, 'bianco', popup))
        btn_edit.bind(on_release=lambda x: self.start_edit_flow(popup))
        btn_close.bind(on_release=popup.dismiss)

        popup.open()

        sm = App.get_running_app().root
        archive_screen = sm.get_screen('archivio_bianco')
        archive_screen.detail_popup = popup

    def format_data_for_label_white(self, key):
        """Recupera i dati, gestendo stringhe e liste (es. da selezione multipla)."""
        value = self.wine_data.get(key, 'N/D')

        if isinstance(value, list):
            return ", ".join(value)
        return str(value)

    def start_edit_flow(self, popup_instance):
        """Chiude il popup e avvia il flusso di modifica, chiamando il metodo nell'App."""
        if popup_instance:
            popup_instance.dismiss()

        app = App.get_running_app()
        wine_color = 'bianco'
        app.start_edit_card(wine_color, self.wine_data, self.card_doc_id)

class PinkWineCardItem(ButtonBehavior, GridLayout):
    """
    Scheda per visualizzare i dati di un singolo vino rosato.
    Definiamo la proprietà wine_data che riceverà il dizionario da TinyDB.
    """
    # --- COSTANTI DI TEMA ---
    COLORE_INTESTAZIONE_ROSATO = (0.7, 0.45, 0.6, 1.0)  # malva scuro
    COLORE_TITOLO_DETTAGLIO = "#D999CCFF"  # malva chiaro e delicato
    COLORE_VALORI_DETTAGLIO = "#B37399FF"  # malva scuro

    wine_data = DictProperty({})  # Usiamo DictProperty perché wine_data è un dizionario (il record di TinyDB)
    row_index = NumericProperty(0)  # Proprietà per l'indice della riga (0, 1, 2, 3...)
    expanded = BooleanProperty(False)  # Traccia se la scheda è espansa o meno
    card_doc_id = NumericProperty(0)  # per memorizzare l'ID univoco del documento (TinyDB doc_id)

    def toggle_expand_pink(self):
        """Mostra un popup con i dettagli completi della degustazione."""

        # --- RECUPERA L'APP RUNNING INSTANCE ---
        app = App.get_running_app()
        # -------------------------------------------------------------

        # 1. Contenitore principale (Scrollview dentro un BoxLayout per gestire lo scroll)
        scroll_content = BoxLayout(
            orientation='vertical',
            spacing=dp(3),
            size_hint_y=None,
            padding=[dp(20), dp(5), dp(15), dp(5)]
        )
        scroll_content.bind(minimum_height=scroll_content.setter('height'))  # Auto-sizing del contenuto

        # 2. Intestazione (Produttore / Annata / Alcol)
        scroll_content.add_widget(Label(
            text=f"{self.wine_data.get('produttore_rosato', 'Produttore N/D')}   {self.wine_data.get('annata_rosato', 'Annata N/D')}"
                 f"   {self.wine_data.get('alcol_rosato', 'Grad. Alcolica N/D')}° vol.",
            markup=True, halign='left',
            valign='middle',
            size_hint_y=None,
            height=dp(35),
            color=self.COLORE_INTESTAZIONE_ROSATO,
            font_size='16sp',
            font_name='materiale/comicbd.ttf',
            text_size=(dp(270), None)
        ))

        # 3. Funzione per aggiungere una riga di dettaglio
        def add_detail_row_pink(title, keys):
            values = [self.format_data_for_label_pink(key) for key in keys]
            valori_stringa = " / ".join(values)
            detail_text = (
                    f"[color={self.COLORE_TITOLO_DETTAGLIO}]{title}[/color]" +
                    f"[color={self.COLORE_VALORI_DETTAGLIO}][b]{valori_stringa}[/b][/color]"
            )

            label = Label(
                text=detail_text,
                markup=True, halign='left', valign='top',
                size_hint_y=None,
                height=dp(30),
                text_size=(dp(260), None),
                font_name='materiale/comicbd.ttf',
                font_size='13sp'
            )
            label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1] + dp(6)))
            scroll_content.add_widget(label)

        # 4a. Dettagli Vista
        add_detail_row_pink("Vista (Limpidezza / Intensità / Colore):\n",
                            ['limpidezza_rosato', 'intensita_vista_rosato', 'colore_rosato'])

        # 4b. Dettagli Olfatto
        add_detail_row_pink("Olfatto (Condizione / Intensità):\n", ['condizione_rosato', 'intensita_naso_rosato'])
        add_detail_row_pink("Profumi: ", ['profumo_rosato'])

        # 4c. Dettagli Palato
        add_detail_row_pink("Palato: ", ['dolcezza_rosato'])
        add_detail_row_pink("Corpo / Acidità / Tannini / Alcol:\n",
                            ['corpo_rosato', 'acidita_rosato', 'tannicita_rosato', 'livello_alcolico_rosato'])
        add_detail_row_pink("Sapori: ", ['sapore_rosato'])
        add_detail_row_pink("Persistenza / Qualità:\n", ['persistenza_rosato', 'qualita_rosato'])

        # 5. Contenitore dei bottoni
        button_box = BoxLayout(
            orientation='horizontal',
            spacing=dp(10),
            size_hint_y=None,
            height=dp(40),
            padding=dp(2)
        )

        FONT = 'materiale/comicbd.ttf'
        COMPACT_FONT_SIZE = '10sp'

        btn_delete = RoundedButton(
            text='Elimina Scheda',
            size_hint_x=0.35,
            font_name=FONT,
            font_size=COMPACT_FONT_SIZE,
            background_color=(0.8, 0.1, 0.1, 1)
        )
        button_box.add_widget(btn_delete)

        btn_edit = RoundedButton(
            text='Modifica Scheda',
            size_hint_x=0.35,
            font_name=FONT,
            font_size=COMPACT_FONT_SIZE,
            background_color=(0.1, 0.7, 0.1, 1)
        )
        button_box.add_widget(btn_edit)

        btn_close = RoundedButton(
            text="Chiudi",
            size_hint_x=0.30,
            font_name=FONT,
            font_size='12sp',
            background_color=(0.5, 0.5, 0.5, 1)
        )
        button_box.add_widget(btn_close)

        # 6. Contenitore finale del Popup
        final_content = BoxLayout(orientation='vertical', padding=dp(6), spacing=dp(4))

        # --- INTESTAZIONE TITOLO PERSONALIZZATA CON DATA ---
        nome_vino = self.wine_data.get('nome_rosato', 'Vino Sconosciuto')
        data_raw = self.wine_data.get('data_modifica', '')
        data_str = formatta_data(data_raw)
        testo_data = f" [size=13sp][color=#888888]({data_str})[/color][/size]" if data_str else ""

        header_label = Label(
            text=f"[b]{nome_vino}[/b]{testo_data}",
            markup=True,
            font_name='materiale/comicbd.ttf',
            font_size='18sp',
            color=(0.9, 0.4, 0.5, 1),  # Colore rosato
            halign='left',
            valign='middle',
            size_hint_y=None,
            height=dp(30),
            text_size=(dp(280), None)
        )
        final_content.add_widget(header_label)

        # 7. Aggiungi la ScrollView contenente i dettagli
        scroll_view = ScrollView(size_hint_y=0.9, do_scroll_x=False)
        scroll_view.add_widget(scroll_content)

        final_content.add_widget(scroll_view)
        final_content.add_widget(button_box)

        # 8. Creazione del Popup
        popup = Popup(
            title='',
            separator_color=(0.85, 0.35, 0.45, 1),  # Colore separatore rosato
            separator_height=dp(2),
            content=final_content,
            size_hint=(0.95, 0.9),
            background_color=(1, 1, 1, 0.7)
        )

        # =======================================================================
        # COLLEGAMENTO DELLE AZIONI
        # =======================================================================
        btn_delete.bind(on_release=lambda instance: app.confirm_delete_card(self.card_doc_id, 'rosato', popup))
        btn_edit.bind(on_release=lambda x: self.start_edit_flow(popup))
        btn_close.bind(on_release=popup.dismiss)

        popup.open()

        sm = App.get_running_app().root
        archive_screen = sm.get_screen('archivio_rosato')
        archive_screen.detail_popup = popup

    def format_data_for_label_pink(self, key):
        """Recupera i dati, gestendo stringhe e liste (es. da selezione multipla)."""
        value = self.wine_data.get(key, 'N/D')

        if isinstance(value, list):
            return ", ".join(value)
        return str(value)

    def start_edit_flow(self, popup_instance):
        """Chiude il popup e avvia il flusso di modifica, chiamando il metodo nell'App."""

        if popup_instance:
            popup_instance.dismiss()

        app = App.get_running_app()
        wine_color = 'rosato'
        app.start_edit_card(wine_color, self.wine_data, self.card_doc_id)

class RedArchiveScreen(Screen):
    is_crescente = BooleanProperty(False)

    def toggle_ordine_direzione(self):
        self.is_crescente = not self.is_crescente
        criterio = getattr(self.ids, 'spinner_ordinamento', None)
        criterio_testo = criterio.text if criterio else "Inserimento"
        self.load_archive_data(criterio=criterio_testo)

    def on_enter(self):
        criterio = getattr(self.ids, 'spinner_ordinamento', None)
        criterio_testo = criterio.text if criterio else "Inserimento"
        self.load_archive_data(criterio=criterio_testo)

    def load_archive_data(self, criterio="Inserimento"):
        # Assegnazione fondamentale della variabile 'app'
        app = App.get_running_app()
        db_red = app.db_red

        # Salva l'ultimo criterio/verso selezionato nell'istanza dell'app per l'export PDF
        app.ultimo_criterio_ord = criterio
        app.ultimo_verso_crescente = self.is_crescente

        container = self.ids.archive_container
        container.clear_widgets()

        try:
            raw_wines = db_red.all()
        except Exception as e:
            print(f"Errore nella lettura del database rossi: {e}")
            raw_wines = []

        if not raw_wines:
            container.add_widget(Label(text="Nessun vino rosso archiviato.",
                                       size_hint_y=None, height=40,
                                       color=(0.1, 0.1, 0.1, 1)))
            return

        all_wines = []
        for wine_document in raw_wines:
            wine_data = dict(wine_document)
            wine_data['_id'] = wine_document.doc_id
            wine_data['doc_id'] = wine_document.doc_id
            all_wines.append(wine_data)

        vini_ordinati = ordina_lista_vini(all_wines, criterio=criterio, tipo_vino="rosso", crescente=self.is_crescente)

        for i, wine_data in enumerate(vini_ordinati):
            card = RedWineCardItem(wine_data=wine_data, row_index=i, card_doc_id=wine_data['doc_id'])
            container.add_widget(card)

class WhiteArchiveScreen(Screen):
    """Schermata della visualizzazione dell' 'archivio' dei vini bianchi."""

    is_crescente = BooleanProperty(False)

    def toggle_ordine_direzione(self):
        self.is_crescente = not self.is_crescente
        criterio = getattr(self.ids, 'spinner_ordinamento', None)
        criterio_testo = criterio.text if criterio else "Inserimento"
        self.load_archive_data(criterio=criterio_testo)

    def on_enter(self):
        criterio = getattr(self.ids, 'spinner_ordinamento', None)
        criterio_testo = criterio.text if criterio else "Inserimento"
        self.load_archive_data(criterio=criterio_testo)

    def load_archive_data(self, criterio="Inserimento"):
        app = App.get_running_app()
        db_white = app.db_white

        # Salva l'ultimo stato nell'app
        app.ultimo_criterio_ord = criterio
        app.ultimo_verso_crescente = self.is_crescente

        container = self.ids.archive_container
        container.clear_widgets()

        try:
            raw_wines = db_white.all()
        except Exception as e:
            print(f"Errore nella lettura del database bianchi: {e}")
            raw_wines = []

        if not raw_wines:
            container.add_widget(Label(text="Nessun vino bianco archiviato.",
                                       size_hint_y=None, height=40,
                                       color=(0.1, 0.1, 0.1, 1)))
            return

        all_wines = []
        for wine_document in raw_wines:
            wine_data = dict(wine_document)
            wine_data['_id'] = wine_document.doc_id
            wine_data['doc_id'] = wine_document.doc_id
            all_wines.append(wine_data)

        # Applica l'ordinamento dinamico
        vini_ordinati = ordina_lista_vini(all_wines, criterio=criterio, tipo_vino="bianco", crescente=self.is_crescente)

        for i, wine_data in enumerate(vini_ordinati):
            card = WhiteWineCardItem(wine_data=wine_data, row_index=i, card_doc_id=wine_data['doc_id'])
            container.add_widget(card)


class PinkArchiveScreen(Screen):
    """Schermata della visualizzazione dell' 'archivio' dei vini rosati."""

    is_crescente = BooleanProperty(False)

    def toggle_ordine_direzione(self):
        self.is_crescente = not self.is_crescente
        criterio = getattr(self.ids, 'spinner_ordinamento', None)
        criterio_testo = criterio.text if criterio else "Inserimento"
        self.load_archive_data(criterio=criterio_testo)

    def on_enter(self):
        criterio = getattr(self.ids, 'spinner_ordinamento', None)
        criterio_testo = criterio.text if criterio else "Inserimento"
        self.load_archive_data(criterio=criterio_testo)

    def load_archive_data(self, criterio="Inserimento"):
        app = App.get_running_app()
        db_pink = app.db_pink

        # Salva l'ultimo stato nell'app
        app.ultimo_criterio_ord = criterio
        app.ultimo_verso_crescente = self.is_crescente

        container = self.ids.archive_container
        container.clear_widgets()

        try:
            raw_wines = db_pink.all()
        except Exception as e:
            print(f"Errore nella lettura del database rosati: {e}")
            raw_wines = []

        if not raw_wines:
            container.add_widget(Label(text="Nessun vino rosato archiviato.",
                                       size_hint_y=None, height=40,
                                       color=(0.1, 0.1, 0.1, 1)))
            return

        all_wines = []
        for wine_document in raw_wines:
            wine_data = dict(wine_document)
            wine_data['_id'] = wine_document.doc_id
            wine_data['doc_id'] = wine_document.doc_id
            all_wines.append(wine_data)

        # Applica l'ordinamento dinamico
        vini_ordinati = ordina_lista_vini(all_wines, criterio=criterio, tipo_vino="rosato", crescente=self.is_crescente)

        for i, wine_data in enumerate(vini_ordinati):
            card = PinkWineCardItem(wine_data=wine_data, row_index=i, card_doc_id=wine_data['doc_id'])
            container.add_widget(card)

# ==============================================================================
# CLASSE APPLICAZIONE E SCREEN MANAGER
# ==============================================================================


class WineApp(App):
    # Rende la funzione globale accessibile nei file KV tramite app.formatta_data
    formatta_data = staticmethod(formatta_data)

    # Proprietà per lo sfondo. Non usata in questo setup, ma utile per il futuro.
    sfondo_principale = StringProperty("materiale/iniziale.png")

    # Questo dizionario memorizzerà le selezioni dell'utente
    selections = DictProperty({})

    text_inputs = DictProperty({})

    db_red = None  # Aggiungiamo un riferimento al database per i rossi
    db_white = None  # Aggiungiamo un riferimento al database per i bianchi
    db_pink = None  # Aggiungiamo un riferimento al database per i rosati

    # NUOVA PROPRIETÀ per tracciare l'ID del record da aggiornare
    # Usiamo NumericProperty con allownone=True per gestire il valore None (nessuna modifica attiva)
    card_to_update_id = NumericProperty(None, allownone=True)

    # Definisce il colore deselezionato per il reset dei bottoni,
    # ereditato da BaseScreen
    COLOR_DESELECTED_APP = (0.9, 0.9, 0.9, 0.7)

    # Memorizza l'ultimo criterio e verso selezionati dall'utente
    ultimo_criterio_ord = StringProperty("Inserimento")
    ultimo_verso_crescente = BooleanProperty(False)

    def build(self):

        # 1. Inizializziamo SOLO lo ScreenManager e la prima schermata
        self.sm = ScreenManager(transition=FadeTransition())

        # Aggiungiamo SOLO la schermata di benvenuto per ora
        self.sm.add_widget(WelcomeScreen(name='welcome'))

        # 2. Programmiamo il caricamento di tutto il resto "un attimo dopo" l'avvio
        # 0.5 secondi sono sufficienti per far apparire lo schermo al sistema operativo
        Clock.schedule_once(self.lazy_load_everything, 0.5)

        # 3. Gestione tasto back
        Window.bind(on_keyboard=self.on_key_down)

        return self.sm


    def lazy_load_everything(self, dt):
        """
        dt è il 'delta time' passato automaticamente da Clock.
        Anche se non lo usi, deve essere presente tra gli argomenti.
        """
        print("Inizio caricamento database e schermate...")

        # --- 1. INIZIALIZZAZIONE DATABASE ---
        try:
            self.db_red = TinyDB('red_wine_database.json')
            self.db_white = TinyDB('white_wine_database.json')
            self.db_pink = TinyDB('pink_wine_database.json')
            print("Database pronti.")
        except Exception as e:
            print(f"Errore caricamento DB: {e}")

        # --- 2. CREAZIONE DELLE SCHERMATE ---
        # Le creiamo in una lista per poi aggiungerle con un ciclo
        schermate_da_aggiungere = [
            WineSelectionScreen(name='selection'),

            # ROSSI
            RedWineViewScreen(name='vista_rosso'),
            RedWineNoseScreen(name='naso_rosso'),
            RedWineTasteScreen(name='palato_rosso'),
            RedWineEpilogueScreen(name='conclusioni_rosso'),
            RedWineInfoScreen(name='info_rosso'),
            RedArchiveScreen(name='archivio_rosso'),

            # BIANCHI
            WhiteWineViewScreen(name='vista_bianco'),
            WhiteWineNoseScreen(name='naso_bianco'),
            WhiteWineTasteScreen(name='palato_bianco'),
            WhiteWineEpilogueScreen(name='conclusioni_bianco'),
            WhiteWineInfoScreen(name='info_bianco'),
            WhiteArchiveScreen(name='archivio_bianco'),

            # ROSATI
            PinkWineViewScreen(name='vista_rosato'),
            PinkWineNoseScreen(name='naso_rosato'),
            PinkWineTasteScreen(name='palato_rosato'),
            PinkWineEpilogueScreen(name='conclusioni_rosato'),
            PinkWineInfoScreen(name='info_rosato'),
            PinkArchiveScreen(name='archivio_rosato')
        ]

        # --- 3. AGGIUNTA ALLO SCREEN MANAGER ---
        for screen in schermate_da_aggiungere:
            # Verifichiamo che la schermata non sia già stata aggiunta (per sicurezza)
            if not self.sm.has_screen(screen.name):
                self.sm.add_widget(screen)

        print("Tutte le schermate sono state caricate con successo!")

    def on_stop(self):
        """Chiude le connessioni TinyDB all'uscita."""
        print("WineApp: Avvio della chiusura esplicita delle risorse DB.")

        for db in [self.db_red, self.db_white, self.db_pink]:
            if db:
                try:
                    db.close()
                    print(f"TinyDB {db} chiuso.")
                except Exception as e:
                    print(f"ATTENZIONE: Errore durante la chiusura del DB: {e}")

        return super().on_stop()

    # metodo on_key_down
    def on_key_down(self, window, key, *args):
        """Gestisce l'evento di pressione dei tasti, in particolare il tasto 'Back' (27)."""

        # 27 è il codice chiave per il pulsante Indietro su Kivy/Android
        if key == 27:
            current_screen = self.root.current
            is_in_degustazione = current_screen.startswith(('vista_', 'naso_', 'palato_', 'conclusioni_', 'info_'))

            if is_in_degustazione:
                # Naviga alla selezione vino e azzera lo stato di modifica e i dati
                self.root.current = 'selection'
                self.card_to_update_id = None
                self.text_inputs = {}
                self.selections = {}
                return True

            if current_screen in ('welcome', 'selection'):
                # Qui si potrebbe mostrare un popup di conferma uscita
                return True

        return False


    # All'interno di WineApp (metodo che i bottoni sulla schermata 'selection' dovrebbero chiamare)

    def go_to_first_step_and_reset(self, wine_color):
        """Resetta i campi (perché non siamo in modalità edit) e naviga alla prima schermata."""

        # Esegui il reset completo (che avevamo definito prima)
        self.reset_all_data_entry_fields(wine_color)

        # Naviga alla prima schermata
        self.root.current = f'vista_{wine_color}'

    def show_confirm_popup(self, wine_color, info_screen):
        """Crea e mostra il popup di conferma per il colore specificato."""

        FONT = 'materiale/comicbd.ttf'
        COLORE_SFONDO_CHIARO = (0.98, 0.95, 0.90, 0.6)  # Beige Chiaro Universale (sfondo) con trasparenza al 60%
        COLORE_BORDO_SCURO = (0.15, 0.15, 0.15, 1)  # Antracite (testo/bordo)
        RAGGIO_ANGOLI = 15  # Raggio di arrotondamento in pixel
        final_rounded_box = BoxLayout(orientation='vertical', padding=15, spacing=15)

        # TITOLO del popup
        final_rounded_box.add_widget(
            Label(
                text='Sei sicuro?',
                size_hint_y=0.3,
                font_size='18sp',
                bold=True,
                font_name=FONT,
                color=COLORE_BORDO_SCURO
            )
        )

        # Label di avviso (Testo scuro)
        final_rounded_box.add_widget(Label(text='una volta salvato, tutti\n i valori saranno resettati!',
                                           size_hint_y=0.6, font_size='14sp', halign='center',
                                           valign='middle', color=COLORE_BORDO_SCURO,
                                           font_name=FONT))

        # Contenitore per i bottoni
        button_box = BoxLayout(size_hint_y=0.4, spacing=15)

        # Bottoni (con i colori individuali)
        btn_ok = RoundedButton(
            text='Salva', font_name=FONT, background_color=(0.1, 0.7, 0.1, 1)
        )
        btn_cancel = RoundedButton(
            text='Annulla', font_name=FONT, background_color=(0.7, 0.1, 0.1, 1)
        )

        button_box.add_widget(btn_ok)
        button_box.add_widget(btn_cancel)
        final_rounded_box.add_widget(button_box)

        # --- 5. DISEGNO DELLO SFONDO ARROTONDATO SUL CONTENITORE FINALE ---
        with final_rounded_box.canvas.before:
            Color(rgba=COLORE_SFONDO_CHIARO)

            rect = RoundedRectangle(
                pos=final_rounded_box.pos,
                size=final_rounded_box.size,
                radius=[(RAGGIO_ANGOLI, RAGGIO_ANGOLI) for _ in range(4)]
            )

            # Collega la posizione e la dimensione (Fix per l'errore precedente)
            final_rounded_box.bind(
                pos=lambda instance, value: setattr(rect, 'pos', value),
                size=lambda instance, value: setattr(rect, 'size', value)
            )

        # --- CREAZIONE DEL POPUP (Trasparenti) ---

        # 3. Crea l'oggetto Popup
        confirm_popup = Popup(
            title='',  # niente titolo
            content=final_rounded_box,  # contenuto unico senza genitori
            size_hint=(0.75, 0.35),
            auto_dismiss=False,
            # PROPRIETÀ CHIAVE: Rende il Popup Trasparente
            background='',  # Rimuove la texture di sfondo scura
            background_color=(0, 0, 0, 0),
            separator_color=(0, 0, 0, 0),
            title_size='0sp'  # Nasconde definitivamente l'area del titolo
        )

        # 4. Collega le azioni ai bottoni
        btn_ok.bind(on_release=lambda x: self.confirm_and_save(wine_color, info_screen, confirm_popup))
        btn_cancel.bind(on_release=confirm_popup.dismiss)

        # 5. Mostra il popup
        confirm_popup.open()

    def confirm_and_save(self, wine_color, info_screen, popup_instance):
        """Esegue il salvataggio (INSERT) o l'aggiornamento (UPDATE) per il vino specifico e chiude il popup."""

        # Chiude il popup
        popup_instance.dismiss()

        # 0. Seleziona il DB corretto e definisci la destinazione di navigazione
        if wine_color == 'rosso':
            db = self.db_red
            archive_screen_name = 'archivio_rosso'
        elif wine_color == 'bianco':
            db = self.db_white
            archive_screen_name = 'archivio_bianco'
        else:
            db = self.db_pink
            archive_screen_name = 'archivio_rosato'

        # Combina le selezioni dei bottoni con i dati di testo
        wine_card_ordered = self.selections.copy()

        # 2. Campi della SCHEDA INFO
        wine_card_ordered['nome_' + wine_color] = info_screen.ids['nome_' + wine_color].text
        wine_card_ordered['produttore_' + wine_color] = info_screen.ids['produttore_' + wine_color].text
        wine_card_ordered['annata_' + wine_color] = info_screen.ids['annata_' + wine_color].text
        wine_card_ordered['alcol_' + wine_color] = info_screen.ids['alcol_' + wine_color].text

        # 🕒 ASSEGNAZIONE DATA MODIFICA/CREAZIONE
        wine_card_ordered['data_modifica'] = datetime.now().isoformat()

        # Gestione speciale del campo profumo
        profumo_value = wine_card_ordered.get('profumo_' + wine_color, [])
        if isinstance(profumo_value, list):
            wine_card_ordered['profumo_' + wine_color] = ', '.join(profumo_value)

        # 4. LOGICA AGGIORNAMENTO / INSERIMENTO
        if self.card_to_update_id is not None:
            doc_id = self.card_to_update_id
            db.update(wine_card_ordered, doc_ids=[doc_id])
            print(f"Scheda ID {doc_id} aggiornata con successo per {wine_color} in data {wine_card_ordered['data_modifica']}")
            self.card_to_update_id = None
            self.root.current = archive_screen_name
        else:
            db.insert(wine_card_ordered)
            print(f"Nuova scheda salvata con successo per {wine_color} in data {wine_card_ordered['data_modifica']}")
            self.root.current = 'selection'

        # 5. RESET CAMPI
        self.reset_all_data_entry_fields(wine_color)


    def reset_all_selections(self, colore_del_vino):
        # Definisci il colore deselezionato in un punto accessibile, o direttamente qui:
        COLOR_DESELECTED_APP = (0.9, 0.9, 0.9, 0.7)

        # 1. Resetta il dizionario delle selezioni
        self.selections = {}

        # 2. Resetta i bottoni di ogni scheda in modo pulito

        # VISTA
        view_screen = self.root.get_screen('vista_' + colore_del_vino)
        if view_screen:
            for box_id in ['limpidezza_' + colore_del_vino + '_box', 'intensita_vista_' + colore_del_vino + '_box',
                           'colore_' + colore_del_vino + '_box']:
                if box_id in view_screen.ids:
                    box = view_screen.ids[box_id]
                    for btn in box.children:
                        # Usa la costante di colore
                        if hasattr(btn, 'background_color'):
                            btn.background_color = COLOR_DESELECTED_APP
                        # Nota: l'iterazione sui children in Kivy è in ordine inverso.

        # NASO
        nose_screen = self.root.get_screen('naso_' + colore_del_vino)
        if nose_screen:
            # Nota: Ho corretto 'profumo_terzari' in 'profumo_terziari' se necessario,
            # ma uso l'ID che hai fornito.
            for box_id in ['condizione_' + colore_del_vino + '_box', 'intensita_naso_' + colore_del_vino + '_box',
                           'profumo_primari_' + colore_del_vino + '_box',
                           'profumo_secondari_' + colore_del_vino + '_box',
                           'profumo_terziari_' + colore_del_vino + '_box']:  # Uso 'terziari' per coerenza
                if box_id in nose_screen.ids:
                    box = nose_screen.ids[box_id]
                    for btn in box.children:
                        if hasattr(btn, 'background_color'):
                            btn.background_color = COLOR_DESELECTED_APP

        # PALATO
        taste_screen = self.root.get_screen('palato_' + colore_del_vino)
        if taste_screen:
            # Nota: Ho corretto 'sapore_terzari' in 'sapore_terziari' se necessario.
            # Ho aggiunto 'sapore_grid_content' se non usi la distinzione primari/secondari/terziari per il sapore.
            for box_id in ['dolcezza_' + colore_del_vino + '_box', 'acidita_' + colore_del_vino + '_box',
                           'tannicita_' + colore_del_vino + '_box', 'livello_alcolico_' + colore_del_vino + '_box',
                           'corpo_' + colore_del_vino + '_box',
                           'sapore_primari_' + colore_del_vino + '_box',
                           'sapore_secondari_' + colore_del_vino + '_box',
                           'sapore_terziari_' + colore_del_vino + '_box',  # O 'sapore_grid_content' se è un unico box
                           'persistenza_' + colore_del_vino + '_box']:
                if box_id in taste_screen.ids:
                    box = taste_screen.ids[box_id]
                    for btn in box.children:
                        if hasattr(btn, 'background_color'):
                            btn.background_color = COLOR_DESELECTED_APP

        # CONCLUSIONI
        epilogue_screen = self.root.get_screen('conclusioni_' + colore_del_vino)
        if epilogue_screen:
            for box_id in ['qualita_' + colore_del_vino + '_box']:
                if box_id in epilogue_screen.ids:
                    box = epilogue_screen.ids[box_id]
                    for btn in box.children:
                        if hasattr(btn, 'background_color'):
                            btn.background_color = COLOR_DESELECTED_APP

        print(f"Flusso di reset selezioni per {colore_del_vino} completato.")

    def reset_all_data_entry_fields(self, wine_color):
        """Resetta tutti i campi di input di testo e gli spinner sulla schermata INFO
        e azzera le selezioni dei bottoni (tramite reset_all_selections)."""

        # 1. Resetta le selezioni dei bottoni (funzione esistente)
        self.reset_all_selections(wine_color)

        # 2. Resetta lo stato di modifica
        self.card_to_update_id = None  # Cruciale per assicurare che il prossimo salvataggio sia un INSERT
        self.text_inputs = {}  # Azzera il dizionario di pre-caricamento

        # 3. Resetta i campi di testo (sulla schermata INFO)
        info_screen_name = f'info_{wine_color}'
        if self.root.has_screen(info_screen_name):
            info_screen = self.root.get_screen(info_screen_name)

            # Campi di testo: li azzeriamo
            if info_screen.ids.get(f'nome_{wine_color}'):
                info_screen.ids[f'nome_{wine_color}'].text = ''
            if info_screen.ids.get(f'produttore_{wine_color}'):
                info_screen.ids[f'produttore_{wine_color}'].text = ''
            if info_screen.ids.get(f'annata_{wine_color}'):
                info_screen.ids[f'annata_{wine_color}'].text = ''

            # Spinner/Campo alcol: usa il placeholder di default
            if info_screen.ids.get(f'alcol_{wine_color}'):
                info_screen.ids[f'alcol_{wine_color}'].text = 'Gradazione alcolica'

            # Se usi un campo Note Personali (es. note_rosso)
            if info_screen.ids.get(f'note_{wine_color}'):
                info_screen.ids[f'note_{wine_color}'].text = ''

        print(f"Flusso di inserimento scheda {wine_color} resettato completamente.")

    def cancel_edit_and_go_to_selection(self):
        """Annulla esplicitamente qualsiasi operazione di modifica pendente
        (card_to_update_id) e azzera tutti i campi e selezioni, quindi naviga alla selezione vino."""

        # 1. Resetta tutti i flussi di inserimento per tutti i colori
        for color in ['rosso', 'bianco', 'rosato']:
            self.reset_all_data_entry_fields(color)

        # 2. Naviga alla schermata di selezione
        self.root.current = 'selection'

        print("Modalità modifica annullata. Navigazione a Selezione Vino.")

    def show_main_menu(self, menu_anchor_instance):
        """Mostra il menu assicurando dimensioni fisse e visibilità."""

        # Se esiste già un menu aperto, chiudilo per evitare sovrapposizioni
        if hasattr(self, 'current_dropdown') and self.current_dropdown:
            self.current_dropdown.dismiss()

        # Creazione DropDown con auto_width=False
        self.current_dropdown = DropDown(auto_width=False)

        LARGHEZZA_MENU = dp(220)  # Leggermente più largo per sicurezza
        ALTEZZA_BOTTONE = dp(44)

        menu_items = [
            ('materiale/menu_archivio_rossi.png', 'materiale/menu_archivio_rossi_cliccato.png',
             lambda: self.navigate_to_archive('rosso')),
            ('materiale/menu_archivio_bianchi.png', 'materiale/menu_archivio_bianchi_cliccato.png',
             lambda: self.navigate_to_archive('bianco')),
            ('materiale/menu_archivio_rosati.png', 'materiale/menu_archivio_rosati_cliccato.png',
             lambda: self.navigate_to_archive('rosato')),
            ('materiale/Export_Import_button_testo_noBG.png', 'materiale/mExport_Import_button_testo_noBG_cliccato.png',
             lambda btn_inst=None: self.show_export_import_submenu(btn_inst or menu_anchor_instance)),
            ('materiale/menu_vai_a_degustazione.png', 'materiale/menu_vai_a_degustazione_cliccato.png',
             lambda: self.cancel_edit_and_go_to_selection()),
            ('materiale/menu_esci.png', 'materiale/menu_esci_cliccato.png', self.stop)
        ]

        for img_normal, img_down, action in menu_items:
            btn = Button(
                size_hint=(None, None),
                height=ALTEZZA_BOTTONE,
                width=LARGHEZZA_MENU,
                background_normal=img_normal,
                background_down=img_down,
                border=(0, 0, 0, 0)
            )

            btn.bind(on_release=lambda instance, act=action: self._execute_menu_action(self.current_dropdown, act))
            self.current_dropdown.add_widget(btn)

        # --- FORZATURA DIMENSIONI FINALI ---
        self.current_dropdown.width = LARGHEZZA_MENU
        # L'altezza del DropDown deve essere la somma dei bottoni
        self.current_dropdown.container.height = ALTEZZA_BOTTONE * len(menu_items)

        # Apertura sull'ancora
        self.current_dropdown.open(menu_anchor_instance)


    def _execute_menu_action(self, dropdown, action):
        """Esegue l'azione del bottone e chiude il dropdown."""

        dropdown.dismiss()
        action()

    def navigate_to_archive(self, wine_color):
        """Naviga verso la schermata dell'archivio del colore specificato."""
        # NOTA: Assicurati di definire una schermata chiamata 'archivio_rosso' nel tuo KV
        if wine_color == 'degustazione':
            archive_screen_name = 'selection'
        else:
            archive_screen_name = 'archivio_' + wine_color

        # Puoi aggiungere qui logica per caricare i dati prima del cambio
        print(f"Navigazione verso {archive_screen_name}")

        # Esegue il cambio di schermata
        if self.root.has_screen(archive_screen_name):
            # 1. Forza il ricaricamento dei dati dell'archivio PRIMA di navigare.
            # Questo è cruciale per vedere subito modifiche/eliminazioni/nuovi record.
            screen_instance = self.root.get_screen(archive_screen_name)
            if hasattr(screen_instance, 'load_archive_data'):
                screen_instance.load_archive_data()

            # 2. Naviga
            self.root.current = archive_screen_name
        else:
            print(f"Errore: La schermata '{archive_screen_name}' non è definita nel ScreenManager.")

    from kivy.uix.button import Button
    from kivy.uix.dropdown import DropDown
    from kivy.metrics import dp

    def show_export_import_submenu(self, button_instance):
        """Mostra le frecce leggermente più grandi e ben visibili."""

        if hasattr(self, 'current_dropdown') and self.current_dropdown:
            self.current_dropdown.dismiss()

        content_layout = BoxLayout(
            orientation='vertical',
            spacing=dp(12),  # Spazio leggermente aumentato tra i due pulsanti
            padding=[0, 0, 0, 0],
            size_hint=(None, None),
            size=(dp(240), dp(170))  # Contenitore ingrandito
        )

        items = [
            ('materiale/menu_esporta_round_testo_noBG.png', lambda: self.esporta_dati()),
            ('materiale/menu_importa_round_testo_noBG.png', lambda: self.mostra_menu_importa())
        ]

        for img_path, action in items:
            # Pulsanti leggermente più grandi (230x78 dp) mantenendo la proporzione nativa
            btn = ImageButton(
                source=img_path,
                size_hint=(None, None),
                size=(dp(230), dp(78)),  # <-- LEGGERMENTE PIÙ GRANDI
                allow_stretch=True,
                keep_ratio=True,
                on_release=lambda instance, act=action: [view.dismiss(), act()]
            )
            content_layout.add_widget(btn)

        # ModalView adattato alla nuova dimensione dei bottoni
        view = ModalView(
            size_hint=(None, None),
            size=(dp(255), dp(185)),  # <-- Adattato di conseguenza
            background='',
            background_color=(0, 0, 0, 0),  # Trasparente
            auto_dismiss=True
        )

        view.add_widget(content_layout)
        view.open()


    def start_edit_card(self, wine_color, wine_data, card_doc_id):
        """Prepara l'app per la modifica di una scheda esistente.
        Carica i dati della scheda in app.selections e app.text_inputs."""

        # --- AZZERA LO STATO PRIMA DI CARICARE I NUOVI DATI ---
        self.selections.clear()
        self.text_inputs.clear()
        # -----------------------------------------------------------------

        # 1. RECUPERA E IMPOSTA L'ID DEL DOCUMENTO
        # L'ID viene passato come argomento e salvato direttamente.
        self.card_to_update_id = card_doc_id

        # Mappa i dati della scheda in selections e text_inputs per pre-caricare l'UI
        for key, value in wine_data.items():
            if key not in ['_id', 'colore_vino']:  # Escludi ID e colore vino
                # I campi di testo (e lo spinner alcolico) devono essere mappati in text_inputs
                if key in ['nome_' + wine_color, 'produttore_' + wine_color, 'annata_' + wine_color, 'note_personali', 'alcol_' + wine_color]:
                    self.text_inputs[key] = str(value)
                else:
                    # Le selezioni dei bottoni (singole o multiple) vanno in selections
                    self.selections[key] = value

        # 3. Imposta la modalità di modifica
        self.is_editing = True

        # 4. Naviga alla prima schermata di degustazione (Vista)
        first_screen_name = 'vista_' + wine_color.lower()
        if self.root.has_screen(first_screen_name):
            self.root.current = first_screen_name

    def confirm_delete_card(self, card_id, wine_color, detail_popup=None):
        """Mostra un popup di conferma prima dell'eliminazione."""
        self.card_to_delete_id = card_id  # Salva l'ID
        self.wine_color_to_delete = wine_color  # Salva il colore del DB target

        # SALVA IL RIFERIMENTO AL POPUP DEI DETTAGLI PASSATO COME ARGOMENTO.
        self.detail_popup_to_close = detail_popup

        # Dati stilistici per il popup
        FONT = 'materiale/comicbd.ttf'
        COLORE_SFONDO_CHIARO = (0.98, 0.95, 0.90, 0.6)  # Beige Chiaro (sfondo)
        COLORE_BORDO_SCURO = (0.15, 0.15, 0.15, 1)  # Antracite (testo)
        RAGGIO_ANGOLI = 15

        # 2. Costruisce il contenuto del popup di conferma
        final_rounded_box = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        final_rounded_box.add_widget(
            Label(
                text='SEI SICURO?',
                size_hint_y=0.3,
                font_size='18sp',
                bold=True,
                font_name=FONT,
                color=(0.8, 0.1, 0.1, 1)  # Usa il rosso per enfasi
            )
        )

        # Label di avviso (Testo scuro)
        final_rounded_box.add_widget(
            Label(
                text='Questa azione non può\n essere annullata!',
                size_hint_y=0.6,
                font_size='14sp',
                halign='center',
                valign='middle',
                color=COLORE_BORDO_SCURO,
                font_name=FONT
            )
        )

        # Contenitore per i bottoni
        button_box = BoxLayout(size_hint_y=0.4, spacing=dp(15))

        # Bottoni (RoundedButton personalizzati)
        btn_delete = RoundedButton(
            text='ELIMINA',
            font_name=FONT,
            background_color=(0.8, 0.1, 0.1, 1)  # Rosso per eliminare
        )
        btn_cancel = RoundedButton(
            text='Annulla',
            font_name=FONT,
            background_color=(0.5, 0.5, 0.5, 1)  # Grigio per annullare
        )

        button_box.add_widget(btn_delete)
        button_box.add_widget(btn_cancel)
        final_rounded_box.add_widget(button_box)

        # 3. DISEGNO DELLO SFONDO ARROTONDATO SUL CONTENITORE FINALE
        with final_rounded_box.canvas.before:
            Color(rgba=COLORE_SFONDO_CHIARO)
            rect = Factory.RoundedRectangle(
                pos=final_rounded_box.pos,
                size=final_rounded_box.size,
                radius=[(RAGGIO_ANGOLI, RAGGIO_ANGOLI) for _ in range(4)]
            )
            # Collega la posizione e la dimensione per l'aggiornamento grafico
            final_rounded_box.bind(
                pos=lambda instance, value: setattr(rect, 'pos', value),
                size=lambda instance, value: setattr(rect, 'size', value)
            )

        # 4. CREAZIONE DEL POPUP (Trasparente)
        confirm_popup = Popup(
            title='',
            content=final_rounded_box,
            size_hint=(0.75, 0.4),  # Leggermente più alto del popup di salvataggio (0.35)
            auto_dismiss=False,
            # PROPRIETÀ CHIAVE: Rende il Popup Trasparente
            background='',
            background_color=(0, 0, 0, 0),
            separator_color=(0, 0, 0, 0),
            title_size='0sp'
        )

        # 5. Collega le azioni ai bottoni
        # Il bottone Elimina chiama il metodo delete_card (Passaggio 2B) e gli passa il popup per chiuderlo
        btn_delete.bind(on_release=lambda x: self.delete_card(confirm_popup))
        btn_cancel.bind(on_release=confirm_popup.dismiss)

        # 6. Mostra il popup
        confirm_popup.open()

    def delete_card(self, popup_to_dismiss):
        """Elimina la scheda con l'ID salvato e ricarica l'archivio."""

        card_id = self.card_to_delete_id
        wine_color = self.wine_color_to_delete

        # Check di sicurezza
        if card_id is None or wine_color is None:
            if popup_to_dismiss:
                popup_to_dismiss.dismiss()
            return

        # ====================================================================
        # 1. MAPPATURA DEL COLORE (DEVE ESSERE QUI)
        # ====================================================================
        color_map = {'rosso': 'red', 'bianco': 'white', 'rosato': 'pink'}
        short_color = color_map.get(wine_color, 'red')
        db_attr_name = f'db_{short_color}'

        # ====================================================================
        # 2. ELIMINA DAL DB (TinyDB)
        # ====================================================================
        try:
            db = getattr(self, db_attr_name)

            # TinyDB: Rimuovi il documento usando il suo ID univoco
            # Assicurati che 'from tinydb import where' sia importato nel file, se necessario.
            db.remove(doc_ids=[card_id])
            print(f"Scheda {wine_color} con ID {card_id} eliminata con successo.")

        except Exception as e:
            print(f"ERRORE ELIMINAZIONE DB: {e}")
            if popup_to_dismiss:
                popup_to_dismiss.dismiss()
            return

        # ====================================================================
        # 3. AGGIORNA INTERFACCIA E NAVIGA
        # ====================================================================
        archive_screen_name = f'archivio_{wine_color}'
        if self.root.has_screen(archive_screen_name):
            screen_instance = self.root.get_screen(archive_screen_name)

            # 3a. Ricarica i dati (mostrando la lista aggiornata)
            screen_instance.load_archive_data()

            # 3b. Naviga alla schermata dell'archivio
            self.root.current = archive_screen_name

        # ====================================================================
        # 4. CHIUDI IL POPUP DI DETTAGLIO (USANDO IL RIFERIMENTO SALVATO)
        # ====================================================================
        # Chiudiamo il popup di dettaglio scheda usando il riferimento che abbiamo salvato
        # in confirm_delete_card (self.detail_popup_to_close)
        if hasattr(self, 'detail_popup_to_close') and self.detail_popup_to_close:
            self.detail_popup_to_close.dismiss()
            self.detail_popup_to_close = None

        # ====================================================================
        # 5. CHIUDI IL POPUP DI CONFERMA (Chiamato 'popup_to_dismiss')
        # ====================================================================
        if popup_to_dismiss:
            popup_to_dismiss.dismiss()

        # 6. Resetta le variabili temporanee
        self.card_to_delete_id = None
        self.wine_color_to_delete = None
        # Rimuovi anche la variabile temporanea del popup di dettaglio, se presente
        if hasattr(self, 'detail_popup_to_close'):
            del self.detail_popup_to_close

    def on_start(self):
        # Questo forza Kivy a ricalcolare la finestra dopo un istante
        Clock.schedule_once(self.refresh_window, 0.1)

    def refresh_window(self, dt):
        # Trucco: cambiamo leggermente la dimensione della finestra e torniamo indietro
        # Questo "scrollone" costringe il driver Android a mostrare l'immagine
        w, h = Window.size
        Window.size = (w, h + 1)
        Window.size = (w, h)
        # Forza il ridisegno del canvas
        Window.canvas.ask_update()

    def esporta_dati(self):
        content = BoxLayout(
            orientation='vertical',
            spacing=dp(15),
            padding=dp(15)
        )

        # Bottone Esporta DB (Verde chiaro)
        btn_db = CustomOvalButton(
            text="Esporta DB",
            font_size='14sp',
            bold=True,
            color=(0.1, 0.1, 0.1, 1),
            bg_color=[0.45, 0.85, 0.55, 1],
            border_color=[0.0, 0.7, 0.9, 1],
            size_hint=(None, None),
            size=(dp(160), dp(48)),
            pos_hint={'center_x': 0.5}
        )

        # Bottone Esporta HTML
        btn_html = CustomOvalButton(
            text="Esporta HTML",
            font_size='14sp',
            bold=True,
            color=(1, 1, 1, 1),
            bg_color=[0.68, 0.48, 0.82, 1],  # Viola Chiaro
            border_color=[0.0, 0.7, 0.9, 1],
            size_hint=(None, None),
            size=(dp(160), dp(48)),
            pos_hint={'center_x': 0.5}
        )

        view = ModalView(
            size_hint=(None, None),
            size=(dp(240), dp(160)),
            auto_dismiss=True,
            background='',
            background_color=(0, 0, 0, 0),
            overlay_color=(0, 0, 0, 0.2)
        )

        btn_db.bind(on_release=lambda instance: [view.dismiss(), self.esporta_file_db()])

        # Chiamiamo mostra_scelta_html senza argomenti obbligatori
        btn_html.bind(on_release=lambda instance: [view.dismiss(), self.mostra_scelta_html()])

        content.add_widget(btn_db)
        content.add_widget(btn_html)

        view.add_widget(content)
        view.open()

    def mostra_scelta_html(self):
        """Apre un ModalView trasparente per scegliere la categoria da esportare in HTML."""
        content = BoxLayout(
            orientation='vertical',
            spacing=dp(12),
            padding=dp(15)
        )

        opzioni = [
            ("Tutti gli archivi", "tutti", [0.72, 0.75, 0.80, 1], (0.15, 0.15, 0.15, 1)),
            ("Solo Rossi", "rossi", [0.7, 0.45, 0.45, 1], (1, 1, 1, 1)),
            ("Solo Rosati", "rosati", [0.9, 0.75, 0.75, 1], (0.2, 0.1, 0.1, 1)),
            ("Solo Bianchi", "bianchi", [0.9, 0.85, 0.55, 1], (0.2, 0.2, 0.1, 1))
        ]

        view = ModalView(
            size_hint=(None, None),
            size=(dp(240), dp(260)),
            auto_dismiss=True,
            background='',
            background_color=(0, 0, 0, 0),
            overlay_color=(0, 0, 0, 0.2)
        )

        for testo, cat, color_bg, color_text in opzioni:
            btn = CustomOvalButton(
                text=testo,
                font_size='14sp',
                bold=True,
                color=color_text,
                bg_color=color_bg,
                border_color=[0.0, 0.7, 0.9, 1],
                size_hint=(None, None),
                size=(dp(180), dp(44)),
                pos_hint={'center_x': 0.5}
            )
            btn.bind(on_release=lambda instance, c=cat: [view.dismiss(), self.esporta_file_html(c)])
            content.add_widget(btn)

        view.add_widget(content)
        view.open()

    def esporta_file_db(self):
        """Esporta un backup dei database dell'applicazione con data e ora nel nome nella cartella Download."""
        # Generiamo il timestamp corrente (es. 2026-10-20_10-30-00)
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        files_db = [
            "red_wine_database.json",
            "pink_wine_database.json",
            "white_wine_database.json",
            "wine_database.db"
        ]

        # Determiniamo la cartella di destinazione pubblica su Android (Download) o PC
        from kivy.utils import platform
        if platform == 'android':
            try:
                from android.storage import primary_external_storage_path
                # Creiamo una cartella dedicata per questo backup dentro Download per tenere tutto in ordine
                download_dir = os.path.join(primary_external_storage_path(), 'Download', f"WineBackup_{timestamp}")
                os.makedirs(download_dir, exist_ok=True)
                cartella_destinazione = download_dir
            except Exception as e:
                print(f"Errore accesso cartella Download pubblica: {e}, uso fallback.")
                cartella_destinazione = get_export_folder()
        else:
            cartella_destinazione = get_export_folder()
            os.makedirs(cartella_destinazione, exist_ok=True)

        copiati = 0
        for f in files_db:
            if os.path.exists(f):
                # Copiamo direttamente il file mantenendo il nome originale o aggiungendo il timestamp
                nome_backup = f"backup_{timestamp}_{f}"
                percorso_dest = os.path.join(cartella_destinazione, nome_backup)
                shutil.copy(f, percorso_dest)
                copiati += 1

        print(f"Esportati {copiati} file di database in: {cartella_destinazione}")

        # Su PC apriamo anche la cartella di destinazione per comodità
        if platform != 'android':
            import webbrowser
            webbrowser.open(os.path.realpath(cartella_destinazione))

    def carica_vini_da_file(self, nome_file):
        """Cerca il file JSON nella cartella di progetto e carica i dati."""
        percorsi_da_provare = [
            nome_file,
            os.path.join(os.path.dirname(__file__), nome_file),
            os.path.join("data", nome_file),
            os.path.join("database", nome_file)
        ]

        for percorso in percorsi_da_provare:
            if os.path.exists(percorso):
                try:
                    with open(percorso, 'r', encoding='utf-8') as f:
                        dati = json.load(f)
                        print(f"DEBUG: Trovato {percorso} | Tipo dati: {type(dati)}")

                        if isinstance(dati, list):
                            return dati
                        elif isinstance(dati, dict):
                            # Se è un dizionario con chiavi o id
                            for chiave in ['vini', 'wines', 'data', 'items']:
                                if chiave in dati and isinstance(dati[chiave], list):
                                    return dati[chiave]

                            valori = list(dati.values())
                            if valori and isinstance(valori[0], dict):
                                return valori
                            elif valori and isinstance(valori[0], list):
                                lista_piatta = []
                                for elem in valori:
                                    if isinstance(elem, list):
                                        lista_piatta.extend(elem)
                                    elif isinstance(elem, dict):
                                        lista_piatta.append(elem)
                                return lista_piatta
                except Exception as e:
                    print(f"DEBUG: Errore lettura {percorso}: {e}")

        print(f"DEBUG: File {nome_file} non trovato nei percorsi controllati.")
        return []

    def esporta_file_html(self, categoria):
        """Genera un report HTML dettagliato rispettando l'ordinamento attivo nell'app."""
        CARTELLA_DEST = get_export_folder()
        dati_vini = []

        # Recuperiamo i criteri di ordinamento salvati nell'app (se presenti)
        criterio_attivo = getattr(self, 'ultimo_criterio_ord', 'Inserimento')
        verso_crescente = getattr(self, 'ultimo_verso_crescente', False)

        # Mappatura delle categorie, dei file e del tipo vino corrispondente per la funzione di ordinamento
        config_categorie = {
            "rossi": [("Vini Rossi", "red_wine_database.json", "rosso")],
            "rosati": [("Vini Rosati", "pink_wine_database.json", "rosato")],
            "bianchi": [("Vini Bianchi", "white_wine_database.json", "bianco")],
            "tutti": [
                ("Vini Rossi", "red_wine_database.json", "rosso"),
                ("Vini Rosati", "pink_wine_database.json", "rosato"),
                ("Vini Bianchi", "white_wine_database.json", "bianco")
            ]
        }

        elementi_da_elaborare = config_categorie.get(categoria, [])

        # Generiamo il timestamp corrente per il report HTML
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        from tinydb import TinyDB
        for titolo_sezione, filename, tipo_vino in elementi_da_elaborare:
            if os.path.exists(filename):
                db = TinyDB(filename)
                raw_wines = db.all()
                db.close()

                if raw_wines:
                    all_wines = []
                    for wine_document in raw_wines:
                        wine_data = dict(wine_document)
                        wine_data['_id'] = wine_document.doc_id
                        wine_data['doc_id'] = wine_document.doc_id
                        all_wines.append(wine_data)

                    try:
                        vini_ordinati = ordina_lista_vini(
                            all_wines,
                            criterio=criterio_attivo,
                            tipo_vino=tipo_vino,
                            crescente=verso_crescente
                        )
                    except Exception as e:
                        print(f"Errore nell'ordinamento dei vini per l'export: {e}")
                        vini_ordinati = all_wines

                    dati_vini.append((titolo_sezione, vini_ordinati))

        nome_file = f"report_vini_{categoria}_{timestamp}.html"
        percorso_completo = os.path.join(CARTELLA_DEST, nome_file)

        # --- INIZIO COSTRUZIONE HTML (Garantisce che righe_html esista sempre) ---
        righe_html = f"""<!DOCTYPE html>
    <html lang="it">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Report Degustazione Vini - {categoria.capitalize()}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f9f9fb;
                color: #333;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 700px;
                background: #fff;
                padding: 25px;
                border-radius: 10px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                margin: auto;
            }}
            h1 {{
                color: #722F37;
                text-align: center;
                border-bottom: 3px solid #722F37;
                padding-bottom: 12px;
                margin-bottom: 25px;
            }}
            h2 {{
                color: #444;
                border-bottom: 1px solid #ddd;
                padding-bottom: 6px;
                margin-top: 30px;
            }}
            .vino-card {{
                background: #fdfdfd;
                border: 1px solid #e5e5e5;
                border-radius: 6px;
                padding: 15px;
                margin-bottom: 15px;
            }}
            .vino-card p {{
                margin: 4px 0;
            }}
            .label {{
                font-weight: bold;
                color: #555;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                font-size: 0.85em;
                color: #777;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Report Degustazione - {categoria.upper()}</h1>
            <p style="text-align: center; color: #666; font-size: 0.9em;">Criterio di ordinamento: <b>{criterio_attivo}</b> ({'Crescente' if verso_crescente else 'Decrescente'})</p>
    """

        if not dati_vini:
            righe_html += "<p style='text-align: center; color: #777;'>Nessun dato trovato per questa categoria.</p>"
        else:
            for sezione, records in dati_vini:
                righe_html += f"<h2>{sezione}</h2>"
                for r in records:
                    if isinstance(r, dict):
                        suf = "_rosso" if "rosso" in "".join(r.keys()) else (
                            "_bianco" if "bianco" in "".join(r.keys()) else "")

                        nome = r.get(f'nome{suf}', r.get('nome', 'Vino senza nome'))
                        annata = r.get(f'annata{suf}', r.get('annata', 'N/D'))
                        produttore = r.get(f'produttore{suf}', r.get('produttore', 'N/D'))
                        alcol = r.get(f'alcol{suf}', r.get('alcol', 'N/D'))
                        data_mod = r.get('data_modifica', '')[:10]
                        if data_mod:
                            parts = data_mod.split('-')
                            if len(parts) == 3:
                                data_mod = f"({parts[2]}/{parts[1]}/{parts[0][2:]})"

                        limpidezza = r.get(f'limpidezza{suf}', r.get('limpidezza', 'N/D'))
                        intensita_v = r.get(f'intensita_vista{suf}', r.get('intensita_vista', 'N/D'))
                        colore = r.get(f'colore{suf}', r.get('colore', 'N/D'))
                        if isinstance(colore, list):
                            colore = ", ".join(colore)

                        condizione = r.get(f'condizione{suf}', r.get('condizione', 'N/D'))
                        intensita_n = r.get(f'intensita_naso{suf}', r.get('intensita_naso', 'N/D'))
                        profumo = r.get(f'profumo{suf}', r.get('profumo', 'N/D'))
                        if isinstance(profumo, list):
                            profumo = ", ".join(profumo)

                        dolcezza = r.get(f'dolcezza{suf}', r.get('dolcezza', 'N/D'))
                        corpo = r.get(f'corpo{suf}', r.get('corpo', 'N/D'))
                        acidita = r.get(f'acidita{suf}', r.get('acidita', 'N/D'))
                        tannicita = r.get(f'tannicita{suf}', r.get('tannicita', 'N/D'))
                        livello_alc = r.get(f'livello_alcolico{suf}', r.get('livello_alcolico', 'N/D'))

                        sapore = r.get(f'sapore{suf}', r.get('sapore', 'N/D'))
                        if isinstance(sapore, list):
                            sapore = ", ".join(sapore)

                        persistenza = r.get(f'persistenza{suf}', r.get('persistenza', 'N/D'))
                        qualita = r.get(f'qualita{suf}', r.get('qualita', 'N/D'))

                        righe_html += f"""
                        <div class="vino-card">
                            <h3 style="color: #722F37; margin-top: 0; margin-bottom: 5px;">{nome} <span style="font-size: 0.8em; color: #666;">{data_mod}</span></h3>
                            <p style="margin: 2px 0 10px 0; font-weight: bold; color: #444;">{produttore} &nbsp;&nbsp; {annata} &nbsp;&nbsp; {alcol}° vol.</p>

                            <hr style="border: 0; border-top: 1px solid #eee; margin: 8px 0;">

                            <p><span class="label">Vista (Limpidezza / Intensità / Colore):</span><br>
                            {limpidezza} / {intensita_v} / {colore}</p>

                            <p><span class="label">Olfatto (Condizione / Intensità):</span><br>
                            {condizione} / {intensita_n}</p>

                            <p><span class="label">Profumi:</span><br>
                            {profumo}</p>

                            <p><span class="label">Palato:</span><br>
                            {dolcezza}</p>

                            <p><span class="label">Corpo / Acidità / Tannini / Alcol:</span><br>
                            {corpo} / {acidita} / {tannicita} / {livello_alc}</p>

                            <p><span class="label">Sapori:</span><br>
                            {sapore}</p>

                            <p><span class="label">Persistenza / Qualità:</span><br>
                            {persistenza} / {qualita}</p>
                        </div>
                        """
                    else:
                        righe_html += f"<div class='vino-card'><p>{str(r)}</p></div>"

        righe_html += """
            <div class="footer">
                Generato con WineTastingApp
            </div>
        </div>
    </body>
    </html>
    """
        # --- FINE COSTRUZIONE HTML ---

        # Salvataggio fisico del file
        from kivy.utils import platform
        if platform == 'android':
            try:
                # Salviamo direttamente nella cartella Download pubblica di Android
                from android.storage import app_storage_path, primary_external_storage_path
                import shutil

                # Percorso della cartella Download pubblica del dispositivo
                download_dir = os.path.join(primary_external_storage_path(), 'Download')
                if not os.path.exists(download_dir):
                    os.makedirs(download_dir, exist_ok=True)

                percorso_pubblico = os.path.join(download_dir, nome_file)

                # Scriviamo prima nel percorso temporaneo e poi copiamo nella cartella Download
                with open(percorso_completo, "w", encoding="utf-8") as f:
                    f.write(righe_html)

                shutil.copy(percorso_completo, percorso_pubblico)
                print(f"Report HTML salvato con successo in Download: {percorso_pubblico}")

            except Exception as e:
                print(f"Errore nel salvataggio pubblico su Android: {e}")
                # Fallback sul percorso privato se la cartella pubblica non è accessibile
                with open(percorso_completo, "w", encoding="utf-8") as f:
                    f.write(righe_html)
        else:
            # Su PC salva normalmente nella cartella di esportazione
            with open(percorso_completo, "w", encoding="utf-8") as f:
                f.write(righe_html)
            print(f"File salvato sul PC in: {percorso_completo}")
            import webbrowser
            webbrowser.open('file://' + os.path.realpath(percorso_completo))

    def scrivi_file_android(self, uri_string, contenuto):
        """Scrive il contenuto nel file selezionato dall'utente tramite Android SAF."""
        try:
            from jnius import autoclass
            from android import mActivity

            Uri = autoclass('android.net.Uri')
            String = autoclass('java.lang.String')

            context = mActivity.getApplicationContext()
            content_resolver = context.getContentResolver()

            uri = Uri.parse(uri_string)
            # Apre uno stream di scrittura in modalità "w" (tronca/scrive da zero)
            pfd = content_resolver.openFileDescriptor(uri, "w")
            fos = autoclass('java.io.FileOutputStream')(pfd.getFileDescriptor())

            # Converte il contenuto in bytes e lo scrive nello stream
            byte_data = contenuto.encode('utf-8')
            fos.write(byte_data)
            fos.close()
            pfd.close()
            print("File salvato con successo tramite selettore nativo Android!")
        except Exception as e:
            print(f"Errore durante la scrittura del file su Android: {e}")

    def mostra_menu_importa(self):
        """Mostra il popup iniziale per l'importazione dei dati."""
        content = BoxLayout(
            orientation='vertical',
            spacing=dp(15),
            padding=dp(15)
        )

        # Pulsante Importa DB
        btn_import = CustomOvalButton(
            text="Seleziona File DB",
            font_size='14sp',
            bold=True,
            color=(1, 1, 1, 1),
            bg_color=[0.25, 0.55, 0.85, 1],  # Blu / Azzurro pastello
            border_color=[0.0, 0.7, 0.9, 1],
            size_hint=(None, None),
            size=(dp(180), dp(48)),
            pos_hint={'center_x': 0.5}
        )

        view = ModalView(
            size_hint=(None, None),
            size=(dp(240), dp(120)),
            auto_dismiss=True,
            background='',
            background_color=(0, 0, 0, 0),
            overlay_color=(0, 0, 0, 0.2)
        )

        btn_import.bind(on_release=lambda instance: [view.dismiss(), self.apri_file_chooser_importa()])

        content.add_widget(btn_import)
        view.add_widget(content)
        view.open()

    def apri_file_chooser_importa(self):
        """Apre il selettore file nativo di Android tramite l'API standard android.activity di p4a."""
        from kivy.utils import platform

        if platform == 'android':
            try:
                import android.activity
                from jnius import autoclass
                from android import mActivity

                Intent = autoclass('android.content.Intent')
                intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
                intent.addCategory(Intent.CATEGORY_OPENABLE)
                intent.setType("application/json")

                CHOOSER_CODE = 9005

                def on_activity_result(requestCode, resultCode, intentData):
                    if requestCode == CHOOSER_CODE:
                        try:
                            android.activity.unbind(on_activity_result=on_activity_result)
                        except Exception:
                            pass

                        # -1 corrisponde a RESULT_OK in Android
                        if resultCode == -1 and intentData is not None:
                            uri = intentData.getData()
                            if uri is not None:
                                local_path = self._copia_uri_locale(uri)
                                if local_path:
                                    from kivy.clock import Clock
                                    Clock.schedule_once(lambda dt: self._prepara_importazione([local_path], None), 0.1)

                # Registriamo il callback con il modulo ufficiale di python-for-android
                android.activity.bind(on_activity_result=on_activity_result)

                # Avviamo l'activity per il risultato
                mActivity.startActivityForResult(intent, CHOOSER_CODE)
                print("Selettore file nativo Android avviato con successo.")
                return
            except Exception as e:
                print(f"Errore nell'avvio del selettore nativo Android: {e}")

        # --- FALLBACK PER PC (Desktop Ubuntu) ---
        box = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        path_iniziale = get_export_folder()

        file_chooser = FileChooserListView(
            path=path_iniziale,
            filters=['*.json'],
            size_hint=(1, 1)
        )
        box.add_widget(file_chooser)

        btn_box = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
        btn_annulla = Button(text="Annulla", size_hint_x=0.4)
        btn_conferma = Button(text="Importa", size_hint_x=0.6, background_color=(0.25, 0.55, 0.85, 1))

        btn_box.add_widget(btn_annulla)
        btn_box.add_widget(btn_conferma)
        box.add_widget(btn_box)

        popup = Popup(
            title="Seleziona File da Importare",
            content=box,
            size_hint=(0.9, 0.8)
        )

        btn_annulla.bind(on_release=popup.dismiss)

        def conferma_selezione(instance):
            if file_chooser.selection:
                file_scelto = file_chooser.selection[0]
                popup.dismiss()
                self._prepara_importazione([file_scelto], popup)

        btn_conferma.bind(on_release=conferma_selezione)
        popup.open()

    def _copia_uri_locale(self, uri):
        """Legge l'URI esterno tramite ContentResolver e lo copia localmente per l'importazione."""
        try:
            from android import mActivity
            from jnius import autoclass

            cr = mActivity.getContentResolver()
            input_stream = cr.openInputStream(uri)

            local_path = os.path.join(get_export_folder(), "import_temp.json")

            FileOutputStream = autoclass('java.io.FileOutputStream')
            out_stream = FileOutputStream(local_path)

            from jnius import ByteArray
            buffer = ByteArray(1024)
            while True:
                bytes_read = input_stream.read(buffer)
                if bytes_read == -1:
                    break
                out_stream.write(buffer, 0, bytes_read)

            input_stream.close()
            out_stream.close()
            print(f"File esterno copiato con successo in locale: {local_path}")
            return local_path
        except Exception as e:
            print(f"Errore nella lettura del file esterno: {e}")
            return None

    def _ottieni_percorso_da_uri(self, uri):
        """Helper per convertire un URI di Android in un percorso file temporaneo leggibile da Python."""
        try:
            from android import mActivity
            import shutil

            cr = mActivity.getContentResolver()
            input_stream = cr.openInputStream(uri)

            # Salviamo una copia temporanea del file scelto nella cartella interna dell'app per poterlo leggere con TinyDB
            temp_path = os.path.join(get_export_folder(), "temp_import.json")

            FileOutputStream = autoclass('java.io.FileOutputStream')
            out_stream = FileOutputStream(temp_path)

            # Buffer di lettura
            from jnius import ByteArray
            buffer = ByteArray(1024)
            while True:
                bytes_read = input_stream.read(buffer)
                if bytes_read == -1:
                    break
                out_stream.write(buffer, 0, bytes_read)

            input_stream.close()
            out_stream.close()
            return temp_path
        except Exception as e:
            print(f"Errore nella lettura dell'URI del file: {e}")
            return None

    def _prepara_importazione(self, selezione, popup_file):
        """Verifica il file selezionato e chiede la modalità di importazione."""
        if not selezione:
            return

        percorso_file = selezione[0]
        popup_file.dismiss()

        # Popup per scegliere la modalità: Unisci vs Sostituisci
        content = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(15))

        lbl = Label(
            text="Come desideri importare i vini?",
            font_size='14sp',
            bold=True,
            size_hint_y=None,
            height=dp(30)
        )
        content.add_widget(lbl)

        btn_unisci = CustomOvalButton(
            text="Unisci (Aggiungi nuovi)",
            font_size='13sp',
            bold=True,
            color=(1, 1, 1, 1),
            bg_color=[0.3, 0.65, 0.4, 1],  # Verde
            border_color=[0.0, 0.7, 0.9, 1],
            size_hint=(None, None),
            size=(dp(200), dp(44)),
            pos_hint={'center_x': 0.5}
        )

        btn_sostituisci = CustomOvalButton(
            text="Sostituisci Tutto",
            font_size='13sp',
            bold=True,
            color=(1, 1, 1, 1),
            bg_color=[0.8, 0.3, 0.3, 1],  # Rosso
            border_color=[0.0, 0.7, 0.9, 1],
            size_hint=(None, None),
            size=(dp(200), dp(44)),
            pos_hint={'center_x': 0.5}
        )

        view = ModalView(
            size_hint=(None, None),
            size=(dp(250), dp(200)),
            auto_dismiss=True,
            background='',
            background_color=(0, 0, 0, 0),
            overlay_color=(0, 0, 0, 0.2)
        )

        btn_unisci.bind(
            on_release=lambda x: [view.dismiss(), self.esegui_importazione(percorso_file, modalita="unisci")])
        btn_sostituisci.bind(
            on_release=lambda x: [view.dismiss(), self.esegui_importazione(percorso_file, modalita="sostituisci")])

        content.add_widget(btn_unisci)
        content.add_widget(btn_sostituisci)

        view.add_widget(content)
        view.open()

    def esegui_importazione(self, percorso_file, modalita="unisci"):
        """Importa i vini evitando duplicati basandosi su (Nome + Produttore + Annata)
        e aggiorna la scheda se la versione importata ha una data più recente.
        """
        try:
            import json
            with open(percorso_file, 'r', encoding='utf-8') as f:
                dati_importati = json.load(f)

            # Estrazione vini dal file JSON
            vini_da_importare = []
            if isinstance(dati_importati, list):
                vini_da_importare = dati_importati
            elif isinstance(dati_importati, dict):
                for table_val in dati_importati.values():
                    if isinstance(table_val, dict):
                        for doc_val in table_val.values():
                            if isinstance(doc_val, dict):
                                vini_da_importare.append(doc_val)
                    elif isinstance(table_val, list):
                        vini_da_importare.extend(table_val)

            db_map = {
                "rosso": self.db_red,
                "bianco": self.db_white,
                "rosato": self.db_pink
            }

            nuovi_inseriti = 0
            aggiornati = 0

            # Se sostituisci, svuota i DB
            if modalita == "sostituisci":
                for db in db_map.values():
                    db.truncate()

            for vino in vini_da_importare:
                if not isinstance(vino, dict):
                    continue

                vino_pulito = {k: v for k, v in vino.items() if k != '_id'}

                # Se manca la data nel file importato, usa la data attuale
                if 'data_modifica' not in vino_pulito or not vino_pulito['data_modifica']:
                    vino_pulito['data_modifica'] = datetime.now().isoformat()

                # Riconoscimento categoria
                cat_target = "rosso"
                if any('bianco' in k.lower() for k in vino_pulito.keys()):
                    cat_target = "bianco"
                elif any('rosat' in k.lower() or 'pink' in k.lower() for k in vino_pulito.keys()):
                    cat_target = "rosato"

                db_target = db_map[cat_target]

                # Helper per estrarre il valore pulito dai vari suffissi
                def get_val(d, *keys):
                    for k in keys:
                        for dict_k, dict_v in d.items():
                            if k in dict_k.lower() and dict_v:
                                return str(dict_v).strip().lower()
                    return ''

                nome = get_val(vino_pulito, 'nome_rosso', 'nome_bianco', 'nome_rosato', 'nome')
                produttore = get_val(vino_pulito, 'produttore_rosso', 'produttore_bianco', 'produttore_rosato', 'produttore', 'cantina')
                annata = get_val(vino_pulito, 'annata_rosso', 'annata_bianco', 'annata_rosato', 'annata')

                if modalita == "sostituisci":
                    db_target.insert(vino_pulito)
                    nuovi_inseriti += 1
                else:
                    # Modalità UNISCI: Cerca duplicati
                    tutti_esistenti = db_target.all()
                    trovato_doc = None

                    for doc in tutti_esistenti:
                        d_nome = get_val(doc, 'nome_rosso', 'nome_bianco', 'nome_rosato', 'nome')
                        d_prod = get_val(doc, 'produttore_rosso', 'produttore_bianco', 'produttore_rosato', 'produttore', 'cantina')
                        d_ann = get_val(doc, 'annata_rosso', 'annata_bianco', 'annata_rosato', 'annata')

                        if d_nome == nome and d_prod == produttore and d_ann == annata:
                            trovato_doc = doc
                            break

                    if trovato_doc:
                        # Confronto date di modifica
                        data_esistente = trovato_doc.get('data_modifica', '1970-01-01T00:00:00')
                        data_nuova = vino_pulito.get('data_modifica', '1970-01-01T00:00:00')

                        if data_nuova > data_esistente:
                            db_target.update(vino_pulito, doc_ids=[trovato_doc.doc_id])
                            aggiornati += 1
                    else:
                        db_target.insert(vino_pulito)
                        nuovi_inseriti += 1

            # Ricarica lo schermo dell'archivio attivo
            current_screen = self.sm.current_screen if hasattr(self, 'sm') else None
            if current_screen and hasattr(current_screen, 'load_archive_data'):
                current_screen.load_archive_data()

            msg = f"Importazione completata!\n\nNuovi inseriti: {nuovi_inseriti}\nSchede aggiornate: {aggiornati}"
            popup_successo = Popup(
                title="Esito Importazione",
                content=Label(text=msg, halign='center'),
                size_hint=(None, None),
                size=(dp(300), dp(180))
            )
            popup_successo.open()

        except Exception as e:
            popup_errore = Popup(
                title="Errore Importazione",
                content=Label(text=f"Impossibile importare il file:\n{e}"),
                size_hint=(None, None),
                size=(dp(320), dp(180))
            )
            popup_errore.open()


if __name__ == '__main__':
    WineApp().run()
