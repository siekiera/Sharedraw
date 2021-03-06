import io
from tkinter import *
from tkinter.ttk import Treeview

from PIL import Image, ImageDraw, ImageTk

from sharedraw.cntrl.sync import ClientsTable, OwnershipManager
from sharedraw.config import config
from sharedraw.networking.messages import *
from sharedraw.networking.networking import PeerPool

__author__ = 'michalek'

WIDTH, HEIGHT = 640, 480


class SharedrawUI:
    """ Fasada widoku aplikacji
    """

    def __init__(self, peer_pool: PeerPool, om: OwnershipManager):
        self.root = Tk()
        self.peer_pool = peer_pool
        self.om = om
        self.ui = MainFrame(self)

    def start(self):
        """ Uruchamia UI
        """
        self.root.mainloop()

    def get_png(self):
        """ Zwraca piksele jako PNG
        :return: piksele jako PNG
        """
        return self.ui.drawer.as_png()

    def connect(self, ip, port):
        """ Podłącza do innego klienta
        :param ip: ip (str)
        :param port: port (int)
        :return:
        """
        self.peer_pool.connect_to(ip, int(port))

    def paint(self, message: PaintMessage):
        """ Aktualizuje UI
        :param message: komunikat
        :return:
        """
        self.ui.drawer.draw(message.changed_pxs, message.color)

    def update_image(self, message: ImageMessage):
        """ Aktualizuje UI
        :param message: komunikat
        :return:
        """
        self.ui.drawer.update_with_png(message.rawdata)

    def clean(self):
        """ Czyści obrazek
        """
        self.ui.drawer.clean_img()

    def update_clients_info(self, clients: ClientsTable):
        self.ui.update_clients_info(clients)


class MainFrame(Frame):
    """ Główna ramka aplikacji
    """

    def __init__(self, ui: SharedrawUI):
        Frame.__init__(self, ui.root)
        self.parent = ui.root
        self.ui = ui

        self.parent.title("Sharedraw [%s:%s, id: %s]" % (self.ui.peer_pool.ip, self.ui.peer_pool.port, own_id))
        self.drawer = Drawer(self.parent, WIDTH, HEIGHT, self.save)
        self.clients_table = Treeview(self.parent, columns=('R', 'G', 'from'))
        self.clients_table.heading('#0', text='Id')
        self.clients_table.heading('R', text='R')
        self.clients_table.heading('G', text='G')
        self.clients_table.heading('from', text='Otrzymano od:')
        self.clients_table.pack()
        self.token_owner_label = MutableLabel(self.parent, 'Posiadacz tokena: %s', lambda s: s if s else 'Nikt', None)
        self.token_owner_label.pack()
        self.locked_label = MutableLabel(self.parent, 'Tablica %s', lambda b: 'zablokowana' if b else 'odblokowana',
                                         False)
        self.locked_label.pack()
        # Przycisk czyszczenia
        self.clean_btn = self._create_button(text="Czyść", func=self.clean)
        # Przycisk podłączenia
        self.connect_btn = self._create_button(text="Podłącz", func=self.connect)
        # Przycisk żądania przejęcia na własność
        self.req_btn = self._create_button(text="Chcę przejąć tablicę", func=self._make_request)
        # Rezygnacja z posiadania blokady
        self.resign_btn = self._create_button(text='Zrezygnuj z blokady', func=self._resign)

    def _create_button(self, text: str, func):
        """ Tworzy nowy przycisk w bieżącej ramce
        :param text: tekst przycisku
        :param func: funkcja wywoływana po naciśnięciu
        :return: przycisk
        """
        btn = Button(self.parent, text=text, command=func)
        btn.pack()
        return btn

    def save(self):
        """ Wysyła komunikat o zmianie obrazka do innych klientów
        :return:
        """
        if self.drawer.changed_pxs:
            msg = PaintMessage(self.drawer.changed_pxs, self.drawer.color)
            self.ui.peer_pool.send(msg)
            # Reset listy punktów
            self.drawer.changed_pxs = []

    def clean(self):
        """ Czyści obrazek oraz wysyła komunikat o wyczyszczeniu
        :return:
        """
        self.drawer.clean_img()
        msg = CleanMessage(own_id)
        self.ui.peer_pool.send(msg)

    def _make_request(self):
        """ Żąda przejęcia tablicy na własność
        :return:
        """
        clients_info = self.ui.om.claim_ownership()
        self.update_clients_info(clients_info)

    def _resign(self):
        clients_info = self.ui.om.resign()
        self.update_clients_info(clients_info)

    def connect(self):
        """ Uruchamia okno dialogowe do podłączenia się z innym klientem
        :return:
        """
        d = ConnectDialog(self.ui)
        self.parent.wait_window(d.top)

    def update_clients_info(self, clients: ClientsTable):
        # Aktualizacja listy klientów
        for ch in self.clients_table.get_children():
            self.clients_table.delete(ch)
        for client in clients.clients:
            self.clients_table.insert('', 'end', text=client.id,
                                      values=(client.requested, client.granted, client.received_from_id))
        # Aktualizacja info o właścicielu tokena i blokadzie
        self.locked_label.update_text(clients.locked)
        self.token_owner_label.update_text(clients.token_owner)
        # Aktualizacja blokady
        has_token = clients.token_owner == own_id
        self.__set_lock_state(clients.locked, has_token)
        # Aktualizacja przycisków
        # jeśli zablokowaliśmy, to nie możemy tego zrobić drugi raz
        is_locker = (has_token and clients.locked)
        # tak samo jeśli już zażądaliśmy
        has_requested = clients.find_self().has_requested()
        self.__set_button_enabled(self.req_btn, not (is_locker or has_requested))
        # jeśli nie zablokowaliśmy, to nie możemy rezygnować
        self.__set_button_enabled(self.resign_btn, is_locker)
        # Możemy się podłączyć, tylko, jeśli nie jesteśmy do nikogo podłączeni
        self.__set_button_enabled(self.connect_btn, len(clients.clients) <= 1)
        # Przycisk czyść aktywny jeśli możemy rysować
        self.__set_button_enabled(self.clean_btn, has_token or not clients.locked)

    @staticmethod
    def __set_button_enabled(btn: Button, enabled: bool):
        btn.configure(state=(NORMAL if enabled else DISABLED))

    def __set_lock_state(self, locked: bool, has_token: bool):
        self.drawer.locked = locked and not has_token
        # Dodatkowo ustawiamy kolor tła, żeby było ładnie widać
        if locked:
            if has_token:
                color = '#66FF66'
            else:
                color = '#FF9999'
        else:
            color = '#FFFFFF'
        self.parent.configure(bg=color)


class Drawer:
    """ Klasa zawierająca płótno oraz zapis śladu ruchów myszy
    """
    x, y = None, None
    color = "black"

    def __init__(self, parent, width, height, send):
        self.send = send
        self.c = Canvas(parent, width=width, height=height, bg="white")
        self.c.pack()
        self.img = Image.new("RGB", (width, height), (255, 255, 255))
        self.img_draw = ImageDraw.Draw(self.img)
        self.c.bind("<B1-Motion>", self.__motion_left)
        self.c.bind("<B3-Motion>", self.__motion_right)
        self.c.bind("<ButtonRelease-1>", self.__release)
        self.c.bind("<ButtonRelease-3>", self.__release)
        self.changed_pxs = []
        self.locked = False

    def __motion_left(self, e):
        # Lewy przycisk - czarna linia
        self.color = "black"
        self.__motion(e)

    def __motion_right(self, e):
        # Prawy przycisk - biała linia
        self.color = "white"
        self.__motion(e)

    def __motion(self, e):
        if self.locked:
            # Tablica zablokowana przez innego użytkownika - nie rysujemy
            return
        prevx = self.x if self.x is not None else e.x
        prevy = self.y if self.y is not None else e.y
        self.c.create_line(prevx, prevy, e.x, e.y, fill=self.color)
        self.img_draw.line([prevx, prevy, e.x, e.y], fill=self.color)
        self.x = e.x
        self.y = e.y
        self.changed_pxs.append((e.x, e.y))
        # Limit w celu zapewnienia płynności
        if len(self.changed_pxs) > config.line_max_length:
            # Wysyłamy
            self.send()
            # Linia zawiera tylko ostatni punkt
            self.changed_pxs.append((self.x, self.y))

    def __release(self, e):
        self.x = None
        self.y = None
        self.send()

    def draw(self, points: [], color: str):
        """ Rysuje łamaną przechodzącą przez punkty points
        :param points: punkty należące do łamanej w postaci [(x1, y1), (x2, y2), ...]
        :param color: kolor
        :return:
        """
        if not points:
            return
        prevx, prevy = points[0]
        for x, y in points[1:]:
            self.c.create_line(prevx, prevy, x, y, fill=color)
            self.img_draw.line([prevx, prevy, x, y], fill=color)
            prevx, prevy = x, y
        self.x, self.y = (None, None)

    def clean_img(self):
        """ Czyści obrazek
        """
        self.c.delete('all')
        self.img = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255))
        self.img_draw = ImageDraw.Draw(self.img)
        self.changed_pxs = []

    def as_png(self):
        imgbytearr = io.BytesIO()
        self.img.save(imgbytearr, format='PNG')
        return imgbytearr.getvalue()

    def update_with_png(self, raw_data: bytes):
        stream = io.BytesIO(raw_data)
        png = Image.open(stream).convert('RGB')
        self.img.paste(png)
        pi = ImageTk.PhotoImage(image=png, size=(WIDTH, HEIGHT))
        self.c.create_image(WIDTH / 2, HEIGHT / 2, image=pi)


class ConnectDialog:
    """ Dialog otwierany do zdefiniowania ustawień połączenia
    """

    def __init__(self, ui: SharedrawUI):
        top = self.top = Toplevel(ui.root)
        self.ui = ui
        Label(top, text="IP").pack()
        self.ip_entry = Entry(top)
        self.ip_entry.insert(0, ui.peer_pool.ip)
        self.ip_entry.pack()
        Label(top, text="Port").pack()
        self.port_entry = Entry(top)
        self.port_entry.insert(0, "5555")
        self.port_entry.pack()

        b = Button(top, text="Połącz", command=self.connect)
        b.pack()

    def connect(self):
        self.ui.connect(self.ip_entry.get(), self.port_entry.get())
        self.top.destroy()


class MutableLabel(Label):
    """ Napis ze zmiennym tekstem
    """

    def __init__(self, parent, name_pattern, evaluator, initial_value):
        """
        :param parent: komponent rodzica
        :param name_pattern: stały element nazwy jako string zawierający "%s"
        :param evaluator: jednoargumentowa funkcja ewaluująca wartość
        :param initial_value: wartość początkowa
        """
        self._v = StringVar()
        super().__init__(parent, textvariable=self._v)
        self.name_pattern = name_pattern
        self.evaluator = evaluator
        self.update_text(initial_value)

    def update_text(self, value):
        self._v.set(self.name_pattern % self.evaluator(value))
