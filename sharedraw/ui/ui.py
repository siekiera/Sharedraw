from tkinter import *
# from PIL import Image, ImageDraw
from sharedraw.networking.messages import PaintMessage
from sharedraw.networking.networking import PeerPool

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
        """ Zwraca piksele jako PNG - prawdopodobnie do usunięcia
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

    def update(self, message):
        """ Aktualizuje UI
        :param message: komunikat
        :return:
        """
        if type(message) is PaintMessage:
            self.ui.drawer.draw(message.changed_pxs)


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
        self.parent.title("Sharedraw [localhost:%s]" % self.ui.peer_pool.port)
        self.drawer = Drawer(self.parent, WIDTH, HEIGHT, self.save)
        self.b = Button(self.parent, text="Zapisz")
        self.b.pack()
        self.b.bind("<Button-1>", self.save)
        connect_btn = Button(self.parent, text="Podłącz")
        connect_btn.pack()
        connect_btn.bind("<Button-1>", self.connect)

    def save(self, e):
        """ Wysyła komunikat o zmianie obrazka do innych klientów
        :param e: zdarzenie
        :return:
        """
        # TODO:: docelowo to trzeba robić automatycznie, a nie po naciśnięciu przycisku
        msg = PaintMessage(self.drawer.changed_pxs)
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


class Drawer():
    """ Klasa zawierająca płótno oraz zapis śladu ruchów myszy
    """
    x, y = None, None

    def __init__(self, parent, width, height, send):
        self.send = send
        self.c = Canvas(parent, width=width, height=height, bg="white")
        self.c.pack()
        # TODO - to można wywalić raczej
        # self.img = Image.new("RGB", (width, height), (255, 255, 255))
        # self.img_draw = ImageDraw.Draw(self.img)
        self.c.bind("<B1-Motion>", self.motion)
        self.c.bind("<ButtonRelease-1>", self.release)
        self.changed_pxs = []

    def motion(self, e):
        prevx = self.x if self.x is not None else e.x
        prevy = self.y if self.y is not None else e.y
        self.c.create_line(prevx, prevy, e.x, e.y)
        # self.img_draw.line([prevx, prevy, e.x, e.y])
        self.x = e.x
        self.y = e.y
        self.changed_pxs.append((e.x, e.y))
        # print('e (%s,%s)' % (e.x, e.y))
        # print('self (%s,%s)' % (self.x, self.y))

    def release(self, e):
        self.x = None
        self.y = None
        self.send(e)

    def draw(self, points: []):
        """ Rysuje łamaną przechodzącą przez punkty points
        :param points: punkty należące do łamanej w postaci [(x1, y1), (x2, y2), ...]
        :return:
        """
        prevx, prevy = points[0]
        for x, y in points[1:]:
            self.c.create_line(prevx, prevy, x, y)
            prevx, prevy = x, y
        self.x, self.y = (None, None)

    def as_png(self):
        # TODO:: prawdopodobnie do usunięcia
        # imgbytearr = io.BytesIO()
        # self.img.save(imgbytearr, format='PNG')
        # return imgbytearr.getvalue()
        pass


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