import io
from tkinter import *
from PIL import Image, ImageDraw
from sharedraw.networking.messages import PaintMessage, ImageMessage
from sharedraw.networking.networking import PeerPool, own_id

__author__ = 'michalek'

WIDTH, HEIGHT = 640, 480


class SharedrawUI:
    """ Fasada widoku aplikacji
    """
    def __init__(self, peer_pool: PeerPool):
        self.root = Tk()
        self.peer_pool = peer_pool
        self.ui = MainFrame(self)

    def start(self):
        """ Uruchamia UI
        """
        # self.root.protocol("WM_DELETE_WINDOW", self.close)
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

    def update_clients_info(self, clients: []):
        self.ui.update_clients_info(clients)


class MainFrame(Frame):
    """ Główna ramka aplikacji
    """
    def __init__(self, ui: SharedrawUI):
        Frame.__init__(self, ui.root)
        self.parent = ui.root
        self.ui = ui
        self.init()
        # self.c = None

    def init(self):
        self.parent.title("Sharedraw [localhost:%s, id: %s]" % (self.ui.peer_pool.port, own_id))
        self.drawer = Drawer(self.parent, WIDTH, HEIGHT, self.save)
        self.clients_info = StringVar()
        Label(self.parent, textvariable=self.clients_info).pack()
        self.update_clients_info([])
        b = Button(self.parent, text="Zapisz")
        b.pack()
        b.bind("<Button-1>", self.save)
        connect_btn = Button(self.parent, text="Podłącz")
        connect_btn.pack()
        connect_btn.bind("<Button-1>", self.connect)

    def save(self, e):
        """ Wysyła komunikat o zmianie obrazka do innych klientów
        :param e: zdarzenie
        :return:
        """
        # TODO:: docelowo to trzeba robić automatycznie, a nie po naciśnięciu przycisku
        msg = PaintMessage(self.drawer.changed_pxs, self.drawer.color)
        self.ui.peer_pool.send(msg)
        # Reset listy punktów
        self.drawer.changed_pxs = []

    def connect(self, e):
        """ Uruchamia okno dialogowe do podłączenia się z innym klientem
        :param e: zdarzenie
        :return:
        """
        d = ConnectDialog(self.ui)
        self.parent.wait_window(d.top)

    def update_clients_info(self, clients: []):
        self.clients_info.set("Podłączone klienty: %s" % str(clients))


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
        self.c.bind("<B1-Motion>", self.motion_left)
        self.c.bind("<B3-Motion>", self.motion_right)
        self.c.bind("<ButtonRelease-1>", self.release)
        self.c.bind("<ButtonRelease-3>", self.release)
        self.changed_pxs = []

    def motion_left(self, e):
        # Lewy przycisk - czarna linia
        self.color = "black"
        self.motion(e)

    def motion_right(self, e):
        # Prawy przycisk - biała linia
        self.color = "white"
        self.motion(e)

    def motion(self, e):
        prevx = self.x if self.x is not None else e.x
        prevy = self.y if self.y is not None else e.y
        self.c.create_line(prevx, prevy, e.x, e.y, fill=self.color)
        self.img_draw.line([prevx, prevy, e.x, e.y], fill=self.color)
        self.x = e.x
        self.y = e.y
        self.changed_pxs.append((e.x, e.y))
        # print('e (%s,%s)' % (e.x, e.y))
        # print('self (%s,%s)' % (self.x, self.y))

    def release(self, e):
        self.x = None
        self.y = None
        self.send(e)

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
            prevx, prevy = x, y
        self.x, self.y = (None, None)

    def as_png(self):
        imgbytearr = io.BytesIO()
        self.img.save(imgbytearr, format='PNG')
        return imgbytearr.getvalue()

    def update_with_png(self, raw_data: bytes):
        stream = io.BytesIO(raw_data)
        # self.img.frombytes(raw_data, decoder_name='PNG')
        self.img = Image.open(stream)
        self.img_draw = ImageDraw.Draw(self.img)
        pi = PhotoImage(self.img_draw)
        self.c.create_image(0, 0, image=pi)


class ConnectDialog:
    """ Dialog otwierany do zdefiniowania ustawień połączenia
    """
    def __init__(self, ui: SharedrawUI):
        top = self.top = Toplevel(ui.root)
        self.ui = ui
        Label(top, text="IP").pack()
        self.ip_entry = Entry(top)
        self.ip_entry.insert(0, "127.0.0.1")
        self.ip_entry.pack()
        Label(top, text="Port").pack()
        self.port_entry = Entry(top)
        self.port_entry.insert(0, "12345")
        self.port_entry.pack()

        b = Button(top, text="Połącz", command=self.connect)
        b.pack()

    def connect(self):
        self.ui.connect(self.ip_entry.get(), self.port_entry.get())
        self.top.destroy()