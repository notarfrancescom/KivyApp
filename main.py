# -*- coding: utf-8 -*-
import kivy
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.lang import Builder
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior
from kivy.graphics import Color, RoundedRectangle
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
from tinydb import TinyDB, Query
import json  # Utile per visualizzare i dati per debug
from kivy.core.window import Window

# Importa i widget utilizzati nel KV
from kivy.uix.image import Image
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.spinner import Spinner


# Imposta la dimensione fissa della finestra
# Queste linee VANNO RIMOSSE (o commentate) prima di creare l'APK per usare la risoluzione nativa.
Window.size = (360, 640)
#Window.size = (1080, 1920)
Window.resizable = False

# Colore di default per i bottoni deselezionati
COLOR_DESELECTED_APP = (0.9, 0.9, 0.9, 0.7)


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

        # 3. Se siamo in modalità modifica, evidenzia i valori
        if app.card_to_update_id is not None:
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

    def on_enter(self, *args):
        super().on_enter(*args)
        app = App.get_running_app()

        # Reset dei colori (metodo della BaseScreen)
        self._reset_button_colors()

        # Se siamo in modifica, applica le selezioni caricate
        if app.card_to_update_id is not None:
            # DEBUG: stampa cosa c'è in app.selections se ancora non vedi nulla
            print(f"DEBUG NASO: {app.selections}")
            self._apply_selections(app, self.SELECTION_KEYS)


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
    def on_enter(self, *args):
        super().on_enter(*args)
        app = App.get_running_app()

        # Reset dei colori
        self._reset_button_colors()

        # Se siamo in modifica, evidenzia i valori salvati
        if app.card_to_update_id is not None:
            self._apply_selections(app, self.SELECTION_KEYS)


class RedWineEpilogueScreen(BaseScreen):
    """Schermata di 'Conclusione' del vino rosso."""
    SELECTION_KEYS = ['qualita_rosso_box']
    def on_enter(self, *args):
        # 🚨 IMPORTANTE: Chiama la logica di caricamento dati del genitore
        super().on_enter(*args)

        # Forza lo stato del MenuButton su 'normal' per resettare l'immagine
        menu_btn = self.ids.get('menu_button')
        if menu_btn:
            menu_btn.state = 'normal'
    pass


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

            # Se la schermata Info non si auto-resetta dopo il salvataggio:
            # self.ids['nome_rosso'].text = ''
            # self.ids['produttore_rosso'].text = ''
            # self.ids['annata_rosso'].text = ''
            # self.ids['alcol_rosso'].text = 'Gradazione alcolica'


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

    def on_enter(self, *args):
        super().on_enter(*args)
        app = App.get_running_app()

        # Reset dei colori (metodo della BaseScreen)
        self._reset_button_colors()

        # Se siamo in modifica, applica le selezioni caricate
        if app.card_to_update_id is not None:
            # DEBUG: stampa cosa c'è in app.selections se ancora non vedi nulla
            print(f"DEBUG NASO: {app.selections}")
            self._apply_selections(app, self.SELECTION_KEYS)


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
    def on_enter(self, *args):
        super().on_enter(*args)
        app = App.get_running_app()

        # Reset dei colori
        self._reset_button_colors()

        # Se siamo in modifica, evidenzia i valori salvati
        if app.card_to_update_id is not None:
            self._apply_selections(app, self.SELECTION_KEYS)


class WhiteWineEpilogueScreen(BaseScreen):
    """Schermata di 'Conclusione' del vino rosso."""
    SELECTION_KEYS = ['qualita_bianco_box']
    def on_enter(self, *args):
        # 🚨 IMPORTANTE: Chiama la logica di caricamento dati del genitore
        super().on_enter(*args)

        # Forza lo stato del MenuButton su 'normal' per resettare l'immagine
        menu_btn = self.ids.get('menu_button')
        if menu_btn:
            menu_btn.state = 'normal'
    pass


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

            # Se la schermata Info non si auto-resetta dopo il salvataggio:
            # self.ids['nome_bianco'].text = ''
            # self.ids['produttore_bianco'].text = ''
            # self.ids['annata_bianco'].text = ''
            # self.ids['alcol_bianco'].text = 'Gradazione alcolica'


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

    def on_enter(self, *args):
        super().on_enter(*args)
        app = App.get_running_app()

        # Reset dei colori (metodo della BaseScreen)
        self._reset_button_colors()

        # Se siamo in modifica, applica le selezioni caricate
        if app.card_to_update_id is not None:
            # DEBUG: stampa cosa c'è in app.selections se ancora non vedi nulla
            print(f"DEBUG NASO: {app.selections}")
            self._apply_selections(app, self.SELECTION_KEYS)


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
    def on_enter(self, *args):
        super().on_enter(*args)
        app = App.get_running_app()

        # Reset dei colori
        self._reset_button_colors()

        # Se siamo in modifica, evidenzia i valori salvati
        if app.card_to_update_id is not None:
            self._apply_selections(app, self.SELECTION_KEYS)


class PinkWineEpilogueScreen(BaseScreen):
    """Schermata di 'Conclusione' del vino rosato."""
    SELECTION_KEYS = ['qualita_rosato_box']
    def on_enter(self, *args):
        # 🚨 IMPORTANTE: Chiama la logica di caricamento dati del genitore
        super().on_enter(*args)

        # Forza lo stato del MenuButton su 'normal' per resettare l'immagine
        menu_btn = self.ids.get('menu_button')
        if menu_btn:
            menu_btn.state = 'normal'
    pass


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

            # Se la schermata Info non si auto-resetta dopo il salvataggio:
            # self.ids['nome_rosato'].text = ''
            # self.ids['produttore_rosato'].text = ''
            # self.ids['annata_rosato'].text = ''
            # self.ids['alcol_rosato'].text = 'Gradazione alcolica'


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

        # 2. Intestazione
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
            # Combina i valori usando il metodo helper
            colore_titolo_rosso = "#F27373FF"   # Rosso Fragola
            colore_valori_rosso = "#E63333FF"   # Rosso Scuro/Vino
            values = [self.format_data_for_label_red(key) for key in keys]
            valori_stringa = " / ".join(values)
            detail_text = (
                    f"[color={colore_titolo_rosso}]{title}[/color]" +  # Prima parte (Titolo)
                    f"[color={colore_valori_rosso}][b]{valori_stringa}[/b][/color]"  # Seconda parte (Valori)
            )

            # Usiamo Label dinamico (Dimensione fissa in X e altezza automatica in Y)
            label = Label(
                text=detail_text,
                markup=True, halign='left', valign='top',
                size_hint_y=None,
                height=dp(30),  # Altezza minima di default, per sicurezza.
                text_size=(dp(260), None),  # Usa una larghezza FISSA (es. 260dp)
                font_name='materiale/comicbd.ttf',
                font_size='13sp'
            )
            # Usa una funzione lambda per impostare 'height' al solo valore Y di 'texture_size' (indice [1])
            label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1] + dp(6)))
            # Ho aggiunto dp(5) per un piccolo padding extra/margine

            scroll_content.add_widget(label)

        # 4a. Dettagli Vista
        add_detail_row_red("Vista (Limpidezza / Intensità / Colore):\n", ['limpidezza_rosso', 'intensita_vista_rosso', 'colore_rosso'])

        # 4b. Dettagli Olfatto
        add_detail_row_red("Olfatto (Condizione / Intensità):\n", ['condizione_rosso', 'intensita_naso_rosso']),
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
            height=dp(40),  # Altezza fissa per i bottoni
            padding=dp(2)
        )

        # Poiché i testi sono lunghi, usiamo un font molto piccolo (10sp)
        FONT = 'materiale/comicbd.ttf'
        COMPACT_FONT_SIZE = '10sp'

        # A. Bottone Elimina Scheda
        btn_delete = RoundedButton(
            text='Elimina Scheda',
            size_hint_x=0.35,  # 1/3 dello spazio
            font_name=FONT,
            font_size=COMPACT_FONT_SIZE,
            background_color=(0.8, 0.1, 0.1, 1)  # Rosso per l'azione distruttiva
        )
        # Collega all'App: chiama la funzione di conferma, passando l'ID e il colore
        #btn_delete.bind(on_release=lambda instance: app.confirm_delete_card(self.card_doc_id, 'rosso'))
        button_box.add_widget(btn_delete)

        # B. Bottone Modifica Scheda
        btn_edit = RoundedButton(
            text='Modifica Scheda',
            size_hint_x=0.35,
            font_name=FONT,
            font_size=COMPACT_FONT_SIZE,
            background_color=(0.1, 0.7, 0.1, 1)  # Verde
        )
        # Collega all'azione di avvio modifica e chiudi il popup
        #btn_edit.bind(on_release=lambda instance: self.start_edit_flow(popup))
        button_box.add_widget(btn_edit)

        # C. Bottone Chiudi/Annulla
        btn_close = RoundedButton(
            text="Chiudi",
            size_hint_x=0.30,
            font_name=FONT,
            font_size='12sp',
            background_color=(0.5, 0.5, 0.5, 1)  # Grigio neutro
        )
        # Collega l'azione di chiusura del popup
        #btn_close.bind(on_release=popup.dismiss)  # NOTA: 'popup' viene definito più in basso
        button_box.add_widget(btn_close)

        # 6. Contenitore finale del Popup (per Scrollview e Bottone)
        final_content = BoxLayout(orientation='vertical', padding=dp(6), spacing=dp(4))

        # 7. Aggiungi la ScrollView contenente tutti i dettagli
        scroll_view = ScrollView(size_hint_y=0.9, do_scroll_x=False)
        scroll_view.add_widget(scroll_content)  # Aggiunge il contenuto di testo alla ScrollView

        final_content.add_widget(scroll_view)  # Aggiunge la ScrollView al contenitore finale
        final_content.add_widget(button_box)  # Aggiunge il contenitore dei bottoni

        # 8. Creazione del Popup
        # Recuperiamo il nome del vino
        nome_vino = self.wine_data.get('nome_rosso', 'Vino Sconosciuto')

        popup = Popup(
            title=nome_vino,
            title_font='materiale/comicbd.ttf',
            title_color=(0.9, 0.2, 0.2, 1),  # Rosso Scuro/Vino
            title_size='18sp',
            separator_color=(0.6, 0, 0, 1),
            content=final_content,  # Usa il contenitore finale
            size_hint=(0.95, 0.9),
            background_color=(1, 1, 1, 0.7)
        )

        # =======================================================================
        # COLLEGAMENTO DELLE AZIONI (DOPO CHE 'popup' È STATO DEFINITO)
        # =======================================================================

        # A. Collega l'azione del bottone Elimina (Passando il riferimento al popup di dettaglio)
        btn_delete.bind(on_release=lambda instance: app.confirm_delete_card(self.card_doc_id, 'rosso', popup))

        # B. Collega l'azione del bottone di Modifica (Passando il riferimento al popup di dettaglio)
        btn_edit.bind(on_release=lambda x: self.start_edit_flow(popup))

        # C. Collega l'azione del bottone di chiusura al popup.dismiss
        btn_close.bind(on_release=popup.dismiss)

        popup.open()

        # TROVA LO SCHERMO ARCHIVIO ATTUALE E SALVA IL RIFERIMENTO DEL POPUP
        sm = App.get_running_app().root
        archive_screen = sm.get_screen(f'archivio_rosso')
        archive_screen.detail_popup = popup  # <--- SALVA IL RIFERIMENTO QUI
    def format_data_for_label_red(self, key):
        """Recupera i dati, gestendo stringhe e liste (es. da selezione multipla)."""
        value = self.wine_data.get(key, 'N/D')

        if isinstance(value, list):
            # Se è una lista, unisci gli elementi con una virgola
            return ", ".join(value)
        # Se è una stringa o altro, restituisci il valore così com'è
        return str(value)

    def start_edit_flow(self, popup_instance):
        """Chiude il popup e avvia il flusso di modifica, chiamando il metodo nell'App."""

        # Chiude il popup per mostrare la schermata di modifica
        if popup_instance:
            popup_instance.dismiss()

        app = App.get_running_app()
        # Il colore del vino è implicito dalla schermata di archivio
        wine_color = 'rosso'

        # Chiama il metodo definito nel Punto B (start_edit_card) passando i dati, il colore e
        # L'ID UNIVOCO della scheda da aggiornare.
        # Devi ASSICURARTI che il metodo start_edit_card nella tua WineApp accetti 3 argomenti.
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

        # 2. Intestazione
        scroll_content.add_widget(Label(
            text=f"{self.wine_data.get('produttore_bianco', 'Produttore N/D')}   {self.wine_data.get('annata_bianco', 'Annata N/D')}"
                 f"   {self.wine_data.get('alcol_bianco', 'Grad. Alcolica N/D')}° vol.",
            markup=True, halign='left',  # Allinea a sinistra
            valign='middle',  # centra verticalmente
            size_hint_y=None,
            height=dp(35),
            color=(0.7, 0.5, 0.0, 1.0),  # Giallo-oro--ocra-scuro
            font_size='16sp',
            font_name='materiale/comicbd.ttf',
            text_size=(dp(270), None)  # dimensione massima del testo affinché l'allineamento funzioni
        ))

        # 3. Funzione per aggiungere una riga di dettaglio
        def add_detail_row_white(title, keys):
            # Combina i valori usando il metodo helper
            colore_titolo_bianco = "#E6B31AFF"  # Giallo-oro luminoso
            colore_valori_bianco = "#B38000FF"  # Giallo-oro--ocra-scuro
            values = [self.format_data_for_label_white(key) for key in keys]
            valori_stringa = " / ".join(values)
            detail_text = (
                    f"[color={colore_titolo_bianco}]{title}[/color]" +  # Prima parte (Titolo)
                    f"[color={colore_valori_bianco}][b]{valori_stringa}[/b][/color]"  # Seconda parte (Valori)
            )

            # Usiamo Label dinamico (Dimensione fissa in X e altezza automatica in Y)
            label = Label(
                text=detail_text,
                markup=True, halign='left', valign='top',
                size_hint_y=None,
                height=dp(30),  # Altezza minima di default, per sicurezza.
                text_size=(dp(260), None),  # Usa una larghezza FISSA (es. 260dp)
                font_name='materiale/comicbd.ttf',
                font_size='13sp'
            )
            # Usa una funzione lambda per impostare 'height' al solo valore Y di 'texture_size' (indice [1])
            label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1] + dp(6)))
            # Ho aggiunto dp(5) per un piccolo padding extra/margine

            scroll_content.add_widget(label)

        # 4a. Dettagli Vista
        add_detail_row_white("Vista (Limpidezza / Intensità / Colore):\n", ['limpidezza_bianco', 'intensita_vista_bianco', 'colore_bianco'])

        # 4b. Dettagli Olfatto
        add_detail_row_white("Olfatto (Condizione / Intensità):\n", ['condizione_bianco', 'intensita_naso_bianco']),
        add_detail_row_white("Profumi: ", ['profumo_bianco'])

        # 4c. Dettagli Palato
        add_detail_row_white("Palato: ", ['dolcezza_bianco'])
        add_detail_row_white("Corpo / Acidità / Tannini / Alcol:\n", ['corpo_bianco', 'acidita_bianco', 'tannicita_bianco', 'livello_alcolico_bianco'])
        add_detail_row_white("Sapori: ", ['sapore_bianco'])
        add_detail_row_white("Persistenza / Qualità:\n", ['persistenza_bianco', 'qualita_bianco'])

        # 5. Contenitore dei bottoni (sotto i dettagli)
        button_box = BoxLayout(
            orientation='horizontal',
            spacing=dp(10),
            size_hint_y=None,
            height=dp(40),  # Altezza fissa per i bottoni
            padding=dp(2)
        )

        # Poiché i testi sono lunghi, usiamo un font molto piccolo (10sp)
        FONT = 'materiale/comicbd.ttf'
        COMPACT_FONT_SIZE = '10sp'

        # A. Bottone Elimina Scheda
        btn_delete = RoundedButton(
            text='Elimina Scheda',
            size_hint_x=0.35,  # 1/3 dello spazio
            font_name=FONT,
            font_size=COMPACT_FONT_SIZE,
            background_color=(0.8, 0.1, 0.1, 1)  # Rosso per l'azione distruttiva
        )
        # Collega all'App: chiama la funzione di conferma, passando l'ID e il colore
        # btn_delete.bind(on_release=lambda instance: app.confirm_delete_card(self.card_doc_id, 'bianco'))
        button_box.add_widget(btn_delete)

        # B. Bottone Modifica Scheda
        btn_edit = RoundedButton(
            text='Modifica Scheda',
            size_hint_x=0.35,
            font_name=FONT,
            font_size=COMPACT_FONT_SIZE,
            background_color=(0.1, 0.7, 0.1, 1)  # Verde
        )
        # Collega all'azione di avvio modifica e chiudi il popup
        # btn_edit.bind(on_release=lambda instance: self.start_edit_flow(popup))
        button_box.add_widget(btn_edit)

        # C. Bottone Chiudi/Annulla
        btn_close = RoundedButton(
            text="Chiudi",
            size_hint_x=0.30,
            font_name=FONT,
            font_size='12sp',
            background_color=(0.5, 0.5, 0.5, 1)  # Grigio neutro
        )
        # Collega l'azione di chiusura del popup
        # btn_close.bind(on_release=popup.dismiss)  # NOTA: 'popup' viene definito più in basso
        button_box.add_widget(btn_close)

        # 6. Contenitore finale del Popup (per Scrollview e Bottone)
        final_content = BoxLayout(orientation='vertical', padding=dp(6), spacing=dp(4))

        # 7. Aggiungi la ScrollView contenente tutti i dettagli
        scroll_view = ScrollView(size_hint_y=0.9, do_scroll_x=False)
        scroll_view.add_widget(scroll_content)  # Aggiunge il contenuto di testo alla ScrollView

        final_content.add_widget(scroll_view)  # Aggiunge la ScrollView al contenitore finale
        final_content.add_widget(button_box)  # Aggiunge il contenitore dei bottoni

        # 8. Creazione del Popup
        # Recuperiamo il nome del vino
        nome_vino = self.wine_data.get('nome_bianco', 'Vino Sconosciuto')

        popup = Popup(
            title=nome_vino,
            title_font='materiale/comicbd.ttf',
            title_color=(0.7, 0.5, 0.0, 1.0),  # Giallo-oro--ocra-scuro
            title_size='18sp',
            separator_color=(0.65, 0.45, 0.0, 1.0),  # Marrone Ruggine Scuro
            content=final_content,  # Usa il contenitore finale
            size_hint=(0.95, 0.9),
            background_color=(1, 1, 1, 0.7)
        )

        # =======================================================================
        # COLLEGAMENTO DELLE AZIONI (DOPO CHE 'popup' È STATO DEFINITO)
        # =======================================================================

        # A. Collega l'azione del bottone Elimina (Passando il riferimento al popup di dettaglio)
        btn_delete.bind(on_release=lambda instance: app.confirm_delete_card(self.card_doc_id, 'bianco', popup))

        # B. Collega l'azione del bottone di Modifica (Passando il riferimento al popup di dettaglio)
        btn_edit.bind(on_release=lambda x: self.start_edit_flow(popup))

        # C. Collega l'azione del bottone di chiusura al popup.dismiss
        btn_close.bind(on_release=popup.dismiss)

        popup.open()

        # TROVA LO SCHERMO ARCHIVIO ATTUALE E SALVA IL RIFERIMENTO DEL POPUP
        sm = App.get_running_app().root
        archive_screen = sm.get_screen(f'archivio_bianco')
        archive_screen.detail_popup = popup  # <--- SALVA IL RIFERIMENTO QUI
    def format_data_for_label_white(self, key):
        """Recupera i dati, gestendo stringhe e liste (es. da selezione multipla)."""
        value = self.wine_data.get(key, 'N/D')

        if isinstance(value, list):
            # Se è una lista, unisci gli elementi con una virgola
            return ", ".join(value)
        # Se è una stringa o altro, restituisci il valore così com'è
        return str(value)

    def start_edit_flow(self, popup_instance):
        """Chiude il popup e avvia il flusso di modifica, chiamando il metodo nell'App."""

        # Chiude il popup per mostrare la schermata di modifica
        if popup_instance:
            popup_instance.dismiss()

        app = App.get_running_app()
        # Il colore del vino è implicito dalla schermata di archivio (es. 'bianco')
        # Se usi un campo colore nel DB:
        wine_color = self.wine_data.get('colore_vino', 'bianco')
        # Altrimenti, assumi che RedWineCardItem gestisca solo il bianco:
        wine_color = 'bianco'

        # Chiama il metodo definito nel Punto B (start_edit_card) passando i dati, il colore e
        # L'ID UNIVOCO della scheda da aggiornare.
        # Devi ASSICURARTI che il metodo start_edit_card nella tua WineApp accetti 3 argomenti.
        app.start_edit_card(wine_color, self.wine_data, self.card_doc_id)

class PinkWineCardItem(ButtonBehavior, GridLayout):
    """
    Scheda per visualizzare i dati di un singolo vino.
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

        # 2. Intestazione
        scroll_content.add_widget(Label(
            text=f"{self.wine_data.get('produttore_rosato', 'Produttore N/D')}   {self.wine_data.get('annata_rosato', 'Annata N/D')}"
                 f"   {self.wine_data.get('alcol_rosato', 'Grad. Alcolica N/D')}° vol.",
            markup=True, halign='left',  # Allinea a sinistra
            valign='middle',  # centra verticalmente
            size_hint_y=None,
            height=dp(35),
            color=self.COLORE_INTESTAZIONE_ROSATO,
            font_size='16sp',
            font_name='materiale/comicbd.ttf',
            text_size=(dp(270), None)  # dimensione massima del testo affinché l'allineamento funzioni
        ))

        # 3. Funzione per aggiungere una riga di dettaglio
        def add_detail_row_pink(title, keys):
            # Combina i valori usando il metodo helper
            values = [self.format_data_for_label_pink(key) for key in keys]
            valori_stringa = " / ".join(values)
            detail_text = (
                    f"[color={self.COLORE_TITOLO_DETTAGLIO}]{title}[/color]" +  # Prima parte (Titolo)
                    f"[color={self.COLORE_VALORI_DETTAGLIO}][b]{valori_stringa}[/b][/color]"  # Seconda parte (Valori)
            )

            # Usiamo Label dinamico (Dimensione fissa in X e altezza automatica in Y)
            label = Label(
                text=detail_text,
                markup=True, halign='left', valign='top',
                size_hint_y=None,
                height=dp(30),  # Altezza minima di default, per sicurezza.
                text_size=(dp(260), None),  # Usa una larghezza FISSA (es. 260dp)
                font_name='materiale/comicbd.ttf',
                font_size='13sp'
            )
            # Usa una funzione lambda per impostare 'height' al solo valore Y di 'texture_size' (indice [1])
            label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1] + dp(6)))
            # Ho aggiunto dp(5) per un piccolo padding extra/margine

            scroll_content.add_widget(label)

        # 4a. Dettagli Vista
        add_detail_row_pink("Vista (Limpidezza / Intensità / Colore):\n", ['limpidezza_rosato', 'intensita_vista_rosato', 'colore_rosato'])

        # 4b. Dettagli Olfatto
        add_detail_row_pink("Olfatto (Condizione / Intensità):\n", ['condizione_rosato', 'intensita_naso_rosato']),
        add_detail_row_pink("Profumi: ", ['profumo_rosato'])

        # 4c. Dettagli Palato
        add_detail_row_pink("Palato: ", ['dolcezza_rosato'])
        add_detail_row_pink("Corpo / Acidità / Tannini / Alcol:\n", ['corpo_rosato', 'acidita_rosato', 'tannicita_rosato', 'livello_alcolico_rosato'])
        add_detail_row_pink("Sapori: ", ['sapore_rosato'])
        add_detail_row_pink("Persistenza / Qualità:\n", ['persistenza_rosato', 'qualita_rosato'])

        # 5. Contenitore dei bottoni (sotto i dettagli)
        button_box = BoxLayout(
            orientation='horizontal',
            spacing=dp(10),
            size_hint_y=None,
            height=dp(40),  # Altezza fissa per i bottoni
            padding=dp(2)
        )

        # Poiché i testi sono lunghi, usiamo un font molto piccolo (10sp)
        FONT = 'materiale/comicbd.ttf'
        COMPACT_FONT_SIZE = '10sp'

        # A. Bottone Elimina Scheda
        btn_delete = RoundedButton(
            text='Elimina Scheda',
            size_hint_x=0.35,  # 1/3 dello spazio
            font_name=FONT,
            font_size=COMPACT_FONT_SIZE,
            background_color=(0.8, 0.1, 0.1, 1)  # Rosso per l'azione distruttiva
        )
        # Collega all'App: chiama la funzione di conferma, passando l'ID e il colore
        # btn_delete.bind(on_release=lambda instance: app.confirm_delete_card(self.card_doc_id, 'rosato'))
        button_box.add_widget(btn_delete)

        # B. Bottone Modifica Scheda
        btn_edit = RoundedButton(
            text='Modifica Scheda',
            size_hint_x=0.35,
            font_name=FONT,
            font_size=COMPACT_FONT_SIZE,
            background_color=(0.1, 0.7, 0.1, 1)  # Verde
        )
        # Collega all'azione di avvio modifica e chiudi il popup
        # btn_edit.bind(on_release=lambda instance: self.start_edit_flow(popup))
        button_box.add_widget(btn_edit)

        # C. Bottone Chiudi/Annulla
        btn_close = RoundedButton(
            text="Chiudi",
            size_hint_x=0.30,
            font_name=FONT,
            font_size='12sp',
            background_color=(0.5, 0.5, 0.5, 1)  # Grigio neutro
        )
        # Collega l'azione di chiusura del popup
        # btn_close.bind(on_release=popup.dismiss)  # NOTA: 'popup' viene definito più in basso
        button_box.add_widget(btn_close)

        # 6. Contenitore finale del Popup (per Scrollview e Bottone)
        final_content = BoxLayout(orientation='vertical', padding=dp(6), spacing=dp(4))

        # 7. Aggiungi la ScrollView contenente tutti i dettagli
        scroll_view = ScrollView(size_hint_y=0.9, do_scroll_x=False)
        scroll_view.add_widget(scroll_content)  # Aggiunge il contenuto di testo alla ScrollView

        final_content.add_widget(scroll_view)  # Aggiunge la ScrollView al contenitore finale
        final_content.add_widget(button_box)  # Aggiunge il contenitore dei bottoni

        # 8. Creazione del Popup
        # Recuperiamo il nome del vino
        nome_vino = self.wine_data.get('nome_rosato', 'Vino Sconosciuto')

        popup = Popup(
            title=nome_vino,
            title_font='materiale/comicbd.ttf',
            title_color=self.COLORE_INTESTAZIONE_ROSATO,  # malva scuro
            content=final_content,  # Usa il contenitore finale
            size_hint=(0.95, 0.9),
            separator_color=(0.63, 0.40, 0.54, 1.0),  # Malva Scuro/Melanzana Pallida
            background_color=(1, 1, 1, 0.7)
        )

        # =======================================================================
        # COLLEGAMENTO DELLE AZIONI (DOPO CHE 'popup' È STATO DEFINITO)
        # =======================================================================

        # A. Collega l'azione del bottone Elimina (Passando il riferimento al popup di dettaglio)
        btn_delete.bind(on_release=lambda instance: app.confirm_delete_card(self.card_doc_id, 'rosato', popup))

        # B. Collega l'azione del bottone di Modifica (Passando il riferimento al popup di dettaglio)
        btn_edit.bind(on_release=lambda x: self.start_edit_flow(popup))

        # C. Collega l'azione del bottone di chiusura al popup.dismiss
        btn_close.bind(on_release=popup.dismiss)

        popup.open()

        # TROVA LO SCHERMO ARCHIVIO ATTUALE E SALVA IL RIFERIMENTO DEL POPUP
        sm = App.get_running_app().root
        archive_screen = sm.get_screen(f'archivio_rosato')
        archive_screen.detail_popup = popup  # <--- SALVA IL RIFERIMENTO QUI

    def format_data_for_label_pink(self, key):
        """Recupera i dati, gestendo stringhe e liste (es. da selezione multipla)."""
        value = self.wine_data.get(key, 'N/D')

        if isinstance(value, list):
            # Se è una lista, unisci gli elementi con una virgola
            return ", ".join(value)
        # Se è una stringa o altro, restituisci il valore così com'è
        return str(value)

    def start_edit_flow(self, popup_instance):
        """Chiude il popup e avvia il flusso di modifica, chiamando il metodo nell'App."""

        # Chiude il popup per mostrare la schermata di modifica
        if popup_instance:
            popup_instance.dismiss()

        app = App.get_running_app()
        # Il colore del vino è implicito dalla schermata di archivio (es. 'rosso')
        # Se usi un campo colore nel DB:
        wine_color = self.wine_data.get('colore_vino', 'rosato')
        # Altrimenti, assumi che RedWineCardItem gestisca solo il rosato:
        wine_color = 'rosato'

        # Chiama il metodo definito nel Punto B (start_edit_card) passando i dati, il colore e
        # L'ID UNIVOCO della scheda da aggiornare.
        # Devi ASSICURARTI che il metodo start_edit_card nella tua WineApp accetti 3 argomenti.
        app.start_edit_card(wine_color, self.wine_data, self.card_doc_id)


class RedArchiveScreen(Screen):
    """Schermata della visualizzazione dell' 'archivio' dei vini rossi."""

    def on_enter(self):
        # Chiamato quando la schermata diventa attiva.
        self.load_archive_data()

    def load_archive_data(self):
        # Carica i dati dal database e popola il GridLayout.
        app_red = App.get_running_app()
        db_red = app_red.db_red  # Riferimento al TinyDB dei vini rossi

        # Svuota il contenitore prima di ricaricare (utile per i cambiamenti di schermo)
        container = self.ids.archive_container
        container.clear_widgets()

        # Legge tutti i documenti dal database
        all_wines = db_red.all()

        if not all_wines:
            container.add_widget(Label(text="Nessun vino rosso archiviato.",
                                       size_hint_y=None, height=40,
                                       color=(0.1, 0.1, 0.1, 1)))
            return

        # Passa l'indice della riga (i)
        for i, wine_document in enumerate(all_wines):
            # 1. Converti il Documento TinyDB in un normale dizionario
            wine_data = dict(wine_document)

            # 2. AGGIUNGI l'ID del documento (doc_id) al dizionario dei dati.
            # Questo ID è cruciale per la funzione UPDATE.
            wine_data['_id'] = wine_document.doc_id

            # 3. Crea e aggiungi il widget della scheda
            card = RedWineCardItem(wine_data=wine_data, row_index=i, card_doc_id=wine_document.doc_id)
            container.add_widget(card)


class WhiteArchiveScreen(Screen):
    """Schermata della visualizzazione dell' 'archivio' dei vini bianchi."""

    def on_enter(self):
        # Chiamato quando la schermata diventa attiva.
        self.load_archive_data()

    def load_archive_data(self):
        # Carica i dati dal database e popola il GridLayout.
        app_white = App.get_running_app()
        db_white = app_white.db_white  # Riferimento al TinyDB dei vini bianchi

        # Svuota il contenitore prima di ricaricare (utile per i cambiamenti di schermo)
        container = self.ids.archive_container
        container.clear_widgets()

        # Legge tutti i documenti dal database
        all_wines = db_white.all()

        if not all_wines:
            container.add_widget(Label(text="Nessun vino bianco archiviato.",
                                       size_hint_y=None, height=40,
                                       color=(0.1, 0.1, 0.1, 1)))
            return

        # Passa l'indice della riga (i)
        for i, wine_document in enumerate(all_wines):
            # 1. Converti il Documento TinyDB in un normale dizionario
            wine_data = dict(wine_document)
            # 2. AGGIUNGI l'ID del documento (doc_id) al dizionario dei dati.
            # Questo ID è cruciale per la funzione UPDATE.
            wine_data['_id'] = wine_document.doc_id
            # 3. Crea e aggiungi il widget della scheda
            card = WhiteWineCardItem(wine_data=wine_data, row_index=i, card_doc_id=wine_document.doc_id)
            container.add_widget(card)

class PinkArchiveScreen(Screen):
    """Schermata della visualizzazione dell' 'archivio' dei vini rosati."""

    def on_enter(self):
        # Chiamato quando la schermata diventa attiva.
        self.load_archive_data()

    def load_archive_data(self):
        # Carica i dati dal database e popola il GridLayout.
        app_pink = App.get_running_app()
        db_pink = app_pink.db_pink  # Riferimento al TinyDB dei vini rosati

        # Svuota il contenitore prima di ricaricare (utile per i cambiamenti di schermo)
        container = self.ids.archive_container
        container.clear_widgets()

        # Legge tutti i documenti dal database
        all_wines = db_pink.all()

        if not all_wines:
            container.add_widget(Label(text="Nessun vino rosato archiviato.",
                                       size_hint_y=None, height=40,
                                       color=(0.1, 0.1, 0.1, 1)))
            return

        # Passa l'indice della riga (i)
        for i, wine_document in enumerate(all_wines):
            # 1. Converti il Documento TinyDB in un normale dizionario
            wine_data = dict(wine_document)

            # 2. AGGIUNGI l'ID del documento (doc_id) al dizionario dei dati.
            # Questo ID è cruciale per la funzione UPDATE.
            wine_data['_id'] = wine_document.doc_id

            # 3. Crea e aggiungi il widget della scheda
            card = PinkWineCardItem(wine_data=wine_data, row_index=i, card_doc_id=wine_document.doc_id)
            container.add_widget(card)

# ==============================================================================
# CLASSE APPLICAZIONE E SCREEN MANAGER
# ==============================================================================


class WineApp(App):
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
            # Assumendo che 'pink' o 'rosato' sia il caso rimanente
            db = self.db_pink
            archive_screen_name = 'archivio_rosato'  # O 'archivio_rosato', a seconda del KV

        # Combina le selezioni dei bottoni (selections) con i dati di testo (text_inputs)
        wine_card_ordered = self.selections.copy()

        # 2. Campi della SCHEDA INFO (Priorità)
        wine_card_ordered['nome_' + wine_color] = info_screen.ids['nome_' + wine_color].text
        wine_card_ordered['produttore_' + wine_color] = info_screen.ids['produttore_' + wine_color].text
        wine_card_ordered['annata_' + wine_color] = info_screen.ids['annata_' + wine_color].text
        # Qui è meglio salvare la stringa attuale dello spinner, anche se è il placeholder
        wine_card_ordered['alcol_' + wine_color] = info_screen.ids['alcol_' + wine_color].text
        # AGGIUNGI QUI IL CAMPO NOTE PERSONALI SE ESISTE:
        # wine_card_ordered['note_personali'] = info_screen.ids['note_' + wine_color].text

        # 3. I campi delle ALTRE SCHEDE (limpidezza, acidità, ecc.) sono GIA' in wine_card_ordered
        # grazie a self.selections.copy() all'inizio.

        # Verifichiamo l'esistenza di tutti i campi essenziali, altrimenti usiamo ''

        # Esempio: assicurarsi che 'profumo' sia una stringa (TinyDB preferisce non avere liste vuote)
        profumo_value = wine_card_ordered.get('profumo_' + wine_color, [])
        if isinstance(profumo_value, list):
            wine_card_ordered['profumo_' + wine_color] = ', '.join(profumo_value)
        # Nota: Assicurati che le chiavi 'limpidezza_rosso', 'acidita_bianco', ecc. siano gestite correttamente
        # quando si popolano le selezioni (tramite il metodo BaseScreen.on_button_press).

        # =========================================================================
        # 4. LOGICA AGGIORNAMENTO / INSERIMENTO
        # =========================================================================
        if self.card_to_update_id is not None:
            # --- MODALITÀ DI AGGIORNAMENTO (UPDATE) ---
            doc_id = self.card_to_update_id

            # Esegue l'aggiornamento nel DB utilizzando l'ID del documento
            db.update(wine_card_ordered, doc_ids=[doc_id])

            print(f"Scheda ID {doc_id} aggiornata con successo per vino: {wine_color}")

            # Resetta lo stato di modifica
            self.card_to_update_id = None

            # Naviga verso l'archivio del vino appena modificato
            self.root.current = archive_screen_name

        else:
            # --- MODALITÀ DI INSERIMENTO NUOVA SCHEDA (INSERT) ---
            db.insert(wine_card_ordered)

            print("Scheda salvata con successo per vino:", wine_color)
            print(json.dumps(wine_card_ordered, indent=4))

            # Naviga verso la schermata di scelta vino 'selection' (logica originale)
            self.root.current = 'selection'

        # =========================================================================
        # 5. RESET CAMPI (Eseguito sempre dopo insert o update)
        # =========================================================================

        # Esegui il reset completo (che include il reset di self.text_inputs, self.selections,
        # self.card_to_update_id e i campi di testo sulla info_screen)
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
        """Crea e mostra un DropDown menu utilizzando l'Ancora Larga con bottoni immagine."""

        dropdown = DropDown()

        LARGHEZZA_MENU = menu_anchor_instance.width
        ALTEZZA_BOTTONE = 44  # Altezza in pixel (dp)

        # 2. Lista delle opzioni del menu:
        # (img_normale, img_cliccata, azione)
        menu_items = [
            # SOSTITUISCI QUESTI PERCORSI CON I TUOI FILE IMMAGINE REALI
            ('materiale/menu_archivio_rossi.png', 'materiale/menu_archivio_rossi_cliccato.png',
             lambda: self.navigate_to_archive('rosso')),
            ('materiale/menu_archivio_bianchi.png', 'materiale/menu_archivio_bianchi_cliccato.png',
             lambda: self.navigate_to_archive('bianco')),
            ('materiale/menu_archivio_rosati.png', 'materiale/menu_archivio_rosati_cliccato.png',
             lambda: self.navigate_to_archive('rosato')),
            ('materiale/menu_vai_a_degustazione.png', 'materiale/menu_vai_a_degustazione_cliccato.png',
             lambda: self.cancel_edit_and_go_to_selection()),
            ('materiale/menu_esci.png', 'materiale/menu_esci_cliccato.png', self.stop)
        ]

        # 3. Creazione e configurazione dei bottoni
        for img_normal, img_down, action in menu_items:
            btn = Button(
                text='',  # Rimuovi il testo
                size_hint_y=None,
                height=dp(ALTEZZA_BOTTONE),
                width=LARGHEZZA_MENU,

                # IMPOSTA GLI SFONDI COME IMMAGINI
                background_normal=img_normal,
                background_down=img_down
            )

            # Collega l'azione e l'istruzione per chiudere il menu
            btn.bind(on_release=lambda instance, act=action: self._execute_menu_action(dropdown, act))

            # AGGIUNGI IL BOTTONE DIRETTAMENTE AL DROPDOWN
            dropdown.add_widget(btn)

        # 4. Apri il menu a comparsa (sotto il bottone che lo ha attivato)
        dropdown.open(menu_anchor_instance)

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

if __name__ == '__main__':
    WineApp().run()
